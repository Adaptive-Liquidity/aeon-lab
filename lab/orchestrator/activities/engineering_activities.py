"""Temporal activities for the 6-phase engineering workflow (orch-pipeline).

Mirrors the structure of `research_activities.py`. Adds an explicit
`security_review_activity` that the workflow invokes when the diff touches
any security trigger described in `rules/common/security.md`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict
from typing import Any

try:
    from temporalio import activity

    _activity = activity.defn
except Exception:  # pragma: no cover

    def _activity(fn=None, **_kw):
        return fn if fn is not None else (lambda f: f)


from lab.bridge.agent_dispatcher import (
    AgentDispatcher,
    StageRequest,
    default_invoker_unavailable,
)
from lab.bridge.hooks_bridge import emit_stage_event
from lab.orchestrator.graphs.engineering_graph import run_engineering_phase_graph
from lab.orchestrator.state import (
    QualityGateVerdict,
    StageInvocation,
    StageOutcome,
)

log = logging.getLogger("lab.orchestrator.activities.engineering")

_dispatcher = AgentDispatcher(invoker=default_invoker_unavailable)


def set_dispatcher(dispatcher: AgentDispatcher) -> None:
    global _dispatcher
    _dispatcher = dispatcher


SECURITY_TRIGGER_PATTERNS = (
    r"\bauth(n|z|entication|orization)?\b",
    r"\binput\s+validation\b",
    r"\bsql\b",
    r"\bquery\b",
    r"\bfilesystem\b|\bfile\s+system\b|\bfs\b",
    r"\bsecret(s)?\b|\bcredential",
    r"\btoken\b|\bjwt\b|\bapi\s*key\b",
    r"\bcrypto\b|\bencrypt\b|\bdecrypt\b",
    r"\bexternal\s+api\b|\bnetwork\s+request\b",
    r"\bcookie\b|\bsession\b",
)


def diff_touches_security(diff: str) -> bool:
    return any(re.search(p, diff, flags=re.IGNORECASE) for p in SECURITY_TRIGGER_PATTERNS)


@_activity
async def engineering_phase_activity(invocation: StageInvocation) -> StageOutcome:
    project_id = invocation.project_id
    stage = invocation.stage
    await emit_stage_event(
        project_id, "engineering", stage, "started",
        {"attempt": invocation.attempt},
    )
    try:
        outcome = await run_engineering_phase_graph(
            dispatcher=_dispatcher,
            invocation=invocation,
        )
    except Exception as exc:
        log.exception("phase failed: %s/%s", project_id, stage)
        outcome = StageOutcome(
            project_id=project_id,
            track="engineering",
            stage=stage,
            outputs={},
            agent="<unknown>",
            skills_injected=[],
            error=str(exc),
        )
        await emit_stage_event(
            project_id, "engineering", stage, "failed", {"error": str(exc)},
        )
        return outcome

    await emit_stage_event(
        project_id,
        "engineering",
        stage,
        "succeeded" if outcome.error is None else "failed",
        {"agent": outcome.agent, "cost_usd": outcome.cost_usd},
    )
    return outcome


@_activity
async def quality_gate_activity_engineering(
    outcome: StageOutcome,
) -> QualityGateVerdict:
    from lab.quality_gates.orchestrator import run_quality_gate

    verdict = await run_quality_gate(track="engineering", outcome=outcome)
    await emit_stage_event(
        outcome.project_id,
        "engineering",
        outcome.stage,
        "gate_blocked" if not verdict.allow else "gate_passed",
        asdict(verdict),
    )
    return verdict


@_activity
async def security_review_activity(
    project_id: str, diff_text: str, context: dict[str, Any],
) -> StageOutcome:
    """Force-inject the security-reviewer agent on a diff."""
    request = StageRequest(
        track="engineering",
        stage="review",
        project_id=project_id,
        inputs={"diff": diff_text, "trigger": "security"},
        context=context,
        prefer_fallback=True,  # use security-reviewer (fallback in review map)
        extra_skills=("security-review", "security-bounty-hunter"),
    )
    result = await _dispatcher.dispatch(request)
    await emit_stage_event(
        project_id, "engineering", "review", "security_review_done",
        {"agent": result.agent, "confidence": result.confidence},
    )
    return StageOutcome(
        project_id=result.project_id,
        track="engineering",
        stage="review",
        outputs=result.outputs,
        agent=result.agent,
        skills_injected=result.skills_injected,
        model_used=result.model_used,
        cost_usd=result.cost_usd or 0.0,
        latency_ms=result.latency_ms or 0,
        confidence=result.confidence or 0.0,
        error=result.error,
    )
