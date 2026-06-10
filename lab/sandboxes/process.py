"""Local subprocess sandbox.

Fastest tier; provides no real isolation but enforces a hard timeout.
Use for trusted, deterministic build/test commands.
"""

from __future__ import annotations

import asyncio
import os
import time

from lab.sandboxes.controller import SandboxRequest, SandboxResult, SandboxTier


class ProcessSandbox:
    async def run(self, req: SandboxRequest) -> SandboxResult:
        started = time.time()
        env = {**os.environ, **(req.env or {})}
        try:
            proc = await asyncio.create_subprocess_exec(
                *req.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=req.cwd,
                env=env,
            )
        except FileNotFoundError as exc:
            return SandboxResult(
                tier=SandboxTier.PROCESS,
                exit_code=127,
                stdout="",
                stderr=str(exc),
                wall_seconds=0.0,
                error="binary not on PATH",
            )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=req.timeout_sec
            )
        except asyncio.TimeoutError:
            proc.kill()
            return SandboxResult(
                tier=SandboxTier.PROCESS,
                exit_code=124,
                stdout="",
                stderr=f"timeout after {req.timeout_sec}s",
                wall_seconds=time.time() - started,
                error="timeout",
            )
        return SandboxResult(
            tier=SandboxTier.PROCESS,
            exit_code=proc.returncode or 0,
            stdout=stdout_b.decode("utf-8", "replace"),
            stderr=stderr_b.decode("utf-8", "replace"),
            wall_seconds=time.time() - started,
        )
