"""Natural-language evaluation of the implemented Agent route → execute → verify path.

External MCP and model calls are replaced only at their boundary.  The real
planner, deterministic input parsing, AgentLoop, executor and verifier run for
each Korean user message, so Tool selection is not supplied as an AgentPlan.
"""

from dataclasses import dataclass
from datetime import date

import pytest

from app.models.baby import Baby
from app.services.agent import agent_service
from app.services.agent.agent_loop import AgentLoop, AgentState


@dataclass(frozen=True)
class NaturalLanguageCase:
    message: str
    expected_route: str
    expected_tools: tuple[str, ...]
    expected_response_type: str
    category: str | None = None


CASES = [
    NaturalLanguageCase("분유 120ml 먹었어", "care", ("record_care_event",), "record_confirmation"),
    NaturalLanguageCase("모유 80ml 수유했어", "care", ("record_care_event",), "record_confirmation"),
    NaturalLanguageCase("소변과 대변 봤어", "care", ("record_care_event",), "record_confirmation"),
    NaturalLanguageCase("낮잠 1시간 30분 잤어", "care", ("record_care_event",), "record_confirmation"),
    NaturalLanguageCase("오늘 수유 몇번했어", "care", ("get_care_records",), "text"),
    NaturalLanguageCase("오늘 수면 총 몇시간 했어", "care", ("get_care_records",), "text"),
    NaturalLanguageCase("지난 7일 수유 패턴 알려줘", "care", ("get_care_records",), "text"),
    NaturalLanguageCase("분유 먹었어", "care", (), "clarification_required"),
    NaturalLanguageCase("낮잠 잤어", "care", (), "clarification_required"),
    NaturalLanguageCase("서울 동작구 소아과 찾아줘", "hospital", ("search_pediatric_hospitals",), "hospital_list"),
    NaturalLanguageCase("부산 응급실 알려줘", "hospital", ("search_emergency_hospitals",), "hospital_list"),
    NaturalLanguageCase("근처 소아과 알려줘", "hospital_clarification", (), "clarification_required"),
    NaturalLanguageCase("생후 4개월 아기 수유 간격 알려줘", "rag", ("search_feeding_guide",), "text", "feeding"),
    NaturalLanguageCase("아기가 자다가 울면서 깨는데 어떻게 해야 해?", "rag", ("search_sleep_guide",), "text", "sleep"),
    NaturalLanguageCase("이유식은 언제 시작해?", "rag", ("search_weaning_guide",), "text", "weaning"),
    NaturalLanguageCase("뒤집기는 보통 언제 해?", "rag", ("search_development_guide",), "text", "development"),
    NaturalLanguageCase("아기 침대 안전수칙 알려줘", "rag", ("search_safety_guide",), "text", "safety"),
    NaturalLanguageCase("아기 목욕은 어떻게 시키면 좋아?", "general_guidance", (), "text", "general_baby"),
    NaturalLanguageCase("오늘 서울 날씨 알려줘", "out_of_scope", (), "out_of_scope", "out_of_scope"),
    NaturalLanguageCase("땅콩 알레르기가 있으면 무엇을 조심해야 해?", "allergy_guidance", (), "text"),
]


def _request(message: str):
    return type("Request", (), {"message": message, "baby_id": "baby-eval", "session_id": "session-eval"})()


@pytest.mark.asyncio
async def test_twenty_natural_language_requests_run_through_real_agent_route_execute_verify(monkeypatch):
    """Evaluate natural input; expected Tool plans are asserted after real planning."""
    categories = {case.message: case.category for case in CASES if case.category is not None}

    async def classify_category(message: str) -> str | None:
        category = categories.get(message)
        # Keep the production classifier contract: out_of_scope becomes None.
        return None if category == "out_of_scope" else category

    async def record_care_event(_payload: dict) -> dict:
        return {"success": True, "message": "기록을 저장했습니다."}

    async def get_care_records(payload: dict) -> dict:
        if payload["query_type"] == "pattern":
            return {"success": True, "data": {"pattern": {"sufficient_data": True, "feeding": {"count": 12, "average_amount_ml": 110, "average_interval_minutes": 180}}}}
        return {"success": True, "data": {"records": [
            {"event_type": "feeding", "details": {}},
            {"event_type": "sleep", "details": {"duration_minutes": 90}},
        ]}}

    async def search_hospitals(hospital_type: str, region: str, page: int, limit: int) -> dict:
        return {"region": region, "type": hospital_type, "data": [{"hospital_name": "테스트 소아과", "address": region, "phone": "02-0000-0000"}]}

    async def search_knowledge(category: str, query: str, baby_age_months: int) -> dict:
        return {"success": True, "answer": f"{category} 근거 기반 안내", "sources": [{"title": "테스트 근거"}], "confidence": "high", "safety_notice": None}

    async def general_guidance(_message: str, *_args) -> str:
        return "안전한 일반 육아 안내입니다."

    async def allergy_guidance(_message: str, *_args) -> str:
        return "알레르기 일반 안내입니다."

    monkeypatch.setattr(agent_service, "classify_category", classify_category)
    monkeypatch.setattr(agent_service, "record_care_event", record_care_event)
    monkeypatch.setattr(agent_service, "get_care_records", get_care_records)
    monkeypatch.setattr(agent_service, "search_hospitals", search_hospitals)
    monkeypatch.setattr(agent_service, "search_knowledge_from_mcp", search_knowledge)
    monkeypatch.setattr(agent_service, "generate_general_baby_guidance", general_guidance)
    monkeypatch.setattr(agent_service, "generate_allergy_guidance", allergy_guidance)

    baby = Baby(id="baby-eval", user_id="user-eval", baby_name="테스트 아기", birth_date=date(2026, 5, 1), gender="female", feeding_type="formula", allergies=[])
    for index, case in enumerate(CASES, start=1):
        request = _request(case.message)
        state = AgentState(request_id=f"natural-language-{index}")
        execution = await AgentLoop().run(
            state,
            planner=lambda item=request: agent_service._plan_chat_action(item),
            executor=lambda plan, item=request: agent_service._execute_chat_plan(plan, item, baby, [], []),
            verifier=agent_service._reflect_chat_result,
            fallback=agent_service._execute_safe_fallback,
        )

        assert state.plan is not None, case.message
        assert state.plan.route == case.expected_route, case.message
        assert state.plan.selected_tools == case.expected_tools, case.message
        assert execution.response["response_type"] == case.expected_response_type, case.message
        assert state.result_validation in {"passed", "missing_input"}, case.message
