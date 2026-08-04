from fastapi.testclient import TestClient
from nova_graphstore_sdk.backends.in_memory import InMemoryGraphStore
from nova_world_model_engine.config import Settings
from nova_world_model_engine.main import create_app

from tests.fakes.context_repository import FakeContextRepository
from tests.fakes.history_repository import FakeWorldHistoryRepository


def test_health_and_readiness(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    # Every port injected as a fake -- boots the real app, real lifespan, real
    # routes, with no Postgres/Redis/Neo4j reachable (this sandbox has none).
    app = create_app(
        Settings(),
        context_repository=FakeContextRepository(),
        history_repository=FakeWorldHistoryRepository(),
        graph_store=InMemoryGraphStore(),
    )
    with TestClient(app) as client:
        health = client.get("/internal/health")
        readiness = client.get("/internal/readiness")

    assert health.status_code == 200
    assert health.json()["status"] == "healthy"
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True
