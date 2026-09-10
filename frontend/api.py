"""Streamlit과 FastAPI 사이의 공통 API 계층.

백엔드가 준비되기 전에는 ``USE_MOCK_API=true``로 목데이터를 사용한다.
준비 후에는 환경변수를 false로 바꾸고, 확정된 엔드포인트별 함수가
아래 공통 HTTP 클라이언트를 사용하도록 연결한다.
페이지 파일은 이 모듈의 함수만 호출하며 HTTP 세부 구현을 직접 갖지 않는다.
"""

from __future__ import annotations

import os
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests
from dotenv import load_dotenv


# Streamlit is launched from the frontend directory in some environments, so
# load the project-level settings explicitly instead of relying on its shell.
# 실행 셸에 남아 있는 이전 값보다 프로젝트 .env를 우선해야 팀별 서버 주소
# 변경이 즉시 반영됩니다.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

def _normalize_backend_url(value: str) -> str:
    """Accept a mistakenly pasted Markdown URL while always using its raw URL."""
    match = re.fullmatch(r"\[([^\]]+)\]\([^\)]+\)", value.strip())
    return (match.group(1) if match else value).rstrip("/")


BACKEND_API_URL = _normalize_backend_url(
    os.getenv("BACKEND_API_URL", "http://localhost:8000")
)
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
    "baby_name": "태경",
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
    user_id = selected_user if selected_user in {"user-001", "user-002"} else (
        "user-001" if selected_user.startswith(("서아", "태경")) else "user-002"
    )
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
            # The database permits optional growth fields.  Do not let a
            # backend null replace the existing demo fallback used by the
            # dashboard and growth chart.
            populated_data = {key: value for key, value in data.items() if value is not None}
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
                    **populated_data,
                    "baby_id": data.get("id", baby_id),
                    "age_days": age_days,
                    "feeding_type": feeding_labels.get(data.get("feeding_type"), data.get("feeding_type")),
                },
            }
        return result
    fallback = BABY.copy()
    fallback["baby_id"] = baby_id
    return {"success": True, "data": fallback}


def update_baby(
    baby_id: str,
    payload: dict[str, Any],
    *,
    user_id: str,
    session_id: str,
) -> dict:
    """Save the editable baby profile through the authenticated backend API."""
    if USE_MOCK_API:
        updated = {**BABY, **payload, "baby_id": baby_id}
        return {"success": True, "message": "목데이터에 아기 정보를 저장했습니다.", "data": updated}

    gender_codes = {"여아": "female", "남아": "male"}
    feeding_codes = {"모유": "breast", "분유": "formula", "혼합": "mixed"}
    request_payload = {
        **payload,
        "gender": gender_codes.get(payload.get("gender"), payload.get("gender")),
        "feeding_type": feeding_codes.get(
            payload.get("feeding_type"), payload.get("feeding_type")
        ),
    }
    return request_backend(
        "PATCH",
        f"/api/babies/{baby_id}",
        json=request_payload,
        headers={"X-User-Id": user_id, "X-Session-Id": session_id},
    )


def get_feeding_reminder(
    baby_id: str,
    *,
    user_id: str,
    session_id: str,
) -> dict:
    """Read the saved feeding-reminder interval for the logged-in baby."""
    if USE_MOCK_API:
        return {
            "success": True,
            "message": "목 알림 설정입니다.",
            "data": {"id": "mock-reminder", "baby_id": baby_id, "feeding_interval_minutes": 180},
        }
    return request_backend(
        "GET",
        f"/api/reminders/feeding/{baby_id}",
        headers={"X-User-Id": user_id, "X-Session-Id": session_id},
    )


def update_feeding_reminder(
    baby_id: str,
    interval_minutes: int,
    *,
    user_id: str,
    session_id: str,
) -> dict:
    """Persist the feeding-reminder interval in the backend database."""
    if USE_MOCK_API:
        return {
            "success": True,
            "message": "목 알림 설정을 저장했습니다.",
            "data": {"id": "mock-reminder", "baby_id": baby_id, "feeding_interval_minutes": interval_minutes},
        }
    return request_backend(
        "PATCH",
        f"/api/reminders/feeding/{baby_id}/settings",
        json={"feeding_interval_minutes": interval_minutes},
        headers={"X-User-Id": user_id, "X-Session-Id": session_id},
    )


def change_feeding_reminder_action(*, baby_id: str, action: str, user_id: str, session_id: str) -> dict:
    """Persist confirm/snooze/skip instead of changing only Streamlit state."""
    reminder = get_feeding_reminder(baby_id, user_id=user_id, session_id=session_id)
    reminder_id = (reminder.get("data") or {}).get("id")
    if not reminder.get("success") or not reminder_id:
        return {"success": False, "message": reminder.get("message", "수유 알림을 찾지 못했습니다."), "data": {}}
    if USE_MOCK_API:
        return {"success": True, "message": "알림 상태를 변경했습니다.", "data": {"action": action}}
    return request_backend(
        "PATCH",
        f"/api/reminders/{reminder_id}",
        json={"action": action},
        headers={"X-User-Id": user_id, "X-Session-Id": session_id},
    )


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


def get_care_records(baby_id: str, *, user_id: str | None = None, session_id: str | None = None, days: int = 1) -> dict:
    """Read saved care logs from the requested recent-day range."""
    if not USE_MOCK_API:
        headers = {}
        if user_id:
            headers["X-User-Id"] = user_id
        if session_id:
            headers["X-Session-Id"] = session_id
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        return request_backend(
            "GET",
            "/api/care-logs",
            params={
                "baby_id": baby_id,
                "query_type": "range",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            headers=headers,
        )
    return {
        "success": True,
        "data": [
            {"time": "오늘 14:30", "icon": "🍼", "title": "분유 수유", "detail": "100ml · 알림 확인으로 기록", "event_type": "feeding"},
            {"time": "오늘 12:05", "icon": "🌙", "title": "낮잠 종료", "detail": "10:20–12:05 · 1시간 45분", "event_type": "sleep"},
            {"time": "오늘 09:40", "icon": "💩", "title": "기저귀 · 대변", "detail": "노란색, 묽은 형태 · 사진 분석 메모 있음", "event_type": "diaper"},
            {"time": "9월 2일", "icon": "📏", "title": "성장 측정", "detail": "몸무게 4.2kg · 키 54.1cm · 머리둘레 37cm", "event_type": "growth"},
        ],
    }


def delete_care_log(log_id: str, *, user_id: str, session_id: str) -> dict:
    """Delete one saved care log owned by the signed-in user."""
    if USE_MOCK_API:
        return {"success": True, "message": "육아 기록을 삭제했습니다.", "data": {"log_id": log_id}}
    return request_backend(
        "DELETE",
        f"/api/care-logs/{log_id}",
        headers={"X-User-Id": user_id, "X-Session-Id": session_id},
    )


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


def stream_hospital_search(
    region: str,
    *,
    hospital_type: str,
    user_id: str,
    session_id: str,
):
    """Yield hospital-search progress events from the SSE endpoint."""
    if USE_MOCK_API:
        yield {"event": "completed", "data": search_hospitals(
            region,
            hospital_type=hospital_type,
            user_id=user_id,
            session_id=session_id,
        )}
        return

    try:
        response = requests.get(
            f"{BACKEND_API_URL}/api/hospitals/search/stream",
            params={"region": region, "type": hospital_type, "page": 1, "limit": 3},
            headers={"X-User-Id": user_id, "X-Session-Id": session_id},
            stream=True,
            # 소아과 공공데이터는 제공자 리다이렉트·전문과 조회로 최대 20초가 걸릴 수 있다.
            # 일반 채팅의 짧은 제한을 그대로 쓰면 결과가 도착하기 전에 연결 오류가 된다.
            timeout=max(API_TIMEOUT_SECONDS, 35),
        )
        if not response.ok:
            try:
                body = response.json()
                message_text = body.get("detail") or "병원 검색을 처리하지 못했습니다."
            except ValueError:
                message_text = "병원 검색을 처리하지 못했습니다."
            yield {"event": "error", "data": {"message": message_text}}
            return

        event_name = "message"
        event_data: dict[str, Any] = {}
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
        yield {"event": "error", "data": {"message": "병원 검색 서버에 연결할 수 없습니다."}}


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
                    },
                    {
                        "hospital_name": "햇살소아청소년과의원",
                        "address": f"{region} 예시로 28",
                        "phone": "02-2345-6789",
                        "operating_hours": "평일 09:00~18:30",
                    },
                    {
                        "hospital_name": "튼튼소아청소년과의원",
                        "address": f"{region} 예시로 45",
                        "phone": "02-3456-7890",
                        "operating_hours": "평일 09:00~19:00",
                    },
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


def create_quick_care_log(
    baby_id: str,
    *,
    event_type: str,
    session_id: str,
    user_id: str,
    **details: Any,
) -> dict:
    """Save a non-feeding quick record through the existing care-log API."""
    payload = {
        "baby_id": baby_id,
        "event_type": event_type,
        "input_source": "ui",
        "recorded_at": datetime.now().astimezone().isoformat(),
        "idempotency_key": f"{session_id}-{event_type}-{uuid4().hex}",
        **details,
    }
    if USE_MOCK_API:
        return {"success": True, "message": "육아 기록을 저장했습니다.", "data": payload}
    return request_backend(
        "POST",
        "/api/care-logs",
        json=payload,
        headers={"X-User-Id": user_id, "X-Session-Id": session_id},
    )


def get_care_summary(baby_id: str, *, user_id: str, session_id: str) -> dict:
    """최근 저장 기록을 집계한 육아 관리 상단 요약을 조회합니다."""
    if not USE_MOCK_API:
        return request_backend(
            "GET",
            f"/api/care-summary/{baby_id}",
            params={"days": 7},
            headers={"X-User-Id": user_id, "X-Session-Id": session_id},
        )
    return {
        "success": True,
        "data": {
            "period_days": 7,
            "feeding": {"count": 47, "average_amount_ml": 96, "average_interval_minutes": 192},
            "sleep": {"total_minutes": 5964, "daily_average_minutes": 852},
            "diaper": {"stool_count": 19},
        },
    }
def transcribe_audio(audio_file: Any, baby_id: str, session_id: str, user_id: str) -> dict:
    """음성 파일을 STT API로 보내고, 사용자가 확인할 텍스트를 반환한다.

    ``POST /api/speech/transcriptions``로 파일·아기·세션을 전송한다.
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
        "/api/speech/transcriptions",
        data={"baby_id": baby_id, "session_id": session_id, "user_id": user_id},
        files={"audio": (getattr(audio_file, "name", "voice.webm"), audio_file, getattr(audio_file, "type", "audio/webm"))},
    )


def confirm_stt_record(*, tool_call_id: str, baby_id: str, session_id: str, request_id: str, user_id: str) -> dict:
    """승인 대기 Snapshot을 검증해 기록을 한 번만 저장한다."""
    if USE_MOCK_API:
        return {
            "success": True,
            "message": "음성 수유 기록을 저장했습니다.",
            "data": {"tool_call_id": tool_call_id},
        }
    return request_backend(
        "POST",
        "/api/speech/approvals/confirm",
        json={
            "tool_call_id": tool_call_id,
            "baby_id": baby_id,
            "session_id": session_id,
            "request_id": request_id,
        },
        headers={"X-User-Id": user_id, "X-Session-Id": session_id},
    )


def reject_stt_record(*, tool_call_id: str, baby_id: str, session_id: str, request_id: str, user_id: str) -> dict:
    """승인 대기 Snapshot을 폐기하며 DB 기록은 만들지 않는다."""
    if USE_MOCK_API:
        return {"success": True, "message": "음성 기록 저장을 취소했습니다.", "data": {"tool_call_id": tool_call_id}}
    return request_backend(
        "POST",
        "/api/speech/approvals/reject",
        json={
            "tool_call_id": tool_call_id,
            "baby_id": baby_id,
            "session_id": session_id,
            "request_id": request_id,
        },
        headers={"X-User-Id": user_id, "X-Session-Id": session_id},
    )
