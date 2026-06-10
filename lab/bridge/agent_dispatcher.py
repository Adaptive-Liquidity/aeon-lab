"""Route a pipeline stage to an ECC or Claw agent invocation.

A `StageRequest` carries the stage name, input artifacts, and prior context.
The dispatcher resolves the primary agent + injected skills via the stage
skill map and invokes the underlying harness — Claude Code, Codex, OpenCode,
or the local researchclaw runtime — through a single async interface.

This is intentionally thin: it does not own the loop (that's LangGraph) and
it does not own retry policy (that's Temporal). It just packages the right
prompt, the right tools, and the right model and hands the result back.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

from lab.bridge.stage_skill_map import (
    StageMapping,
    cost_tier,
    is_quality_gate,
    is_security_trigger_eligible,
    resolve_agent_for_stage,
    resolve_skills_for_stage,
)

log = logging.getLogger("lab.bridge.dispatcher")


@dataclass
class StageRequest:
    track: str  # research | engineering
    stage: str
    project_id: str
    inputs: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    prefer_fallback: bool = False
    extra_skills: tuple[str, ...] = ()


@dataclass
class StageResult:
    track: str
    stage: str
    project_id: str
    outputs: dict[str, Any]
    agent: str
    skills_injected: list[str]
    model_used: str | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None
    confidence: float | None = None
    rollback_requested: bool = False
    error: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)


# An AgentInvoker is any async callable that takes a fully-prepared prompt
# bundle and returns a StageResult. The dispatcher does not care whether
# the invoker is Claude Code SDK, Codex SDK, OpenCode, or researchclaw's
# in-process LLM client — we expose one Protocol-ish callable.
AgentInvoker = Callable[["StagePrompt"], Awaitable[StageResult]]


@dataclass
class StagePrompt:
    track: str
    stage: str
    project_id: str
    agent_path: Path
    skill_paths: list[Path]
    inputs: dict[str, Any]
    context: dict[str, Any]
    cost_tier: str
    quality_gate_required: bool
    security_trigger_eligible: bool


class AgentDispatcher:
    """Resolves the agent + skills for a stage and dispatches to an invoker."""

    def __init__(
        self,
        invoker: AgentInvoker,
        *,
        on_dispatch: Callable[[StagePrompt], None] | None = None,
    ) -> None:
        self._invoker = invoker
        self._on_dispatch = on_dispatch

    async def dispatch(self, request: StageRequest) -> StageResult:
        prompt = self._build_prompt(request)
        if self._on_dispatch is not None:
            try:
                self._on_dispatch(prompt)
            except Exception:  # observers must not break dispatch
                log.exception("on_dispatch observer failed")
        log.info(
            "dispatch stage=%s/%s agent=%s skills=%d tier=%s",
            request.track,
            request.stage,
            prompt.agent_path.name,
            len(prompt.skill_paths),
            prompt.cost_tier,
        )
        return await self._invoker(prompt)

    def _build_prompt(self, request: StageRequest) -> StagePrompt:
        track = request.track
        stage = request.stage
        agent_path = resolve_agent_for_stage(
            track, stage, prefer_fallback=request.prefer_fallback
        )
        skills = list(resolve_skills_for_stage(track, stage))
        for extra in request.extra_skills:
            extra_path = agent_path.parent.parent / "skills" / extra / "SKILL.md"
            if extra_path.exists() and extra_path not in skills:
                skills.append(extra_path)
        return StagePrompt(
            track=track,
            stage=stage,
            project_id=request.project_id,
            agent_path=agent_path,
            skill_paths=skills,
            inputs=request.inputs,
            context=request.context,
            cost_tier=cost_tier(track, stage),
            quality_gate_required=is_quality_gate(track, stage),
            security_trigger_eligible=is_security_trigger_eligible(track, stage),
        )


async def default_invoker_unavailable(prompt: StagePrompt) -> StageResult:
    """Failure-mode invoker used until a real harness is bound."""
    return StageResult(
        track=prompt.track,
        stage=prompt.stage,
        project_id=prompt.project_id,
        outputs={},
        agent=prompt.agent_path.stem,
        skills_injected=[p.parent.name for p in prompt.skill_paths],
        error=(
            "no AgentInvoker bound; configure one of: claude-code-sdk, "
            "codex-sdk, opencode, researchclaw_inproc"
        ),
    )
