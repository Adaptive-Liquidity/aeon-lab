"""6-phase engineering workflow.

Maps ECC's orch-pipeline phases (Intake -> Research/Reuse -> Plan -> Scaffold
-> Implement -> Review -> Commit) onto Temporal. The two legacy HITL gates
(GATE 1 after Plan, GATE 2 before Commit) are replaced by the quality stack.

Adds a conditional `security_review_activity` whenever the diff produced
during Implement touches any of the security triggers defined in
`lab/orchestrator/activities/engineering_activities.py`.
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


from lab.orchestrator.stages import (
    ENGINEERING_SEQUENCE,
    EngineeringPhase,
    LEGACY_HITL_ENGINEERING_GATES,
    next_engineering_phase,
)
from lab.orchestrator.state import (
    ProjectBrief,
    QualityGateVerdict,
    StageInvocation,
    StageOutcome,
)


@workflow.defn(name="EngineeringWorkflow") if _TEMPORAL else (lambda c: c)
class EngineeringWorkflow:
    @workflow.run if _TEMPORAL else (lambda f: f)
    async def run(self, brief: ProjectBrief) -> dict:
        from lab.orchestrator.activities.engineering_activities import (
            engineering_phase_activity,
            quality_gate_activity_engineering,
            security_review_activity,
        )

        retry_policy = (
            RetryPolicy(
                maximum_attempts=2,
                initial_interval=timedelta(seconds=10),
                maximum_interval=timedelta(minutes=1),
            )
            if _TEMPORAL
            else None
        )

        state = {
            "project_id": brief.project_id,
            "cost_usd_spent": 0.0,
            "phase_history": [],
            "quality_gates": [],
            "security_reviewed": False,
        }
        prior_outputs: dict[str, dict] = {}
        current: EngineeringPhase | None = EngineeringPhase.INTAKE
        loop_count = 0
        max_loops = len(ENGINEERING_SEQUENCE) * 3

        while current is not None and loop_count < max_loops:
            loop_count += 1
            invocation = StageInvocation(
                project_id=brief.project_id,
                track="engineering",
                stage=current.value,
                inputs=prior_outputs.get(current.value, {}),
                context={"brief": asdict(brief), "history": state["phase_history"]},
            )
            outcome: StageOutcome = await workflow.execute_activity(
                engineering_phase_activity,
                invocation,
                start_to_close_timeout=timedelta(hours=1),
                retry_policy=retry_policy,
            )

            state["cost_usd_spent"] += outcome.cost_usd
            state["phase_history"].append(current.value)
            prior_outputs[current.value] = outcome.outputs

            if state["cost_usd_spent"] > brief.budget_usd:
                return {
                    "status": "budget_exhausted",
                    "spent": state["cost_usd_spent"],
                    "state": state,
                }

            # Security trigger autoinjection on Implement diffs.
            if current is EngineeringPhase.IMPLEMENT:
                from lab.orchestrator.activities.engineering_activities import (
                    diff_touches_security,
                )

                diff_text = outcome.outputs.get("diff", "")
                if diff_text and diff_touches_security(diff_text):
                    sec_outcome = await workflow.execute_activity(
                        security_review_activity,
                        brief.project_id,
                        diff_text,
                        invocation.context,
                        start_to_close_timeout=timedelta(minutes=20),
                        retry_policy=retry_policy,
                    )
                    state["security_reviewed"] = True
                    state["cost_usd_spent"] += sec_outcome.cost_usd
                    if sec_outcome.error or sec_outcome.confidence < 0.7:
                        # Rollback to Implement so the next attempt addresses findings.
                        current = EngineeringPhase.IMPLEMENT
                        prior_outputs[current.value] = {
                            **prior_outputs.get(current.value, {}),
                            "security_findings": sec_outcome.outputs,
                        }
                        continue

            if current in LEGACY_HITL_ENGINEERING_GATES or outcome.confidence < 0.5:
                verdict: QualityGateVerdict = await workflow.execute_activity(
                    quality_gate_activity_engineering,
                    outcome,
                    start_to_close_timeout=timedelta(minutes=15),
                    retry_policy=retry_policy,
                )
                state["quality_gates"].append(asdict(verdict))
                if not verdict.allow:
                    target = verdict.rollback_to or _default_rollback(current)
                    current = EngineeringPhase(target)
                    continue

            current = next_engineering_phase(current)

        return {"status": "complete", "state": state}


def _default_rollback(phase: EngineeringPhase) -> str:
    rollback = {
        EngineeringPhase.PLAN: EngineeringPhase.RESEARCH_REUSE,
        EngineeringPhase.COMMIT: EngineeringPhase.REVIEW,
        EngineeringPhase.REVIEW: EngineeringPhase.IMPLEMENT,
    }.get(phase)
    if rollback is not None:
        return rollback.value
    idx = ENGINEERING_SEQUENCE.index(phase)
    return ENGINEERING_SEQUENCE[max(0, idx - 1)].value
