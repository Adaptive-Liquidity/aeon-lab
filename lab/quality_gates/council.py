"""Council — four-voice debate for ambiguous decisions.

Implements `skills/council/SKILL.md`. When the orchestrator returns
moderate-confidence verdicts, it consults a council of four personas
(pragmatist, skeptic, builder, auditor) and reduces their votes to a
single allow/rollback string.

The default implementation is rule-based and inspectable. The full LLM
council is wired by replacing `_voice_vote` with a real agent invocation
through the dispatcher.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CouncilVerdict:
    consensus: str  # "allow" | "rollback"
    votes: dict[str, str]
    rationale: list[str]


def council_vote(*, eval_score: float, santa_passed: bool, gateguard_passed: bool, gan_score: float) -> CouncilVerdict:
    votes = {
        "pragmatist": _voice_vote(eval_score, weight_eval=0.6, weight_evidence=0.4, evidence=gateguard_passed),
        "skeptic": _voice_vote(eval_score, weight_eval=0.3, weight_evidence=0.7, evidence=gateguard_passed),
        "builder": _voice_vote(gan_score, weight_eval=0.7, weight_evidence=0.3, evidence=santa_passed),
        "auditor": _voice_vote(eval_score, weight_eval=0.4, weight_evidence=0.6, evidence=santa_passed and gateguard_passed),
    }
    allow_count = sum(1 for v in votes.values() if v == "allow")
    consensus = "allow" if allow_count >= 3 else "rollback"
    rationale = [
        f"votes: allow={allow_count}/4",
        f"eval_score={eval_score:.2f} gan_score={gan_score:.2f}",
        f"santa={'pass' if santa_passed else 'fail'} gateguard={'pass' if gateguard_passed else 'fail'}",
    ]
    return CouncilVerdict(consensus=consensus, votes=votes, rationale=rationale)


def _voice_vote(score: float, *, weight_eval: float, weight_evidence: float, evidence: bool) -> str:
    threshold = 0.6 * weight_eval + (1.0 if evidence else 0.0) * weight_evidence
    return "allow" if (score >= 0.55 and threshold >= 0.5) else "rollback"
