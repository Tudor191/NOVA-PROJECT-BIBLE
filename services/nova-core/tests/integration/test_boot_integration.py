"""End-to-end: boot the real FastAPI app (lifespan-driven) against the in-memory
Event Bus backend and hit its actual HTTP endpoints. This is the closest thing to
"git clone -> turbo run dev -> nova-core reports System Ready" (Roadmap Phase 0
acceptance criteria) that can run without a live NATS server.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from nova_core.config import NovaCoreSettings
from nova_core.main import create_app


@pytest.fixture(autouse=True)
def _use_in_memory_event_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")


def test_app_boots_and_health_reports_healthy() -> None:
    app = create_app(NovaCoreSettings())
    with TestClient(app) as client:
        response = client.get("/internal/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["boot_phase"] == 7
    assert body["uptime_seconds"] >= 0.0


def test_readiness_reports_ready_after_boot() -> None:
    app = create_app(NovaCoreSettings())
    with TestClient(app) as client:
        response = client.get("/internal/readiness")

    assert response.status_code == 200
    assert response.json() == {"ready": True, "boot_phase": 7}


def test_metrics_endpoint_exposes_prometheus_text_format() -> None:
    app = create_app(NovaCoreSettings())
    with TestClient(app) as client:
        response = client.get("/internal/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
