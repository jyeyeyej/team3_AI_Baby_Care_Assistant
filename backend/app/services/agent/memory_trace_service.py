"""Small redacted trace writer; transcripts and prompt contents are excluded."""

import json
from typing import Any

async def write_stt_trace(redis, snapshot: dict, status: str, error_code: str | None = None) -> None:
    payload = {"user_id": snapshot["user_id"], "session_id": snapshot["session_id"], "baby_id": snapshot["baby_id"],
               "tool_call_id": snapshot["tool_call_id"], "selected_tools": ["record_care_event"],
               "approval_status": status, "status": "success" if status == "approved" else status, "error_code": error_code}
    await redis.set(f"trace:{snapshot['user_id']}:{snapshot['session_id']}:{snapshot['request_id']}", json.dumps(payload, ensure_ascii=False), ex=86400)

async def write_chat_trace(
    redis, *, user_id: str, session_id: str, baby_id: str, request_id: str,
    tool_used: bool, memory_count: int, memory_created: int,
    selected_tools: list[str] | None = None, tool_arguments: list[dict[str, Any]] | None = None,
    result_validation: str = "not_applicable", reflection_action: str = "none",
) -> None:
    """Store redacted execution facts; never store prompts, transcripts, or secrets."""
    payload = {
        "user_id": user_id, "session_id": session_id, "baby_id": baby_id,
        "selected_tools": selected_tools if selected_tools is not None else ([] if not tool_used else ["unknown"]),
        "tool_arguments": tool_arguments or [], "status": "success",
        "result_validation": result_validation, "reflection_action": reflection_action,
        "memory_retrieved_count": memory_count, "memory_created_count": memory_created,
    }
    await redis.set(f"trace:{user_id}:{session_id}:{request_id}", json.dumps(payload, ensure_ascii=False), ex=86400)
