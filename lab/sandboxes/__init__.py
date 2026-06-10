"""Tiered execution sandboxes.

Five tiers, in increasing isolation and cost:

  process     — local subprocess (fastest, least safe)
  docker      — disposable container
  ssh         — managed remote VM
  microvm     — firecracker-managed snapshot VM
  cloud-burst — provider GPU spot (RunPod / Modal / Together)

The controller picks a tier based on the stage's `cost_tier`, declared
risk class (touches network / writes filesystem), and current load.
"""

from lab.sandboxes.controller import (
    SandboxController,
    SandboxRequest,
    SandboxResult,
    SandboxTier,
    select_tier,
)

__all__ = [
    "SandboxController",
    "SandboxRequest",
    "SandboxResult",
    "SandboxTier",
    "select_tier",
]
