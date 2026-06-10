"""Codex SDK invoker.

Shells out to `codex` (OpenAI Codex CLI) in non-interactive exec mode.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time

from lab.bridge.agent_dispatcher import StagePrompt, StageResult

log = logging.getLogger("lab.invokers.codex_sdk")


async def invoke(prompt: StagePrompt) -> StageResult:
    started = time.time()
    msg_parts = []
    if prompt.agent_path.exists():
        msg_parts.append(prompt.agent_path.read_text(encoding="utf-8"))
    for skill in prompt.skill_paths:
        if skill.exists():
            msg_parts.append(skill.read_text(encoding="utf-8"))
    msg_parts.append(json.dumps(prompt.inputs, indent=2, default=str))
    msg = "\n\n".join(msg_parts)

    cmd = ["codex", "exec", "--json", "-"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ.copy(),
        )
        stdout, stderr = await proc.communicate(msg.encode("utf-8"))
    except FileNotFoundError:
        return StageResult(
            track=prompt.track,
            stage=prompt.stage,
            project_id=prompt.project_id,
            outputs={},
            agent=prompt.agent_path.stem,
            skills_injected=[p.parent.name for p in prompt.skill_paths],
            error="codex CLI not on PATH",
        )

    if proc.returncode != 0:
        return StageResult(
            track=prompt.track,
            stage=prompt.stage,
            project_id=prompt.project_id,
            outputs={},
            agent=prompt.agent_path.stem,
            skills_injected=[p.parent.name for p in prompt.skill_paths],
            error=f"codex exit={proc.returncode}: {stderr.decode('utf-8','replace')[:400]}",
            latency_ms=int((time.time() - started) * 1000),
        )

    text = stdout.decode("utf-8", "replace")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = {"raw": text}

    return StageResult(
        track=prompt.track,
        stage=prompt.stage,
        project_id=prompt.project_id,
        outputs=parsed,
        agent=prompt.agent_path.stem,
        skills_injected=[p.parent.name for p in prompt.skill_paths],
        model_used=parsed.get("model"),
        cost_usd=float(parsed.get("cost_usd", 0.0) or 0.0),
        latency_ms=int((time.time() - started) * 1000),
        confidence=0.7,
    )
