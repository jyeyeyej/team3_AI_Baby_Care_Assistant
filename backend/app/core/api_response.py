"""Common frontend-facing response helpers."""

from typing import Any
from uuid import uuid4


def success(message: str, data: Any, request_id: str | None = None) -> dict[str, Any]:
    """Build the single success envelope used by FastAPI endpoints."""
    return {"success": True, "message": message, "data": data,
            "request_id": request_id or str(uuid4())}
