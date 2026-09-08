"""Information API schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class HospitalSearchResponse(BaseModel):
    region: str
    type: Literal["pediatric", "emergency"]
    data: list[dict]
    source: str
    checked_at: str | None
    notice: str | None


class HospitalSearchQuery(BaseModel):
    region: str = Field(min_length=2, max_length=100)
    type: Literal["pediatric", "emergency"]
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=10, ge=1, le=30)
