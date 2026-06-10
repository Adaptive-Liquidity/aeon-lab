"""Mock invoker for tests and dry-runs.

Echoes the prompt structure back as a successful StageResult with a fixed
confidence. Use it as a smoke harness while bringing up new stages or
when the real harness is unavailable.
"""

from __future__ import annotations

from lab.bridge.agent_dispatcher import StagePrompt, StageResult


async def invoke(prompt: StagePrompt) -> StageResult:
    return StageResult(
        track=prompt.track,
        stage=prompt.stage,
        project_id=prompt.project_id,
        outputs={
            "_mock": True,
            "inputs_echo": prompt.inputs,
        },
        agent=prompt.agent_path.stem,
        skills_injected=[p.parent.name for p in prompt.skill_paths],
        model_used="mock-model",
        cost_usd=0.0,
        latency_ms=1,
        confidence=0.9,
    )
