"""Managed-remote SSH sandbox.

Targets a pre-provisioned VM described by the env vars:
  ECC_LAB_SSH_HOST, ECC_LAB_SSH_USER, ECC_LAB_SSH_KEY

Used for medium-risk workloads where a fresh disposable container is
overkill but a process tier is too dangerous.
"""

from __future__ import annotations

import logging
import os
import time

from lab.sandboxes.controller import SandboxRequest, SandboxResult, SandboxTier

log = logging.getLogger("lab.sandboxes.ssh")


class SshSandbox:
    async def run(self, req: SandboxRequest) -> SandboxResult:
        started = time.time()
        host = os.environ.get("ECC_LAB_SSH_HOST")
        if not host:
            return SandboxResult(
                tier=SandboxTier.SSH,
                exit_code=1,
                stdout="",
                stderr="ECC_LAB_SSH_HOST not set; tier unavailable",
                wall_seconds=0.0,
                error="ssh tier unconfigured",
            )

        try:
            import asyncssh  # type: ignore
        except Exception:
            return SandboxResult(
                tier=SandboxTier.SSH,
                exit_code=1,
                stdout="",
                stderr="asyncssh not installed; tier unavailable",
                wall_seconds=0.0,
                error="asyncssh missing",
            )

        try:
            async with asyncssh.connect(
                host,
                username=os.environ.get("ECC_LAB_SSH_USER", os.getlogin()),
                client_keys=[os.environ["ECC_LAB_SSH_KEY"]] if "ECC_LAB_SSH_KEY" in os.environ else None,
                known_hosts=None,
            ) as conn:
                result = await conn.run(" ".join(req.command), timeout=req.timeout_sec)
                return SandboxResult(
                    tier=SandboxTier.SSH,
                    exit_code=int(result.exit_status or 0),
                    stdout=str(result.stdout),
                    stderr=str(result.stderr),
                    wall_seconds=time.time() - started,
                )
        except Exception as exc:
            log.exception("ssh sandbox failed")
            return SandboxResult(
                tier=SandboxTier.SSH,
                exit_code=1,
                stdout="",
                stderr=str(exc),
                wall_seconds=time.time() - started,
                error=str(exc),
            )
