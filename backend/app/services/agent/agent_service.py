"""Safe, deterministic RAG-chat orchestration for the current MVP."""

import json
import re
from datetime import date
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp_clients.baby_info_client import search_knowledge_from_mcp
from app.mcp_clients.baby_care_client import get_care_records, record_care_event
from app.models.baby import Baby
from .memory_service import get_relevant_memories, save_memory_candidate
from .memory_trace_service import write_chat_trace

CATEGORY_KEYWORDS = {
    "feeding": ("수유", "분유", "모유", "트림"),
    "sleep": ("수면", "잠", "낮잠", "재우"),
    "weaning": ("이유식", "식재료", "알레르기"),
    "development": ("발달", "뒤집", "기어", "말", "걸음"),
    "safety": ("안전", "질식", "낙상", "화상", "카시트"),
}

OUT_OF_SCOPE = (
    "AI 육아 도우미는 수유·수면·배변 기록, 최근 기록·패턴 조회, "
    "육아 정보 검색, 기저귀 사진 관찰, 병원 검색을 도와드릴 수 있어요."
)


def _text_response(answer: str, *, response_type: str = "text") -> dict:
    return {"response_type": response_type, "answer": answer, "sources": []}


def _feeding_record(message: str) -> dict | None:
    """Parse only explicit, bounded text feeding records; never guess an amount."""
    if not any(word in message for word in ("먹었", "마셨", "수유했", "기록해", "기록해줘")):
        return None
    amount_match = re.search(r"(\d{1,3})\s*(?:ml|밀리(?:리터)?)", message, re.IGNORECASE)
    if amount_match is None:
        return {"missing": True}
    feeding_type = "breast" if "모유" in message else "formula" if "분유" in message else None
    if feeding_type is None:
        return {"missing": True}
    return {"amount_ml": int(amount_match.group(1)), "feeding_type": feeding_type}


async def _handle_care_request(request) -> dict | None:
    """Run deterministic care-record scenarios before the RAG category path."""
    message = request.message.strip()
    if message in {"안녕", "안녕하세요", "반가워", "반갑습니다"}:
        return _text_response("안녕하세요. 수유 기록, 최근 기록 조회, 육아 정보, 기저귀 사진, 병원 검색을 도와드릴게요.")

    if "최근 수유" in message and any(word in message for word in ("기록", "알려", "보여", "조회")):
        result = await get_care_records({"baby_id": request.baby_id, "query_type": "latest_feeding"})
        if not result.get("success"):
            raise RuntimeError(result.get("message", "최근 수유 기록을 조회하지 못했습니다."))
        latest = (result.get("data") or {}).get("latest_feeding")
        if latest is None:
            return _text_response("아직 저장된 수유 기록이 없어요. 예: ‘방금 분유 100ml 먹었어’라고 입력해 주세요.")
        details = latest.get("details", {})
        amount = details.get("amount_ml", "확인 필요")
        return _text_response(f"최근 수유 기록은 {amount}ml이며, 기록 시각은 {latest.get('recorded_at', '확인 필요')}입니다.")

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
            return _text_response("수유 기록에는 수유 방식과 양이 필요해요. 예: ‘방금 분유 100ml 먹었어’라고 입력해 주세요.", response_type="clarification_required")
        result = await record_care_event({
            "baby_id": request.baby_id,
            "event_type": "feeding",
            "input_source": "text",
            "feeding_type": record["feeding_type"],
            "amount_ml": record["amount_ml"],
            "idempotency_key": f"chat-{request.session_id}-{uuid4()}",
        })
        if not result.get("success"):
            raise RuntimeError(result.get("message", "수유 기록을 저장하지 못했습니다."))
        return _text_response(result.get("message", f"수유 {record['amount_ml']}ml를 기록했습니다."), response_type="record_confirmation")
    return None


def classify_category(message: str) -> str | None:
    return next((category for category, words in CATEGORY_KEYWORDS.items() if any(word in message for word in words)), None)


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


async def answer_chat(request, app) -> dict:
    request_id = str(uuid4())
    baby = await _validate_context(request, app)
    memories = await get_relevant_memories(app.state.db_engine, request.user_id, request.message)
    care_response = await _handle_care_request(request)
    if care_response is not None:
        await write_chat_trace(app.state.redis, user_id=request.user_id, session_id=request.session_id, baby_id=request.baby_id, request_id=request_id, tool_used=True, memory_count=len(memories), memory_created=False)
        return {"success": True, "message": "요청을 처리했습니다.", "request_id": request_id, "data": care_response}
    category = classify_category(request.message)
    if category is None:
        created = await save_memory_candidate(app.state.db_engine, request.user_id, request.message)
        await write_chat_trace(app.state.redis, user_id=request.user_id, session_id=request.session_id, baby_id=request.baby_id, request_id=request_id, tool_used=False, memory_count=len(memories), memory_created=created)
        return {"success": True, "message": "지원 범위를 안내했습니다.", "request_id": request_id,
                "data": {"response_type": "out_of_scope", "answer": OUT_OF_SCOPE, "sources": []}}
    age_months = max(0, min(36, (date.today() - baby.birth_date).days // 30))
    result = await search_knowledge_from_mcp(category, request.message, age_months)
    if not result.get("success"):
        raise RuntimeError("육아 정보 검색에 실패했습니다.")
    chat = {"response_type": "text", "answer": result["answer"], "sources": result.get("sources", []),
            "confidence": result.get("confidence"), "safety_notice": result.get("safety_notice")}
    await app.state.redis.rpush(f"chat:{request.user_id}:{request.session_id}", json.dumps({"role": "user", "content": request.message}, ensure_ascii=False), json.dumps({"role": "assistant", "content": chat["answer"]}, ensure_ascii=False))
    await app.state.redis.ltrim(f"chat:{request.user_id}:{request.session_id}", -8, -1)
    await app.state.redis.expire(f"chat:{request.user_id}:{request.session_id}", 86400)
    created = await save_memory_candidate(app.state.db_engine, request.user_id, request.message)
    await write_chat_trace(app.state.redis, user_id=request.user_id, session_id=request.session_id, baby_id=request.baby_id, request_id=request_id, tool_used=True, memory_count=len(memories), memory_created=created)
    return {"success": True, "message": "AI 답변을 생성했습니다.", "request_id": request_id, "data": chat}
