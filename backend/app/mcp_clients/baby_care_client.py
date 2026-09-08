"""baby_care_server MCP 호출을 담당합니다."""

import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.core.config import BABY_CARE_MCP_URL


logger = logging.getLogger(__name__)


ALLOWED_TOOLS = frozenset({
    "record_care_event",
    "get_care_records",
    "analyze_infant_stool",
})


@asynccontextmanager
async def baby_care_session():
    """baby_care_server와 Streamable HTTP 세션을 연결합니다."""
    async with streamable_http_client(BABY_CARE_MCP_URL) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


async def call_baby_care_tool(
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """허용된 Care MCP Tool을 호출하고 JSON 결과를 반환합니다."""
    if tool_name not in ALLOWED_TOOLS:
        raise ValueError("허용되지 않은 Care MCP Tool입니다.")

    try:
        async with baby_care_session() as session:
            server_tools = {
                tool.name
                for tool in (await session.list_tools()).tools
            }

            if tool_name not in server_tools:
                raise RuntimeError("baby_care_server에 요청한 Tool이 없습니다.")

            result = await session.call_tool(
                tool_name,
                arguments=arguments,
            )

            text = "\n".join(
                content.text
                for content in result.content
                if hasattr(content, "text")
            )

            if result.isError:
                raise RuntimeError(text or "Care MCP Tool 실행에 실패했습니다.")

            if not text:
                raise RuntimeError("Care MCP Tool이 빈 응답을 반환했습니다.")

            try:
                return json.loads(text)
            except json.JSONDecodeError as error:
                raise RuntimeError(
                    "Care MCP Tool 응답이 JSON 형식이 아닙니다."
                ) from error
    except ValueError:
        raise
    except RuntimeError:
        raise
    except Exception as error:
        logger.exception(
            "Care MCP 세션 연결에 실패했습니다. url=%s tool=%s",
            BABY_CARE_MCP_URL,
            tool_name,
        )
        raise RuntimeError("baby_care_server 연결에 실패했습니다.") from error


async def record_care_event(
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """육아 기록 저장 Tool을 호출합니다."""
    return await call_baby_care_tool(
        "record_care_event",
        arguments,
    )


async def get_care_records(
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """육아 기록·패턴 조회 Tool을 호출합니다."""
    return await call_baby_care_tool(
        "get_care_records",
        arguments,
    )


async def analyze_infant_stool(arguments: dict[str, Any]) -> dict[str, Any]:
    """기저귀 사진 고정 Workflow를 호출합니다."""
    return await call_baby_care_tool("analyze_infant_stool", arguments)
