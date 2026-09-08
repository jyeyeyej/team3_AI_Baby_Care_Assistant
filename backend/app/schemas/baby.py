"""아기 정보 API의 요청과 응답 형식을 정의합니다."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BabyCreateRequest(BaseModel):
    """아기 등록 요청 데이터입니다."""

    baby_name: str = Field(
        min_length=1,
        max_length=30,
        description="아기 이름 또는 애칭",
    )
    birth_date: date = Field(
        description="아기 생년월일",
    )
    gender: Literal["male", "female"] = Field(
        description="아기 성별",
    )
    current_weight_kg: float | None = Field(
        default=None,
        gt=0,
        description="현재 몸무게(kg)",
    )
    current_height_cm: float | None = Field(
        default=None,
        gt=0,
        description="현재 키(cm)",
    )
    feeding_type: Literal["breast", "formula", "mixed"] = Field(
        description="수유 방식",
    )
    allergies: list[str] = Field(
        default_factory=list,
        description="등록된 알레르기 목록",
    )


class BabyUpdateRequest(BaseModel):
    """아기 수정 요청 데이터입니다."""

    baby_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )
    birth_date: date | None = None
    gender: Literal["male", "female"] | None = None
    current_weight_kg: float | None = Field(
        default=None,
        gt=0,
    )
    current_height_cm: float | None = Field(
        default=None,
        gt=0,
    )
    feeding_type: Literal["breast", "formula", "mixed"] | None = None
    allergies: list[str] | None = None


class BabyResponse(BaseModel):
    """아기 정보 조회·등록·수정 결과입니다."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    baby_name: str
    birth_date: date
    gender: str
    current_weight_kg: float | None
    current_height_cm: float | None
    feeding_type: str
    allergies: list[str]
    created_at: datetime
    updated_at: datetime