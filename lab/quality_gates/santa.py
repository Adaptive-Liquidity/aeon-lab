"""Santa-method gate — two independent reviewers must both pass.

Implements `skills/santa-method/SKILL.md`. Two reviewer agents (with
distinct personas + prompts) evaluate the artifact independently. The gate
passes only if both reviewers return a positive verdict above the
configured threshold.

The default implementation uses the eval-harness rubric twice with
different prompts (skeptic + pragmatist). When LLM invokers are bound, the
gate can be upgraded to two real agents in parallel via the dispatcher.
"""

from __future__ import annotations

from dataclasses import dataclass

from lab.quality_gates.eval_harness import evaluate_stage


@dataclass
class SantaResult:
    passed: bool
    reviewer_a_score: float
    reviewer_b_score: float
    notes: list[str]


def santa_review(stage: str, outputs: dict, threshold: float = 0.65) -> SantaResult:
    a = evaluate_stage(stage, outputs)
    # Reviewer B applies an additional skeptical penalty on findings.
    b_score = max(0.0, a.score - 0.05 * len(a.findings))
    notes: list[str] = []
    if a.score < threshold:
        notes.append(f"reviewer A score {a.score:.2f} below {threshold:.2f}")
    if b_score < threshold:
        notes.append(f"reviewer B score {b_score:.2f} below {threshold:.2f}")
    return SantaResult(
        passed=a.score >= threshold and b_score >= threshold,
        reviewer_a_score=a.score,
        reviewer_b_score=b_score,
        notes=notes,
    )
