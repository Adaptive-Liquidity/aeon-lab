"""Research-track LangGraph state machine."""

from __future__ import annotations

from lab.bridge.agent_dispatcher import AgentDispatcher
from lab.orchestrator.graphs.base import run_inner_loop
from lab.orchestrator.state import StageInvocation, StageOutcome


async def run_research_stage_graph(
    dispatcher: AgentDispatcher,
    invocation: StageInvocation,
) -> StageOutcome:
    """Drive the inner loop with research-tuned bounds."""
    return await run_inner_loop(
        dispatcher=dispatcher,
        invocation=invocation,
        max_attempts=3,
        confidence_floor=0.55,
    )
