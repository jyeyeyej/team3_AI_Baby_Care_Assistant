"""육아 기록 저장·조회 입력과 응답 Schema입니다."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from .common import StrictBaseModel, ToolError


EventType = Literal["feeding", "sleep", "diaper", "growth"]
InputSource = Literal["text", "ui", "stt"]
FeedingType = Literal["breast", "formula", "mixed"]
SleepAction = Literal["start", "end"]
QueryType = Literal["today", "range", "pattern", "latest_feeding"]


class RecordCareEventInput(StrictBaseModel):
    baby_id: str = Field(min_length=1, max_length=100)
    event_type: EventType
    input_source: InputSource
    idempotency_key: str = Field(min_length=1, max_length=100)
    recorded_at: datetime | None = None
    confirmed_by_user: bool = False

    feeding_type: FeedingType | None = None
    amount_ml: int | None = Field(default=None, ge=0, le=500)

    action: SleepAction | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=720)

    urine: bool | None = None
    stool: bool | None = None
    color: str | None = Field(default=None, max_length=30)
    consistency: str | None = Field(default=None, max_length=30)
    memo: str | None = Field(default=None, max_length=500)

    weight_kg: float | None = Field(default=None, gt=0, le=50)
    height_cm: float | None = Field(default=None, gt=0, le=150)
    head_circumference_cm: float | None = Field(default=None, gt=0, le=100)


class GetCareRecordsInput(StrictBaseModel):
    baby_id: str = Field(min_length=1, max_length=100)
    query_type: QueryType
    days: int = Field(default=7, ge=1, le=30)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_range_dates(self):
        if self.query_type == "range":
            if self.start_date is None or self.end_date is None:
                raise ValueError("range 조회에는 start_date와 end_date가 필요합니다.")
            if self.start_date > self.end_date:
                raise ValueError("start_date는 end_date보다 늦을 수 없습니다.")
        return self


class CareRecord(StrictBaseModel):
    log_id: str
    baby_id: str
    event_type: EventType
    recorded_at: datetime
    details: dict[str, Any]


class CareRecordData(StrictBaseModel):
    log_id: str
    event_type: EventType
    recorded_at: datetime
    duplicated: bool = False


class CareRecordToolResponse(StrictBaseModel):
    success: bool
    message: str
    data: CareRecordData | None = None
    error: ToolError | None = None


class FeedingPattern(StrictBaseModel):
    count: int = Field(ge=0)
    average_amount_ml: float | None = Field(default=None, ge=0)
    average_interval_minutes: float | None = Field(default=None, ge=0)


class SleepPattern(StrictBaseModel):
    completed_session_count: int = Field(ge=0)
    total_sleep_minutes: int | None = Field(default=None, ge=0)
    average_sleep_minutes: float | None = Field(default=None, ge=0)


class DiaperPattern(StrictBaseModel):
    urine_count: int = Field(ge=0)
    stool_count: int = Field(ge=0)


class CarePattern(StrictBaseModel):
    period_days: int = Field(ge=1, le=30)
    start_date: date
    end_date: date
    record_count: int = Field(ge=0)
    recorded_day_count: int = Field(ge=0)
    sufficient_data: bool
    insufficient_reason: str | None = None
    feeding: FeedingPattern
    sleep: SleepPattern
    diaper: DiaperPattern


class CareRecordsData(StrictBaseModel):
    baby_id: str
    query_type: QueryType
    records: list[CareRecord] = Field(default_factory=list)
    pattern: CarePattern | None = None
    latest_feeding: CareRecord | None = None


class CareRecordsToolResponse(StrictBaseModel):
    success: bool
    message: str
    data: CareRecordsData | None = None
    error: ToolError | None = None
