"""Firecracker microVM sandbox.

Talks to a local `firecracker-containerd` or `flintlock` API.

This module is a polished stub: it documents the request shape, validates
the configuration, and returns an explanatory error when the supporting
infrastructure is absent. Production deployments wire it to their VM API.
"""

from __future__ import annotations

import logging
import os
import time

from lab.sandboxes.controller import SandboxRequest, SandboxResult, SandboxTier

log = logging.getLogger("lab.sandboxes.microvm")


class MicroVmSandbox:
    async def run(self, req: SandboxRequest) -> SandboxResult:
        started = time.time()
        endpoint = os.environ.get("ECC_LAB_MICROVM_ENDPOINT")
        if not endpoint:
            return SandboxResult(
                tier=SandboxTier.MICROVM,
                exit_code=1,
                stdout="",
                stderr=(
                    "ECC_LAB_MICROVM_ENDPOINT not set. To enable firecracker-tier "
                    "sandboxes, point this at a firecracker-containerd or flintlock API."
                ),
                wall_seconds=0.0,
                error="microvm tier unconfigured",
            )
        # Implementations call out to flintlock REST or firecracker socket here.
        return SandboxResult(
            tier=SandboxTier.MICROVM,
            exit_code=1,
            stdout="",
            stderr="microvm execution not implemented in this drop; bind a flintlock API to enable.",
            wall_seconds=time.time() - started,
            error="not implemented",
        )
