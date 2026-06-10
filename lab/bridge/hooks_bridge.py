"""Emit Claw pipeline stage transitions into ECC's hooks system.

ECC ships a rich hook surface (`hooks/hooks.json`) covering memory
persistence, continuous-learning-v2, session adapters, etc. The lab fires
each Temporal activity start/finish, each quality-gate decision, and each
rollback into that hook system so the existing automations work without
modification.

Two emission paths are supported:

  1. **In-process Python** — when ECC's hook runner is loaded as a library.
     We invoke the same script entrypoints `hooks/` defines for each event.
  2. **Spawn subprocess** — falls back to `node scripts/hooks/<runner>.js`
     with a JSON event on stdin when the in-proc binding is unavailable
     (which is the default on Windows without bun/tsx).

Events are also appended to a JSONL stream under
`{lab_data_home}/events.jsonl` so the dashboard's WebSocket can tail them.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lab import ECC_ROOT, lab_data_home

log = logging.getLogger("lab.bridge.hooks")


@dataclass
class StageEvent:
    project_id: str
    track: str           # research | engineering
    stage: str
    event: str           # started | succeeded | failed | gate_blocked | rollback
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "lab.stage_event",
            "project_id": self.project_id,
            "track": self.track,
            "stage": self.stage,
            "event": self.event,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


_HOOKS_DEFINITION = ECC_ROOT / "hooks" / "hooks.json"
_HOOKS_DIR = ECC_ROOT / "scripts" / "hooks"


class HooksBridge:
    """Routes lab stage events through ECC's hook system + event log."""

    def __init__(
        self,
        *,
        event_log_path: Path | None = None,
        invoke_hooks: bool | None = None,
    ) -> None:
        self.event_log_path = event_log_path or (lab_data_home() / "events.jsonl")
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        if invoke_hooks is None:
            invoke_hooks = os.environ.get("ECC_LAB_INVOKE_HOOKS", "1") == "1"
        self.invoke_hooks = invoke_hooks
        self._lock = asyncio.Lock()

    async def emit(self, event: StageEvent) -> None:
        async with self._lock:
            await asyncio.to_thread(self._append_event_log, event)
        if self.invoke_hooks:
            await self._invoke_hooks(event)

    def _append_event_log(self, event: StageEvent) -> None:
        with self.event_log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.to_dict()) + "\n")

    async def _invoke_hooks(self, event: StageEvent) -> None:
        runner = _HOOKS_DIR / "lab-event-router.js"
        if not runner.exists():
            return
        try:
            await asyncio.to_thread(
                self._spawn_hook_runner, runner, event.to_dict()
            )
        except Exception:
            log.exception("hook runner failed for event=%s", event.event)

    @staticmethod
    def _spawn_hook_runner(runner: Path, payload: dict[str, Any]) -> None:
        try:
            subprocess.run(
                ["node", str(runner)],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                timeout=15,
            )
        except FileNotFoundError:
            log.debug("node not on PATH; skipping hook runner")
        except subprocess.TimeoutExpired:
            log.warning("hook runner timed out")


_default_bridge: HooksBridge | None = None


def default_bridge() -> HooksBridge:
    global _default_bridge
    if _default_bridge is None:
        _default_bridge = HooksBridge()
    return _default_bridge


async def emit_stage_event(
    project_id: str,
    track: str,
    stage: str,
    event: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Convenience wrapper. Most callers should use this."""
    await default_bridge().emit(
        StageEvent(
            project_id=project_id,
            track=track,
            stage=stage,
            event=event,
            payload=payload or {},
        )
    )
