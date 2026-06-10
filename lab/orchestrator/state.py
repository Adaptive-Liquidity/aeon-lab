"""Shared state shapes for workflows and activities.

These dataclasses are passed through Temporal's data converter so they need
to be JSON-friendly (no Path, no datetime — use strings/floats).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProjectBrief:
    project_id: str
    title: str
    description: str
    track: str  # research | engineering
    constraints: dict[str, Any] = field(default_factory=dict)
    budget_usd: float = 50.0
    max_wall_clock_sec: int = 24 * 3600


@dataclass
class StageInvocation:
    project_id: str
    track: str
    stage: str
    inputs: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    prefer_fallback: bool = False
    attempt: int = 1


@dataclass
class StageOutcome:
    project_id: str
    track: str
    stage: str
    outputs: dict[str, Any]
    agent: str
    skills_injected: list[str]
    model_used: str | None = None
    cost_usd: float = 0.0
    latency_ms: int = 0
    confidence: float = 0.0
    rollback_to: str | None = None
    error: str | None = None
    artifact_hashes: list[str] = field(default_factory=list)


@dataclass
class QualityGateVerdict:
    project_id: str
    track: str
    stage: str
    allow: bool
    confidence: float
    eval_score: float
    santa_passed: bool
    gateguard_passed: bool
    council_consensus: str | None
    rollback_to: str | None
    findings: list[str] = field(default_factory=list)
    escalate_to_human: bool = False


@dataclass
class WorkflowState:
    project_id: str
    track: str
    title: str
    description: str
    stage_history: list[str] = field(default_factory=list)
    cost_usd_spent: float = 0.0
    budget_usd: float = 50.0
    artifacts: dict[str, str] = field(default_factory=dict)  # path -> hash
    last_outcome: dict[str, Any] | None = None
    quality_gates: list[dict[str, Any]] = field(default_factory=list)
