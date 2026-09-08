"""Execute only the allowlisted STT pending call kept in Redis."""

from app.mcp_clients.baby_care_client import record_care_event


async def execute_stt_pending_call(snapshot: dict) -> dict:
    pending = snapshot.get("pending_call", {})
    if pending.get("name") != "record_care_event" or not isinstance(pending.get("arguments"), dict):
        raise ValueError("승인 대기 중인 기록 요청이 올바르지 않습니다.")
    arguments = dict(pending["arguments"])
    arguments["input_source"] = "stt"
    arguments["confirmed_by_user"] = True
    arguments["idempotency_key"] = snapshot["idempotency_key"]
    result = await record_care_event(arguments)
    if not result.get("success"):
        raise RuntimeError("승인된 육아 기록 저장에 실패했습니다.")
    return result.get("data", result)
