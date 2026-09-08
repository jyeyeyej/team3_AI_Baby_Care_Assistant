import asyncio
import sys

# psycopg의 비동기 PostgreSQL 연결은 Windows 기본 Proactor 이벤트 루프와
# 호환되지 않는다. MCP 서버가 이벤트 루프를 만들기 전에 Selector 정책을 설정한다.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from mcp.server.fastmcp import FastMCP

from config import get_settings
from tools.search_development_guide import run as development_run
from tools.search_emergency_hospitals import run as emergency_run
from tools.search_feeding_guide import run as feeding_run
from tools.search_pediatric_hospitals import run as pediatric_run
from tools.search_safety_guide import run as safety_run
from tools.search_sleep_guide import run as sleep_run
from tools.search_weaning_guide import run as weaning_run

settings = get_settings()
mcp = FastMCP(
    "baby_info_server",
    host=settings.mcp_host,
    port=settings.mcp_port,
    streamable_http_path=settings.mcp_streamable_http_path,
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
async def search_pediatric_hospitals(region: str, page: int = 1, limit: int = 10) -> dict:
    """지역명으로 소아과를 검색합니다."""
    return await pediatric_run(region, page, limit)


@mcp.tool()
async def search_emergency_hospitals(region: str, page: int = 1, limit: int = 10) -> dict:
    """지역명으로 응급실을 검색합니다."""
    return await emergency_run(region, page, limit)


@mcp.tool()
async def search_feeding_guide(query: str, baby_age_months: int | None = None, top_k: int = 5) -> dict:
    """수유 관련 공식 육아 지식을 검색합니다."""
    return await feeding_run(query, baby_age_months, top_k)


@mcp.tool()
async def search_sleep_guide(query: str, baby_age_months: int | None = None, top_k: int = 5) -> dict:
    """수면 관련 공식 육아 지식을 검색합니다."""
    return await sleep_run(query, baby_age_months, top_k)


@mcp.tool()
async def search_weaning_guide(query: str, baby_age_months: int | None = None, top_k: int = 5) -> dict:
    """이유식 관련 공식 육아 지식을 검색합니다."""
    return await weaning_run(query, baby_age_months, top_k)


@mcp.tool()
async def search_development_guide(query: str, baby_age_months: int | None = None, top_k: int = 5) -> dict:
    """발달 관련 공식 육아 지식을 검색합니다."""
    return await development_run(query, baby_age_months, top_k)


@mcp.tool()
async def search_safety_guide(query: str, baby_age_months: int | None = None, top_k: int = 5) -> dict:
    """영유아 안전 관련 공식 육아 지식을 검색합니다."""
    return await safety_run(query, baby_age_months, top_k)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
