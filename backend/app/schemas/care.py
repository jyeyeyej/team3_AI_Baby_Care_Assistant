"""육아 기록과 수유 알림 API 형식을 정의합니다."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CareLogCreateRequest(BaseModel):
    """빠른 육아 기록 저장 요청 데이터입니다."""

    baby_id: str = Field(min_length=1, max_length=100)
    event_type: Literal["feeding", "sleep", "diaper", "growth"]
    input_source: Literal["ui", "text", "stt"]
    recorded_at: datetime | None = None
    idempotency_key: str = Field(min_length=1, max_length=100)
    confirmed_by_user: bool = False

    feeding_type: Literal["breast", "formula", "mixed"] | None = None
    amount_ml: int | None = Field(default=None, ge=0, le=500)

    action: Literal["start", "end"] | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=720)

    urine: bool = False
    stool: bool = False
    color: str | None = Field(default=None, max_length=50)
    consistency: str | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=500)

    weight_kg: float | None = Field(default=None, gt=0, le=50)
    height_cm: float | None = Field(default=None, gt=0, le=150)
    head_circumference_cm: float | None = Field(default=None, gt=0, le=100)

    @model_validator(mode="after")
    def validate_event_details(self):
        """기록 유형별 필수 입력값을 확인합니다."""
        if self.event_type == "feeding" and self.feeding_type is None:
            raise ValueError("수유 기록에는 수유 방식을 입력해 주세요.")

        if self.event_type == "sleep" and self.action is None and self.duration_minutes is None:
            raise ValueError("수면 기록에는 시간 또는 시작·종료를 입력해 주세요.")

        if self.event_type == "diaper" and not self.urine and not self.stool:
            raise ValueError("기저귀 기록에는 소변 또는 대변을 선택해 주세요.")

        if self.event_type == "growth":
            values = [
                self.weight_kg,
                self.height_cm,
                self.head_circumference_cm,
            ]
            if not any(value is not None for value in values):
                raise ValueError("성장 기록에는 수치 하나 이상을 입력해 주세요.")

        return self


class CareLogUpdateRequest(BaseModel):
    """기존 육아 기록의 수정 가능한 값입니다.

    이벤트 유형은 변경하지 않습니다. 기록 유형을 바꾸는 것은 기존 기록을
    삭제하고 새 idempotency_key로 다시 저장하는 방식으로만 허용합니다.
    """

    recorded_at: datetime | None = None
    feeding_type: Literal["breast", "formula", "mixed"] | None = None
    amount_ml: int | None = Field(default=None, ge=0, le=500)
    action: Literal["start", "end"] | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=720)
    urine: bool | None = None
    stool: bool | None = None
    color: str | None = Field(default=None, max_length=50)
    consistency: str | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=500)
    weight_kg: float | None = Field(default=None, gt=0, le=50)
    height_cm: float | None = Field(default=None, gt=0, le=150)
    head_circumference_cm: float | None = Field(default=None, gt=0, le=100)

    @model_validator(mode="after")
    def require_update_value(self):
        if not self.model_fields_set:
            raise ValueError("수정할 값을 하나 이상 입력해 주세요.")
        return self


class CareRecordResponse(BaseModel):
    """Care MCP가 반환한 육아 기록 결과입니다."""

    model_config = ConfigDict(extra="allow")

    data: dict[str, Any]


class CareRecordsQuery(BaseModel):
    """육아 기록 조회 조건입니다."""

    baby_id: str = Field(min_length=1, max_length=100)
    query_type: Literal["today", "range", "pattern", "latest_feeding"] = "today"
    start_date: date | None = None
    end_date: date | None = None
    days: int = Field(default=7, ge=1, le=30)

    @model_validator(mode="after")
    def validate_date_range(self):
        """기간 조회에 필요한 날짜와 순서를 확인합니다."""
        if self.query_type != "range":
            return self

        if self.start_date is None or self.end_date is None:
            raise ValueError("기간 조회에는 시작일과 종료일이 필요합니다.")

        if self.start_date > self.end_date:
            raise ValueError("시작일은 종료일보다 늦을 수 없습니다.")

        return self


class ReminderActionRequest(BaseModel):
    """수유 알림 상태 변경 요청 데이터입니다."""

    action: Literal["confirm", "snooze", "skip"]


class ReminderSettingsUpdateRequest(BaseModel):
    """수유 알림 간격 설정 수정 요청 데이터입니다."""

    feeding_interval_minutes: int = Field(
        ge=30,
        le=720,
        description="수유 알림 간격(분)",
    )


class FeedingReminderResponse(BaseModel):
    """수유 알림 설정 조회·수정 결과입니다."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    baby_id: str
    feeding_interval_minutes: int
    created_at: datetime
    updated_at: datetime


class ReminderActionResponse(BaseModel):
    """수유 알림 상태 변경 결과입니다."""

    reminder_id: str
    baby_id: str
    action: Literal["confirm", "snooze", "skip"]
    status: Literal["confirmed", "snoozed", "skipped"]
    next_reminder_at: datetime | None
