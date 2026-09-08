"""Shared strict Pydantic base and API response schema."""

from typing import Any
from pydantic import BaseModel, ConfigDict


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApiResponse(StrictBaseModel):
    success: bool = True
    message: str
    data: Any
    request_id: str
