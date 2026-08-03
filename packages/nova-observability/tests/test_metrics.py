"""Metrics are Prometheus-pull, not OTLP-push (see metrics.py's module docstring),
so these tests need no network access or live collector at all.
"""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient
from nova_observability import configure_metrics, get_meter
from nova_observability.metrics import prometheus_asgi_app


def test_configure_metrics_and_create_a_counter() -> None:
    configure_metrics("test-service")
    meter = get_meter(__name__)
    counter = meter.create_counter("test.counter")
    counter.add(1, {"engine": "test-service"})


async def test_prometheus_asgi_app_serves_metrics_in_prometheus_text_format() -> None:
    configure_metrics("test-service")
    meter = get_meter(__name__)
    counter = meter.create_counter("nova_test_requests_total")
    counter.add(3)

    transport = ASGITransport(app=prometheus_asgi_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
