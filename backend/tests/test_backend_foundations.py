from datetime import date

from app.core.api_response import success
from app.mcp_clients.baby_info_client import validate_hospital_result, validate_knowledge_result
from app.models.baby import Baby
from app.repositories.vaccination_repository import load_schedule
from app.services.care.growth_service import build_growth_information
from app.services.info.vaccination_service import get_vaccinations


def test_success_response_has_the_frontend_contract():
    response = success("ok", {"id": "sample"}, "request-1")
    assert response == {
        "success": True,
        "message": "ok",
        "data": {"id": "sample"},
        "request_id": "request-1",
    }


def test_local_vaccination_schedule_is_valid_and_used():
    schedule = load_schedule()
    baby = Baby(
        id="baby-1", user_id="user-1", baby_name="아기", birth_date=date.today(),
        gender="female", feeding_type="formula", allergies=[],
    )
    result = get_vaccinations(baby)
    assert schedule
    assert len(result["items"]) == len(schedule)
    assert result["baby_id"] == "baby-1"


def test_growth_information_never_turns_reference_into_a_diagnosis():
    baby = Baby(
        id="baby-1", user_id="user-1", baby_name="아기", birth_date=date.today(),
        gender="male", feeding_type="breast", allergies=[],
    )
    result = build_growth_information(baby, [{"event_type": "growth"}])
    assert result["records"] == [{"event_type": "growth"}]
    assert "진단" in result["reference_notice"]


def test_info_mcp_success_contracts_are_normalized_for_the_backend():
    hospital = validate_hospital_result({
        "success": True, "region": "서울특별시", "data": [{"hospital_name": "소아과", "address": "서울"}],
        "source": "public_data", "checked_at": "2026-09-08T12:00:00+09:00", "notice": "방문 전 확인해 주세요.",
    })
    knowledge = validate_knowledge_result({
        "success": True, "answer": "근거 기반 답변", "category": "feeding", "confidence": "high", "safety_notice": None,
        "sources": [{"document_id": "doc-1", "chunk_id": "chunk-1", "title": "자료", "organization": "기관",
                     "url": "https://example.org/source", "verified_at": "2026-09-03", "score": 0.9}],
    }, "feeding")
    assert hospital["data"][0]["phone"] is None
    assert knowledge["sources"][0]["url"] == "https://example.org/source"


def test_info_mcp_rejects_a_success_response_with_wrong_category():
    payload = {"success": True, "answer": "답변", "category": "sleep", "confidence": "low", "safety_notice": None, "sources": []}
    try:
        validate_knowledge_result(payload, "feeding")
    except RuntimeError as exc:
        assert "카테고리" in str(exc)
    else:
        raise AssertionError("wrong MCP category must be rejected")
