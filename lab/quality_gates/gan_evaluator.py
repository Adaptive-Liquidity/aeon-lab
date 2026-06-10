"""GAN-evaluator gate — adversarial scoring vs the spec.

Implements `skills/gan-style-harness/SKILL.md`. The evaluator scores the
artifact against the original spec/brief on a rubric; the generator is
expected to iterate until evaluator score >= threshold.

This module is the *evaluator half*. The generator side runs as the
stage's primary agent (in the LangGraph inner loop). When the gate runs
post-stage, we score the stage outputs relative to its declared inputs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from lab.quality_gates.eval_harness import evaluate_stage


@dataclass
class GanResult:
    score: float
    rubric: dict[str, float]
    notes: list[str]


def gan_evaluate(stage: str, inputs: dict[str, Any], outputs: dict[str, Any]) -> GanResult:
    base = evaluate_stage(stage, outputs)
    text = "\n".join(
        str(v) for v in outputs.values() if isinstance(v, (str, int, float))
    )

    # Rubric over and above base eval: alignment to spec, novelty, completeness.
    alignment = _alignment_score(inputs, text)
    completeness = base.score
    novelty = _novelty_score(text)
    rubric = {
        "alignment": alignment,
        "completeness": completeness,
        "novelty": novelty,
    }
    score = (alignment + completeness + novelty) / 3
    notes = list(base.findings)
    if alignment < 0.5:
        notes.append("output does not reference the declared inputs strongly")
    return GanResult(score=score, rubric=rubric, notes=notes)


def _alignment_score(inputs: dict[str, Any], text: str) -> float:
    if not inputs or not text:
        return 0.5
    keywords: list[str] = []
    for v in inputs.values():
        if isinstance(v, str):
            keywords.extend(_extract_keywords(v))
    if not keywords:
        return 0.6
    hits = sum(1 for k in keywords if re.search(rf"\b{re.escape(k)}\b", text, re.I))
    return min(1.0, hits / max(1, min(len(keywords), 10)))


def _extract_keywords(text: str) -> list[str]:
    words = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?", text)
    return list(dict.fromkeys(words))[:10]


def _novelty_score(text: str) -> float:
    # Crude: count distinct content-bearing terms.
    unique = len(set(re.findall(r"\b[a-z]{6,}\b", text.lower())))
    return min(1.0, unique / 80)
