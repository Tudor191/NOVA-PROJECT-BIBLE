"""Smoke test only: verifies the TracerProvider is wired up correctly (spans can be
created) without requiring a live OTLP collector. Exporting is asynchronous/batched,
so configuring against an unreachable endpoint must not raise -- only actually
flushing would surface a connection error, and NOVA engines must never crash because
the observability backend is temporarily down.
"""

from __future__ import annotations

import os

from nova_observability import configure_tracing, get_tracer


def test_configure_tracing_does_not_raise_without_a_live_collector() -> None:
    os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    configure_tracing("test-service")
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("test-span") as span:
        span.set_attribute("nova.test", True)
