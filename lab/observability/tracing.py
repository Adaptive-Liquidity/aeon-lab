"""OpenTelemetry init + span helpers.

Idempotent: calling init_tracing() many times is safe. When the OTel
exporter is unreachable we drop spans silently.

Environment:
  OTEL_EXPORTER_OTLP_ENDPOINT  -- defaults to http://localhost:4317
  OTEL_SERVICE_NAME            -- defaults to "ecc-lab"
  ECC_LAB_OTEL_DISABLED        -- "1" turns tracing off (noop spans only).
"""

from __future__ import annotations

import contextlib
import logging
import os
from typing import Iterator

log = logging.getLogger("lab.observability.tracing")

_initialized = False


def init_tracing(*, service_name: str | None = None) -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True

    if os.environ.get("ECC_LAB_OTEL_DISABLED") == "1":
        log.info("OTel disabled via ECC_LAB_OTEL_DISABLED=1")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
    except Exception:
        log.warning("opentelemetry packages not installed; tracing disabled")
        return

    resource = Resource.create({SERVICE_NAME: service_name or os.environ.get("OTEL_SERVICE_NAME", "ecc-lab")})
    provider = TracerProvider(resource=resource)
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    try:
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        log.info("OTel tracing initialized -> %s", endpoint)
    except Exception:
        log.exception("OTel exporter init failed; spans will be no-ops")


def get_tracer(name: str = "ecc-lab"):
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except Exception:
        return _NullTracer()


@contextlib.contextmanager
def span(name: str, **attrs) -> Iterator[None]:
    """Convenience wrapper that produces a span with given attributes."""
    tracer = get_tracer()
    try:
        with tracer.start_as_current_span(name) as s:
            for k, v in attrs.items():
                try:
                    s.set_attribute(k, v)  # type: ignore[union-attr]
                except Exception:
                    pass
            yield
    except Exception:
        yield


class _NullTracer:
    @contextlib.contextmanager
    def start_as_current_span(self, name: str):
        yield _NullSpan()


class _NullSpan:
    def set_attribute(self, *_a, **_kw):
        pass
