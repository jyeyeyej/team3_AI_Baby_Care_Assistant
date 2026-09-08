"""Client for the two hospital-search tools on baby_info_server."""

import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Literal

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, ValidationError

from app.core.config import BABY_INFO_MCP_URL


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _ToolFailure(_StrictModel):
    success: Literal[False]
    message: str = Field(min_length=1, max_length=500)
    error_code: str = Field(min_length=1, max_length=100)


class _Hospital(_StrictModel):
    hospital_name: str = Field(min_length=1)
    address: str = Field(min_length=1)
    phone: str | None = None
    operating_hours: str | None = None
    emergency_level: str | None = None


class _HospitalSuccess(_StrictModel):
    success: Literal[True]
    region: str = Field(min_length=2, max_length=100)
    data: list[_Hospital]
    source: Literal["public_data"]
    checked_at: datetime
    notice: str = Field(min_length=1)


class _KnowledgeSource(_StrictModel):
    document_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    organization: str = Field(min_length=1)
    url: AnyHttpUrl
    verified_at: str | None = None
    score: float = Field(ge=0.0, le=1.0)


class _KnowledgeSuccess(_StrictModel):
    success: Literal[True]
    answer: str = Field(min_length=1)
    category: Literal["feeding", "sleep", "weaning", "development", "safety"]
    sources: list[_KnowledgeSource]
    confidence: Literal["high", "low"]
    safety_notice: str | None = None


def _validated_result(payload: object, success_model: type[_StrictModel]) -> dict[str, Any]:
    """Accept only the documented success or business-failure Tool envelopes."""
    if not isinstance(payload, dict):
        raise RuntimeError("baby_info_server MCP 응답 형식이 올바르지 않습니다.")
    try:
        if payload.get("success") is False:
            return _ToolFailure.model_validate(payload).model_dump(mode="json")
        return success_model.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        raise RuntimeError("baby_info_server MCP 응답 형식이 올바르지 않습니다.") from exc


def validate_hospital_result(payload: object) -> dict[str, Any]:
    return _validated_result(payload, _HospitalSuccess)


def validate_knowledge_result(payload: object, category: str) -> dict[str, Any]:
    result = _validated_result(payload, _KnowledgeSuccess)
    if result.get("success") and result["category"] != category:
        raise RuntimeError("baby_info_server MCP 응답 카테고리가 일치하지 않습니다.")
    return result


@asynccontextmanager
async def baby_info_session():
    async with streamable_http_client(BABY_INFO_MCP_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


async def search_hospitals_from_mcp(hospital_type: str, region: str, page: int, limit: int) -> dict:
    tool_name = {"pediatric": "search_pediatric_hospitals", "emergency": "search_emergency_hospitals"}[hospital_type]
    try:
        async with baby_info_session() as session:
            tools = {tool.name for tool in (await session.list_tools()).tools}
            if tool_name not in tools:
                raise RuntimeError("baby_info_server에 병원 검색 Tool이 없습니다.")
            result = await session.call_tool(tool_name, {"region": region, "page": page, "limit": limit})
            text = "\n".join(item.text for item in result.content if hasattr(item, "text"))
            if result.isError or not text:
                raise RuntimeError("병원 검색 Tool 실행에 실패했습니다.")
            return validate_hospital_result(json.loads(text))
    except (RuntimeError, ValueError):
        raise
    except Exception as exc:
        raise RuntimeError("baby_info_server 연결에 실패했습니다.") from exc


async def search_knowledge_from_mcp(category: str, query: str, baby_age_months: int | None) -> dict:
    tool_name = f"search_{category}_guide"
    try:
        async with baby_info_session() as session:
            available = {tool.name for tool in (await session.list_tools()).tools}
            if tool_name not in available:
                raise RuntimeError("baby_info_server에 육아 정보 검색 Tool이 없습니다.")
            result = await session.call_tool(tool_name, {"query": query, "baby_age_months": baby_age_months, "top_k": 5})
            text = "\n".join(item.text for item in result.content if hasattr(item, "text"))
            if result.isError or not text:
                raise RuntimeError("육아 정보 검색 Tool 실행에 실패했습니다.")
            return validate_knowledge_result(json.loads(text), category)
    except (RuntimeError, ValueError):
        raise
    except Exception as exc:
        raise RuntimeError("baby_info_server 연결에 실패했습니다.") from exc
