"""Factories are avoided here so FastMCP exposes clear, stable tool names."""

from ..schemas.knowledge import KnowledgeSearchInput
from ..services.rag_service import search_knowledge


async def search_category(category: str, query: str, baby_age_months: int | None = None, top_k: int = 5) -> dict:
    request = KnowledgeSearchInput(query=query.strip(), baby_age_months=baby_age_months, top_k=top_k)
    try:
        return await search_knowledge(category, request.query, request.baby_age_months, request.top_k)
    except RuntimeError as exc:
        return {"success": False, "message": "육아 정보 검색 서비스를 사용할 수 없습니다.", "error_code": "RAG_SERVICE_UNAVAILABLE"}
