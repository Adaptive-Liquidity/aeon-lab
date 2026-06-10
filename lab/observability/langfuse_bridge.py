"""Langfuse bridge for LLM-specific tracing.

When LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY are set, the bridge emits
generation events for each model call alongside OTel spans.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("lab.observability.langfuse_bridge")


@dataclass
class LangfuseBridge:
    _client: Any = None
    _disabled: bool = False

    @classmethod
    def get(cls) -> "LangfuseBridge":
        instance = cls()
        if not (os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")):
            instance._disabled = True
            return instance
        try:
            from langfuse import Langfuse  # type: ignore

            instance._client = Langfuse(
                public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
                secret_key=os.environ["LANGFUSE_SECRET_KEY"],
                host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
            )
            log.info("Langfuse bridge active")
        except Exception:
            log.exception("Langfuse init failed")
            instance._disabled = True
        return instance

    def trace_generation(
        self,
        *,
        project_id: str,
        track: str,
        stage: str,
        model: str | None,
        prompt: str,
        completion: str,
        cost_usd: float,
        latency_ms: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self._disabled or self._client is None:
            return
        try:
            trace = self._client.trace(
                name=f"{track}.{stage}",
                input=prompt[:2000],
                output=completion[:4000],
                metadata={
                    "project_id": project_id,
                    "track": track,
                    "stage": stage,
                    "cost_usd": cost_usd,
                    "latency_ms": latency_ms,
                    **(metadata or {}),
                },
            )
            trace.generation(
                name=stage,
                model=model,
                input=prompt[:2000],
                output=completion[:4000],
                metadata={"cost_usd": cost_usd, "latency_ms": latency_ms},
            )
        except Exception:
            log.exception("langfuse trace_generation failed")
