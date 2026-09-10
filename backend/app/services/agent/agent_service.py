"""Safe, deterministic RAG-chat orchestration for the current MVP."""

import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import OPENAI_API_KEY, OPENAI_MODEL
from app.mcp_clients.baby_info_client import search_knowledge_from_mcp
from app.mcp_clients.baby_care_client import get_care_records, record_care_event
from app.services.info.hospital_service import search_hospitals
from app.models.baby import Baby
from .agent_loop import AgentExecution, AgentLoop, AgentPlan, AgentState, RetryableAgentError
from .memory_service import get_recent_conversation, get_relevant_memories, save_memory_candidate
from .memory_trace_service import write_chat_trace

OUT_OF_SCOPE = (
    "AI 육아 도우미는 수유·수면·배변 기록, 최근 기록·패턴 조회, "
    "육아 정보 검색, 기저귀 사진 관찰, 병원 검색을 도와드릴 수 있어요."
)

GuidanceCategory = Literal[
    "feeding", "sleep", "weaning", "development", "safety", "general_baby", "out_of_scope"
]
RAG_CATEGORIES = frozenset({"feeding", "sleep", "weaning", "development", "safety"})


class IntentClassification(BaseModel):
    category: GuidanceCategory
    intent: Literal["guidance", "urgent_safety", "out_of_scope"]
    is_medical_urgent: bool


INTENT_CLASSIFIER_PROMPT = """당신은 한국어 육아 도우미의 사용자 요청을 분류합니다.
category, intent, is_medical_urgent 필드만 포함한 JSON 객체로 응답하세요.
category에는 feeding, sleep, weaning, development, safety, general_baby, out_of_scope 중 하나만 사용하세요.
수면 중 깸·울음·재우기 질문은 sleep으로 분류합니다. 증상 또는 주의가 필요한 신호는
safety로 분류합니다. 육아 기록을 생성하거나 추정하지 마세요. 명시적 기록 요청은 다른
처리 단계에서 검증합니다. 육아와 관련 있지만 전용 카테고리에 맞지 않는 질문은
general_baby로 분류하세요. 육아와 무관한 요청에만 out_of_scope를 사용하세요.
intent는 guidance, urgent_safety, out_of_scope 중 하나로 category와 일치하게 설정하세요.
명확한 응급 경고 신호가 있을 때만 is_medical_urgent를 true로 설정하세요."""


def _text_response(answer: str, *, response_type: str = "text") -> dict:
    return {"response_type": response_type, "answer": answer, "sources": []}


def _reflect_chat_result(chat: dict) -> tuple[str, str]:
    """Validate only observable response facts before returning them to the user."""
    reflection_hint = chat.pop("_reflection_hint", None)
    if not isinstance(chat.get("answer"), str) or not chat["answer"].strip():
        raise RuntimeError("최종 응답이 비어 있습니다.")
    sources = chat.get("sources", [])
    if not isinstance(sources, list):
        raise RuntimeError("출처 응답 형식이 올바르지 않습니다.")
    if chat.get("confidence") == "high" and not sources:
        chat["confidence"] = "low"
        chat["safety_notice"] = "근거 출처를 확인하지 못해 일반 안내로 제공했습니다."
        return "downgraded_missing_sources", "safe_fallback"
    if reflection_hint == "no_evidence_safe_fallback":
        return "no_evidence_safe_fallback", "safe_fallback"
    if chat.get("response_type") == "clarification_required":
        return "missing_input", "clarification"
    return "passed", "none"


def _format_recorded_at_kst(recorded_at: object) -> str:
    """Format an API timestamp for caregivers in the app's Korea timezone."""
    if not isinstance(recorded_at, str) or not recorded_at:
        return "확인 필요"
    try:
        parsed = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        local_time = parsed.astimezone(ZoneInfo("Asia/Seoul"))
        return f"{local_time.year}년 {local_time.month}월 {local_time.day}일 {local_time.hour}시 {local_time.minute:02d}분"
    except ValueError:
        return "확인 필요"


CITY_ALIASES = {
    "서울": "서울특별시", "서울시": "서울특별시", "서울특별시": "서울특별시",
    "부산": "부산광역시", "부산시": "부산광역시", "부산광역시": "부산광역시",
    "대구": "대구광역시", "대구시": "대구광역시", "대구광역시": "대구광역시",
    "인천": "인천광역시", "인천시": "인천광역시", "인천광역시": "인천광역시",
    "광주": "광주광역시", "광주시": "광주광역시", "광주광역시": "광주광역시",
    "대전": "대전광역시", "대전시": "대전광역시", "대전광역시": "대전광역시",
    "울산": "울산광역시", "울산시": "울산광역시", "울산광역시": "울산광역시",
    "세종": "세종특별자치시", "세종시": "세종특별자치시", "세종특별자치시": "세종특별자치시",
    "제주": "제주특별자치도", "제주시": "제주특별자치도", "제주특별자치도": "제주특별자치도",
}


def _extract_hospital_region(message: str) -> str | None:
    """Extract supported 시·구·동 combinations without relying on an LLM."""
    compact = re.sub(r"\s+", " ", message.strip())
    city = next((canonical for alias, canonical in CITY_ALIASES.items() if alias in compact), None)
    district_match = re.search(r"(?<![가-힣])([가-힣]+(?:구|군))(?![가-힣])", compact)
    locality_match = re.search(r"(?<![가-힣])([가-힣0-9]+(?:동|읍|면))(?![가-힣])", compact)
    district = district_match.group(1) if district_match else ""
    locality = locality_match.group(1) if locality_match else ""
    parts = [part for part in (city, district, locality) if part]
    return " ".join(parts) or None


def _hospital_type_for_request(message: str) -> str | None:
    if any(word in message for word in ("응급실", "응급 의료", "응급의료")):
        return "emergency"
    # In this baby-care service, an unqualified "병원" request means a
    # nearby pediatric clinic unless the user explicitly asks for emergency care.
    if any(word in message for word in ("소아과", "소아청소년과", "소아 병원", "병원")):
        return "pediatric"
    return None


def _format_hospital_answer(region: str, data: dict, hospital_type: str) -> str:
    items = data.get("data", [])
    if not items:
        label = "응급실" if hospital_type == "emergency" else "소아과"
        return f"{region}에서 검색된 {label}가 없어요. 지역명을 다시 확인해 주세요."
    rows = []
    for index, hospital in enumerate(items[:3], start=1):
        name = hospital.get("hospital_name", "의료기관")
        address = hospital.get("address", "주소 확인 필요")
        phone = hospital.get("phone") or "전화번호 확인 필요"
        rows.append(f"{index}. {name}\n{address}\n{phone}")
    default_notice = "위급한 경우 119에 연락하세요." if hospital_type == "emergency" else "운영시간과 진료 가능 여부는 방문 전 의료기관에 확인해 주세요."
    notice = data.get("notice", default_notice)
    label = "응급실" if hospital_type == "emergency" else "소아과"
    return f"{region} 주변 {label} 검색 결과입니다.\n\n" + "\n\n".join(rows) + f"\n\n{notice}"


async def _handle_hospital_request(message: str) -> dict | None:
    hospital_type = _hospital_type_for_request(message)
    if hospital_type is None:
        return None
    region = _extract_hospital_region(message)
    if region is None:
        return _text_response(
            "검색할 지역을 함께 알려주세요. 예: ‘서울 소아과’, ‘신대방동 응급실’, ‘서울 동작구 소아과 찾아줘’",
            response_type="clarification_required",
        )
    result = await search_hospitals(hospital_type, region, page=1, limit=3)
    return _text_response(_format_hospital_answer(region, result, hospital_type), response_type="hospital_list")


GENERAL_BABY_GUIDANCE_PROMPT = """당신은 한국어 육아 도우미입니다. 보호자의 질문에
짧고 실용적인 일반 육아 안내를 제공하세요. 질병을 진단하거나 약 용량·처방을 제시하지
마세요. 월령, 증상 시작 시점, 동반 증상처럼 답변에 필요한 정보가 부족하면 1~2개의
확인 질문을 덧붙이세요. 호흡 곤란, 청색증, 의식 저하, 탈수, 반복 구토, 고열 등
위험 신호가 의심되면 일반 안내보다 즉시 의료기관 또는 119 도움을 우선하라고 안내하세요."""

ALLERGY_AI_KEYWORDS = (
    "알레르기", "알러지", "땅콩", "두드러기", "먹고 토", "먹은 후 토", "먹은 뒤 토",
    "입술 부", "혀 부", "쌕쌕",
)

ALLERGY_GUIDANCE_PROMPT = """당신은 한국어 육아 도우미입니다. 등록된 알레르기 정보와
월령을 참고하여 음식 알레르기 관련 일반 안내를 짧고 실용적으로 제공하세요. 질병을
진단하거나, 새로운 식품 섭취를 허용하거나, 약물 용량·처방·응급약 사용법을 지시하지
마세요. 음식 회피, 식품 라벨 확인, 교차 접촉 주의처럼 일반적인 예방 안내만 하세요.
호흡이 힘듦, 입술·혀의 심한 부종, 반복 구토, 청색증, 의식 저하처럼 위험 신호가 있으면
답변 첫머리에서 즉시 119 또는 의료기관과 보호자가 받은 알레르기 행동계획을 따르도록
안내하세요. 정보가 부족하면 증상, 섭취 시점, 동반 증상을 1~2개만 확인하세요."""


def _memory_instruction(memories: list) -> str:
    preferences = [memory.content for memory in memories if getattr(memory, "memory_type", "") == "preference"]
    if not preferences:
        return ""
    return "\n보호자의 저장된 답변 선호를 따르세요: " + " / ".join(preferences[:3])


async def personalize_rag_answer(rag_answer: str, memories: list | None = None) -> str:
    """Apply answer-format preferences without changing RAG-supported facts.

    The MCP knowledge server owns factual retrieval and its sources.  This
    optional final pass may only shorten or rephrase that already-grounded
    answer; a failure deliberately falls back to the original MCP answer.
    """
    preferences = [
        memory.content
        for memory in memories or []
        if getattr(memory, "memory_type", "") == "preference"
    ]
    if not preferences or not OPENAI_API_KEY:
        return rag_answer

    try:
        response = await AsyncOpenAI(api_key=OPENAI_API_KEY).chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 근거 기반 육아 답변의 표현만 개인화합니다. "
                        "아래 원문에 있는 사실, 주의사항, 불확실성만 유지하세요. "
                        "새로운 의료 정보, 진단, 처방, 수치, 출처를 추가하거나 "
                        "원문의 안전 안내를 생략하지 마세요. 사용자 선호에 맞춰 "
                        "길이·말투·단위·구성만 조정하세요."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"사용자 답변 선호: {' / '.join(preferences[:3])}\n\n"
                        f"근거 기반 원문 답변:\n{rag_answer}"
                    ),
                },
            ],
        )
        answer = response.choices[0].message.content
        return answer.strip() if isinstance(answer, str) and answer.strip() else rag_answer
    except Exception:
        # Personalization must never make a grounded answer unavailable.
        return rag_answer


async def generate_general_baby_guidance(message: str, memories: list | None = None, recent_messages: list[dict] | None = None) -> str:
    """Provide safe coverage for in-scope questions without a matching RAG source."""
    fallback = (
        "아기와 관련된 질문으로 이해했어요. 아기의 월령, 언제부터 있었는지, 함께 보이는 "
        "증상을 알려주시면 더 구체적으로 도와드릴게요. 호흡이 힘들어 보이거나 축 처짐, "
        "반복 구토, 고열처럼 평소와 다른 위험 신호가 있으면 의료기관에 바로 문의하세요."
    )
    if not OPENAI_API_KEY:
        return fallback
    try:
        response = await AsyncOpenAI(api_key=OPENAI_API_KEY).chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": GENERAL_BABY_GUIDANCE_PROMPT + _memory_instruction(memories or [])},
                *(recent_messages or [])[-4:],
                {"role": "user", "content": message},
            ],
        )
        return response.choices[0].message.content.strip() or fallback
    except Exception:
        return fallback


def _is_allergy_ai_request(message: str) -> bool:
    """Route allergy-related questions away from unsupported RAG categories."""
    compact = re.sub(r"\s+", "", message)
    return any(keyword.replace(" ", "") in compact for keyword in ALLERGY_AI_KEYWORDS)


async def generate_allergy_guidance(
    message: str,
    baby: Baby,
    memories: list | None = None,
    recent_messages: list[dict] | None = None,
) -> str:
    """Generate guarded AI-only allergy guidance when no allergy RAG is available."""
    allergies = ", ".join(baby.allergies) if baby.allergies else "등록된 알레르기 없음"
    age_days = max(0, (date.today() - baby.birth_date).days)
    profile_context = (
        f"아기 이름: {baby.baby_name}\n"
        f"월령: 생후 {age_days}일\n"
        f"등록된 알레르기: {allergies}\n"
        f"수유 방식: {baby.feeding_type}"
    )
    fallback = (
        f"{baby.baby_name}의 등록된 알레르기 정보({allergies})를 반영한 AI 일반 안내예요. "
        "원인 식품은 피하고 식품 라벨과 교차 접촉 가능성을 확인해 주세요. "
        "호흡이 힘들어 보이거나 입술·혀가 심하게 붓고, 반복해서 토하거나 축 처지면 "
        "즉시 119 또는 의료기관에 연락하고 보호자가 받은 알레르기 행동계획을 따라 주세요."
    )
    if not OPENAI_API_KEY:
        return fallback
    try:
        response = await AsyncOpenAI(api_key=OPENAI_API_KEY).chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": ALLERGY_GUIDANCE_PROMPT + _memory_instruction(memories or []) + "\n\n아기 정보:\n" + profile_context},
                *(recent_messages or [])[-4:],
                {"role": "user", "content": message},
            ],
        )
        answer = response.choices[0].message.content.strip()
        return answer or fallback
    except Exception:
        return fallback


def _parse_amount_ml(value: str) -> int | None:
    """Validate one Arabic or Korean-numeral millilitre value."""
    if value.isdigit():
        amount = int(value)
    else:
        digits = {"영": 0, "공": 0, "일": 1, "이": 2, "삼": 3, "사": 4,
                  "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
        amount = 0
        pending = 0
        for character in value:
            if character in digits:
                pending = digits[character]
            elif character == "백":
                amount += (pending or 1) * 100
                pending = 0
            elif character == "십":
                amount += (pending or 1) * 10
                pending = 0
        amount += pending
    return amount if 0 < amount <= 500 else None


def _extract_amounts_ml(message: str) -> list[int] | None:
    """Read every explicitly stated ml value; a negative value invalidates the record."""
    matches = list(re.finditer(
        r"(?P<sign>[+-]?)(?P<value>\d{1,3}|[일이삼사오육칠팔구영공십백]+)\s*(?:ml|밀리(?:리터)?)",
        message,
        re.IGNORECASE,
    ))
    if not matches:
        return None
    amounts = []
    for match in matches:
        # Do not silently discard a typed minus sign (for example, ``-100ml``)
        # and turn it into a valid 100ml feeding record.
        if match.group("sign") == "-":
            return None
        amount = _parse_amount_ml(match.group("value"))
        if amount is None:
            return None
        amounts.append(amount)
    return amounts


def _extract_amount_ml(message: str) -> int | None:
    """Read the first numeric or Korean-number amount immediately before ml units."""
    amounts = _extract_amounts_ml(message)
    return amounts[0] if amounts else None


def _relative_recorded_at(message: str, *, now: datetime | None = None) -> str | None:
    """Convert explicit Korean relative times such as ``30분 전에`` into UTC timestamps."""
    now = now or datetime.now(timezone.utc)
    compact = message.replace(" ", "")
    match = re.search(r"(?:(\d{1,2})시간)?(?:(\d{1,3})분)?전(?:에)?", compact)
    if match is None:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    elapsed_minutes = hours * 60 + minutes
    if not 1 <= elapsed_minutes <= 24 * 60:
        return None
    return (now - timedelta(minutes=elapsed_minutes)).isoformat()


def _feeding_record(message: str) -> dict | None:
    """Parse bounded text feeding records without restricting amounts to UI presets."""
    is_feeding_action = any(word in message for word in ("먹었", "먹였", "먹여", "마셨", "수유했", "줬", "주었", "기록해", "기록해줘"))
    is_spaced_feeding_action = "수유" in message and "했" in message
    # The reminder UI lets a caregiver reply with only an amount (for example
    # ``165ml``).  Treat that unambiguous, standalone input as a feeding record
    # too, while leaving questions such as "165ml 먹어도 돼?" as guidance.
    is_amount_only = re.fullmatch(r"\s*[-+]?(?:\d{1,3}|[일이삼사오육칠팔구영공십백]+)\s*(?:ml|밀리(?:리터)?)\s*", message, re.IGNORECASE)
    if not is_feeding_action and not is_spaced_feeding_action and not is_amount_only:
        return None
    amounts = _extract_amounts_ml(message)
    if amounts is None:
        return {"missing": True}
    # “30ml 수유하고 50ml를 추가로 더 수유했어” describes one feeding
    # session. Store its total, instead of losing the follow-up amount.
    amount_ml = sum(amounts) if len(amounts) > 1 and any(word in message for word in ("추가", "더")) else amounts[0]
    if not 1 <= amount_ml <= 500:
        return {"missing": True}
    feeding_type = "mixed" if "혼합" in message or ("모유" in message and "분유" in message) else "breast" if "모유" in message else "formula" if "분유" in message else None
    return {"amount_ml": amount_ml, "feeding_type": feeding_type}


def _diaper_record(message: str) -> dict | None:
    """소변·대변을 명시한 채팅 문장을 기저귀 기록으로 변환합니다."""
    compact = message.replace(" ", "")
    if not any(word in compact for word in ("봤", "쌌", "했", "기록", "방금")):
        return None
    urine = any(word in compact for word in ("소변", "오줌", "쉬했", "쉬쌌"))
    stool = any(word in compact for word in ("대변", "응가", "똥"))
    if not urine and not stool:
        return None
    return {"urine": urine, "stool": stool}


def _sleep_record(message: str) -> dict | None:
    """수면 시간까지 말한 채팅 문장을 완료 수면 기록으로 변환합니다."""
    compact = message.replace(" ", "")
    if not any(word in compact for word in ("수면", "낮잠", "잤어", "잠잤")):
        return None

    korean_hours = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9}
    hour_match = re.search(r"(\d{1,2}|한|두|세|네|다섯|여섯|일곱|여덟|아홉)시간", compact)
    minute_match = re.search(r"(\d{1,3})분", compact)
    if hour_match:
        hour_text = hour_match.group(1)
        hours = int(hour_text) if hour_text.isdigit() else korean_hours[hour_text]
        minutes = int(minute_match.group(1)) if minute_match else (30 if "시간반" in compact else 0)
        duration_minutes = hours * 60 + minutes
    elif minute_match:
        duration_minutes = int(minute_match.group(1))
    else:
        return {"missing": True}

    if not 1 <= duration_minutes <= 720:
        return {"missing": True}
    return {"duration_minutes": duration_minutes}


def _today_summary_request(message: str) -> str | None:
    """Return the requested today-summary type, without mistaking it for a new record."""
    compact = message.replace(" ", "")
    asks_for_value = any(phrase in compact for phrase in (
        "몇번", "몇회", "총몇", "얼마나", "알려줘", "알려", "보여줘", "보여", "조회", "상태", "어때",
    ))
    if "오늘" not in compact or not asks_for_value:
        return None
    if "수유" in compact:
        return "feeding"
    if any(word in compact for word in ("수면", "낮잠", "잠")):
        return "sleep"
    if any(word in compact for word in ("소변", "대변", "똥", "응가", "배변", "오줌")):
        return "diaper"
    return None


def _duration_label(total_minutes: int) -> str:
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}시간 {minutes}분"
    if hours:
        return f"{hours}시간"
    return f"{minutes}분"


async def _handle_care_request(request, baby: Baby) -> dict | None:
    """Run deterministic care-record scenarios before the RAG category path."""
    message = request.message.strip()
    recorded_at = _relative_recorded_at(message)
    if message in {"안녕", "안녕하세요", "반가워", "반갑습니다"}:
        return _text_response("안녕하세요. 수유 기록, 최근 기록 조회, 육아 정보, 기저귀 사진, 병원 검색을 도와드릴게요.")

    today_summary = _today_summary_request(message)
    if today_summary is not None:
        result = await get_care_records({"baby_id": request.baby_id, "query_type": "today"})
        if not result.get("success"):
            raise RuntimeError(result.get("message", "오늘 육아 기록을 조회하지 못했습니다."))
        records = (result.get("data") or {}).get("records") or []
        if today_summary == "feeding":
            count = sum(record.get("event_type") == "feeding" for record in records)
            return _text_response(f"오늘 수유는 총 {count}회 기록됐어요.")
        if today_summary == "diaper":
            diaper_records = [record.get("details") or {} for record in records if record.get("event_type") == "diaper"]
            urine_count = sum(details.get("urine") is True for details in diaper_records)
            stool_count = sum(details.get("stool") is True for details in diaper_records)
            return _text_response(f"오늘 소변은 {urine_count}회, 대변은 {stool_count}회 기록됐어요.")
        total_minutes = sum(
            int((record.get("details") or {}).get("duration_minutes") or 0)
            for record in records
            if record.get("event_type") == "sleep"
        )
        return _text_response(f"오늘 수면은 총 {_duration_label(total_minutes)} 기록됐어요.")

    if "최근 수유" in message and any(word in message for word in ("기록", "알려", "보여", "조회")):
        result = await get_care_records({"baby_id": request.baby_id, "query_type": "latest_feeding"})
        if not result.get("success"):
            raise RuntimeError(result.get("message", "최근 수유 기록을 조회하지 못했습니다."))
        latest = (result.get("data") or {}).get("latest_feeding")
        if latest is None:
            return _text_response("아직 저장된 수유 기록이 없어요. 예: ‘방금 분유 100ml 먹었어’라고 입력해 주세요.")
        details = latest.get("details", {})
        amount = details.get("amount_ml", "확인 필요")
        recorded_at = _format_recorded_at_kst(latest.get("recorded_at"))
        return _text_response(f"최근 수유 기록은 {amount}ml이며, 기록 시각은 {recorded_at}입니다.")

    if "수유 패턴" in message or ("수유" in message and "패턴" in message):
        result = await get_care_records({"baby_id": request.baby_id, "query_type": "pattern", "days": 7})
        if not result.get("success"):
            raise RuntimeError(result.get("message", "수유 패턴을 조회하지 못했습니다."))
        pattern = ((result.get("data") or {}).get("pattern") or {})
        feeding = pattern.get("feeding", {})
        if not pattern.get("sufficient_data"):
            return _text_response(pattern.get("insufficient_reason") or "최근 7일 기록이 부족해 수유 패턴을 계산하기 어려워요.")
        return _text_response(
            f"최근 7일 수유는 {feeding.get('count', 0)}회 기록됐고, "
            f"평균 수유량은 {feeding.get('average_amount_ml', '확인 필요')}ml, "
            f"평균 간격은 {feeding.get('average_interval_minutes', '확인 필요')}분입니다."
        )

    record = _feeding_record(message)
    if record is not None:
        if record.get("missing"):
            return _text_response("수유 기록이 잘못 입력되었어요. 다시 입력해주세요.", response_type="clarification_required")
        feeding_type = record["feeding_type"] or baby.feeding_type
        if feeding_type not in {"breast", "formula", "mixed"}:
            return _text_response("아기의 수유 방식을 확인할 수 없어요. 모유 또는 분유를 함께 입력해 주세요.", response_type="clarification_required")
        result = await record_care_event({
            "baby_id": request.baby_id,
            "event_type": "feeding",
            "input_source": "text",
            "feeding_type": feeding_type,
            "amount_ml": record["amount_ml"],
            "idempotency_key": f"chat-{request.session_id}-{uuid4()}",
            **({"recorded_at": recorded_at} if recorded_at else {}),
        })
        if not result.get("success"):
            raise RuntimeError(result.get("message", "수유 기록을 저장하지 못했습니다."))
        return _text_response(result.get("message", f"수유 {record['amount_ml']}ml를 기록했습니다."), response_type="record_confirmation")

    diaper = _diaper_record(message)
    if diaper is not None:
        result = await record_care_event({
            "baby_id": request.baby_id,
            "event_type": "diaper",
            "input_source": "text",
            **diaper,
            "idempotency_key": f"chat-{request.session_id}-{uuid4()}",
            **({"recorded_at": recorded_at} if recorded_at else {}),
        })
        if not result.get("success"):
            raise RuntimeError(result.get("message", "기저귀 기록을 저장하지 못했습니다."))
        diaper_kind = "소변·대변" if diaper["urine"] and diaper["stool"] else "소변" if diaper["urine"] else "대변"
        return _text_response(result.get("message", f"기저귀 {diaper_kind} 기록을 저장했습니다."), response_type="record_confirmation")

    sleep = _sleep_record(message)
    if sleep is not None:
        if sleep.get("missing"):
            return _text_response("수면 기록에는 시간이 필요해요. 예: ‘낮잠 1시간 30분 잤어’라고 입력해 주세요.", response_type="clarification_required")
        result = await record_care_event({
            "baby_id": request.baby_id,
            "event_type": "sleep",
            "input_source": "text",
            "duration_minutes": sleep["duration_minutes"],
            "idempotency_key": f"chat-{request.session_id}-{uuid4()}",
            **({"recorded_at": recorded_at} if recorded_at else {}),
        })
        if not result.get("success"):
            raise RuntimeError(result.get("message", "수면 기록을 저장하지 못했습니다."))
        hours, minutes = divmod(sleep["duration_minutes"], 60)
        duration_label = f"{hours}시간" + (f" {minutes}분" if minutes else "")
        return _text_response(result.get("message", f"수면 {duration_label}을 기록했습니다."), response_type="record_confirmation")
    return None


async def classify_intent(message: str) -> IntentClassification | None:
    """Return a validated semantic category without breaking the chat flow."""
    if not OPENAI_API_KEY:
        return None
    try:
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": INTENT_CLASSIFIER_PROMPT},
                {"role": "user", "content": message},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            return None
        return IntentClassification.model_validate(json.loads(content))
    except (ValidationError, ValueError, KeyError, IndexError):
        return None
    except Exception:
        return None


async def classify_category(message: str) -> str | None:
    """Classify free-form guidance through a validated semantic model result."""
    classification = await classify_intent(message)
    return None if classification is None or classification.category == "out_of_scope" else classification.category


async def _validate_context(request, app) -> Baby:
    raw = await app.state.redis.get(f"session:{request.user_id}:{request.session_id}")
    if not raw:
        raise PermissionError("세션이 없거나 만료되었습니다.")
    session_data = json.loads(raw)
    if session_data.get("user_id") != request.user_id or session_data.get("baby_id") != request.baby_id:
        raise PermissionError("요청한 아기 정보에 접근할 수 없습니다.")
    async with AsyncSession(app.state.db_engine, expire_on_commit=False) as db:
        baby = (await db.execute(select(Baby).where(Baby.id == request.baby_id, Baby.user_id == request.user_id))).scalar_one_or_none()
    if baby is None:
        raise PermissionError("아기 정보를 찾을 수 없습니다.")
    return baby


def _care_plan(message: str) -> AgentPlan | None:
    """Plan care Tools without executing them, so the policy is traceable first."""
    today_summary = _today_summary_request(message)
    if today_summary is not None:
        return AgentPlan("care", ("get_care_records",), ({"query_type": "today", "summary_type": today_summary},))
    record = _feeding_record(message)
    if record is not None:
        return AgentPlan("care", () if record.get("missing") else ("record_care_event",), () if record.get("missing") else ({"event_type": "feeding", "input_source": "text"},))
    record = _diaper_record(message)
    if record is not None:
        return AgentPlan("care", ("record_care_event",), ({"event_type": "diaper", "input_source": "text"},))
    record = _sleep_record(message)
    if record is not None:
        return AgentPlan("care", () if record.get("missing") else ("record_care_event",), () if record.get("missing") else ({"event_type": "sleep", "input_source": "text"},))
    if "수유 패턴" in message or ("수유" in message and "패턴" in message):
        return AgentPlan("care", ("get_care_records",), ({"query_type": "pattern", "days": 7},))
    return None


async def _plan_chat_action(request) -> AgentPlan:
    """Select one allowlisted route before any MCP call occurs."""
    if _is_allergy_ai_request(request.message):
        return AgentPlan("allergy_guidance")
    care = _care_plan(request.message)
    if care is not None:
        return care
    hospital_type = _hospital_type_for_request(request.message)
    if hospital_type is not None:
        region = _extract_hospital_region(request.message)
        if region is None:
            return AgentPlan("hospital_clarification")
        tool_name = "search_emergency_hospitals" if hospital_type == "emergency" else "search_pediatric_hospitals"
        return AgentPlan("hospital", (tool_name,), ({"region": region, "page": 1, "limit": 3},), can_retry=True)
    category = await classify_category(request.message)
    if category is None:
        return AgentPlan("out_of_scope")
    if category == "general_baby":
        return AgentPlan("general_guidance")
    return AgentPlan("rag", (f"search_{category}_guide",), ({"category": category, "top_k": 5},))


async def _execute_chat_plan(plan: AgentPlan, request, baby: Baby, memories: list, recent_messages: list[dict]) -> AgentExecution:
    if plan.route == "allergy_guidance":
        return AgentExecution({
            "response_type": "text",
            "answer": "AI 일반 안내 · 등록된 알레르기 정보를 반영했어요.\n\n" + await generate_allergy_guidance(request.message, baby, memories, recent_messages),
            "sources": [], "confidence": "low",
            "safety_notice": "일반 안내이며 진단·처방을 대신하지 않습니다. 위험 증상은 즉시 119 또는 의료기관에 문의하세요.",
        })
    if plan.route == "care":
        response = await _handle_care_request(request, baby)
        if response is None:
            raise RuntimeError("육아 기록 처리 계획과 실행 결과가 일치하지 않습니다.")
        return AgentExecution(response)
    if plan.route == "hospital_clarification":
        return AgentExecution(_text_response("검색할 지역을 함께 알려주세요. 예: ‘서울 소아과’, ‘신대방동 응급실’, ‘서울 동작구 소아과 찾아줘’", response_type="clarification_required"))
    if plan.route == "hospital":
        try:
            response = await _handle_hospital_request(request.message)
        except RuntimeError as error:
            raise RetryableAgentError("hospital_tool_unavailable", "병원 검색 Tool을 일시적으로 사용할 수 없습니다.") from error
        if response is None:
            raise RuntimeError("병원 검색 계획과 실행 결과가 일치하지 않습니다.")
        return AgentExecution(response)
    if plan.route == "out_of_scope":
        return AgentExecution({"response_type": "out_of_scope", "answer": OUT_OF_SCOPE, "sources": []})
    if plan.route == "general_guidance":
        return AgentExecution({
            "response_type": "text", "answer": await generate_general_baby_guidance(request.message, memories, recent_messages),
            "sources": [], "confidence": "low", "safety_notice": "일반 육아 안내이며 진단을 대신하지 않습니다.",
        })
    if plan.route == "rag":
        category = plan.selected_tools[0].removeprefix("search_").removesuffix("_guide")
        age_months = max(0, min(36, (date.today() - baby.birth_date).days // 30))
        result = await search_knowledge_from_mcp(category, request.message, age_months)
        if not result.get("success"):
            raise RuntimeError("육아 정보 검색에 실패했습니다.")
        no_evidence = result.get("confidence") == "low" and not result.get("sources")
        answer = (
            await generate_general_baby_guidance(request.message, memories, recent_messages)
            if no_evidence
            else await personalize_rag_answer(result["answer"], memories)
        )
        return AgentExecution({
            "response_type": "text",
            "answer": answer,
            "sources": result.get("sources", []), "confidence": result.get("confidence"),
            "safety_notice": result.get("safety_notice") or ("일반 육아 안내이며 진단을 대신하지 않습니다." if no_evidence else None),
            **({"_reflection_hint": "no_evidence_safe_fallback"} if no_evidence else {}),
        })
    raise RuntimeError("지원하지 않는 Agent 실행 계획입니다.")


async def _persist_chat_turn(request, app, chat: dict) -> int:
    await app.state.redis.rpush(
        f"chat:{request.user_id}:{request.session_id}",
        json.dumps({"role": "user", "content": request.message}, ensure_ascii=False),
        json.dumps({"role": "assistant", "content": chat["answer"]}, ensure_ascii=False),
    )
    await app.state.redis.ltrim(f"chat:{request.user_id}:{request.session_id}", -8, -1)
    await app.state.redis.expire(f"chat:{request.user_id}:{request.session_id}", 86400)
    return await save_memory_candidate(app.state.db_engine, request.user_id, request.message)


async def _execute_safe_fallback(plan: AgentPlan, error: RetryableAgentError) -> AgentExecution:
    """Return a truthful fallback after the one allowed read-only retry is exhausted."""
    if plan.route == "hospital":
        return AgentExecution(_text_response(
            "현재 병원 정보를 불러오지 못했어요. 잠시 후 다시 시도해 주세요. 위급한 상황이면 119에 연락하세요.",
            response_type="error",
        ))
    raise error


async def answer_chat(request, app) -> dict:
    """Public chat entry point; API contract remains unchanged while execution uses AgentLoop."""
    state = AgentState(request_id=str(uuid4()))
    baby = await _validate_context(request, app)
    memories = await get_relevant_memories(app.state.db_engine, request.user_id, request.message)
    recent_messages = await get_recent_conversation(app.state.redis, request.user_id, request.session_id)
    execution = await AgentLoop().run(
        state,
        planner=lambda: _plan_chat_action(request),
        executor=lambda plan: _execute_chat_plan(plan, request, baby, memories, recent_messages),
        verifier=_reflect_chat_result,
        fallback=_execute_safe_fallback,
    )
    created = await _persist_chat_turn(request, app, execution.response)
    plan = state.plan or AgentPlan("out_of_scope")
    await write_chat_trace(
        app.state.redis, user_id=request.user_id, session_id=request.session_id, baby_id=request.baby_id,
        request_id=state.request_id, tool_used=bool(plan.selected_tools), memory_count=len(memories), memory_created=created,
        selected_tools=list(plan.selected_tools), tool_arguments=list(plan.tool_arguments),
        result_validation=state.result_validation, reflection_action=state.reflection_action,
        error_type=state.error_type, retry_count=state.retry_count, execution_stages=state.stages,
    )
    message = "요청을 처리했습니다." if plan.route == "care" else "AI 답변을 생성했습니다."
    if plan.route == "hospital":
        message = "병원 검색 결과를 조회했습니다."
    elif plan.route == "out_of_scope":
        message = "지원 범위를 안내했습니다."
    elif plan.route == "allergy_guidance":
        message = "알레르기 AI 안내를 생성했습니다."
    return {"success": True, "message": message, "request_id": state.request_id, "data": execution.response}
