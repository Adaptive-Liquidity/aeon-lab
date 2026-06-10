"""Map Claw pipeline stages to concrete ECC skill paths and ECC agent names.

Claw's own `metaclaw_bridge/stage_skill_map.py` references generic skill names
("hypothesis-formulation", "academic-writing-structure", etc.). ECC ships 261
concrete skills under `skills/`. This module resolves each Claw stage to the
ECC skills that should be injected and the primary/fallback ECC agent that
runs the stage.

The map is intentionally explicit. Adding a new stage means adding an entry
here; the orchestrator will refuse to run a stage with no mapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lab import ECC_ROOT

SKILLS_DIR = ECC_ROOT / "skills"
AGENTS_DIR = ECC_ROOT / "agents"


@dataclass(frozen=True)
class StageMapping:
    """How a single pipeline stage maps onto the ECC agent/skill fabric."""

    stage: str
    primary_agent: str
    fallback_agents: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    quality_gate_required: bool = False
    security_trigger_eligible: bool = False
    cost_tier: str = "standard"  # cheap | standard | premium

    def skill_paths(self) -> list[Path]:
        return [SKILLS_DIR / s / "SKILL.md" for s in self.skills]

    def agent_path(self, name: str | None = None) -> Path:
        return AGENTS_DIR / f"{name or self.primary_agent}.md"


# ---------------------------------------------------------------------------
# Research pipeline (Claw 26-stage) — Phase A..H
# ---------------------------------------------------------------------------

RESEARCH_STAGE_MAP: dict[str, StageMapping] = {
    "topic_init": StageMapping(
        stage="topic_init",
        primary_agent="planner",
        fallback_agents=("code-explorer", "architect"),
        skills=("intent-driven-development", "product-capability"),
        cost_tier="cheap",
    ),
    "problem_decompose": StageMapping(
        stage="problem_decompose",
        primary_agent="planner",
        fallback_agents=("architect",),
        skills=("blueprint", "plan-orchestrate", "recursive-decision-ledger"),
        cost_tier="standard",
    ),
    "search_strategy": StageMapping(
        stage="search_strategy",
        primary_agent="docs-lookup",
        skills=(
            "scientific-thinking-literature-review",
            "exa-search",
            "deep-research",
        ),
        cost_tier="cheap",
    ),
    "literature_collect": StageMapping(
        stage="literature_collect",
        primary_agent="docs-lookup",
        skills=(
            "scientific-db-pubmed-database",
            "scientific-db-uspto-database",
            "exa-search",
            "deep-research",
        ),
        cost_tier="cheap",
    ),
    "literature_screen": StageMapping(
        stage="literature_screen",
        primary_agent="mle-reviewer",
        fallback_agents=("code-reviewer",),
        skills=("scientific-thinking-scholar-evaluation",),
        quality_gate_required=True,
        cost_tier="standard",
    ),
    "knowledge_extract": StageMapping(
        stage="knowledge_extract",
        primary_agent="docs-lookup",
        skills=("scientific-pkg-gget", "scientific-thinking-literature-review"),
        cost_tier="cheap",
    ),
    "synthesis": StageMapping(
        stage="synthesis",
        primary_agent="architect",
        fallback_agents=("mle-reviewer",),
        skills=("mle-workflow", "recursive-decision-ledger"),
        cost_tier="standard",
    ),
    "hypothesis_gen": StageMapping(
        stage="hypothesis_gen",
        primary_agent="architect",
        fallback_agents=("mle-reviewer",),
        skills=("mle-workflow", "recursive-decision-ledger"),
        cost_tier="premium",
    ),
    "experiment_design": StageMapping(
        stage="experiment_design",
        primary_agent="architect",
        fallback_agents=("code-architect", "mle-reviewer"),
        skills=("mle-workflow", "pytorch-patterns", "eval-harness"),
        quality_gate_required=True,
        cost_tier="premium",
    ),
    "codebase_search": StageMapping(
        stage="codebase_search",
        primary_agent="code-explorer",
        skills=("repo-scan", "search-first"),
        cost_tier="cheap",
    ),
    "code_generation": StageMapping(
        stage="code_generation",
        primary_agent="tdd-guide",
        fallback_agents=("build-error-resolver", "python-reviewer"),
        skills=(
            "tdd-workflow",
            "python-patterns",
            "pytorch-patterns",
            "mle-workflow",
        ),
        security_trigger_eligible=True,
        cost_tier="premium",
    ),
    "sanity_check": StageMapping(
        stage="sanity_check",
        primary_agent="build-error-resolver",
        fallback_agents=("python-reviewer",),
        skills=("python-testing", "tdd-workflow"),
        cost_tier="cheap",
    ),
    "resource_planning": StageMapping(
        stage="resource_planning",
        primary_agent="planner",
        skills=("benchmark-optimization-loop",),
        cost_tier="cheap",
    ),
    "experiment_run": StageMapping(
        stage="experiment_run",
        primary_agent="mle-reviewer",
        fallback_agents=("performance-optimizer",),
        skills=("mle-workflow", "benchmark-optimization-loop"),
        cost_tier="standard",
    ),
    "iterative_refine": StageMapping(
        stage="iterative_refine",
        primary_agent="performance-optimizer",
        fallback_agents=("mle-reviewer", "tdd-guide"),
        skills=(
            "benchmark-optimization-loop",
            "agent-introspection-debugging",
            "mle-workflow",
        ),
        cost_tier="premium",
    ),
    "result_analysis": StageMapping(
        stage="result_analysis",
        primary_agent="mle-reviewer",
        fallback_agents=("code-reviewer",),
        skills=("mle-workflow", "regex-vs-llm-structured-text"),
        cost_tier="standard",
    ),
    "research_decision": StageMapping(
        stage="research_decision",
        primary_agent="architect",
        fallback_agents=("mle-reviewer",),
        skills=("recursive-decision-ledger", "council"),
        cost_tier="standard",
    ),
    "knowledge_summary": StageMapping(
        stage="knowledge_summary",
        primary_agent="doc-updater",
        skills=("knowledge-ops",),
        cost_tier="cheap",
    ),
    "paper_outline": StageMapping(
        stage="paper_outline",
        primary_agent="marketing-agent",
        fallback_agents=("doc-updater",),
        skills=("article-writing", "brand-voice"),
        cost_tier="standard",
    ),
    "paper_draft": StageMapping(
        stage="paper_draft",
        primary_agent="marketing-agent",
        fallback_agents=("doc-updater",),
        skills=("article-writing", "brand-voice"),
        cost_tier="premium",
    ),
    "peer_review": StageMapping(
        stage="peer_review",
        primary_agent="code-reviewer",
        fallback_agents=("mle-reviewer",),
        skills=("scientific-thinking-scholar-evaluation", "santa-method"),
        cost_tier="standard",
    ),
    "paper_revision": StageMapping(
        stage="paper_revision",
        primary_agent="marketing-agent",
        fallback_agents=("doc-updater",),
        skills=("article-writing", "brand-voice"),
        cost_tier="standard",
    ),
    "quality_gate": StageMapping(
        stage="quality_gate",
        primary_agent="code-reviewer",
        fallback_agents=("security-reviewer", "mle-reviewer"),
        skills=(
            "eval-harness",
            "gan-style-harness",
            "santa-method",
            "gateguard",
        ),
        quality_gate_required=True,
        cost_tier="premium",
    ),
    "knowledge_archive": StageMapping(
        stage="knowledge_archive",
        primary_agent="doc-updater",
        skills=("knowledge-ops",),
        cost_tier="cheap",
    ),
    "export_publish": StageMapping(
        stage="export_publish",
        primary_agent="doc-updater",
        skills=("knowledge-ops",),
        cost_tier="cheap",
    ),
    "citation_verify": StageMapping(
        stage="citation_verify",
        primary_agent="security-reviewer",
        fallback_agents=("code-reviewer",),
        skills=("gateguard", "scientific-thinking-scholar-evaluation"),
        cost_tier="cheap",
    ),
}


# ---------------------------------------------------------------------------
# Engineering pipeline (ECC orch-pipeline 6-phase)
# ---------------------------------------------------------------------------

ENGINEERING_STAGE_MAP: dict[str, StageMapping] = {
    "intake": StageMapping(
        stage="intake",
        primary_agent="code-explorer",
        skills=("intent-driven-development", "product-capability"),
        cost_tier="cheap",
    ),
    "research_reuse": StageMapping(
        stage="research_reuse",
        primary_agent="code-explorer",
        fallback_agents=("docs-lookup",),
        skills=("search-first", "documentation-lookup", "exa-search", "repo-scan"),
        cost_tier="cheap",
    ),
    "plan": StageMapping(
        stage="plan",
        primary_agent="planner",
        fallback_agents=("architect", "code-architect"),
        skills=("blueprint", "plan-orchestrate", "product-capability"),
        quality_gate_required=True,
        cost_tier="standard",
    ),
    "scaffold": StageMapping(
        stage="scaffold",
        primary_agent="code-architect",
        fallback_agents=("planner",),
        skills=("tdd-workflow",),
        cost_tier="standard",
    ),
    "implement": StageMapping(
        stage="implement",
        primary_agent="tdd-guide",
        fallback_agents=("build-error-resolver",),
        skills=("tdd-workflow",),
        security_trigger_eligible=True,
        cost_tier="premium",
    ),
    "review": StageMapping(
        stage="review",
        primary_agent="code-reviewer",
        fallback_agents=("security-reviewer",),
        skills=(
            "eval-harness",
            "gan-style-harness",
            "santa-method",
            "gateguard",
            "security-review",
        ),
        quality_gate_required=True,
        cost_tier="standard",
    ),
    "commit": StageMapping(
        stage="commit",
        primary_agent="code-reviewer",
        skills=("git-workflow",),
        cost_tier="cheap",
    ),
}


# ---------------------------------------------------------------------------
# Combined view
# ---------------------------------------------------------------------------

LAB_STAGE_SKILL_MAP: dict[str, dict[str, StageMapping]] = {
    "research": RESEARCH_STAGE_MAP,
    "engineering": ENGINEERING_STAGE_MAP,
}


def resolve_skills_for_stage(track: str, stage: str) -> list[Path]:
    """Return the absolute paths of all ECC skill SKILL.md files to inject.

    Raises ValueError if the stage is unknown — never silently swallow a
    missing mapping; we want loud failure during pipeline build.
    """
    mapping = _lookup(track, stage)
    return mapping.skill_paths()


def resolve_agent_for_stage(track: str, stage: str, *, prefer_fallback: bool = False) -> Path:
    """Return the absolute path of the ECC agent that runs this stage."""
    mapping = _lookup(track, stage)
    if prefer_fallback and mapping.fallback_agents:
        return mapping.agent_path(mapping.fallback_agents[0])
    return mapping.agent_path()


def is_quality_gate(track: str, stage: str) -> bool:
    return _lookup(track, stage).quality_gate_required


def is_security_trigger_eligible(track: str, stage: str) -> bool:
    return _lookup(track, stage).security_trigger_eligible


def cost_tier(track: str, stage: str) -> str:
    return _lookup(track, stage).cost_tier


def _lookup(track: str, stage: str) -> StageMapping:
    track_map = LAB_STAGE_SKILL_MAP.get(track)
    if track_map is None:
        raise ValueError(f"unknown track: {track!r}; expected research|engineering")
    mapping = track_map.get(stage)
    if mapping is None:
        raise ValueError(f"unmapped stage {stage!r} for track {track!r}")
    return mapping
