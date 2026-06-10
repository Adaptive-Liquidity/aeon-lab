"""Cost ledger that mirrors `skills/cost-tracking`'s schema.

Each entry: project_id, agent_role, stage, model, in_tokens, out_tokens,
cost_usd, timestamp. Aggregations roll up daily / per-project.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from lab import lab_data_home

log = logging.getLogger("lab.observability.cost_ledger")


@dataclass
class CostEntry:
    project_id: str
    track: str
    stage: str
    agent_role: str
    model: str
    in_tokens: int = 0
    out_tokens: int = 0
    cost_usd: float = 0.0
    timestamp: float = field(default_factory=lambda: time.time())


class CostLedger:
    _lock = threading.Lock()
    _shared: "CostLedger | None" = None

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (lab_data_home() / "cost_ledger.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def shared(cls) -> "CostLedger":
        with cls._lock:
            if cls._shared is None:
                cls._shared = cls()
            return cls._shared

    def append(self, entry: CostEntry) -> None:
        try:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(entry)) + "\n")
        except Exception:
            log.exception("cost ledger write failed")

    def rollup(self, *, project_id: str | None = None) -> dict[str, Any]:
        totals: dict[str, Any] = {
            "total_usd": 0.0,
            "by_project": {},
            "by_model": {},
            "by_stage": {},
        }
        if not self.path.exists():
            return totals
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if project_id and row.get("project_id") != project_id:
                    continue
                cost = float(row.get("cost_usd", 0.0))
                totals["total_usd"] += cost
                _add(totals["by_project"], row.get("project_id"), cost)
                _add(totals["by_model"], row.get("model"), cost)
                _add(totals["by_stage"], row.get("stage"), cost)
        return totals


def _add(bucket: dict[str, float], key: str | None, cost: float) -> None:
    if key is None:
        return
    bucket[key] = bucket.get(key, 0.0) + cost


def record_cost(
    *,
    project_id: str,
    track: str,
    stage: str,
    agent_role: str,
    model: str,
    in_tokens: int = 0,
    out_tokens: int = 0,
    cost_usd: float = 0.0,
) -> None:
    CostLedger.shared().append(
        CostEntry(
            project_id=project_id,
            track=track,
            stage=stage,
            agent_role=agent_role,
            model=model,
            in_tokens=in_tokens,
            out_tokens=out_tokens,
            cost_usd=cost_usd,
        )
    )
