"""STT upload and one-time approval routes."""

import json
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from app.core.record_policy import STT_APPROVAL_TTL_SECONDS
from app.mcp_clients.baby_care_client import analyze_infant_stool
from app.models.baby import Baby
from app.schemas.media import DiaperAnalysisResponse, SttApprovalRequest, SttResponse
from app.services.agent.memory_trace_service import write_stt_trace
from app.services.agent.tool_call_service import execute_stt_pending_call
from app.services.auth_service import get_login_session
from app.services.media.image_service import delete_diaper_image, save_diaper_image
from app.services.media.speech_service import transcribe_audio as transcribe_upload
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api", tags=["음성 입력"])


async def current_user(request: Request, user_id: str, session_id: str) -> dict:
    session = await get_login_session(request.app.state.redis, user_id, session_id)
    if not session:
        raise HTTPException(status_code=401, detail="로그인 세션이 없거나 만료되었습니다.")
    return session


def extract_feeding(transcript: str) -> dict | None:
    lowered = transcript.replace(" ", "").lower()
    if any(word in lowered for word in ("안먹", "못먹", "하나도안먹", "수유안")):
        return None
    amount = re.search(r"(\d{1,3})\s*(?:ml|밀리(?:리터)?)", transcript, re.I)
    if "분유" in transcript:
        return {"event_type": "feeding", "feeding_type": "formula", "amount_ml": int(amount.group(1)) if amount else None}
    if "모유" in transcript or "수유" in transcript:
        return {"event_type": "feeding", "feeding_type": "breast", "amount_ml": int(amount.group(1)) if amount else None}
    return None


@router.post("/speech/transcriptions", response_model=SttResponse)
async def transcribe_audio(
    request: Request,
    baby_id: str = Form(...),
    session_id: str = Form(...),
    user_id: str = Form(...),
    audio: UploadFile = File(...),
) -> dict:
    session = await current_user(request, user_id, session_id)
    if session.get("baby_id") != baby_id:
        raise HTTPException(status_code=403, detail="요청한 아기 정보에 접근할 수 없습니다.")
    transcript = await transcribe_upload(audio)
    event = extract_feeding(transcript)
    request_id = str(uuid4())
    if event is None:
        return {
            "success": True,
            "message": "음성을 텍스트로 변환했습니다.",
            "request_id": request_id,
            "data": {"transcript": transcript, "response_type": "speech_transcription"},
        }
    tool_call_id = str(uuid4())
    snapshot = {"user_id": user_id, "baby_id": baby_id, "session_id": session_id, "request_id": request_id, "tool_call_id": tool_call_id,
                "pending_call": {"name": "record_care_event", "arguments": {"baby_id": baby_id, **event}}, "approval_snapshot": event,
                "idempotency_key": f"{session_id}-{tool_call_id}", "status": "waiting_stt_approval",
                "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=STT_APPROVAL_TTL_SECONDS)).isoformat()}
    await request.app.state.redis.set(f"stt_approval:{user_id}:{session_id}:{tool_call_id}", json.dumps(snapshot, ensure_ascii=False), ex=STT_APPROVAL_TTL_SECONDS)
    return {
        "success": True,
        "message": "기록 내용을 확인해 주세요.",
        "request_id": request_id,
        "data": {
            "transcript": transcript,
            "response_type": "stt_record_approval",
            "tool_call_id": tool_call_id,
            "record": event,
        },
    }


@router.post("/images/diaper-analysis", response_model=DiaperAnalysisResponse)
async def diaper_analysis(
    request: Request,
    baby_id: str = Form(...),
    session_id: str = Form(...),
    user_id: str = Form(...),
    feeding_type: str = Form(...),
    has_fever: bool | None = Form(default=None),
    stool_count_24h: int | None = Form(default=None),
    image: UploadFile = File(...),
) -> dict:
    session = await current_user(request, user_id, session_id)
    if session.get("baby_id") != baby_id:
        raise HTTPException(status_code=403, detail="요청한 아기 정보에 접근할 수 없습니다.")
    if feeding_type not in {"breast", "formula", "mixed"}:
        raise HTTPException(status_code=422, detail="수유 방식이 올바르지 않습니다.")
    async with AsyncSession(request.app.state.db_engine, expire_on_commit=False) as db:
        baby = (await db.execute(select(Baby).where(Baby.id == baby_id, Baby.user_id == user_id))).scalar_one_or_none()
    if baby is None:
        raise HTTPException(status_code=404, detail="아기 정보를 찾을 수 없습니다.")
    image_path = await save_diaper_image(image)
    try:
        age_months = max(0, min(36, (date.today() - baby.birth_date).days // 30))
        result = await analyze_infant_stool({"baby_id": baby_id, "image_path": str(image_path), "baby_age_months": age_months,
                                             "feeding_type": feeding_type, "has_fever": has_fever, "stool_count_24h": stool_count_24h})
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="기저귀 사진 분석 서비스에 연결할 수 없습니다.") from exc
    finally:
        # Care 서버도 정상 흐름에서 지우지만, MCP 오류까지 포함해 원본을 남기지 않습니다.
        delete_diaper_image(image_path)
    if not result.get("success") or not isinstance(result.get("data"), dict):
        raise HTTPException(status_code=502, detail="기저귀 사진 분석에 실패했습니다.")
    return {"success": True, "message": result.get("message", "기저귀 사진을 분석했습니다."), "data": result["data"], "request_id": str(uuid4())}


@router.post("/speech/approvals/confirm", response_model=SttResponse)
async def confirm_stt(payload: SttApprovalRequest, request: Request) -> dict:
    session = await current_user(request, request.headers.get("X-User-Id", ""), payload.session_id)
    user_id = session["user_id"]
    key = f"stt_approval:{user_id}:{payload.session_id}:{payload.tool_call_id}"
    raw = await request.app.state.redis.get(key)
    if not raw:
        raise HTTPException(status_code=404, detail="승인 대기 기록을 찾을 수 없습니다.")
    snapshot = json.loads(raw)
    if any(snapshot.get(field) != getattr(payload, field) for field in ("baby_id", "session_id", "request_id", "tool_call_id")) or snapshot.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="승인 요청이 일치하지 않습니다.")
    if snapshot.get("status") != "waiting_stt_approval":
        raise HTTPException(status_code=409, detail="이미 처리된 승인 요청입니다.")
    if datetime.fromisoformat(snapshot["expires_at"]) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="승인 요청이 만료되었습니다.")
    snapshot["status"] = "processing"
    if not await request.app.state.redis.set(key, json.dumps(snapshot, ensure_ascii=False), xx=True):
        raise HTTPException(status_code=409, detail="승인 요청을 처리할 수 없습니다.")
    try:
        data = await execute_stt_pending_call(snapshot)
    except Exception as exc:
        snapshot["status"] = "failed"; await request.app.state.redis.set(key, json.dumps(snapshot, ensure_ascii=False), ex=STT_APPROVAL_TTL_SECONDS)
        await write_stt_trace(request.app.state.redis, snapshot, "failed", "MCP_SERVER_UNAVAILABLE")
        raise HTTPException(status_code=503, detail="승인된 기록 저장에 실패했습니다.") from exc
    snapshot["status"] = "approved"; await request.app.state.redis.set(key, json.dumps(snapshot, ensure_ascii=False), ex=STT_APPROVAL_TTL_SECONDS)
    await write_stt_trace(request.app.state.redis, snapshot, "approved")
    return {"success": True, "message": "승인된 육아 기록을 저장했습니다.", "request_id": payload.request_id, "data": {"tool_call_id": payload.tool_call_id, "record": data}}


@router.post("/speech/approvals/reject", response_model=SttResponse)
async def reject_stt(payload: SttApprovalRequest, request: Request) -> dict:
    session = await current_user(request, request.headers.get("X-User-Id", ""), payload.session_id)
    key = f"stt_approval:{session['user_id']}:{payload.session_id}:{payload.tool_call_id}"
    raw = await request.app.state.redis.get(key)
    if not raw:
        raise HTTPException(status_code=404, detail="승인 대기 기록을 찾을 수 없습니다.")
    snapshot = json.loads(raw)
    if snapshot.get("user_id") != session["user_id"] or snapshot.get("baby_id") != payload.baby_id or snapshot.get("request_id") != payload.request_id or snapshot.get("status") != "waiting_stt_approval":
        raise HTTPException(status_code=409, detail="거절할 승인 요청이 일치하지 않습니다.")
    snapshot["status"] = "rejected"; await request.app.state.redis.set(key, json.dumps(snapshot, ensure_ascii=False), ex=STT_APPROVAL_TTL_SECONDS)
    await write_stt_trace(request.app.state.redis, snapshot, "rejected")
    return {"success": True, "message": "음성 기록 저장을 취소했습니다.", "request_id": payload.request_id, "data": {"tool_call_id": payload.tool_call_id}}
