"""`/v1/knowledge/graph` -- exercises the subgraph endpoint against nodes acquired
via `POST /v1/knowledge/nodes` and relationships applied through the saga
dispatcher (`repository/outbox_dispatcher.py`), the same two-step "Postgres
commits intent, then the graph write actually lands" flow `test_saga.py` covers
directly.
"""

import pytest
from fastapi.testclient import TestClient
from nova_embeddings_sdk.backends.in_memory import InMemoryEmbeddingProvider
from nova_graphstore_sdk.backends.in_memory import InMemoryGraphStore
from nova_knowledge_engine.config import Settings
from nova_knowledge_engine.main import create_app
from nova_knowledge_engine.repository.outbox_dispatcher import apply_pending_graph_writes
from nova_vectorstore_sdk.backends.in_memory import InMemoryVectorStore

from tests.fakes.metadata_repository import FakeKnowledgeMetadataRepository


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeKnowledgeMetadataRepository()
    graph_store = InMemoryGraphStore()
    app = create_app(
        Settings(),
        repository=repository,
        vector_index=InMemoryVectorStore(),
        embedding_provider=InMemoryEmbeddingProvider(),
        graph_store=graph_store,
    )
    with TestClient(app) as client:
        yield client, repository, graph_store


def test_subgraph_lists_acquired_nodes(harness) -> None:  # type: ignore[no-untyped-def]
    client, _repository, _graph_store = harness
    client.post(
        "/v1/knowledge/nodes",
        json={"label": "Technology", "name": "PostgreSQL", "source_type": "user"},
    )

    response = client.get("/v1/knowledge/graph")

    assert response.status_code == 200
    body = response.json()
    assert any(n["node_id"] == "technology:postgresql" for n in body["nodes"])


async def test_subgraph_includes_edges_once_graph_write_lands(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository, graph_store = harness
    a = client.post(
        "/v1/knowledge/nodes",
        json={"label": "Technology", "name": "PostgreSQL", "source_type": "user"},
    ).json()["node"]
    b = client.post(
        "/v1/knowledge/nodes",
        json={"label": "Technology", "name": "pgvector", "source_type": "user"},
    ).json()["node"]

    from uuid import uuid4

    from nova_knowledge_engine.domain import graph_operations

    await graph_operations.create_relationship(
        repository,
        from_id=a["node_id"],
        to_id=b["node_id"],
        relationship_type="DEPENDS_ON",
        confidence=0.9,
        source="test",
        correlation_id=uuid4(),
    )
    # Nothing in Neo4j yet -- only the Postgres-side intent has been recorded.
    before = client.get("/v1/knowledge/graph")
    assert before.json()["edges"] == []

    applied = await apply_pending_graph_writes(repository, graph_store)
    assert applied == 3  # 2 node upserts (from acquisition) + 1 relationship upsert

    after = client.get("/v1/knowledge/graph")
    edges = after.json()["edges"]
    assert len(edges) == 1
    assert edges[0]["from_id"] == a["node_id"]
    assert edges[0]["to_id"] == b["node_id"]
    assert edges[0]["relationship_type"] == "DEPENDS_ON"


def test_subgraph_scope_parsing_rejects_invalid_scope(harness) -> None:  # type: ignore[no-untyped-def]
    client, _repository, _graph_store = harness
    response = client.get("/v1/knowledge/graph", params={"scope": "not-a-valid-scope"})
    assert response.status_code == 400
