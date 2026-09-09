import pytest

from app.services.agent.agent_loop import AgentExecution, AgentLoop, AgentPlan, AgentState, RetryableAgentError


@pytest.mark.asyncio
async def test_agent_loop_plans_executes_and_verifies_an_allowlisted_tool():
    state = AgentState(request_id="request-1")

    async def planner():
        return AgentPlan(
            route="hospital",
            selected_tools=("search_pediatric_hospitals",),
            tool_arguments=({"region": "서울특별시 동작구"},),
        )

    async def executor(plan):
        assert plan.selected_tools == ("search_pediatric_hospitals",)
        return AgentExecution({"answer": "검색 결과", "sources": []})

    execution = await AgentLoop().run(
        state,
        planner=planner,
        executor=executor,
        verifier=lambda response: ("passed", "none"),
    )

    assert execution.response["answer"] == "검색 결과"
    assert state.plan is not None
    assert state.result_validation == "passed"
    assert state.stages == ["received", "planning", "tool_policy_checked", "tool_executed", "result_verified"]


@pytest.mark.asyncio
async def test_agent_loop_retries_only_a_read_only_retryable_plan_once():
    state = AgentState(request_id="request-2")
    attempts = 0

    async def planner():
        return AgentPlan(route="hospital", selected_tools=("search_pediatric_hospitals",), can_retry=True)

    async def executor(_plan):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RetryableAgentError("hospital_tool_unavailable", "temporary failure")
        return AgentExecution({"answer": "검색 결과", "sources": []})

    execution = await AgentLoop().run(
        state, planner=planner, executor=executor, verifier=lambda response: ("passed", "none"),
    )

    assert execution.response["answer"] == "검색 결과"
    assert attempts == 2
    assert state.retry_count == 1
    assert state.result_validation == "passed_after_retry"
    assert state.reflection_action == "retry_once"


@pytest.mark.asyncio
async def test_agent_loop_returns_safe_fallback_after_one_retry_is_exhausted():
    state = AgentState(request_id="request-3")
    attempts = 0

    async def planner():
        return AgentPlan(route="hospital", selected_tools=("search_pediatric_hospitals",), can_retry=True)

    async def executor(_plan):
        nonlocal attempts
        attempts += 1
        raise RetryableAgentError("hospital_tool_unavailable", "temporary failure")

    async def fallback(_plan, _error):
        return AgentExecution({"answer": "잠시 후 다시 시도해 주세요.", "sources": []})

    execution = await AgentLoop().run(
        state, planner=planner, executor=executor, verifier=lambda response: ("passed", "none"), fallback=fallback,
    )

    assert execution.response["answer"] == "잠시 후 다시 시도해 주세요."
    assert attempts == 2
    assert state.retry_count == 1
    assert state.result_validation == "hospital_tool_unavailable_safe_fallback"
    assert state.reflection_action == "retry_once_then_safe_fallback"
