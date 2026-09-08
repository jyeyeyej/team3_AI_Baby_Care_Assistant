"""User-safe SSE progress events; internal prompts and traces never leave here."""

import json
from collections.abc import AsyncIterator

from .agent_service import answer_chat

def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

async def stream_chat(request, app) -> AsyncIterator[str]:
    yield _event("received", {"status": "received"})
    yield _event("loading_context", {"status": "loading_context"})
    yield _event("analyzing_request", {"status": "analyzing_request"})
    yield _event("generating_answer", {"status": "generating_answer"})
    try:
        result = await answer_chat(request, app)
    except PermissionError:
        yield _event("error", {"status": "error", "code": "SESSION_INVALID", "message": "세션을 확인할 수 없습니다."})
        return
    except RuntimeError:
        yield _event("error", {"status": "error", "code": "RAG_SERVICE_UNAVAILABLE", "message": "육아 정보 검색 서비스를 사용할 수 없습니다."})
        return
    yield _event("completed", {"status": "completed", "result": result})
