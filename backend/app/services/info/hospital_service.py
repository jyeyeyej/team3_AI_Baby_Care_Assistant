"""Hospital search service: selects and validates the appropriate MCP tool."""

from app.mcp_clients.baby_info_client import search_hospitals_from_mcp


async def search_hospitals(hospital_type: str, region: str, page: int, limit: int) -> dict:
    result = await search_hospitals_from_mcp(hospital_type, region, page, limit)
    if not result.get("success"):
        raise ValueError(result.get("message", "병원 검색에 실패했습니다."))
    data = result.get("data")
    if not isinstance(data, list):
        raise RuntimeError("병원 검색 MCP 응답 형식이 올바르지 않습니다.")
    # The MCP normalizer has already removed incomplete mandatory fields.  Keep
    # optional values as null and never coerce them to empty strings.
    return {"region": result.get("region", region), "type": hospital_type, "data": data, "source": result.get("source", "public_data"), "checked_at": result.get("checked_at"), "notice": result.get("notice")}
