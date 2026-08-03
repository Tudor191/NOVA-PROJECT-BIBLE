"""OpenTelemetry metrics setup, shared across every engine.

Metrics flow Prometheus-pull, not OTLP-push: `prometheus_asgi_app()` exposes the
per-engine `/internal/metrics` scrape endpoint every engine's API is required to
have (docs/architecture/11-api-architecture.md §3), which Prometheus scrapes
directly (docs/architecture/01-technology-stack.md §7 -- "metrics... to Prometheus").
This deliberately does *not* also push metrics through the otel-collector: that
would double-count every metric (once via collector aggregation, once via direct
scrape) for no benefit, since Prometheus's pull model needs no intermediary. Traces
(tracing.py) are push-based via OTLP because pull doesn't make sense for spans.
"""

from __future__ import annotations

from typing import Any

from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.metrics import Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

_configured = False


def configure_metrics(service_name: str, *, expose_prometheus: bool = True) -> None:
    """Configure the global MeterProvider for `service_name`. Safe to call more than once.

    `expose_prometheus=False` disables metrics entirely (rare -- only for processes
    that genuinely have nothing worth exposing, e.g. a one-shot CLI tool).
    """
    global _configured
    if _configured:
        return
    resource = Resource.create({SERVICE_NAME: service_name})
    readers: list[Any] = [PrometheusMetricReader()] if expose_prometheus else []
    provider = MeterProvider(resource=resource, metric_readers=readers)
    metrics.set_meter_provider(provider)
    _configured = True


def get_meter(name: str) -> Meter:
    return metrics.get_meter(name)


def prometheus_asgi_app() -> Any:
    """An ASGI app exposing metrics in Prometheus text format. Mount at
    `/internal/metrics` (docs/architecture/11-api-architecture.md §3). Requires
    `configure_metrics(..., expose_prometheus=True)` (the default) to have already run.
    """
    from prometheus_client import make_asgi_app

    return make_asgi_app()
