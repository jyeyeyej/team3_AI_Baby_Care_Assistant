"""육아 기록 저장 MCP Tool 함수입니다."""

from typing import Literal

from ..schemas.care import RecordCareEventInput
from ..services.care_service import record_care_event as save_care_event


def record_care_event(
    baby_id: str,
    event_type: Literal["feeding", "sleep", "diaper", "growth"],
    input_source: Literal["text", "ui", "stt"],
    idempotency_key: str,
    recorded_at: str | None = None,
    confirmed_by_user: bool = False,
    feeding_type: Literal["breast", "formula", "mixed"] | None = None,
    amount_ml: int | None = None,
    action: Literal["start", "end"] | None = None,
    duration_minutes: int | None = None,
    urine: bool | None = None,
    stool: bool | None = None,
    color: str | None = None,
    consistency: str | None = None,
    memo: str | None = None,
    weight_kg: float | None = None,
    height_cm: float | None = None,
    head_circumference_cm: float | None = None,
) -> dict:
    """수유·수면·기저귀·성장 기록 1건을 저장합니다."""
    request = RecordCareEventInput(
        baby_id=baby_id, event_type=event_type, input_source=input_source,
        idempotency_key=idempotency_key, recorded_at=recorded_at,
        confirmed_by_user=confirmed_by_user, feeding_type=feeding_type,
        amount_ml=amount_ml, action=action, duration_minutes=duration_minutes, urine=urine, stool=stool,
        color=color, consistency=consistency, memo=memo, weight_kg=weight_kg,
        height_cm=height_cm, head_circumference_cm=head_circumference_cm,
    )
    return save_care_event(request).model_dump(mode="json")
