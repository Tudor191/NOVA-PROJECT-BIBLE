from fastapi.testclient import TestClient
from nova_embeddings_sdk.backends.in_memory import InMemoryEmbeddingProvider
from nova_memory_engine.config import Settings
from nova_memory_engine.main import create_app
from nova_vectorstore_sdk.backends.in_memory import InMemoryVectorStore

from tests.fakes.memory_repository import FakeMemoryRepository


def test_health_and_readiness(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    # Every port injected as a fake -- boots the real app, real lifespan, real
    # routes, with no Postgres/Redis/Ollama reachable (this sandbox has none).
    app = create_app(
        Settings(),
        memory_repository=FakeMemoryRepository(),
        vector_index=InMemoryVectorStore(),
        embedding_provider=InMemoryEmbeddingProvider(),
    )
    with TestClient(app) as client:
        health = client.get("/internal/health")
        readiness = client.get("/internal/readiness")

    assert health.status_code == 200
    assert health.json()["status"] == "healthy"
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True
