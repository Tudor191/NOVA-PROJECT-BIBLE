"""`/internal/health` and `/internal/readiness`, including design doc Sec8's
one no-graceful-degradation failure mode: a missing Core Identity keeps the
engine alive (health still reports healthy) but not-ready."""

from __future__ import annotations

from fastapi.testclient import TestClient
from nova_personality_engine.config import Settings
from nova_personality_engine.main import create_app

from tests.fakes.repository import FakePersonalityRepository


def test_health_and_readiness_when_core_identity_loads(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakePersonalityRepository())
    with TestClient(app) as client:
        health = client.get("/internal/health")
        readiness = client.get("/internal/readiness")

    assert health.status_code == 200
    assert health.json()["status"] == "healthy"
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True


def test_readiness_is_false_when_core_identity_fails_to_load(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakePersonalityRepository(core_identity=None))
    with TestClient(app) as client:
        health = client.get("/internal/health")
        readiness = client.get("/internal/readiness")

    # Sec8: no safe default for who NOVA is -- the process stays alive
    # (health still 200) but must not serve traffic that depends on identity.
    assert health.status_code == 200
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is False
