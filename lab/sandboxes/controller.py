"""Sandbox tier picker + dispatcher."""

from __future__ import annotations

import asyncio
import enum
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("lab.sandboxes.controller")


class SandboxTier(str, enum.Enum):
    PROCESS = "process"
    DOCKER = "docker"
    SSH = "ssh"
    MICROVM = "microvm"
    CLOUD_BURST = "cloud-burst"


@dataclass
class SandboxRequest:
    project_id: str
    stage: str
    command: list[str]
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    cost_tier: str = "standard"  # cheap | standard | premium
    risk_class: str = "low"      # low | medium | high (touches net / writes fs)
    requires_gpu: bool = False
    timeout_sec: int = 600
    preferred_tier: SandboxTier | None = None


@dataclass
class SandboxResult:
    tier: SandboxTier
    exit_code: int
    stdout: str
    stderr: str
    wall_seconds: float
    artifacts: dict[str, str] = field(default_factory=dict)
    promoted_from: SandboxTier | None = None
    error: str | None = None


# Promotion rules: if a run at tier T fails with a network-policy or
# filesystem-permission error, try the next tier up.
_PROMOTION_ORDER = (
    SandboxTier.PROCESS,
    SandboxTier.DOCKER,
    SandboxTier.SSH,
    SandboxTier.MICROVM,
    SandboxTier.CLOUD_BURST,
)


def select_tier(req: SandboxRequest) -> SandboxTier:
    if req.preferred_tier is not None:
        return req.preferred_tier
    if req.requires_gpu:
        return SandboxTier.CLOUD_BURST
    if req.risk_class == "high":
        return SandboxTier.MICROVM
    if req.risk_class == "medium":
        return SandboxTier.DOCKER
    if req.cost_tier == "premium":
        return SandboxTier.DOCKER
    return SandboxTier.PROCESS


class SandboxController:
    """Routes a SandboxRequest to the chosen tier executor."""

    def __init__(self) -> None:
        from lab.sandboxes.process import ProcessSandbox
        from lab.sandboxes.docker import DockerSandbox
        from lab.sandboxes.ssh import SshSandbox
        from lab.sandboxes.microvm import MicroVmSandbox
        from lab.sandboxes.cloud_burst import CloudBurstSandbox

        self._executors = {
            SandboxTier.PROCESS: ProcessSandbox(),
            SandboxTier.DOCKER: DockerSandbox(),
            SandboxTier.SSH: SshSandbox(),
            SandboxTier.MICROVM: MicroVmSandbox(),
            SandboxTier.CLOUD_BURST: CloudBurstSandbox(),
        }

    async def run(self, req: SandboxRequest) -> SandboxResult:
        tier = select_tier(req)
        result = await self._executors[tier].run(req)
        # Auto-promotion: if a sandbox refused or hit isolation errors, climb.
        if result.exit_code != 0 and self._should_promote(result):
            higher = self._next_tier(tier)
            if higher is not None:
                log.info("promoting sandbox %s -> %s for %s", tier, higher, req.stage)
                promoted = await self._executors[higher].run(req)
                promoted.promoted_from = tier
                return promoted
        return result

    @staticmethod
    def _should_promote(result: SandboxResult) -> bool:
        markers = (
            "permission denied",
            "operation not permitted",
            "network is unreachable",
            "no such device",
            "isolation",
            "egress denied",
        )
        stderr = (result.stderr or "").lower()
        return any(marker in stderr for marker in markers)

    @staticmethod
    def _next_tier(current: SandboxTier) -> SandboxTier | None:
        try:
            idx = _PROMOTION_ORDER.index(current)
        except ValueError:
            return None
        return _PROMOTION_ORDER[idx + 1] if idx + 1 < len(_PROMOTION_ORDER) else None
