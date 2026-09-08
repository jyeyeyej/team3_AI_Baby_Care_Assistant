"""Chat and stream routes."""

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.agent.agent_service import answer_chat
from app.services.agent.chat_stream_service import stream_chat
from app.services.auth_service import get_login_session

router = APIRouter(prefix="/api", tags=["AI 채팅"])


async def authenticated_payload(
    payload: ChatRequest,
    request: Request,
    x_user_id: str = Header(alias="X-User-Id"),
    x_session_id: str = Header(alias="X-Session-Id"),
) -> ChatRequest:
    """헤더 로그인 세션을 검증하고 본문의 user_id를 신뢰하지 않는다."""
    if payload.session_id != x_session_id:
        raise HTTPException(status_code=401, detail="요청 세션이 일치하지 않습니다.")
    login_session = await get_login_session(request.app.state.redis, x_user_id, x_session_id)
    if login_session is None:
        raise HTTPException(status_code=401, detail="세션을 확인할 수 없습니다.")
    return payload.model_copy(update={"user_id": login_session["user_id"]})


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    x_user_id: str = Header(alias="X-User-Id"),
    x_session_id: str = Header(alias="X-Session-Id"),
) -> dict:
    payload = await authenticated_payload(payload, request, x_user_id, x_session_id)
    try:
        return await answer_chat(payload, request.app)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail="세션을 확인할 수 없습니다.") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="육아 정보 검색 서비스를 사용할 수 없습니다.") from exc

@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    x_user_id: str = Header(alias="X-User-Id"),
    x_session_id: str = Header(alias="X-Session-Id"),
) -> StreamingResponse:
    payload = await authenticated_payload(payload, request, x_user_id, x_session_id)
    return StreamingResponse(stream_chat(payload, request.app), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
