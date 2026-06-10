"""Common LangGraph machinery used by the per-track inner-loop graphs.

The graph runs a single agent invocation, evaluates the result, and decides
whether to retry, escalate to a fallback agent/tier, or surface a clean
StageOutcome up to the Temporal activity.

Why LangGraph?
  - Temporal activities are *durable* but coarse-grained. The inner loop
    (tool calls, confidence checks, fallback escalation) needs fast
    iteration without involving the Temporal cluster on every step.
  - LangGraph gives us the typed state machine + checkpointing for that
    inner loop, with optional persistence to the lab data home.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from lab.bridge.agent_dispatcher import (
    AgentDispatcher,
    StageRequest,
    StageResult,
)
from lab.orchestrator.state import StageInvocation, StageOutcome

log = logging.getLogger("lab.orchestrator.graphs")

try:
    from langgraph.graph import StateGraph, END

    _LANGGRAPH = True
except Exception:  # pragma: no cover — degrade gracefully
    _LANGGRAPH = False
    StateGraph = None  # type: ignore[assignment]
    END = "__end__"  # type: ignore[assignment]


@dataclass
class InnerLoopState:
    invocation: StageInvocation
    attempts: int = 0
    last_result: dict[str, Any] | None = None
    last_error: str | None = None
    confidence: float = 0.0
    use_fallback: bool = False
    started_at: float = field(default_factory=time.time)
    max_attempts: int = 3
    confidence_floor: float = 0.6


async def _invoke_once(
    dispatcher: AgentDispatcher, state: InnerLoopState
) -> StageResult:
    state.attempts += 1
    request = StageRequest(
        track=state.invocation.track,
        stage=state.invocation.stage,
        project_id=state.invocation.project_id,
        inputs=state.invocation.inputs,
        context=state.invocation.context,
        prefer_fallback=state.use_fallback,
    )
    return await dispatcher.dispatch(request)


async def run_inner_loop(
    dispatcher: AgentDispatcher,
    invocation: StageInvocation,
    *,
    max_attempts: int = 3,
    confidence_floor: float = 0.6,
) -> StageOutcome:
    """Execute the inner loop for a single stage.

    The loop tries the primary agent, escalates to the fallback on failure
    or low confidence, and gives up after `max_attempts`. Time spent is
    recorded as `latency_ms` on the resulting StageOutcome.
    """
    state = InnerLoopState(
        invocation=invocation,
        max_attempts=max_attempts,
        confidence_floor=confidence_floor,
    )
    result: StageResult | None = None
    while state.attempts < state.max_attempts:
        result = await _invoke_once(dispatcher, state)
        state.last_result = result.outputs
        state.last_error = result.error
        state.confidence = result.confidence or 0.0
        if result.error is None and state.confidence >= state.confidence_floor:
            break
        # escalate: alternate primary <-> fallback
        state.use_fallback = not state.use_fallback
        log.info(
            "inner loop retry stage=%s attempt=%d conf=%.2f fallback=%s err=%s",
            invocation.stage,
            state.attempts,
            state.confidence,
            state.use_fallback,
            result.error,
        )

    elapsed_ms = int((time.time() - state.started_at) * 1000)
    if result is None:
        return StageOutcome(
            project_id=invocation.project_id,
            track=invocation.track,
            stage=invocation.stage,
            outputs={},
            agent="<unbound>",
            skills_injected=[],
            error="dispatcher returned no result",
            latency_ms=elapsed_ms,
        )
    return StageOutcome(
        project_id=invocation.project_id,
        track=invocation.track,
        stage=invocation.stage,
        outputs=result.outputs,
        agent=result.agent,
        skills_injected=result.skills_injected,
        model_used=result.model_used,
        cost_usd=result.cost_usd or 0.0,
        latency_ms=elapsed_ms,
        confidence=state.confidence,
        error=result.error,
    )


def build_langgraph_state_machine(name: str):
    """Optional LangGraph builder for diagnostic graph visualization.

    Returns None when langgraph is not installed (fine for unit tests).
    """
    if not _LANGGRAPH:
        return None

    sg = StateGraph(dict)

    async def invoke(state: dict[str, Any]) -> dict[str, Any]:
        state["attempts"] = state.get("attempts", 0) + 1
        return state

    async def evaluate(state: dict[str, Any]) -> dict[str, Any]:
        if state.get("error"):
            state["next"] = "retry" if state["attempts"] < 3 else "end"
        elif state.get("confidence", 1.0) < state.get("confidence_floor", 0.6):
            state["next"] = "retry" if state["attempts"] < 3 else "end"
        else:
            state["next"] = "end"
        return state

    sg.add_node("invoke", invoke)
    sg.add_node("evaluate", evaluate)
    sg.set_entry_point("invoke")
    sg.add_edge("invoke", "evaluate")
    sg.add_conditional_edges(
        "evaluate",
        lambda s: s.get("next", "end"),
        {"retry": "invoke", "end": END},
    )
    return sg.compile()
