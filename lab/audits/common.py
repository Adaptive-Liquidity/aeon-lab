"""Shared helpers for scheduled lab audits."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def lab_data_home() -> Path:
    return Path(os.environ.get("ECC_LAB_DATA_HOME") or (Path.home() / ".ecc" / "lab"))


def audits_root() -> Path:
    root = lab_data_home() / "audits"
    root.mkdir(parents=True, exist_ok=True)
    return root


def make_report_dir(audit_name: str, when: Optional[datetime] = None) -> Path:
    when = when or datetime.now(timezone.utc)
    stamp = when.strftime("%Y-%m-%dT%H-%M-%SZ")
    out = audits_root() / audit_name / stamp
    out.mkdir(parents=True, exist_ok=True)
    return out


def write_report(audit_name: str, payload: dict) -> Path:
    target = make_report_dir(audit_name)
    report_path = target / "report.json"
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    summary_path = target / "summary.md"
    summary_path.write_text(_render_summary(audit_name, payload), encoding="utf-8")
    _append_history(audit_name, target, payload)
    return target


def _render_summary(name: str, payload: dict) -> str:
    started = payload.get("started_at") or ""
    finished = payload.get("finished_at") or ""
    status = payload.get("status", "unknown")
    findings = payload.get("findings", [])
    lines = [
        f"# Audit: {name}",
        "",
        f"- Status: **{status}**",
        f"- Started: {started}",
        f"- Finished: {finished}",
        f"- Findings: {len(findings)}",
        "",
        "## Findings",
    ]
    if not findings:
        lines.append("- (none)")
    else:
        for finding in findings:
            severity = finding.get("severity", "info").upper()
            title = finding.get("title", "(untitled)")
            detail = finding.get("detail") or ""
            lines.append(f"- **[{severity}] {title}** — {detail}")
    return "\n".join(lines) + "\n"


def _append_history(audit_name: str, report_dir: Path, payload: dict) -> None:
    history = audits_root() / f"{audit_name}.history.jsonl"
    summary = {
        "audit": audit_name,
        "report_dir": str(report_dir),
        "started_at": payload.get("started_at"),
        "finished_at": payload.get("finished_at"),
        "status": payload.get("status"),
        "finding_count": len(payload.get("findings", [])),
    }
    with history.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
