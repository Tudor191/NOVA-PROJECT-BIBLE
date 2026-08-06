from fastapi.testclient import TestClient
from nova_executive_cognition_engine.config import Settings
from nova_executive_cognition_engine.main import create_app


def test_health_and_readiness(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings())
    with TestClient(app) as client:
        health = client.get("/internal/health")
        readiness = client.get("/internal/readiness")

    assert health.status_code == 200
    assert health.json()["status"] == "healthy"
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True
