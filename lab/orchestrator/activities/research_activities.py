"""Temporal activities for the 26-stage research workflow.

Each stage is a separate activity so retry/timeout policy is per-stage and
Temporal's visibility API surfaces fine-grained progress to the dashboard.

The activities are defined with `@activity.defn` when temporalio is
available; otherwise they downgrade to plain async functions so unit tests
can run without a Temporal worker.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

try:
    from temporalio import activity

    _activity = activity.defn
    _activity_heartbeat = activity.heartbeat
except Exception:  # pragma: no cover — used in tests when temporalio absent

    def _activity(fn=None, **_kw):
        return fn if fn is not None else (lambda f: f)

    def _activity_heartbeat(*_a, **_kw):
        return None


from lab.bridge.agent_dispatcher import (
    AgentDispatcher,
    StageRequest,
    default_invoker_unavailable,
)
from lab.bridge.hooks_bridge import emit_stage_event
from lab.orchestrator.graphs.research_graph import run_research_stage_graph
from lab.orchestrator.state import (
    QualityGateVerdict,
    StageInvocation,
    StageOutcome,
)

log = logging.getLogger("lab.orchestrator.activities.research")

# Module-level dispatcher; the worker entrypoint replaces this with a
# real invoker bound to the configured harness.
_dispatcher = AgentDispatcher(invoker=default_invoker_unavailable)


def set_dispatcher(dispatcher: AgentDispatcher) -> None:
    """Bind the dispatcher used by all research activities (called by worker)."""
    global _dispatcher
    _dispatcher = dispatcher


@_activity
async def research_stage_activity(invocation: StageInvocation) -> StageOutcome:
    """Run one stage of the 26-stage research pipeline.

    Internally drives a LangGraph state machine (`run_research_stage_graph`)
    that handles retries, tool-call loops, and confidence checks before
    returning a clean StageOutcome to Temporal.
    """
    project_id = invocation.project_id
    stage = invocation.stage

    await emit_stage_event(
        project_id, "research", stage, "started",
        {"attempt": invocation.attempt, "inputs": list(invocation.inputs)},
    )
    try:
        outcome = await run_research_stage_graph(
            dispatcher=_dispatcher,
            invocation=invocation,
        )
    except Exception as exc:
        log.exception("stage failed: %s/%s", project_id, stage)
        outcome = StageOutcome(
            project_id=project_id,
            track="research",
            stage=stage,
            outputs={},
            agent="<unknown>",
            skills_injected=[],
            error=str(exc),
        )
        await emit_stage_event(
            project_id, "research", stage, "failed", {"error": str(exc)},
        )
        return outcome

    await emit_stage_event(
        project_id,
        "research",
        stage,
        "succeeded" if outcome.error is None else "failed",
        {
            "agent": outcome.agent,
            "cost_usd": outcome.cost_usd,
            "confidence": outcome.confidence,
            "skills_injected": outcome.skills_injected,
        },
    )
    return outcome


@_activity
async def quality_gate_activity_research(
    outcome: StageOutcome,
) -> QualityGateVerdict:
    """Run the quality gate stack against a research stage outcome."""
    from lab.quality_gates.orchestrator import run_quality_gate

    await emit_stage_event(
        outcome.project_id, "research", outcome.stage, "gate_started", {},
    )
    verdict = await run_quality_gate(track="research", outcome=outcome)
    await emit_stage_event(
        outcome.project_id,
        "research",
        outcome.stage,
        "gate_blocked" if not verdict.allow else "gate_passed",
        asdict(verdict),
    )
    return verdict


@_activity
async def rollback_activity_research(
    project_id: str, from_stage: str, to_stage: str, reason: str,
) -> dict[str, Any]:
    """Record a rollback in the event log + return navigation metadata."""
    await emit_stage_event(
        project_id, "research", from_stage, "rollback",
        {"to_stage": to_stage, "reason": reason},
    )
    return {"from": from_stage, "to": to_stage, "reason": reason}
