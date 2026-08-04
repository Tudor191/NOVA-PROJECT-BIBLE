import pytest
from fastapi.testclient import TestClient
from nova_embeddings_sdk.backends.in_memory import InMemoryEmbeddingProvider
from nova_graphstore_sdk.backends.in_memory import InMemoryGraphStore
from nova_knowledge_engine.config import Settings
from nova_knowledge_engine.main import create_app
from nova_vectorstore_sdk.backends.in_memory import InMemoryVectorStore

from tests.fakes.metadata_repository import FakeKnowledgeMetadataRepository


@pytest.fixture
def client(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(),
        repository=FakeKnowledgeMetadataRepository(),
        vector_index=InMemoryVectorStore(),
        embedding_provider=InMemoryEmbeddingProvider(),
        graph_store=InMemoryGraphStore(),
    )
    with TestClient(app) as test_client:
        yield test_client


def _create_conflict(client: TestClient) -> str:
    client.post(
        "/v1/knowledge/nodes",
        json={"label": "Company", "name": "Postgres", "source_type": "user", "domain": "business"},
    )
    conflicting = client.post(
        "/v1/knowledge/nodes",
        json={
            "label": "Technology",
            "name": "Postgres",
            "source_type": "user",
            "domain": "programming",
        },
    )
    conflict_id: str = conflicting.json()["conflict_id"]
    return conflict_id


def test_list_open_contradictions(client: TestClient) -> None:
    _create_conflict(client)

    response = client.get("/v1/knowledge/contradictions", params={"status": "open"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["status"] == "open"


def test_get_contradiction(client: TestClient) -> None:
    contradiction_id = _create_conflict(client)

    response = client.get(f"/v1/knowledge/contradictions/{contradiction_id}")

    assert response.status_code == 200
    assert response.json()["id"] == contradiction_id


def test_get_missing_contradiction_returns_404(client: TestClient) -> None:
    from uuid import uuid4

    response = client.get(f"/v1/knowledge/contradictions/{uuid4()}")
    assert response.status_code == 404


def test_resolve_contradiction(client: TestClient) -> None:
    contradiction_id = _create_conflict(client)

    resolved = client.post(
        f"/v1/knowledge/contradictions/{contradiction_id}/resolve",
        json={"resolution": "Company Postgres renamed to avoid ambiguity"},
    )

    assert resolved.status_code == 200
    body = resolved.json()
    assert body["status"] == "resolved"
    assert body["resolution"] == "Company Postgres renamed to avoid ambiguity"

    still_open = client.get("/v1/knowledge/contradictions", params={"status": "open"})
    assert still_open.json() == []


def test_resolve_missing_contradiction_returns_404(client: TestClient) -> None:
    from uuid import uuid4

    response = client.post(
        f"/v1/knowledge/contradictions/{uuid4()}/resolve", json={"resolution": "n/a"}
    )
    assert response.status_code == 404
