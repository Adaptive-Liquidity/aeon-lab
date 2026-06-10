"""Claude Code SDK invoker.

Shells out to `claude` (Claude Code CLI) with a prepared prompt bundle.
Uses non-interactive `-p` mode and parses the JSON output.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time

from lab.bridge.agent_dispatcher import StagePrompt, StageResult

log = logging.getLogger("lab.invokers.claude_code_sdk")


def _build_message(prompt: StagePrompt) -> str:
    parts = ["Run as the configured agent. Stage context follows."]
    if prompt.agent_path.exists():
        parts.append(prompt.agent_path.read_text(encoding="utf-8"))
    for skill in prompt.skill_paths:
        if skill.exists():
            parts.append(f"\n## Skill: {skill.parent.name}\n" + skill.read_text(encoding="utf-8"))
    parts.append(
        "\n## Stage inputs (JSON)\n```json\n"
        + json.dumps(prompt.inputs, indent=2, default=str)
        + "\n```\n"
    )
    return "\n\n".join(parts)


async def invoke(prompt: StagePrompt) -> StageResult:
    started = time.time()
    msg = _build_message(prompt)
    cmd = ["claude", "-p", "--output-format", "json"]
    env = {**os.environ, "CLAUDE_NONINTERACTIVE": "1"}
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
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
            error="claude CLI not on PATH; install Claude Code first",
        )
    if proc.returncode != 0:
        return StageResult(
            track=prompt.track,
            stage=prompt.stage,
            project_id=prompt.project_id,
            outputs={},
            agent=prompt.agent_path.stem,
            skills_injected=[p.parent.name for p in prompt.skill_paths],
            error=f"claude exit={proc.returncode}: {stderr.decode('utf-8', 'replace')[:400]}",
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
        cost_usd=float(parsed.get("total_cost_usd", 0.0) or 0.0),
        latency_ms=int((time.time() - started) * 1000),
        confidence=0.7,
    )
