from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.core.api_response import success
from app.mcp_clients.baby_info_client import validate_hospital_result, validate_knowledge_result
from app.models.baby import Baby
from app.repositories.vaccination_repository import load_schedule
from app.services.care.growth_service import build_growth_information
from app.services.agent import agent_service
from app.routers.auth_router import is_corrupted_demo_name
from app.services.info.vaccination_service import get_vaccinations


def test_success_response_has_the_frontend_contract():
    response = success("ok", {"id": "sample"}, "request-1")
    assert response == {
        "success": True,
        "message": "ok",
        "data": {"id": "sample"},
        "request_id": "request-1",
    }


def test_only_damaged_demo_names_are_repaired():
    assert is_corrupted_demo_name("????????")
    assert is_corrupted_demo_name("����")
    assert not is_corrupted_demo_name("서아")
    assert not is_corrupted_demo_name("김 보호자")


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


@pytest.mark.asyncio
async def test_general_baby_questions_receive_safe_guidance(monkeypatch):
    monkeypatch.setattr(agent_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(agent_service, "AsyncOpenAI", lambda **_: type("Client", (), {})())

    # Network is intentionally unavailable in tests; the user-safe fallback must still answer.
    answer = await agent_service.generate_general_baby_guidance("아기 목욕은 언제 시키면 좋아?")
    assert "월령" in answer
    assert "의료기관" in answer


@pytest.mark.asyncio
async def test_sleep_crying_question_is_semantically_routed_to_the_sleep_guide(monkeypatch):
    classifier = AsyncMock(return_value=agent_service.IntentClassification(
        category="sleep", intent="guidance", is_medical_urgent=False
    ))
    monkeypatch.setattr(agent_service, "classify_intent", classifier)

    assert await agent_service.classify_category("아기가 자다가 우는데 뭐 때문이야?") == "sleep"
    classifier.assert_awaited_once()


@pytest.mark.asyncio
async def test_general_baby_category_is_not_rejected(monkeypatch):
    monkeypatch.setattr(agent_service, "classify_intent", AsyncMock(return_value=agent_service.IntentClassification(
        category="general_baby", intent="guidance", is_medical_urgent=False
    )))
    assert await agent_service.classify_category("아기 목욕은 언제 시키면 좋아?") == "general_baby"


@pytest.mark.parametrize(
    ("message", "region"),
    [
        ("서울 소아과 찾아줘", "서울특별시"),
        ("신대방동 소아과 알려줘", "신대방동"),
        ("서울 신대방동 소아과 찾아줘", "서울특별시 신대방동"),
        ("서울 동작구 소아과 찾아줘", "서울특별시 동작구"),
        ("동작구 신대방동 소아과 찾아줘", "동작구 신대방동"),
    ],
)
def test_chat_extracts_every_supported_hospital_region_form(message, region):
    assert agent_service._extract_hospital_region(message) == region


def test_generic_hospital_chat_request_defaults_to_pediatric_search():
    assert agent_service._hospital_type_for_request("광진구 병원 알려줘") == "pediatric"
