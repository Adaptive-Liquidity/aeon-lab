"""ECC <-> Claw integration glue.

Bridges the Claw-AI-Lab pipeline (26-stage state machine) to the ECC agent,
skill, command, and hook surfaces.
"""

from lab.bridge.stage_skill_map import (
    LAB_STAGE_SKILL_MAP,
    resolve_skills_for_stage,
    resolve_agent_for_stage,
)
from lab.bridge.agent_dispatcher import AgentDispatcher
from lab.bridge.hooks_bridge import HooksBridge, emit_stage_event

__all__ = [
    "LAB_STAGE_SKILL_MAP",
    "resolve_skills_for_stage",
    "resolve_agent_for_stage",
    "AgentDispatcher",
    "HooksBridge",
    "emit_stage_event",
]
