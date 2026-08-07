"""`/internal/health` and `/internal/readiness`."""

from __future__ import annotations

from fastapi.testclient import TestClient
from nova_communication_engine.config import Settings
from nova_communication_engine.main import create_app

from tests.fakes.ports import FakeModelOrchestrationPort, FakePersonalityPort, FakeWorldModelPort
from tests.fakes.repository import FakeCommunicationRepository


def test_health_and_readiness(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    # Every port injected as a fake -- boots the real app, real lifespan,
    # real routes, with no Postgres/Event Bus RPC reachable (this sandbox
    # has neither).
    app = create_app(
        Settings(),
        repository=FakeCommunicationRepository(),
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        world_model_port=FakeWorldModelPort(),
    )
    with TestClient(app) as client:
        health = client.get("/internal/health")
        readiness = client.get("/internal/readiness")

    assert health.status_code == 200
    assert health.json()["status"] == "healthy"
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True
