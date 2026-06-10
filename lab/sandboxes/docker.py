"""Docker container sandbox.

Spawns a disposable container with the command, mounts the workspace
read-write only when the request's risk class allows it, and tears the
container down on exit.

Requires `docker` Python SDK + a running daemon. Degrades to a structured
error when either is missing — the controller will promote to SSH/microvm.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

from lab.sandboxes.controller import SandboxRequest, SandboxResult, SandboxTier

log = logging.getLogger("lab.sandboxes.docker")


class DockerSandbox:
    def __init__(self, image: str | None = None) -> None:
        self.image = image or os.environ.get("ECC_LAB_SANDBOX_IMAGE", "ghcr.io/ecc-lab/runner:latest")

    async def run(self, req: SandboxRequest) -> SandboxResult:
        started = time.time()
        try:
            import docker  # type: ignore
        except Exception:
            return SandboxResult(
                tier=SandboxTier.DOCKER,
                exit_code=1,
                stdout="",
                stderr="docker SDK not installed; tier unavailable",
                wall_seconds=0.0,
                error="docker SDK missing",
            )

        try:
            client = docker.from_env()
        except Exception as exc:
            return SandboxResult(
                tier=SandboxTier.DOCKER,
                exit_code=1,
                stdout="",
                stderr=f"docker daemon unavailable: {exc!s}",
                wall_seconds=0.0,
                error="docker daemon unavailable",
            )

        mounts = []
        if req.cwd:
            mounts.append({"Source": req.cwd, "Target": "/work", "Type": "bind", "ReadOnly": req.risk_class == "high"})

        loop = asyncio.get_event_loop()
        try:
            container = await loop.run_in_executor(
                None,
                lambda: client.containers.run(
                    self.image,
                    command=req.command,
                    detach=True,
                    network_disabled=req.risk_class != "low",
                    mem_limit="2g",
                    cpu_quota=200000,
                    working_dir="/work" if req.cwd else None,
                    environment=req.env,
                    volumes={
                        m["Source"]: {"bind": m["Target"], "mode": "ro" if m["ReadOnly"] else "rw"}
                        for m in mounts
                    },
                ),
            )
            await loop.run_in_executor(None, lambda: container.wait(timeout=req.timeout_sec))
            logs = await loop.run_in_executor(None, lambda: container.logs().decode("utf-8", "replace"))
            attrs = await loop.run_in_executor(None, lambda: container.attrs)
            await loop.run_in_executor(None, container.remove)
            exit_code = (attrs.get("State") or {}).get("ExitCode", 1)
            return SandboxResult(
                tier=SandboxTier.DOCKER,
                exit_code=exit_code,
                stdout=logs,
                stderr="",
                wall_seconds=time.time() - started,
            )
        except Exception as exc:
            log.exception("docker run failed")
            return SandboxResult(
                tier=SandboxTier.DOCKER,
                exit_code=1,
                stdout="",
                stderr=str(exc),
                wall_seconds=time.time() - started,
                error=str(exc),
            )
