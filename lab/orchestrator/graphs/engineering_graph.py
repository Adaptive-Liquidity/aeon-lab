"""Engineering-track LangGraph state machine."""

from __future__ import annotations

from lab.bridge.agent_dispatcher import AgentDispatcher
from lab.orchestrator.graphs.base import run_inner_loop
from lab.orchestrator.state import StageInvocation, StageOutcome


async def run_engineering_phase_graph(
    dispatcher: AgentDispatcher,
    invocation: StageInvocation,
) -> StageOutcome:
    """Drive the inner loop with engineering-tuned bounds.

    Engineering phases tolerate fewer retries before escalating because
    each attempt may produce real diffs / commits.
    """
    return await run_inner_loop(
        dispatcher=dispatcher,
        invocation=invocation,
        max_attempts=2,
        confidence_floor=0.65,
    )
