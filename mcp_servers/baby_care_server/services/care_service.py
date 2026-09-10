"""육아 기록 저장 업무 로직입니다."""

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from ..config import settings
from ..repositories import care_log_repository
from ..schemas.care import CareRecordData, CareRecordToolResponse, RecordCareEventInput
from ..schemas.common import ToolError


def failure(code: str, message: str, detail: str) -> CareRecordToolResponse:
    """예상 가능한 업무 오류를 공통 형식으로 만듭니다."""
    return CareRecordToolResponse(
        success=False,
        message=message,
        data=None,
        error=ToolError(code=code, detail=detail),
    )


def _success_from_row(row: dict, *, duplicated: bool) -> CareRecordToolResponse:
    """DB 조회 결과를 Tool 성공 응답으로 변환합니다."""
    event_names = {
        "feeding": "수유",
        "sleep": "수면",
        "diaper": "기저귀",
        "growth": "성장",
    }
    event_name = event_names.get(row["event_type"], "육아")
    message = (
        "이미 처리된 요청입니다. 기존 기록을 반환합니다."
        if duplicated
        else f"{event_name} 기록을 저장했습니다."
    )
    return CareRecordToolResponse(
        success=True,
        message=message,
        data=CareRecordData(
            log_id=row["log_id"],
            event_type=row["event_type"],
            recorded_at=row["recorded_at"],
            duplicated=duplicated,
        ),
        error=None,
    )


def _recorded_at_or_now(value: datetime | None) -> datetime:
    """시각이 없으면 설정된 한국 시간의 현재 시각을 사용합니다."""
    timezone = ZoneInfo(settings.app_timezone)
    if value is None:
        return datetime.now(timezone)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone)
    return value


def record_care_event(request: RecordCareEventInput) -> CareRecordToolResponse:
    """검증된 수유·수면·기저귀·성장 기록을 저장합니다."""
    if request.input_source == "stt" and not request.confirmed_by_user:
        return failure(
            "STT_CONFIRMATION_REQUIRED",
            "STT 기록은 사용자 확인 후 저장할 수 있습니다.",
            "input_source가 stt이면 confirmed_by_user=true가 필요합니다.",
        )

    existing = care_log_repository.find_by_idempotency_key(request.idempotency_key)
    if existing is not None:
        if existing["baby_id"] != request.baby_id:
            return failure(
                "IDEMPOTENCY_KEY_CONFLICT",
                "이미 다른 요청에 사용된 중복 방지 키입니다.",
                "새 idempotency_key로 다시 요청해 주세요.",
            )
        return _success_from_row(existing, duplicated=True)

    if not care_log_repository.baby_exists(request.baby_id):
        return failure(
            "BABY_NOT_FOUND",
            "아기 정보를 찾을 수 없습니다.",
            "baby_id에 해당하는 데이터가 없습니다.",
        )

    if request.event_type == "feeding":
        if request.feeding_type is None:
            return failure(
                "INVALID_CARE_EVENT",
                "수유 방식을 입력해 주세요.",
                "feeding 기록에는 feeding_type이 필요합니다.",
            )
        details = {
            "feeding_type": request.feeding_type,
            "amount_ml": request.amount_ml,
        }
    elif request.event_type == "diaper":
        if request.urine is not True and request.stool is not True:
            return failure(
                "INVALID_CARE_EVENT",
                "소변 또는 대변 중 하나 이상을 선택해 주세요.",
                "diaper 기록에는 urine 또는 stool 중 하나 이상이 true여야 합니다.",
            )
        details = {
            "urine": request.urine is True,
            "stool": request.stool is True,
        }
        optional_details = {
            "color": request.color,
            "consistency": request.consistency,
            "memo": request.memo,
        }
        details.update(
            {key: value for key, value in optional_details.items() if value is not None}
        )
    elif request.event_type == "growth":
        growth_details = {
            "weight_kg": request.weight_kg,
            "height_cm": request.height_cm,
            "head_circumference_cm": request.head_circumference_cm,
        }
        details = {
            key: value for key, value in growth_details.items() if value is not None
        }
        if not details:
            return failure(
                "INVALID_CARE_EVENT",
                "성장 측정값을 하나 이상 입력해 주세요.",
                "growth 기록에는 weight_kg, height_cm, head_circumference_cm 중 하나 이상이 필요합니다.",
            )
    else:
        if request.duration_minutes is not None:
            details = {"duration_minutes": request.duration_minutes}
        else:
            if request.action is None:
                return failure(
                    "INVALID_CARE_EVENT",
                    "수면 시간을 입력하거나 시작 또는 종료를 선택해 주세요.",
                    "sleep 기록에는 duration_minutes 또는 action이 필요합니다.",
                )

            open_sleep = care_log_repository.find_open_sleep(request.baby_id)
            if request.action == "start" and open_sleep is not None:
                return failure(
                    "SLEEP_ALREADY_STARTED",
                    "이미 수면 중으로 기록되어 있습니다.",
                    "기존 수면을 먼저 종료한 뒤 다시 시작해 주세요.",
                )
            if request.action == "end" and open_sleep is None:
                return failure(
                    "SLEEP_START_NOT_FOUND",
                    "종료할 수면 시작 기록이 없습니다.",
                    "수면 시작을 먼저 기록해 주세요.",
                )
            details = {"action": request.action}
    saved = care_log_repository.insert_care_log(
        log_id=str(uuid4()),
        baby_id=request.baby_id,
        event_type=request.event_type,
        recorded_at=_recorded_at_or_now(request.recorded_at),
        details=details,
        idempotency_key=request.idempotency_key,
    )
    return _success_from_row(saved, duplicated=False)
