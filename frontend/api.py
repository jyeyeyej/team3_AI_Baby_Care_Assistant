"""Streamlit과 FastAPI 사이의 공통 API 계층.

백엔드가 준비되기 전에는 ``USE_MOCK_API=true``로 목데이터를 사용한다.
준비 후에는 환경변수를 false로 바꾸고, 확정된 엔드포인트별 함수가
아래 공통 HTTP 클라이언트를 사용하도록 연결한다.
페이지 파일은 이 모듈의 함수만 호출하며 HTTP 세부 구현을 직접 갖지 않는다.
"""

from __future__ import annotations

import os
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests
from dotenv import load_dotenv


# Streamlit is launched from the frontend directory in some environments, so
# load the project-level settings explicitly instead of relying on its shell.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000").rstrip("/")
USE_MOCK_API = os.getenv("USE_MOCK_API", "true").lower() == "true"
API_TIMEOUT_SECONDS = float(os.getenv("BACKEND_API_TIMEOUT_SECONDS", "10"))


def backend_settings() -> dict[str, Any]:
    """현재 연결 대상 정보. 화면에는 URL이나 내부 오류를 그대로 노출하지 않는다."""
    return {"base_url": BACKEND_API_URL, "use_mock_api": USE_MOCK_API, "timeout_seconds": API_TIMEOUT_SECONDS}


def request_backend(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """문서의 공통 응답 형식으로 FastAPI 응답과 네트워크 오류를 정규화한다.

    실제 호출은 백엔드 개발 완료 후, 각 엔드포인트 함수에서 사용한다.
    """
    url = f"{BACKEND_API_URL}{path}"
    try:
        response = requests.request(
            method=method,
            url=url,
            params=params,
            json=json,
            data=data,
            files=files,
            headers=headers,
            timeout=API_TIMEOUT_SECONDS,
        )
        try:
            body = response.json()
        except ValueError:
            body = {}

        if isinstance(body, dict):
            error_message = body.get("message") or body.get("detail")
            return {
                "success": bool(body.get("success", response.ok)),
                "message": error_message or ("" if response.ok else "요청을 처리하지 못했습니다."),
                "data": body.get("data", {}),
                "request_id": body.get("request_id"),
                "status_code": response.status_code,
            }
        return {"success": response.ok, "message": "응답 형식이 올바르지 않습니다.", "data": {}, "request_id": None, "status_code": response.status_code}
    except requests.RequestException:
        return {
            "success": False,
            "message": "서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
            "data": {},
            "request_id": None,
            "status_code": None,
        }


BABY = {
    "baby_id": "baby-001",
    "baby_name": "서아",
    "birth_date": "2026-08-03",
    "age_days": 31,
    "gender": "여아",
    "feeding_type": "분유",
    "current_weight_kg": 4.2,
    "birth_weight_kg": 3.2,
    "current_height_cm": 54.1,
    "head_circumference_cm": 37.0,
    "allergies": ["땅콩"],
}


def test_login(selected_user: str) -> dict:
    """Keep the demo account picker, but create a real backend session in live mode."""
    user_id = "user-001" if selected_user.startswith("서아") else "user-002"
    if not USE_MOCK_API:
        return request_backend("POST", "/api/test-login", json={"user_id": user_id})
    return {"success": True, "data": {"user_id": user_id, "baby_id": BABY["baby_id"], "session_id": "demo-session"}}


def get_baby(baby_id: str, *, user_id: str | None = None, session_id: str | None = None) -> dict:
    """Read the logged-in test baby's real profile when the backend is enabled."""
    if not USE_MOCK_API and user_id and session_id:
        result = request_backend(
            "GET",
            f"/api/babies/{baby_id}",
            headers={"X-User-Id": user_id, "X-Session-Id": session_id},
        )
        if result["success"]:
            data = result["data"]
            birth_date = data.get("birth_date", BABY["birth_date"])
            try:
                age_days = (date.today() - date.fromisoformat(birth_date)).days
            except (TypeError, ValueError):
                age_days = BABY["age_days"]
            feeding_labels = {"breast": "모유", "formula": "분유", "mixed": "혼합"}
            return {
                "success": True,
                "data": {
                    **BABY,
                    **data,
                    "baby_id": data.get("id", baby_id),
                    "age_days": age_days,
                    "feeding_type": feeding_labels.get(data.get("feeding_type"), data.get("feeding_type")),
                },
            }
        return result
    fallback = BABY.copy()
    fallback["baby_id"] = baby_id
    return {"success": True, "data": fallback}


def get_dashboard(_: str) -> dict:
    return {
        "success": True,
        "data": {
            "feeding": {"average_count": 7, "average_interval": "평균 3시간 10분 간격"},
            "sleep": {"daily_hours": "15시간", "last": "어제 22:10"},
            "diaper": {"daily_count": 5, "detail": "소변 4회 · 대변 1회"},
            "next_vaccination": {"date": "10월 3일", "name": "DTaP·IPV·Hib 1차", "remaining": "23일 남았어요."},
        },
    }


def get_care_records(_: str) -> dict:
    return {
        "success": True,
        "data": [
            {"time": "오늘 14:30", "icon": "🍼", "title": "분유 수유", "detail": "100ml · 알림 확인으로 기록"},
            {"time": "오늘 12:05", "icon": "🌙", "title": "낮잠 종료", "detail": "10:20–12:05 · 1시간 45분"},
            {"time": "오늘 09:40", "icon": "💩", "title": "기저귀 · 대변", "detail": "노란색, 묽은 형태 · 사진 분석 메모 있음"},
            {"time": "9월 2일", "icon": "📏", "title": "성장 측정", "detail": "몸무게 4.2kg · 키 54.1cm · 머리둘레 37cm"},
        ],
    }


def get_care_pattern(_: str) -> dict:
    return {
        "success": True,
        "data": {
            "sufficient_data": True,
            "average_interval": "3시간 12분",
            "daily_feeding": "6.7회",
            "daily_sleep": "7.8시간",
            "daily_diaper": "2.7회",
            "intervals": [2.7, 3.0, 2.8, 3.4, 3.1, 3.6, 3.45],
        },
    }


def search_hospitals(region: str, hospital_type: str, page: int = 1, limit: int = 10) -> dict[str, Any]:
    """Search hospitals through FastAPI once ``USE_MOCK_API`` is disabled."""
    if not USE_MOCK_API:
        return request_backend("GET", "/api/hospitals/search", params={"region": region, "type": hospital_type, "page": page, "limit": limit})
    return {"success": True, "message": "목데이터 검색 결과입니다.", "data": {"region": region, "type": hospital_type, "data": [], "source": "mock", "checked_at": None, "notice": "실제 병원 검색은 백엔드 연결 후 이용할 수 있습니다."}, "request_id": None, "status_code": 200}


def analyze_diaper_image(image_file, baby_id: str, session_id: str, user_id: str, feeding_type: str, has_fever: bool | None = None, stool_count_24h: int | None = None) -> dict[str, Any]:
    """Upload a diaper image; analysis never saves a care record automatically."""
    if not USE_MOCK_API:
        return request_backend("POST", "/api/images/diaper-analysis", files={"image": image_file}, data={"baby_id": baby_id, "session_id": session_id, "user_id": user_id, "feeding_type": feeding_type, "has_fever": has_fever, "stool_count_24h": stool_count_24h})
    return {"success": True, "message": "목 분석 결과입니다.", "data": {"baby_id": baby_id, "is_analyzable": False, "quality_issues": ["실제 사진 분석은 백엔드 연결 후 이용할 수 있습니다."], "observation": None, "risk": None, "follow_up_questions": [], "sources": [], "warnings": [], "safety_notice": "사진만으로 질환을 진단할 수 없습니다."}, "request_id": None, "status_code": 200}


def create_care_log(payload: dict[str, Any], user_id: str, session_id: str) -> dict[str, Any]:
    """Save an explicitly entered care event through the authenticated API."""
    if not USE_MOCK_API:
        return request_backend("POST", "/api/care-logs", json=payload, headers={"X-User-Id": user_id, "X-Session-Id": session_id})
    return {"success": True, "message": "목데이터에 기록했습니다.", "data": {"event_type": payload["event_type"], "duplicated": False}, "request_id": None, "status_code": 200}


def get_growth(_: str) -> dict:
    return {
        "success": True,
        "data": {
            "weight": [3.2, 3.45, 3.7, 4.0, 4.2],
            "height": [50.0, 51.2, 52.4, 53.4, 54.1],
            "head": [34.0, 34.8, 35.8, 36.5, 37.0],
            "reference": [3.45, 3.6, 3.85, 4.1, 4.35],
        },
    }


def get_vaccinations(_: str) -> dict:
    return {
        "success": True,
        "data": {
            "next": {"name": "DTaP·IPV·Hib 1차", "period": "생후 2개월 권장 일정 기준", "date": "2026. 10. 03 예정"},
            "items": [
                ("BCG", "결핵 예방 · 1회", "접종 완료 · 8/10", "done"),
                ("B형간염 1차", "출생 직후", "접종 완료 · 8/03", "done"),
                ("B형간염 2차", "생후 1개월", "접종 완료 · 9/06", "done"),
                ("DTaP·IPV·Hib 1차", "생후 2개월", "접종 예정 · 10/03", "soon"),
            ],
        },
    }


def send_chat(message: str, *, baby_id: str | None = None, session_id: str | None = None, user_id: str | None = None) -> dict:
    """채팅 API를 통해 Backend Agent와 RAG Tool 선택을 요청한다."""
    if not USE_MOCK_API:
        return request_backend(
            "POST",
            "/api/chat",
            json={"message": message, "baby_id": baby_id, "session_id": session_id},
            headers={"X-User-Id": user_id or "", "X-Session-Id": session_id or ""},
        )
    return {
        "success": True,
        "data": {
            "response_type": "text",
            "answer": "생후 30일 아기의 수유량은 아기마다 달라요. 서아의 최근 수유 기록과 배고픔 신호를 함께 살펴보세요. 평소와 크게 달라지거나 걱정되는 변화가 있으면 소아과에 문의해 주세요.",
            "sources": ["공식 육아정보 기반 · 수유 참고"],
        },
    }


def stream_chat(message: str, *, baby_id: str | None, session_id: str | None, user_id: str | None):
    """Yield user-safe progress events from FastAPI's SSE chat endpoint."""
    if USE_MOCK_API:
        yield {"event": "completed", "data": send_chat(message, baby_id=baby_id, session_id=session_id, user_id=user_id)}
        return

    try:
        response = requests.post(
            f"{BACKEND_API_URL}/api/chat/stream",
            json={"message": message, "baby_id": baby_id, "session_id": session_id},
            headers={"X-User-Id": user_id or "", "X-Session-Id": session_id or ""},
            stream=True,
            timeout=API_TIMEOUT_SECONDS,
        )
        if not response.ok:
            try:
                body = response.json()
                message_text = body.get("detail") or body.get("message") or "채팅 요청을 처리하지 못했습니다."
            except ValueError:
                message_text = "채팅 요청을 처리하지 못했습니다."
            yield {"event": "error", "data": {"message": message_text}}
            return

        event_name = "message"
        event_data: dict[str, Any] = {}
        # SSE 이벤트는 작으므로 기본 버퍼(512 bytes)를 기다리지 않고 즉시 처리합니다.
        for raw_line in response.iter_lines(chunk_size=1, decode_unicode=True):
            line = raw_line.strip() if raw_line else ""
            if line.startswith("event:"):
                event_name = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                try:
                    event_data = json.loads(line.removeprefix("data:").strip())
                except json.JSONDecodeError:
                    event_data = {"message": "스트리밍 응답 형식이 올바르지 않습니다."}
            elif not line:
                if event_data:
                    yield {"event": event_name, "data": event_data}
                event_name, event_data = "message", {}
    except requests.RequestException:
        yield {"event": "error", "data": {"message": "서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."}}


def search_hospitals(
    region: str,
    *,
    hospital_type: str = "pediatric",
    user_id: str,
    session_id: str,
) -> dict:
    """지역명 기반 병원 검색 API를 호출한다."""
    if USE_MOCK_API:
        return {
            "success": True,
            "data": {
                "region": region,
                "items": [
                    {
                        "hospital_name": "서아소아청소년과의원",
                        "address": f"{region} 예시로 12",
                        "phone": "02-1234-5678",
                        "operating_hours": "평일 09:00~18:00",
                    }
                ],
                "notice": "운영시간과 진료 가능 여부는 방문 전 의료기관에 확인해 주세요.",
            },
        }
    return request_backend(
        "GET",
        "/api/hospitals/search",
        params={"region": region, "type": hospital_type, "page": 1, "limit": 10},
        headers={"X-User-Id": user_id, "X-Session-Id": session_id},
    )


def analyze_diaper_image(
    image_file: Any,
    *,
    baby_id: str,
    age_days: int,
    feeding_type: str,
    user_id: str,
    session_id: str,
) -> dict:
    """기저귀 사진을 분석 API로 보내 관찰 결과와 안전 안내를 받는다."""
    if USE_MOCK_API:
        return {
            "success": True,
            "data": {
                "is_analyzable": True,
                "quality_issues": [],
                "observation": {"color": "노란색", "consistency": "묽은 형태"},
                "risk": {
                    "level": "none",
                    "signals": [],
                    "recommended_action": "평소와 다른 변화가 계속되거나 걱정되면 소아과에 문의해 주세요.",
                },
                "sources": ["월령별 배변 관찰 참고 자료"],
                "safety_notice": "사진만으로 질환을 진단할 수 없습니다.",
            },
        }
    feeding_type_code = {"모유": "breast", "분유": "formula", "혼합": "mixed"}.get(feeding_type, feeding_type)
    return request_backend(
        "POST",
        "/api/images/diaper-analysis",
        data={
            "baby_id": baby_id,
            "session_id": session_id,
            "user_id": user_id,
            "feeding_type": feeding_type_code,
        },
        files={"image": (getattr(image_file, "name", "diaper-image.jpg"), image_file, getattr(image_file, "type", "image/jpeg"))},
    )


def create_care_log(
    baby_id: str,
    *,
    amount_ml: int,
    feeding_type: str,
    session_id: str,
    user_id: str,
    input_source: str = "ui",
    confirmed_by_user: bool = False,
    idempotency_key: str | None = None,
) -> dict:
    """수유량 선택 결과를 육아 기록으로 저장한다.

    현재는 시연 데이터를 반환하고, 실제 연결 시에는 확정된 FastAPI 계약인
    ``POST /api/care-logs``로 동일한 필드를 전달한다.
    """
    feeding_type_code = {"모유": "breast", "분유": "formula", "혼합": "mixed"}.get(feeding_type, "formula")
    payload = {
        "baby_id": baby_id,
        "event_type": "feeding",
        "recorded_at": datetime.now().astimezone().isoformat(),
        "input_source": input_source,
        "feeding_type": feeding_type_code,
        "amount_ml": amount_ml,
        "idempotency_key": idempotency_key or f"{session_id}-feeding-{uuid4().hex}",
    }
    if input_source == "stt":
        payload["confirmed_by_user"] = confirmed_by_user
    if USE_MOCK_API:
        return {
            "success": True,
            "message": f"{feeding_type} {amount_ml}ml를 기록했습니다.",
            "data": {"log_id": "demo-feeding-log", **payload},
        }
    return request_backend(
        "POST",
        "/api/care-logs",
        json=payload,
        headers={"X-User-Id": user_id, "X-Session-Id": session_id},
    )


def transcribe_audio(audio_file: Any, baby_id: str, session_id: str) -> dict:
    """음성 파일을 STT API로 보내고, 사용자가 확인할 텍스트를 반환한다.

    백엔드가 준비되면 ``POST /api/media/speech/transcribe`` 계약으로 연결한다.
    현재 시연 모드에서는 녹음 결과를 바로 저장하지 않는 흐름을 확인할 수 있도록
    예시 문장을 반환한다.
    """
    if USE_MOCK_API:
        return {
            "success": True,
            "data": {
                "transcript": "서아가 분유 100ml 먹었어요.",
                "response_type": "stt_record_approval",
                "tool_call_id": "demo-stt-feeding-001",
                "approval_snapshot": {
                    "event_type": "feeding",
                    "amount_ml": 100,
                    "feeding_type": "분유",
                },
                "is_demo": True,
            },
        }

    return request_backend(
        "POST",
        "/api/media/speech/transcribe",
        data={"baby_id": baby_id, "session_id": session_id},
        files={"file": (getattr(audio_file, "name", "voice.webm"), audio_file, getattr(audio_file, "type", "audio/webm"))},
    )
