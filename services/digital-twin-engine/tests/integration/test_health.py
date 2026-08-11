"""`GET /internal/health`, `GET /internal/readiness` -- smoke test that
`create_app` wires up and boots cleanly against a fake repository."""

from __future__ import annotations

from fastapi.testclient import TestClient
from nova_digital_twin_engine.config import Settings
from nova_digital_twin_engine.main import create_app

from tests.fakes.repository import FakeDigitalTwinRepository


def test_health_and_readiness(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakeDigitalTwinRepository())
    with TestClient(app) as client:
        assert client.get("/internal/health").status_code == 200
        assert client.get("/internal/readiness").status_code == 200
