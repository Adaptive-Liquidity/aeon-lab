"""ECC + Claw Autonomous Lab.

Unified zero-human autonomous workgroup combining the ECC agent/skill/eval
fabric with the Claw-AI-Lab 26-stage research pipeline, layered with Temporal,
LangGraph, an MCP security broker, tiered sandboxes, cost-aware model routing,
and end-to-end eval + observability + provenance.

The package is a sibling-import bridge to `lab.researchclaw` when Claw-AI-Lab
lives next to the ECC repo; or to a physically-vendored copy under
`lab/researchclaw/` after running `node lab/scripts/vendor-claw.js`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

__version__ = "0.1.0"

_LAB_ROOT = Path(__file__).resolve().parent
_ECC_ROOT = _LAB_ROOT.parent

# Path bridge: if Claw-AI-Lab exists as a sibling under ECC root and has not
# been physically vendored under lab/researchclaw/, expose its researchclaw
# package as `lab.researchclaw` via sys.path so existing Claw imports work.
_VENDORED = _LAB_ROOT / "researchclaw" / "__init__.py"
if not _VENDORED.exists():
    _SIBLING = _ECC_ROOT / "Claw-AI-Lab" / "backend" / "agent"
    if (_SIBLING / "researchclaw" / "__init__.py").exists():
        sys.path.insert(0, str(_SIBLING))

# Expose top-level subsystems for ergonomic imports.
__all__ = [
    "bridge",
    "orchestrator",
    "quality_gates",
    "mcp_broker",
    "model_router",
    "sandboxes",
    "provenance",
    "observability",
    "api",
]

ECC_ROOT = _ECC_ROOT
LAB_ROOT = _LAB_ROOT


def lab_data_home() -> Path:
    """Return the per-user lab data directory (overridable via ECC_LAB_HOME)."""
    home = os.environ.get("ECC_LAB_HOME")
    if home:
        return Path(home).expanduser().resolve()
    return Path.home() / ".ecc" / "lab"
