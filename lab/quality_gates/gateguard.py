"""Gateguard — fact-forcing evidence check.

Implements `skills/gateguard/SKILL.md`. Refuses to let an artifact pass
unless it carries explicit, structured evidence: file references, test
results, citations with verifiable identifiers, or numeric metrics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class GateguardResult:
    passed: bool
    evidence_count: int
    types: dict[str, int]
    notes: list[str]


_PATTERNS = {
    "file_ref": r"(?P<file>[\w\-/]+\.(?:py|ts|tsx|js|md|yaml|yml|json|toml|sql))(:\d+)?",
    "url": r"https?://[^\s)]+",
    "doi": r"10\.\d{4,9}/[^\s)]+",
    "arxiv": r"arXiv:\s*\d{4}\.\d{4,5}",
    "github": r"github\.com/[\w\-]+/[\w\-]+",
    "metric": r"\d+\.\d+\s*%?",
    "test_id": r"test_[a-zA-Z0-9_]+",
}


def gateguard_check(text: str, *, min_evidence: int = 3) -> GateguardResult:
    counts: dict[str, int] = {}
    for name, pattern in _PATTERNS.items():
        counts[name] = len(re.findall(pattern, text))
    total = sum(counts.values())
    notes: list[str] = []
    if total < min_evidence:
        notes.append(
            f"insufficient evidence: {total} concrete references, need >= {min_evidence}"
        )
    return GateguardResult(
        passed=total >= min_evidence,
        evidence_count=total,
        types=counts,
        notes=notes,
    )
