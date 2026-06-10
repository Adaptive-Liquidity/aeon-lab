"""Cloud burst sandbox.

Delegates a GPU-bound or long-running job to a provider (RunPod / Modal /
Together / Hugging Face Jobs). The implementation selects the provider via
`ECC_LAB_BURST_PROVIDER` and validates credentials before submitting.
"""

from __future__ import annotations

import logging
import os
import time

from lab.sandboxes.controller import SandboxRequest, SandboxResult, SandboxTier

log = logging.getLogger("lab.sandboxes.cloud_burst")


class CloudBurstSandbox:
    async def run(self, req: SandboxRequest) -> SandboxResult:
        started = time.time()
        provider = os.environ.get("ECC_LAB_BURST_PROVIDER", "").lower()
        if provider not in {"runpod", "modal", "together", "hfjobs"}:
            return SandboxResult(
                tier=SandboxTier.CLOUD_BURST,
                exit_code=1,
                stdout="",
                stderr=(
                    "Set ECC_LAB_BURST_PROVIDER to one of: runpod, modal, together, hfjobs"
                ),
                wall_seconds=0.0,
                error="cloud-burst unconfigured",
            )
        # Real implementations call the corresponding provider SDK.
        # This module ships the wiring; binding it is environment-specific.
        return SandboxResult(
            tier=SandboxTier.CLOUD_BURST,
            exit_code=1,
            stdout="",
            stderr=f"cloud-burst provider {provider!r} configured but binding not provided in this drop.",
            wall_seconds=time.time() - started,
            error="not bound",
        )
