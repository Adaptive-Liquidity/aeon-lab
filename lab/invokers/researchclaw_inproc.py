"""In-process researchclaw invoker.

Replaces the bulk of Claw-AI-Lab's monolithic `services/agent_bridge.py`
(147KB of state-machine + dispatch logic) by exposing a single per-stage
async entrypoint. Temporal owns the state machine; this module just runs
one stage with the configured Claw LLM client.

The implementation is intentionally tolerant: if the researchclaw package
is not vendored or bridged, we fall back to a structured error rather
than crashing the worker.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from lab.bridge.agent_dispatcher import StagePrompt, StageResult
from lab.model_router.router import route_model

log = logging.getLogger("lab.invokers.researchclaw_inproc")


def _load_claw_client():
    try:
        from lab.researchclaw.llm.client import LlmClient  # type: ignore
        return LlmClient
    except Exception:
        try:
            from researchclaw.llm.client import LlmClient  # type: ignore
            return LlmClient
        except Exception:
            log.warning("researchclaw LlmClient unavailable; using stub")
            return None


def _build_system_prompt(prompt: StagePrompt) -> str:
    """Concatenate the agent definition and skill bodies into one prompt."""
    chunks: list[str] = []
    if prompt.agent_path.exists():
        chunks.append(f"# Agent: {prompt.agent_path.stem}\n" + prompt.agent_path.read_text(encoding="utf-8"))
    for skill in prompt.skill_paths:
        if skill.exists():
            chunks.append(f"\n# Skill: {skill.parent.name}\n" + skill.read_text(encoding="utf-8"))
    chunks.append(
        "\n# Stage Context\n"
        f"- track: {prompt.track}\n"
        f"- stage: {prompt.stage}\n"
        f"- project_id: {prompt.project_id}\n"
        f"- cost_tier: {prompt.cost_tier}\n"
        f"- quality_gate_required: {prompt.quality_gate_required}\n"
        f"- security_trigger_eligible: {prompt.security_trigger_eligible}\n"
    )
    return "".join(chunks)


def _format_inputs(prompt: StagePrompt) -> str:
    import json

    return (
        "Stage inputs (JSON):\n```json\n"
        + json.dumps(prompt.inputs, indent=2, default=str)
        + "\n```\n\nProduce the artifacts declared in the stage contract."
    )


async def invoke(prompt: StagePrompt) -> StageResult:
    started = time.time()
    LlmClient = _load_claw_client()
    if LlmClient is None:
        return StageResult(
            track=prompt.track,
            stage=prompt.stage,
            project_id=prompt.project_id,
            outputs={},
            agent=prompt.agent_path.stem,
            skills_injected=[p.parent.name for p in prompt.skill_paths],
            error="researchclaw LlmClient not importable; vendor Claw-AI-Lab first",
        )

    model_decision = route_model(
        stage=prompt.stage,
        track=prompt.track,
        cost_tier=prompt.cost_tier,
    )

    system = _build_system_prompt(prompt)
    user = _format_inputs(prompt)

    try:
        client = LlmClient(model=model_decision.model)
        completion = await asyncio.to_thread(
            client.complete, system=system, user=user, temperature=0.4
        )
        text = getattr(completion, "text", str(completion))
        usage = getattr(completion, "usage", None)
        cost = _estimate_cost(usage, model_decision)
    except Exception as exc:
        log.exception("LLM call failed for %s/%s", prompt.track, prompt.stage)
        return StageResult(
            track=prompt.track,
            stage=prompt.stage,
            project_id=prompt.project_id,
            outputs={},
            agent=prompt.agent_path.stem,
            skills_injected=[p.parent.name for p in prompt.skill_paths],
            error=f"llm error: {exc!s}",
            model_used=model_decision.model,
            latency_ms=int((time.time() - started) * 1000),
        )

    return StageResult(
        track=prompt.track,
        stage=prompt.stage,
        project_id=prompt.project_id,
        outputs={"completion": text},
        agent=prompt.agent_path.stem,
        skills_injected=[p.parent.name for p in prompt.skill_paths],
        model_used=model_decision.model,
        cost_usd=cost,
        latency_ms=int((time.time() - started) * 1000),
        confidence=_heuristic_confidence(text),
    )


def _estimate_cost(usage: Any, model_decision: Any) -> float:
    if usage is None:
        return 0.0
    try:
        in_tok = getattr(usage, "input_tokens", 0) or 0
        out_tok = getattr(usage, "output_tokens", 0) or 0
        return (
            in_tok * model_decision.cost_in_per_mtok / 1_000_000
            + out_tok * model_decision.cost_out_per_mtok / 1_000_000
        )
    except Exception:
        return 0.0


def _heuristic_confidence(text: str) -> float:
    if not text:
        return 0.0
    length_score = min(1.0, len(text) / 800)
    refuses = any(
        marker in text.lower() for marker in ("i cannot", "i can't", "as an ai")
    )
    if refuses:
        return 0.15
    return 0.55 + 0.4 * length_score
