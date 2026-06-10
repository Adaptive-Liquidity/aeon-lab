"""Rubric-scored eval-harness gate.

Wraps the rubric defined in `skills/eval-harness/SKILL.md`. Scores the
artifact text against the stage's Definition of Done (DoD) and contract
expectations.

The implementation is heuristic-first and degrades gracefully when no
LLM is bound: it computes structural signals (length, headers, citations,
code-block presence) and combines them with a configurable rubric.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class EvalResult:
    score: float           # 0..1
    sub_scores: dict[str, float]
    findings: list[str]


_DOD_BY_STAGE: dict[str, dict[str, Any]] = {
    # Research track
    "topic_init": {"min_chars": 200, "wants_headers": True},
    "search_strategy": {"min_chars": 400, "needs_yaml": True},
    "literature_collect": {"min_chars": 200, "needs_list": True},
    "literature_screen": {"min_chars": 300, "needs_decisions": True},
    "knowledge_extract": {"min_chars": 500, "needs_cards": True},
    "synthesis": {"min_chars": 600, "needs_headers": True},
    "hypothesis_gen": {"min_chars": 300, "needs_list": True},
    "experiment_design": {"min_chars": 600, "needs_yaml": True},
    "code_generation": {"min_chars": 400, "needs_code": True},
    "sanity_check": {"min_chars": 100},
    "experiment_run": {"min_chars": 200, "needs_metrics": True},
    "iterative_refine": {"min_chars": 400, "needs_metrics": True},
    "result_analysis": {"min_chars": 500, "needs_stats": True},
    "research_decision": {"min_chars": 200, "needs_decision_word": True},
    "paper_outline": {"min_chars": 400, "needs_headers": True},
    "paper_draft": {"min_chars": 4000, "needs_citations": True},
    "peer_review": {"min_chars": 800, "needs_findings": True},
    "paper_revision": {"min_chars": 4000, "needs_citations": True},
    "quality_gate": {"min_chars": 200},
    "citation_verify": {"min_chars": 100, "needs_decisions": True},
    # Engineering track
    "intake": {"min_chars": 150},
    "research_reuse": {"min_chars": 300, "needs_list": True},
    "plan": {"min_chars": 500, "needs_list": True},
    "scaffold": {"min_chars": 200, "needs_code": True},
    "implement": {"min_chars": 400, "needs_code": True},
    "review": {"min_chars": 300, "needs_findings": True},
    "commit": {"min_chars": 50},
}


def _text_of(outputs: dict[str, Any]) -> str:
    if not outputs:
        return ""
    if "completion" in outputs and isinstance(outputs["completion"], str):
        return outputs["completion"]
    parts = []
    for v in outputs.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts.extend(str(x) for x in v if isinstance(x, (str, int, float)))
    return "\n".join(parts)


def evaluate_stage(stage: str, outputs: dict[str, Any]) -> EvalResult:
    text = _text_of(outputs)
    dod = _DOD_BY_STAGE.get(stage, {"min_chars": 150})
    sub: dict[str, float] = {}
    findings: list[str] = []

    chars = len(text)
    min_chars = dod.get("min_chars", 150)
    sub["length"] = min(1.0, chars / max(1, min_chars))
    if chars < min_chars:
        findings.append(f"output too short: {chars} < {min_chars}")

    if dod.get("wants_headers") or dod.get("needs_headers"):
        headers = len(re.findall(r"^#+\s+", text, flags=re.MULTILINE))
        sub["headers"] = min(1.0, headers / 3)
        if headers < 2:
            findings.append("missing structured headers")

    if dod.get("needs_yaml"):
        yaml_score = 1.0 if re.search(r"```ya?ml", text) or re.search(r"^[a-z_]+:\s", text, flags=re.MULTILINE) else 0.0
        sub["yaml"] = yaml_score
        if yaml_score == 0.0:
            findings.append("no YAML block detected")

    if dod.get("needs_code"):
        code_score = 1.0 if re.search(r"```(?:python|ts|tsx|js|go|rust|java)", text) else 0.0
        sub["code"] = code_score
        if code_score == 0.0:
            findings.append("no code block detected")

    if dod.get("needs_list"):
        list_score = min(1.0, len(re.findall(r"^\s*[-*]\s+", text, flags=re.MULTILINE)) / 3)
        sub["list"] = list_score
        if list_score < 0.5:
            findings.append("expected a list of items")

    if dod.get("needs_citations"):
        cites = len(re.findall(r"\[[A-Za-z0-9]+,?\s*\d{4}\]|\[\d+\]", text))
        sub["citations"] = min(1.0, cites / 5)
        if cites < 3:
            findings.append("very few citations")

    if dod.get("needs_stats"):
        stat_score = 1.0 if re.search(r"\bp\s*[=<>]\s*0", text) or re.search(r"std|mean|variance", text, re.I) else 0.0
        sub["stats"] = stat_score
        if stat_score == 0.0:
            findings.append("no statistical summary detected")

    if dod.get("needs_metrics"):
        metric_score = 1.0 if re.search(r"\d+\.\d+", text) else 0.0
        sub["metrics"] = metric_score
        if metric_score == 0.0:
            findings.append("no numeric metric values")

    if dod.get("needs_findings"):
        finds = len(re.findall(r"\b(CRITICAL|HIGH|MEDIUM|LOW|MAJOR|MINOR|FINDING)\b", text))
        sub["findings_count"] = min(1.0, finds / 3)

    if dod.get("needs_decision_word"):
        decision = 1.0 if re.search(r"\b(PROCEED|PIVOT|REFINE|STOP)\b", text) else 0.0
        sub["decision"] = decision
        if decision == 0.0:
            findings.append("explicit PROCEED/PIVOT/REFINE/STOP missing")

    if dod.get("needs_cards"):
        card_score = min(1.0, len(re.findall(r"^##\s+", text, re.M)) / 3)
        sub["cards"] = card_score

    if dod.get("needs_decisions"):
        d = 1.0 if re.search(r"\b(accept|reject|include|exclude|verified|hallucinat)", text, re.I) else 0.0
        sub["decisions"] = d
        if d == 0.0:
            findings.append("no explicit accept/reject decisions")

    score = sum(sub.values()) / max(1, len(sub))
    return EvalResult(score=score, sub_scores=sub, findings=findings)
