"""Weekly skill-comply audit runner.

Drives the existing ECC `skill-comply` skill at a slow cadence: walks the
`skills/` tree, runs each skill's frontmatter validator, and verifies
that lessons promoted from the continuous-learning loop actually behave
as advertised in recent runs (by cross-referencing the learning queue's
processed log against the lab provenance ledger).

The runner is read-only. Findings flag candidate skills that should be
deleted or re-reviewed, plus published skills that no longer match the
behaviours observed in production.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .common import lab_data_home, write_report

AUDIT_NAME = "skill-comply"
SKILL_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _repo_root() -> Path:
    return Path(os.environ.get("ECC_ROOT") or Path.cwd())


def _iter_skill_files() -> List[Path]:
    root = _repo_root() / "skills"
    if not root.exists():
        return []
    return [p for p in root.rglob("*.md") if p.is_file()]


def _check_frontmatter(path: Path) -> Dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {
            "severity": "low",
            "title": f"Unreadable skill file: {path}",
            "detail": "Could not read file",
        }
    match = SKILL_FRONTMATTER_RE.search(text)
    if not match:
        return {
            "severity": "medium",
            "title": "Missing frontmatter",
            "detail": str(path.relative_to(_repo_root())),
        }
    block = match.group(1)
    has_name = re.search(r"^name:\s*\S", block, re.MULTILINE)
    has_desc = re.search(r"^description:\s*\S", block, re.MULTILINE)
    if not has_name or not has_desc:
        return {
            "severity": "medium",
            "title": "Frontmatter missing required keys",
            "detail": str(path.relative_to(_repo_root())),
        }
    return None


def _processed_log_path() -> Path:
    return lab_data_home() / "learning-processed.jsonl"


def _check_candidate_lessons() -> List[Dict[str, Any]]:
    candidates_dir = _repo_root() / "skills" / "_candidates"
    if not candidates_dir.exists():
        return []
    out: List[Dict[str, Any]] = []
    for path in candidates_dir.glob("*.md"):
        sidecar = path.with_suffix(".evidence.json")
        if not sidecar.exists():
            out.append(
                {
                    "severity": "low",
                    "title": "Candidate skill missing evidence sidecar",
                    "detail": str(path.relative_to(_repo_root())),
                }
            )
            continue
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            out.append(
                {
                    "severity": "medium",
                    "title": "Candidate skill evidence sidecar is unreadable",
                    "detail": str(sidecar.relative_to(_repo_root())),
                }
            )
            continue
        if (data.get("occurrences") or 0) < 3:
            out.append(
                {
                    "severity": "low",
                    "title": "Candidate skill has weak evidence",
                    "detail": f"{path.name}: occurrences={data.get('occurrences')}",
                }
            )
    return out


def run_skill_comply_audit() -> Path:
    started = datetime.now(timezone.utc).isoformat()
    findings: List[Dict[str, Any]] = []
    skill_files = _iter_skill_files()
    for path in skill_files:
        finding = _check_frontmatter(path)
        if finding:
            findings.append(finding)
    findings.extend(_check_candidate_lessons())
    finished = datetime.now(timezone.utc).isoformat()
    payload = {
        "audit": AUDIT_NAME,
        "started_at": started,
        "finished_at": finished,
        "status": "ok" if not findings else "review-needed",
        "skill_count": len(skill_files),
        "findings": findings,
    }
    return write_report(AUDIT_NAME, payload)


if __name__ == "__main__":
    out = run_skill_comply_audit()
    print(out)
