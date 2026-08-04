from fastapi.testclient import TestClient
from nova_embeddings_sdk.backends.in_memory import InMemoryEmbeddingProvider
from nova_graphstore_sdk.backends.in_memory import InMemoryGraphStore
from nova_knowledge_engine.config import Settings
from nova_knowledge_engine.main import create_app
from nova_vectorstore_sdk.backends.in_memory import InMemoryVectorStore

from tests.fakes.metadata_repository import FakeKnowledgeMetadataRepository


def test_health_and_readiness(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    # Every port injected as a fake -- boots the real app, real lifespan, real
    # routes, with no Postgres/Neo4j/Ollama reachable (this sandbox has none).
    app = create_app(
        Settings(),
        repository=FakeKnowledgeMetadataRepository(),
        vector_index=InMemoryVectorStore(),
        embedding_provider=InMemoryEmbeddingProvider(),
        graph_store=InMemoryGraphStore(),
    )
    with TestClient(app) as client:
        health = client.get("/internal/health")
        readiness = client.get("/internal/readiness")

    assert health.status_code == 200
    assert health.json()["status"] == "healthy"
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True
