"""Per-project budget tracking + circuit breaker.

A `BudgetTracker` records each model selection and the cost reported by
the upstream invoker. When a project's `spent_usd` exceeds its budget,
subsequent calls to `enforce` raise `BudgetExhausted` so the workflow
exits cleanly with an audit trail.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lab import lab_data_home

log = logging.getLogger("lab.model_router.budgets")


class BudgetExhausted(RuntimeError):
    """Raised when a project's budget cap has been hit."""


@dataclass
class BudgetRow:
    project_id: str
    budget_usd: float
    spent_usd: float = 0.0
    decisions: list[dict[str, Any]] = field(default_factory=list)


class BudgetTracker:
    _global_lock = threading.Lock()
    _global: "BudgetTracker | None" = None

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: dict[str, BudgetRow] = {}
        self._ledger_path = lab_data_home() / "budgets.jsonl"
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def global_instance(cls) -> "BudgetTracker":
        with cls._global_lock:
            if cls._global is None:
                cls._global = cls()
            return cls._global

    def configure(self, project_id: str, budget_usd: float) -> None:
        with self._lock:
            self._rows[project_id] = BudgetRow(project_id=project_id, budget_usd=budget_usd)

    def record_choice(self, project_id: str, decision: Any) -> None:
        with self._lock:
            row = self._rows.get(project_id) or BudgetRow(project_id=project_id, budget_usd=50.0)
            row.decisions.append({"model": decision.model, "tier": decision.tier})
            self._rows[project_id] = row

    def record_spend(self, project_id: str, *, usd: float, model: str | None = None) -> float:
        with self._lock:
            row = self._rows.get(project_id) or BudgetRow(project_id=project_id, budget_usd=50.0)
            row.spent_usd += float(usd)
            self._rows[project_id] = row
            self._append_ledger({
                "project_id": project_id,
                "delta_usd": float(usd),
                "spent_usd": row.spent_usd,
                "budget_usd": row.budget_usd,
                "model": model,
            })
            return row.spent_usd

    def enforce(self, project_id: str) -> None:
        with self._lock:
            row = self._rows.get(project_id)
            if row and row.spent_usd > row.budget_usd:
                raise BudgetExhausted(
                    f"project {project_id!r} spent {row.spent_usd:.2f} > budget {row.budget_usd:.2f}"
                )

    def remaining(self, project_id: str) -> float:
        with self._lock:
            row = self._rows.get(project_id)
            if row is None:
                return float("inf")
            return max(0.0, row.budget_usd - row.spent_usd)

    def _append_ledger(self, entry: dict[str, Any]) -> None:
        try:
            with self._ledger_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except Exception:
            log.debug("budget ledger write failed", exc_info=True)
