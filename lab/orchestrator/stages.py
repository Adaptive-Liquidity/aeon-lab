"""Stage enumerations for both lab tracks.

Wraps Claw's 26-stage research pipeline (sourced from
`researchclaw.pipeline.stages.Stage` when vendored) and ECC's 6-phase
engineering pipeline. Kept as plain Enums here so Temporal workflow and
LangGraph code does not require the heavyweight Claw import path during
type-only resolution.
"""

from __future__ import annotations

from enum import Enum


class ResearchStage(str, Enum):
    TOPIC_INIT = "topic_init"
    PROBLEM_DECOMPOSE = "problem_decompose"
    SEARCH_STRATEGY = "search_strategy"
    LITERATURE_COLLECT = "literature_collect"
    LITERATURE_SCREEN = "literature_screen"
    KNOWLEDGE_EXTRACT = "knowledge_extract"
    SYNTHESIS = "synthesis"
    HYPOTHESIS_GEN = "hypothesis_gen"
    EXPERIMENT_DESIGN = "experiment_design"
    CODEBASE_SEARCH = "codebase_search"
    CODE_GENERATION = "code_generation"
    SANITY_CHECK = "sanity_check"
    RESOURCE_PLANNING = "resource_planning"
    EXPERIMENT_RUN = "experiment_run"
    ITERATIVE_REFINE = "iterative_refine"
    RESULT_ANALYSIS = "result_analysis"
    RESEARCH_DECISION = "research_decision"
    KNOWLEDGE_SUMMARY = "knowledge_summary"
    PAPER_OUTLINE = "paper_outline"
    PAPER_DRAFT = "paper_draft"
    PEER_REVIEW = "peer_review"
    PAPER_REVISION = "paper_revision"
    QUALITY_GATE = "quality_gate"
    KNOWLEDGE_ARCHIVE = "knowledge_archive"
    EXPORT_PUBLISH = "export_publish"
    CITATION_VERIFY = "citation_verify"


class EngineeringPhase(str, Enum):
    INTAKE = "intake"
    RESEARCH_REUSE = "research_reuse"
    PLAN = "plan"
    SCAFFOLD = "scaffold"
    IMPLEMENT = "implement"
    REVIEW = "review"
    COMMIT = "commit"


RESEARCH_SEQUENCE: tuple[ResearchStage, ...] = tuple(ResearchStage)
ENGINEERING_SEQUENCE: tuple[EngineeringPhase, ...] = tuple(EngineeringPhase)


# Stages that — under the legacy HITL design — required human approval.
# The lab replaces these with automated quality gates (Phase 2).
LEGACY_HITL_RESEARCH_GATES: frozenset[ResearchStage] = frozenset(
    {
        ResearchStage.LITERATURE_SCREEN,
        ResearchStage.EXPERIMENT_DESIGN,
        ResearchStage.QUALITY_GATE,
    }
)

LEGACY_HITL_ENGINEERING_GATES: frozenset[EngineeringPhase] = frozenset(
    {EngineeringPhase.PLAN, EngineeringPhase.COMMIT}
)


def next_research_stage(current: ResearchStage) -> ResearchStage | None:
    idx = RESEARCH_SEQUENCE.index(current)
    return RESEARCH_SEQUENCE[idx + 1] if idx + 1 < len(RESEARCH_SEQUENCE) else None


def next_engineering_phase(current: EngineeringPhase) -> EngineeringPhase | None:
    idx = ENGINEERING_SEQUENCE.index(current)
    return (
        ENGINEERING_SEQUENCE[idx + 1]
        if idx + 1 < len(ENGINEERING_SEQUENCE)
        else None
    )
