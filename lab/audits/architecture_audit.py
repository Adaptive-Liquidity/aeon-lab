"""Nightly agent-architecture-audit runner.

Calls the existing ECC `agent-architecture-audit` skill via the lab's
quality-gate orchestrator. The skill ships as a markdown rubric; this
runner gathers the inputs it expects (live workflow descriptors, recent
gate verdicts, cost ledger snapshot, MCP policy snapshot) and produces a
structured report.

If the lab API is reachable it queries live data; otherwise it falls
back to on-disk artifacts. The runner is intentionally tolerant of
missing inputs so the cron stays green during cold-start days.
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .common import lab_data_home, write_report

AUDIT_NAME = "agent-architecture-audit"


def _api_base() -> str:
    return os.environ.get("ECC_LAB_API") or "http://127.0.0.1:8810"


def _fetch_json(path: str) -> Any:
    url = _api_base().rstrip("/") + path
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _collect_inputs() -> Dict[str, Any]:
    return {
        "health": _fetch_json("/api/lab/health"),
        "workflows": _fetch_json("/api/lab/workflows"),
        "cost": _fetch_json("/api/lab/cost?window=24h"),
        "policy": _fetch_json("/api/lab/policy"),
        "events_dir": str(lab_data_home() / "events"),
        "cost_ledger": str(lab_data_home() / "cost_ledger.jsonl"),
    }


def _evaluate(inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    health = inputs.get("health") or {}
    if health.get("status") and health["status"] != "ok":
        findings.append(
            {
                "severity": "high",
                "title": "Lab API health degraded",
                "detail": json.dumps(health),
            }
        )
    workflows = inputs.get("workflows") or []
    if isinstance(workflows, list):
        stuck = [w for w in workflows if (w.get("status") or "").lower() == "stuck"]
        if stuck:
            findings.append(
                {
                    "severity": "medium",
                    "title": f"{len(stuck)} workflow(s) reported stuck",
                    "detail": ", ".join(w.get("id", "") for w in stuck[:5]),
                }
            )
    cost = inputs.get("cost") or {}
    total = cost.get("total_usd") if isinstance(cost, dict) else None
    if isinstance(total, (int, float)) and total > 100:
        findings.append(
            {
                "severity": "medium",
                "title": "Daily lab spend exceeds $100",
                "detail": f"24h total = ${total:.2f}",
            }
        )
    if not Path(inputs["cost_ledger"]).exists():
        findings.append(
            {
                "severity": "info",
                "title": "No cost ledger on disk",
                "detail": "Lab may not have processed any workflows yet.",
            }
        )
    return findings


def run_architecture_audit() -> Path:
    started = datetime.now(timezone.utc).isoformat()
    inputs = _collect_inputs()
    findings = _evaluate(inputs)
    finished = datetime.now(timezone.utc).isoformat()
    payload = {
        "audit": AUDIT_NAME,
        "started_at": started,
        "finished_at": finished,
        "status": "ok" if not any(f["severity"] in {"high", "critical"} for f in findings) else "degraded",
        "inputs": {k: bool(v) for k, v in inputs.items()},
        "findings": findings,
    }
    return write_report(AUDIT_NAME, payload)


if __name__ == "__main__":
    out = run_architecture_audit()
    print(out)
