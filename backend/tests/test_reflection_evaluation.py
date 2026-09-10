"""Controlled before/after evaluation for the implemented reflection policies."""

import json
from dataclasses import dataclass

import pytest

from app.services.agent.agent_loop import AgentExecution, AgentLoop, AgentPlan, AgentState, RetryableAgentError
from app.services.agent.agent_service import _execute_safe_fallback, _reflect_chat_result
from app.services.agent.memory_trace_service import write_chat_trace


@dataclass(frozen=True)
class EvaluationCase:
    name: str
    plan: AgentPlan
    behavior: str = "success"


CASES = [
    EvaluationCase("feeding_record", AgentPlan("care", ("record_care_event",))),
    EvaluationCase("diaper_record", AgentPlan("care", ("record_care_event",))),
    EvaluationCase("sleep_record", AgentPlan("care", ("record_care_event",))),
    EvaluationCase("today_feeding", AgentPlan("care", ("get_care_records",))),
    EvaluationCase("today_sleep", AgentPlan("care", ("get_care_records",))),
    EvaluationCase("care_pattern", AgentPlan("care", ("get_care_records",))),
    EvaluationCase("missing_amount", AgentPlan("care"), "clarification"),
    EvaluationCase("hospital_pediatric", AgentPlan("hospital", ("search_pediatric_hospitals",), can_retry=True)),
    EvaluationCase("hospital_emergency", AgentPlan("hospital", ("search_emergency_hospitals",), can_retry=True)),
    EvaluationCase("hospital_missing_region", AgentPlan("hospital_clarification"), "clarification"),
    EvaluationCase("rag_feeding", AgentPlan("rag", ("search_feeding_guide",))),
    EvaluationCase("rag_sleep", AgentPlan("rag", ("search_sleep_guide",))),
    EvaluationCase("rag_weaning", AgentPlan("rag", ("search_weaning_guide",))),
    EvaluationCase("rag_development", AgentPlan("rag", ("search_development_guide",))),
    EvaluationCase("rag_safety", AgentPlan("rag", ("search_safety_guide",))),
    EvaluationCase("general_guidance", AgentPlan("general_guidance")),
    EvaluationCase("out_of_scope", AgentPlan("out_of_scope")),
    EvaluationCase("hospital_transient_retry", AgentPlan("hospital", ("search_pediatric_hospitals",), can_retry=True), "retry_once"),
    EvaluationCase("hospital_retry_exhausted", AgentPlan("hospital", ("search_pediatric_hospitals",), can_retry=True), "retry_exhausted"),
    EvaluationCase("rag_no_evidence", AgentPlan("rag", ("search_feeding_guide",)), "no_evidence"),
]


class FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int):
        self.values[key] = value


async def _executor_for(case: EvaluationCase, attempts: list[int]) -> AgentExecution:
    attempts[0] += 1
    if case.behavior == "retry_once" and attempts[0] == 1:
        raise RetryableAgentError("hospital_tool_unavailable", "temporary hospital failure")
    if case.behavior == "retry_exhausted":
        raise RetryableAgentError("hospital_tool_unavailable", "temporary hospital failure")
    if case.behavior == "clarification":
        return AgentExecution({"response_type": "clarification_required", "answer": "필수값을 알려주세요.", "sources": []})
    if case.behavior == "no_evidence":
        return AgentExecution({"response_type": "text", "answer": "근거 없는 답변", "sources": [], "confidence": "high"})
    return AgentExecution({"response_type": "text", "answer": "정상 응답", "sources": []})


async def _evaluate(reflection_enabled: bool) -> dict:
    completed = consistent = selected_correct = retries = 0
    for case in CASES:
        expected_tools = case.plan.selected_tools
        attempts = [0]
        state = AgentState(request_id=case.name)

        if reflection_enabled:
            execution = await AgentLoop().run(
                state,
                planner=lambda plan=case.plan: _return_plan(plan),
                executor=lambda _plan, item=case, counter=attempts: _executor_for(item, counter),
                verifier=_reflect_chat_result,
                fallback=_execute_safe_fallback,
            )
            completed += 1
            consistent += state.result_validation in {
                "passed", "passed_after_retry", "missing_input", "downgraded_missing_sources",
                "no_evidence_safe_fallback", "hospital_tool_unavailable_safe_fallback",
            }
            retries += state.retry_count
            selected_correct += state.plan.selected_tools == expected_tools
            continue

        # Baseline: execute only once; no verifier, retry, or safe fallback.
        selected_correct += case.plan.selected_tools == expected_tools
        try:
            execution = await _executor_for(case, attempts)
        except RetryableAgentError:
            continue
        if execution.response.get("confidence") == "high" and not execution.response.get("sources"):
            continue
        completed += 1
        consistent += 1

    total = len(CASES)
    return {
        "total": total,
        "task_completion": completed / total,
        "tool_selection_accuracy": selected_correct / total,
        "response_consistency": consistent / total,
        "average_retry_count": retries / total,
    }


async def _return_plan(plan: AgentPlan) -> AgentPlan:
    return plan


@pytest.mark.asyncio
async def test_reflection_before_after_metrics_for_twenty_controlled_cases():
    baseline = await _evaluate(reflection_enabled=False)
    reflected = await _evaluate(reflection_enabled=True)

    assert baseline == {
        "total": 20, "task_completion": 0.85, "tool_selection_accuracy": 1.0,
        "response_consistency": 0.85, "average_retry_count": 0.0,
    }
    assert reflected == {
        "total": 20, "task_completion": 1.0, "tool_selection_accuracy": 1.0,
        "response_consistency": 1.0, "average_retry_count": 0.1,
    }


@pytest.mark.asyncio
async def test_retry_exhaustion_writes_redacted_trace_evidence():
    case = next(item for item in CASES if item.name == "hospital_retry_exhausted")
    state = AgentState(request_id="reflection-trace-1")
    attempts = [0]
    execution = await AgentLoop().run(
        state,
        planner=lambda: _return_plan(case.plan),
        executor=lambda plan: _executor_for(case, attempts),
        verifier=_reflect_chat_result,
        fallback=_execute_safe_fallback,
    )
    redis = FakeRedis()
    await write_chat_trace(
        redis, user_id="user-eval", session_id="session-eval", baby_id="baby-eval", request_id=state.request_id,
        tool_used=True, memory_count=0, memory_created=0, selected_tools=list(case.plan.selected_tools),
        result_validation=state.result_validation, reflection_action=state.reflection_action,
        error_type=state.error_type, retry_count=state.retry_count, execution_stages=state.stages,
    )

    trace = json.loads(redis.values["trace:user-eval:session-eval:reflection-trace-1"])
    assert execution.response["response_type"] == "error"
    assert attempts == [2]
    assert trace["error_type"] == "hospital_tool_unavailable"
    assert trace["retry_count"] == 1
    assert trace["reflection_action"] == "retry_once_then_safe_fallback"
    assert "retrying_tool" in trace["execution_stages"]
    assert "safe_fallback" in trace["execution_stages"]
