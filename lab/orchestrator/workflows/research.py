"""26-stage research workflow.

A Temporal workflow that walks the research pipeline stage-by-stage. The
HITL gates that Claw originally enforced (LITERATURE_SCREEN,
EXPERIMENT_DESIGN, QUALITY_GATE) are intercepted and dispatched to the
automated quality stack instead of pausing for human approval.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta

try:
    from temporalio import workflow
    from temporalio.common import RetryPolicy

    _TEMPORAL = True
except Exception:  # pragma: no cover

    class _Workflow:
        def defn(self, *a, **kw):
            return lambda c: c

        def run(self, *a, **kw):
            return lambda f: f

        def execute_activity(self, *a, **kw):
            raise RuntimeError("temporalio not installed")

    workflow = _Workflow()  # type: ignore[assignment]
    RetryPolicy = object  # type: ignore[assignment]
    _TEMPORAL = False


# Imports are deferred for activity references — they need the activity
# decorator applied by the activity module. Workflows reference activities
# only by symbol via the worker registration.
from lab.orchestrator.stages import (
    LEGACY_HITL_RESEARCH_GATES,
    RESEARCH_SEQUENCE,
    ResearchStage,
    next_research_stage,
)
from lab.orchestrator.state import (
    ProjectBrief,
    QualityGateVerdict,
    StageInvocation,
    StageOutcome,
)


@workflow.defn(name="ResearchWorkflow") if _TEMPORAL else (lambda c: c)
class ResearchWorkflow:
    @workflow.run if _TEMPORAL else (lambda f: f)
    async def run(self, brief: ProjectBrief) -> dict:
        # Lazy import inside workflow to satisfy Temporal's sandbox.
        from lab.orchestrator.activities.research_activities import (
            quality_gate_activity_research,
            research_stage_activity,
            rollback_activity_research,
        )

        retry_policy = (
            RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=5),
                maximum_interval=timedelta(minutes=2),
            )
            if _TEMPORAL
            else None
        )

        state = {
            "project_id": brief.project_id,
            "cost_usd_spent": 0.0,
            "artifacts": {},
            "stage_history": [],
            "quality_gates": [],
        }

        current: ResearchStage | None = ResearchStage.TOPIC_INIT
        prior_outputs: dict[str, dict] = {}
        max_loop_iters = len(RESEARCH_SEQUENCE) * 3
        loop_count = 0

        while current is not None and loop_count < max_loop_iters:
            loop_count += 1
            invocation = StageInvocation(
                project_id=brief.project_id,
                track="research",
                stage=current.value,
                inputs=prior_outputs.get(current.value, {}),
                context={"brief": asdict(brief), "history": state["stage_history"]},
            )

            outcome: StageOutcome = await workflow.execute_activity(
                research_stage_activity,
                invocation,
                start_to_close_timeout=timedelta(hours=2),
                retry_policy=retry_policy,
            )

            state["cost_usd_spent"] += outcome.cost_usd
            state["stage_history"].append(current.value)
            prior_outputs[current.value] = outcome.outputs

            # Budget circuit breaker
            if state["cost_usd_spent"] > brief.budget_usd:
                return {
                    "status": "budget_exhausted",
                    "spent": state["cost_usd_spent"],
                    "budget": brief.budget_usd,
                    "state": state,
                }

            # Stages that used to be HITL gates now hit the automated stack.
            if current in LEGACY_HITL_RESEARCH_GATES or outcome.confidence < 0.4:
                verdict: QualityGateVerdict = await workflow.execute_activity(
                    quality_gate_activity_research,
                    outcome,
                    start_to_close_timeout=timedelta(minutes=15),
                    retry_policy=retry_policy,
                )
                state["quality_gates"].append(asdict(verdict))
                if not verdict.allow:
                    target = verdict.rollback_to or _default_rollback(current)
                    await workflow.execute_activity(
                        rollback_activity_research,
                        brief.project_id,
                        current.value,
                        target,
                        verdict.findings[:1] and verdict.findings[0] or "gate failed",
                        start_to_close_timeout=timedelta(seconds=30),
                    )
                    current = ResearchStage(target)
                    continue

            current = next_research_stage(current)

        return {"status": "complete", "state": state}


def _default_rollback(stage: ResearchStage) -> str:
    rollback = {
        ResearchStage.LITERATURE_SCREEN: ResearchStage.LITERATURE_COLLECT,
        ResearchStage.EXPERIMENT_DESIGN: ResearchStage.HYPOTHESIS_GEN,
        ResearchStage.QUALITY_GATE: ResearchStage.PAPER_OUTLINE,
    }.get(stage)
    if rollback is not None:
        return rollback.value
    idx = RESEARCH_SEQUENCE.index(stage)
    return RESEARCH_SEQUENCE[max(0, idx - 1)].value
