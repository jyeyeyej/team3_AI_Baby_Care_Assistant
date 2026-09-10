"""Policy-driven Agent Loop used by the chat service.

The loop deliberately separates planning, Tool execution and result validation.
It does not expose a model-controlled arbitrary Tool surface: the Backend planner
selects only allowlisted MCP Tools after authentication and input checks.
"""

from dataclasses import dataclass, field
from typing import Awaitable, Callable


@dataclass(frozen=True)
class AgentPlan:
    """A validated next action and the safe Tool facts to trace."""

    route: str
    selected_tools: tuple[str, ...] = ()
    tool_arguments: tuple[dict, ...] = ()
    can_retry: bool = False


@dataclass
class AgentState:
    """Per-request state kept in process; durable facts are written as a redacted Trace."""

    request_id: str
    stages: list[str] = field(default_factory=lambda: ["received"])
    plan: AgentPlan | None = None
    result_validation: str = "not_applicable"
    reflection_action: str = "none"
    error_type: str | None = None
    retry_count: int = 0
    max_retries: int = 1


@dataclass(frozen=True)
class AgentExecution:
    """The user-safe response returned by an action executor."""

    response: dict


Planner = Callable[[], Awaitable[AgentPlan]]
Executor = Callable[[AgentPlan], Awaitable[AgentExecution]]
Verifier = Callable[[dict], tuple[str, str]]
Fallback = Callable[[AgentPlan, "RetryableAgentError"], Awaitable[AgentExecution]]


class RetryableAgentError(RuntimeError):
    """A read-only Tool failure that may be retried once by Backend policy."""

    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(message)
        self.error_type = error_type


class AgentLoop:
    """Run one controlled request through plan → execute → verify."""

    async def run(
        self,
        state: AgentState,
        *,
        planner: Planner,
        executor: Executor,
        verifier: Verifier,
        fallback: Fallback | None = None,
    ) -> AgentExecution:
        state.stages.append("planning")
        plan = await planner()
        state.plan = plan
        state.stages.append("tool_policy_checked" if plan.selected_tools else "answer_planned")

        while True:
            try:
                execution = await executor(plan)
                break
            except RetryableAgentError as error:
                state.error_type = error.error_type
                if plan.can_retry and state.retry_count < state.max_retries:
                    state.retry_count += 1
                    state.reflection_action = "retry_once"
                    state.stages.append("retrying_tool")
                    continue
                if fallback is None:
                    raise
                execution = await fallback(plan, error)
                state.result_validation = f"{error.error_type}_safe_fallback"
                state.reflection_action = "retry_once_then_safe_fallback" if state.retry_count else "safe_fallback"
                state.stages.append("safe_fallback")
                return execution
        state.stages.append("tool_executed" if plan.selected_tools else "answer_generated")
        state.result_validation, state.reflection_action = verifier(execution.response)
        if state.retry_count:
            state.result_validation = "passed_after_retry" if state.result_validation == "passed" else state.result_validation
            if state.reflection_action == "none":
                state.reflection_action = "retry_once"
        state.stages.append("result_verified")
        return execution
