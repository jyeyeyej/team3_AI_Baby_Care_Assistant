"""STT upload and approval API schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class SttApprovalRequest(BaseModel):
    tool_call_id: str = Field(min_length=1, max_length=100)
    baby_id: str = Field(min_length=1, max_length=100)
    session_id: str = Field(min_length=1, max_length=100)
    request_id: str = Field(min_length=1, max_length=100)


class SttApprovalData(BaseModel):
    transcript: str | None = None
    tool_call_id: str | None = None
    record: dict | None = None


class SttResponse(BaseModel):
    success: bool
    message: str
    data: SttApprovalData
    request_id: str


class DiaperAnalysisData(BaseModel):
    model_config = {"extra": "allow"}
    baby_id: str
    is_analyzable: bool
    quality_issues: list[str] = Field(default_factory=list)
    observation: dict | None = None
    risk: dict | None = None
    follow_up_questions: list[str] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    warnings: list[dict] = Field(default_factory=list)
    safety_notice: str


class DiaperAnalysisResponse(BaseModel):
    success: bool
    message: str
    data: DiaperAnalysisData
    request_id: str
