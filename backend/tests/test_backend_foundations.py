from datetime import date, datetime, timezone
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


@pytest.mark.parametrize(
    "message",
    ["땅콩 알레르기가 있으면 뭘 조심해야 해?", "먹고 토했어", "두드러기가 났어"],
)
def test_allergy_questions_use_the_ai_guidance_route(message):
    assert agent_service._is_allergy_ai_request(message) is True


def test_non_allergy_question_does_not_use_the_allergy_ai_guidance_route():
    assert agent_service._is_allergy_ai_request("낮잠은 몇 시간 재우면 돼?") is False


def test_chat_formats_utc_record_times_in_korea_time():
    assert agent_service._format_recorded_at_kst("2026-09-09T01:38:39Z") == "2026년 9월 9일 10시 38분"


@pytest.mark.parametrize("message", ["110ml", "130ml", "165ml", "분유 50ml 먹었어", "모유 60ml 먹었어", "분유 123ml 먹였어"])
def test_chat_accepts_any_supported_feeding_amount(message):
    record = agent_service._feeding_record(message)
    assert record is not None
    assert 1 <= record["amount_ml"] <= 500


@pytest.mark.parametrize("message", ["0ml", "501ml", "-100ml", "-100ml 수유했어"])
def test_chat_requests_clarification_for_out_of_range_feeding_amounts(message):
    assert agent_service._feeding_record(message) == {"missing": True}


def test_chat_does_not_treat_an_amount_question_as_a_feeding_record():
    assert agent_service._feeding_record("165ml 먹어도 돼?") is None


def test_reflection_marks_missing_input_as_a_clarification_without_a_tool_retry():
    result_validation, action = agent_service._reflect_chat_result({
        "response_type": "clarification_required", "answer": "수유량을 알려주세요.", "sources": [],
    })
    assert (result_validation, action) == ("missing_input", "clarification")


def test_reflection_marks_rag_no_evidence_as_a_safe_fallback():
    chat = {
        "response_type": "text", "answer": "일반 안내를 제공해요.", "sources": [], "confidence": "low",
        "_reflection_hint": "no_evidence_safe_fallback",
    }
    result_validation, action = agent_service._reflect_chat_result(chat)
    assert (result_validation, action) == ("no_evidence_safe_fallback", "safe_fallback")
    assert "_reflection_hint" not in chat


def test_chat_preserves_explicit_relative_record_time():
    now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    assert agent_service._relative_recorded_at("30분전에 100ml 수유했어", now=now) == "2026-09-09T11:30:00+00:00"
    assert agent_service._relative_recorded_at("1시간 5분 전에 100ml 수유했어", now=now) == "2026-09-09T10:55:00+00:00"


def test_chat_identifies_breastmilk_and_formula_as_mixed_feeding():
    record = agent_service._feeding_record("분유와 모유를 섞어서 120ml 줬어")
    assert record == {"amount_ml": 120, "feeding_type": "mixed"}


def test_chat_sums_explicit_additional_feeding_amounts():
    record = agent_service._feeding_record("30ml를 수유하고 부족한 것 같아서 50ml를 추가로 더 수유했어")
    assert record == {"amount_ml": 80, "feeding_type": None}


@pytest.mark.asyncio
async def test_chat_answers_today_feeding_count_before_attempting_to_record(monkeypatch):
    get_records = AsyncMock(return_value={
        "success": True,
        "data": {"records": [{"event_type": "feeding"}, {"event_type": "feeding"}, {"event_type": "sleep"}]},
    })
    monkeypatch.setattr(agent_service, "get_care_records", get_records)

    response = await agent_service._handle_care_request(
        type("Request", (), {"message": "오늘 하루 수유 몇번했는지 알려줘", "baby_id": "baby-1"})(),
        Baby(id="baby-1", user_id="user-1", baby_name="아기", birth_date=date.today(), gender="female", feeding_type="formula", allergies=[]),
    )

    assert response["answer"] == "오늘 수유는 총 2회 기록됐어요."
    get_records.assert_awaited_once_with({"baby_id": "baby-1", "query_type": "today"})


@pytest.mark.asyncio
async def test_chat_answers_today_total_sleep_before_attempting_to_record(monkeypatch):
    get_records = AsyncMock(return_value={
        "success": True,
        "data": {"records": [
            {"event_type": "sleep", "details": {"duration_minutes": 90}},
            {"event_type": "sleep", "details": {"duration_minutes": 45}},
            {"event_type": "feeding", "details": {}},
        ]},
    })
    monkeypatch.setattr(agent_service, "get_care_records", get_records)

    response = await agent_service._handle_care_request(
        type("Request", (), {"message": "오늘 수면을 총 몇시간 했는지 알려줘", "baby_id": "baby-1"})(),
        Baby(id="baby-1", user_id="user-1", baby_name="아기", birth_date=date.today(), gender="female", feeding_type="formula", allergies=[]),
    )

    assert response["answer"] == "오늘 수면은 총 2시간 15분 기록됐어요."
    get_records.assert_awaited_once_with({"baby_id": "baby-1", "query_type": "today"})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    ["오늘 똥 몇번 쌌는지 알려줘", "오늘 소변과 똥 배변 상태 어때?"],
)
async def test_chat_answers_today_diaper_summary_before_attempting_to_record(monkeypatch, message):
    get_records = AsyncMock(return_value={
        "success": True,
        "data": {"records": [
            {"event_type": "diaper", "details": {"urine": True, "stool": True}},
            {"event_type": "diaper", "details": {"urine": True, "stool": False}},
        ]},
    })
    monkeypatch.setattr(agent_service, "get_care_records", get_records)

    response = await agent_service._handle_care_request(
        type("Request", (), {"message": message, "baby_id": "baby-1"})(),
        Baby(id="baby-1", user_id="user-1", baby_name="아기", birth_date=date.today(), gender="female", feeding_type="formula", allergies=[]),
    )

    assert response["answer"] == "오늘 소변은 2회, 대변은 1회 기록됐어요."
    get_records.assert_awaited_once_with({"baby_id": "baby-1", "query_type": "today"})


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
