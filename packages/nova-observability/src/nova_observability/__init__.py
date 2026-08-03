"""nova-observability: shared OpenTelemetry (traces/metrics) and structured logging
setup used by every NOVA engine (docs/architecture/01-technology-stack.md §7).
"""

from nova_observability.logging import configure_logging, get_logger
from nova_observability.metrics import configure_metrics, get_meter, prometheus_asgi_app
from nova_observability.tracing import configure_tracing, get_tracer


def configure_observability(
    service_name: str, *, log_level: str = "INFO", expose_prometheus: bool = True
) -> None:
    """Configure logging, tracing, and metrics for `service_name` in one call.

    Call this once at process startup (e.g. FastAPI lifespan startup) before
    anything else. Individual `configure_*` functions remain available for callers
    that need to opt out of one signal.
    """
    configure_logging(service_name, level=log_level)
    configure_tracing(service_name)
    configure_metrics(service_name, expose_prometheus=expose_prometheus)


__all__ = [
    "configure_logging",
    "configure_metrics",
    "configure_observability",
    "configure_tracing",
    "get_logger",
    "get_meter",
    "get_tracer",
    "prometheus_asgi_app",
]
