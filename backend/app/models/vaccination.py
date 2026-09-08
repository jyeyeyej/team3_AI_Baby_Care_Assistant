"""Validated shape for local vaccination schedule entries."""

from pydantic import BaseModel, Field


class VaccinationScheduleItem(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    dose: str = Field(min_length=1, max_length=50)
    recommended_month: int = Field(ge=0, le=36)
