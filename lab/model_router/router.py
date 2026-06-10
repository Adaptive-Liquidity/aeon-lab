"""Cost-aware model selection.

Reads `capabilities.yaml` and resolves a `ModelDecision` given:
  - track + stage (drives stage_preferences)
  - requested cost_tier (cheap | standard | premium)
  - remaining project budget (enforced via BudgetTracker)
  - optional provider preference (e.g. only Anthropic models)

The decision carries the chosen model name and its per-Mtok costs so
upstream invokers can compute spend.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from lab import ECC_ROOT
from lab.model_router.budgets import BudgetTracker

log = logging.getLogger("lab.model_router.router")

_TIER_ORDER = {"cheap": 0, "standard": 1, "premium": 2}


@dataclass
class ModelDecision:
    model: str
    provider: str
    tier: str
    cost_in_per_mtok: float
    cost_out_per_mtok: float
    context_window: int
    rationale: str = ""


@dataclass
class ModelRouter:
    config_path: Path = field(
        default_factory=lambda: ECC_ROOT / "lab" / "model_router" / "capabilities.yaml"
    )
    _models: dict[str, dict[str, Any]] = field(default_factory=dict, init=False)
    _stage_prefs: dict[str, dict[str, list[str]]] = field(default_factory=dict, init=False)
    _fallback: str = field(default="claude-4.5-haiku", init=False)

    def __post_init__(self) -> None:
        self._load()

    def _load(self) -> None:
        if not self.config_path.exists():
            log.warning("model router config missing: %s", self.config_path)
            return
        data = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        self._models = {m["name"]: m for m in data.get("models", [])}
        self._stage_prefs = data.get("stage_preferences", {})
        self._fallback = (data.get("defaults") or {}).get("fallback_model", self._fallback)

    def select(
        self,
        *,
        track: str,
        stage: str,
        cost_tier: str = "standard",
        provider_filter: tuple[str, ...] = (),
        budget_remaining: float | None = None,
    ) -> ModelDecision:
        prefs = self._stage_prefs.get(track, {})
        candidates = list(prefs.get(stage) or prefs.get("default") or [])
        # Append a tier-respecting catalog fallback so we never crash.
        for name, model in self._models.items():
            if name not in candidates:
                candidates.append(name)

        max_tier = _TIER_ORDER[cost_tier]
        for name in candidates:
            model = self._models.get(name)
            if model is None:
                continue
            if provider_filter and model["provider"] not in provider_filter:
                continue
            if _TIER_ORDER.get(model["tier"], 0) > max_tier:
                continue
            return ModelDecision(
                model=name,
                provider=model["provider"],
                tier=model["tier"],
                cost_in_per_mtok=float(model["cost_in_per_mtok"]),
                cost_out_per_mtok=float(model["cost_out_per_mtok"]),
                context_window=int(model.get("context_window", 0)),
                rationale=f"track={track} stage={stage} tier<={cost_tier}",
            )

        # Tier-too-restrictive fallback.
        m = self._models.get(self._fallback)
        if not m:
            return ModelDecision(
                model=self._fallback,
                provider="anthropic",
                tier="standard",
                cost_in_per_mtok=0.8,
                cost_out_per_mtok=4.0,
                context_window=200000,
                rationale="hard fallback (no catalog row)",
            )
        return ModelDecision(
            model=m["name"],
            provider=m["provider"],
            tier=m["tier"],
            cost_in_per_mtok=float(m["cost_in_per_mtok"]),
            cost_out_per_mtok=float(m["cost_out_per_mtok"]),
            context_window=int(m.get("context_window", 0)),
            rationale="fallback chosen",
        )


_default_router: ModelRouter | None = None


def _router() -> ModelRouter:
    global _default_router
    if _default_router is None:
        _default_router = ModelRouter()
    return _default_router


def route_model(
    *,
    track: str,
    stage: str,
    cost_tier: str = "standard",
    provider_filter: tuple[str, ...] = (),
    project_id: str | None = None,
) -> ModelDecision:
    decision = _router().select(
        track=track,
        stage=stage,
        cost_tier=cost_tier,
        provider_filter=provider_filter,
    )
    if project_id:
        BudgetTracker.global_instance().record_choice(project_id, decision)
    return decision
