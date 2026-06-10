"""Combine individual gate results into a final allow/rollback decision."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class DecisionPolicy:
    eval_min_score: float = 0.7
    confidence_floor: float = 0.6
    escalation_floor: float = 0.3
    require_santa_dual_pass: bool = True
    require_gateguard_evidence: bool = True
    council_required_when_ambiguous: bool = True

    def combine(
        self,
        *,
        eval_score: float,
        santa_passed: bool,
        gateguard_passed: bool,
        council_consensus: str | None,
        gan_score: float | None = None,
    ) -> dict:
        passes: list[bool] = [eval_score >= self.eval_min_score]
        if self.require_santa_dual_pass:
            passes.append(santa_passed)
        if self.require_gateguard_evidence:
            passes.append(gateguard_passed)
        if gan_score is not None:
            passes.append(gan_score >= self.eval_min_score)

        agreement = sum(1 for p in passes if p) / max(1, len(passes))
        # Weight by overall agreement; council only used to break ties.
        confidence = max(0.0, min(1.0, agreement * 0.7 + eval_score * 0.3))
        allow = all(passes)

        escalate = (not allow) and confidence < self.escalation_floor
        if council_consensus and self.council_required_when_ambiguous and 0.4 < confidence < 0.6:
            allow = council_consensus.startswith("allow")
            escalate = False

        return {
            "allow": allow,
            "confidence": confidence,
            "escalate_to_human": escalate,
        }


_default = DecisionPolicy()


def default_policy() -> DecisionPolicy:
    return _default
