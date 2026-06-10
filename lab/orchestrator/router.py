"""Work-item router: classify a task brief as research, engineering, or both.

Signals are deliberately rule-based first; ambiguous cases fall back to a
council vote via `quality_gates/council.py`. The classifier never blocks —
ambiguity always resolves to a default track within a bounded time.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from lab.orchestrator.state import ProjectBrief

log = logging.getLogger("lab.orchestrator.router")


@dataclass
class RouteDecision:
    track: str  # research | engineering
    confidence: float
    signals: dict[str, float] = field(default_factory=dict)
    rationale: str = ""
    ambiguous: bool = False


_RESEARCH_SIGNALS = {
    r"\barxiv\b": 0.9,
    r"\bpaper\b": 0.6,
    r"\bhypothes": 0.85,
    r"\bexperiment\b": 0.6,
    r"\bablation\b": 0.85,
    r"\bbenchmark\b": 0.5,
    r"\bdataset\b": 0.5,
    r"\bbaseline\b": 0.6,
    r"\bmetric\b": 0.4,
    r"\bcitation\b": 0.7,
    r"\bnovel(ty)?\b": 0.7,
    r"\bsynth(esis|esize)\b": 0.6,
    r"\bliterature\b": 0.8,
    r"\breproduc": 0.8,
    r"\bevaluat": 0.4,
    r"\bablate\b": 0.85,
    r"\bnips|neurips|icml|iclr|cvpr|aaai\b": 0.9,
}

_ENGINEERING_SIGNALS = {
    r"\bfix\b": 0.7,
    r"\bbug\b": 0.7,
    r"\bfeature\b": 0.7,
    r"\bpr\b|\bpull request\b": 0.8,
    r"\bimplement\b": 0.5,
    r"\brefactor\b": 0.8,
    r"\bmigrate\b": 0.6,
    r"\bdeploy\b": 0.7,
    r"\bendpoint\b": 0.6,
    r"\bschema\b": 0.4,
    r"\bbuild\b": 0.4,
    r"\btest(s|ing)?\b": 0.4,
    r"\bcomponent\b": 0.4,
    r"\bauth\b|\bauthentication\b": 0.7,
    r"\bapi\b": 0.5,
    r"\bdatabase\b": 0.4,
    r"\brepo\b|\brepository\b": 0.5,
    r"\bservice\b": 0.4,
    r"\bcomponent\b": 0.4,
    r"\b\.tsx?\b|\b\.py\b|\b\.go\b|\b\.rs\b|\b\.java\b": 0.6,
}


def _score(text: str, table: dict[str, float]) -> dict[str, float]:
    matches: dict[str, float] = {}
    for pattern, weight in table.items():
        if re.search(pattern, text, flags=re.IGNORECASE):
            matches[pattern] = weight
    return matches


@dataclass
class WorkItemRouter:
    """Pure rule-based router. Council escalation handled by caller."""

    research_threshold: float = 1.5
    engineering_threshold: float = 1.5
    ambiguity_gap: float = 0.5

    def classify(self, brief: ProjectBrief | str, *, hint: str | None = None) -> RouteDecision:
        if isinstance(brief, ProjectBrief):
            text = " ".join([brief.title or "", brief.description or ""])
            explicit = brief.track
        else:
            text = brief
            explicit = None
        if explicit in {"research", "engineering"}:
            return RouteDecision(
                track=explicit,
                confidence=1.0,
                signals={"explicit_track": 1.0},
                rationale=f"explicit track={explicit}",
            )
        if hint in {"research", "engineering"}:
            return RouteDecision(
                track=hint,
                confidence=0.9,
                signals={"caller_hint": 0.9},
                rationale=f"caller hint={hint}",
            )

        r_signals = _score(text, _RESEARCH_SIGNALS)
        e_signals = _score(text, _ENGINEERING_SIGNALS)
        r_score = sum(r_signals.values())
        e_score = sum(e_signals.values())
        signals = {
            **{f"research::{k}": v for k, v in r_signals.items()},
            **{f"engineering::{k}": v for k, v in e_signals.items()},
            "research_total": r_score,
            "engineering_total": e_score,
        }

        if r_score < self.research_threshold and e_score < self.engineering_threshold:
            return RouteDecision(
                track="engineering",  # safest default for short/unknown briefs
                confidence=0.2,
                signals=signals,
                rationale="neither track exceeded threshold; defaulting to engineering",
                ambiguous=True,
            )

        track = "research" if r_score >= e_score else "engineering"
        gap = abs(r_score - e_score)
        confidence = min(1.0, max(r_score, e_score) / (max(r_score, e_score) + 1.0))
        ambiguous = gap < self.ambiguity_gap and min(r_score, e_score) > 0
        return RouteDecision(
            track=track,
            confidence=confidence,
            signals=signals,
            rationale=f"r={r_score:.2f} e={e_score:.2f} gap={gap:.2f}",
            ambiguous=ambiguous,
        )


_default_router = WorkItemRouter()


def classify(brief: ProjectBrief | str, *, hint: str | None = None) -> RouteDecision:
    return _default_router.classify(brief, hint=hint)
