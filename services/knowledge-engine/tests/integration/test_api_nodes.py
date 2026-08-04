"""End-to-end tests through the real FastAPI routes -- `api/nodes.py` ->
`domain/*` -> `FakeKnowledgeMetadataRepository`, with a real app boot (lifespan,
Event Bus connect, subscriptions registered) exactly as `test_health.py`
establishes.
"""

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


def test_acquire_new_node(client: TestClient) -> None:
    response = client.post(
        "/v1/knowledge/nodes",
        json={"label": "Technology", "name": "PostgreSQL", "source_type": "user"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["outcome"] == "created"
    assert body["node"]["node_id"] == "technology:postgresql"
    assert body["node"]["layer"] == "raw"


def test_acquire_twice_corroborates_not_duplicates(client: TestClient) -> None:
    first = client.post(
        "/v1/knowledge/nodes",
        json={"label": "Technology", "name": "PostgreSQL", "source_type": "user"},
    )
    second = client.post(
        "/v1/knowledge/nodes",
        json={"label": "Technology", "name": "PostgreSQL", "source_type": "document"},
    )
    assert first.json()["outcome"] == "created"
    assert second.json()["outcome"] == "corroborated"
    assert second.json()["node"]["node_id"] == first.json()["node"]["node_id"]


def test_get_node(client: TestClient) -> None:
    created = client.post(
        "/v1/knowledge/nodes",
        json={"label": "Technology", "name": "PostgreSQL", "source_type": "user"},
    )
    node_id = created.json()["node"]["node_id"]

    fetched = client.get(f"/v1/knowledge/nodes/{node_id}")

    assert fetched.status_code == 200
    assert fetched.json()["name"] == "PostgreSQL"


def test_get_missing_node_returns_404(client: TestClient) -> None:
    response = client.get("/v1/knowledge/nodes/technology:does-not-exist")
    assert response.status_code == 404


def test_update_node_bumps_version(client: TestClient) -> None:
    created = client.post(
        "/v1/knowledge/nodes",
        json={"label": "Technology", "name": "PostgreSQL", "source_type": "user"},
    )
    node_id = created.json()["node"]["node_id"]
    assert created.json()["node"]["version"] == 1

    updated = client.patch(f"/v1/knowledge/nodes/{node_id}", json={"domain": "databases"})

    assert updated.status_code == 200
    assert updated.json()["domain"] == "databases"
    assert updated.json()["version"] == 2


def test_update_missing_node_returns_404(client: TestClient) -> None:
    response = client.patch(
        "/v1/knowledge/nodes/technology:does-not-exist", json={"domain": "x"}
    )
    assert response.status_code == 404


def test_update_with_no_fields_is_rejected(client: TestClient) -> None:
    created = client.post(
        "/v1/knowledge/nodes",
        json={"label": "Technology", "name": "PostgreSQL", "source_type": "user"},
    )
    node_id = created.json()["node"]["node_id"]

    response = client.patch(f"/v1/knowledge/nodes/{node_id}", json={})

    assert response.status_code == 400


def test_conflicting_acquisition_records_contradiction(client: TestClient) -> None:
    client.post(
        "/v1/knowledge/nodes",
        json={
            "label": "Company",
            "name": "Postgres",
            "source_type": "user",
            "domain": "business",
        },
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

    assert conflicting.status_code == 201
    body = conflicting.json()
    assert body["outcome"] == "conflict"
    assert body["node"] is None
    assert body["conflict_id"] is not None
