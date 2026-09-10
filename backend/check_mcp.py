"""백엔드 PC에서 두 MCP 서버의 실제 연결과 도구 목록을 확인합니다."""

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.core.config import BABY_CARE_MCP_URL, BABY_INFO_MCP_URL


async def check_server(name: str, url: str) -> bool:
    """MCP 세션을 초기화하고 제공되는 Tool 이름을 출력합니다."""
    try:
        async with streamable_http_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
        print(f"[성공] {name}: {url}")
        print("  Tools: " + ", ".join(tool.name for tool in tools.tools))
        return True
    except Exception as error:
        print(f"[실패] {name}: {url}")
        print(f"  원인: {error}")
        return False


async def main() -> None:
    care_ok, info_ok = await asyncio.gather(
        check_server("Baby Care MCP", BABY_CARE_MCP_URL),
        check_server("Baby Info MCP", BABY_INFO_MCP_URL),
    )
    if not (care_ok and info_ok):
        raise SystemExit(1)


async def check_hospital_search() -> None:
    """MCP 2의 외부 공공데이터 호출까지 실제로 점검합니다."""
    try:
        async with streamable_http_client(BABY_INFO_MCP_URL) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(
                    "search_pediatric_hospitals",
                    {"region": "신대방동", "page": 1, "limit": 3},
                )
        text = "\n".join(item.text for item in result.content if hasattr(item, "text"))
        print("[병원 검색 결과]")
        print(json.dumps(json.loads(text), ensure_ascii=False, indent=2))
        if result.isError:
            raise SystemExit(1)
    except Exception as error:
        print(f"[실패] 병원 검색 실제 호출: {error}")
        raise SystemExit(1) from error


async def check_safety_guide() -> None:
    """MCP 2의 RAG 의존성(임베딩·지식 DB·답변 생성)까지 점검합니다."""
    try:
        async with streamable_http_client(BABY_INFO_MCP_URL) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(
                    "search_safety_guide",
                    {"query": "생후 1개월 아기 안전수칙", "baby_age_months": 1, "top_k": 3},
                )
        text = "\n".join(item.text for item in result.content if hasattr(item, "text"))
        print("[안전수칙 RAG 결과]")
        print(text)
        if result.isError:
            raise SystemExit(1)
    except Exception as error:
        print(f"[실패] 안전수칙 RAG 실제 호출: {error}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if "--hospital" in sys.argv:
        coroutine = check_hospital_search()
    elif "--rag" in sys.argv:
        coroutine = check_safety_guide()
    else:
        coroutine = main()
    asyncio.run(coroutine)
