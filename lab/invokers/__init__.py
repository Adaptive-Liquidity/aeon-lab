"""Agent invokers — one per concrete harness.

An invoker is an async callable `(StagePrompt) -> StageResult` that
dispatches a prepared prompt to a real backend. Three are shipped:

  - researchclaw_inproc: routes to Claw-AI-Lab's existing LLM client in the
    same process (default; closest to legacy Claw behavior).
  - claude_code_sdk: shells out to claude-code via stdio.
  - codex_sdk: shells out to codex via stdio.

The OpenCode and Cursor harnesses are reached via the MCP broker rather
than direct shell-out — they are agent runtimes that already consume MCP.
"""

from __future__ import annotations

import importlib
import logging
from typing import Awaitable, Callable

from lab.bridge.agent_dispatcher import AgentInvoker, default_invoker_unavailable

log = logging.getLogger("lab.invokers")

_REGISTRY: dict[str, str] = {
    "researchclaw_inproc": "lab.invokers.researchclaw_inproc:invoke",
    "claude_code_sdk": "lab.invokers.claude_code_sdk:invoke",
    "codex_sdk": "lab.invokers.codex_sdk:invoke",
    "mock": "lab.invokers.mock:invoke",
}


def load_invoker(name: str) -> AgentInvoker:
    spec = _REGISTRY.get(name)
    if spec is None:
        log.warning("unknown invoker %r; using unavailable fallback", name)
        return default_invoker_unavailable
    module_path, attr = spec.split(":")
    try:
        module = importlib.import_module(module_path)
        return getattr(module, attr)
    except Exception:
        log.exception("failed to load invoker %s; using unavailable fallback", name)
        return default_invoker_unavailable
