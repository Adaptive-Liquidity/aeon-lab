"""Run the full quality gate stack against a single StageOutcome.

Pipeline:
  1. eval_harness    -> score + findings
  2. santa           -> dual-reviewer pass/fail
  3. gateguard       -> evidence count
  4. gan_evaluator   -> adversarial score
  5. policy.combine  -> allow/rollback decision
  6. council (if ambiguous) -> tie-breaker vote

Returns a QualityGateVerdict that Temporal can serialize and that the
workflow uses to either continue forward or roll back.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from lab.orchestrator.state import QualityGateVerdict, StageOutcome
from lab.quality_gates.council import CouncilVerdict, council_vote
from lab.quality_gates.eval_harness import EvalResult, evaluate_stage
from lab.quality_gates.gan_evaluator import GanResult, gan_evaluate
from lab.quality_gates.gateguard import GateguardResult, gateguard_check
from lab.quality_gates.policy import DecisionPolicy, default_policy
from lab.quality_gates.santa import SantaResult, santa_review

log = logging.getLogger("lab.quality_gates.orchestrator")


@dataclass
class QualityGateResult:
    eval_result: EvalResult
    santa_result: SantaResult
    gateguard_result: GateguardResult
    gan_result: GanResult
    council_verdict: CouncilVerdict | None
    combined: dict[str, Any]


_ROLLBACK_MAP_RESEARCH: dict[str, str] = {
    "literature_screen": "literature_collect",
    "experiment_design": "hypothesis_gen",
    "quality_gate": "paper_outline",
    "citation_verify": "paper_revision",
}

_ROLLBACK_MAP_ENGINEERING: dict[str, str] = {
    "plan": "research_reuse",
    "review": "implement",
    "commit": "review",
}


async def run_quality_gate(
    *,
    track: str,
    outcome: StageOutcome,
    policy: DecisionPolicy | None = None,
) -> QualityGateVerdict:
    policy = policy or default_policy()

    # All four checks are pure CPU; run them concurrently via to_thread.
    eval_task = asyncio.to_thread(evaluate_stage, outcome.stage, outcome.outputs)
    santa_task = asyncio.to_thread(santa_review, outcome.stage, outcome.outputs)
    text = _text_of(outcome.outputs)
    gateguard_task = asyncio.to_thread(gateguard_check, text)
    gan_task = asyncio.to_thread(
        gan_evaluate, outcome.stage, outcome.outputs.get("_inputs", {}) or {}, outcome.outputs
    )
    eval_r, santa_r, gg_r, gan_r = await asyncio.gather(
        eval_task, santa_task, gateguard_task, gan_task
    )

    combined = policy.combine(
        eval_score=eval_r.score,
        santa_passed=santa_r.passed,
        gateguard_passed=gg_r.passed,
        council_consensus=None,
        gan_score=gan_r.score,
    )

    council: CouncilVerdict | None = None
    if 0.4 < combined["confidence"] < 0.6:
        council = council_vote(
            eval_score=eval_r.score,
            santa_passed=santa_r.passed,
            gateguard_passed=gg_r.passed,
            gan_score=gan_r.score,
        )
        combined = policy.combine(
            eval_score=eval_r.score,
            santa_passed=santa_r.passed,
            gateguard_passed=gg_r.passed,
            council_consensus=council.consensus,
            gan_score=gan_r.score,
        )

    findings = list(eval_r.findings) + list(santa_r.notes) + list(gg_r.notes) + list(gan_r.notes)
    rollback = None
    if not combined["allow"]:
        map_ = _ROLLBACK_MAP_RESEARCH if track == "research" else _ROLLBACK_MAP_ENGINEERING
        rollback = map_.get(outcome.stage)

    return QualityGateVerdict(
        project_id=outcome.project_id,
        track=track,
        stage=outcome.stage,
        allow=bool(combined["allow"]),
        confidence=float(combined["confidence"]),
        eval_score=float(eval_r.score),
        santa_passed=bool(santa_r.passed),
        gateguard_passed=bool(gg_r.passed),
        council_consensus=(council.consensus if council else None),
        rollback_to=rollback,
        findings=findings[:10],
        escalate_to_human=bool(combined["escalate_to_human"]),
    )


def _text_of(outputs: dict[str, Any]) -> str:
    if not outputs:
        return ""
    parts: list[str] = []
    for v in outputs.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts.extend(str(x) for x in v if isinstance(x, (str, int, float)))
    return "\n".join(parts)
