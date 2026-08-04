"""`/v1/decisions*` -- decisions are recorded via `domain/decision.py` directly
(no public creation endpoint per docs/design/phase-1/01-memory-engine.md §14; a
future Reasoning Engine calls `domain.decision.record` in-process), so these tests
seed via the domain function and read back through the real HTTP routes.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from nova_embeddings_sdk.backends.in_memory import InMemoryEmbeddingProvider
from nova_memory_engine.config import Settings
from nova_memory_engine.domain import decision
from nova_memory_engine.main import create_app
from nova_vectorstore_sdk.backends.in_memory import InMemoryVectorStore

from tests.fakes.memory_repository import FakeMemoryRepository


@pytest.fixture
def repo() -> FakeMemoryRepository:
    return FakeMemoryRepository()


@pytest.fixture
def client(monkeypatch, repo: FakeMemoryRepository):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(),
        memory_repository=repo,
        vector_index=InMemoryVectorStore(),
        embedding_provider=InMemoryEmbeddingProvider(),
    )
    with TestClient(app) as test_client:
        yield test_client


async def test_get_decision_round_trips(client: TestClient, repo: FakeMemoryRepository) -> None:
    user_id = uuid4()
    _, stored = await decision.record(
        repo,
        user_id=user_id,
        objective="Choose an event bus",
        alternatives=["NATS", "Kafka", "RabbitMQ"],
        chosen_alternative="NATS",
        reasoning="Aligns with local-first philosophy",
        correlation_id=uuid4(),
    )

    response = client.get(f"/v1/decisions/{stored.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["objective"] == "Choose an event bus"
    assert body["chosen_alternative"] == "NATS"


def test_get_missing_decision_returns_404(client: TestClient) -> None:
    response = client.get(f"/v1/decisions/{uuid4()}")
    assert response.status_code == 404


async def test_search_decisions_scoped_to_user(
    client: TestClient, repo: FakeMemoryRepository
) -> None:
    owner = uuid4()
    stranger = uuid4()
    await decision.record(
        repo,
        user_id=owner,
        objective="Pick a database",
        alternatives=["Postgres", "MySQL"],
        chosen_alternative="Postgres",
        reasoning="pgvector support",
        correlation_id=uuid4(),
    )
    await decision.record(
        repo,
        user_id=stranger,
        objective="Pick a language",
        alternatives=["Python", "Go"],
        chosen_alternative="Python",
        reasoning="ecosystem",
        correlation_id=uuid4(),
    )

    response = client.get("/v1/decisions/search", params={"user_id": str(owner)})

    assert response.status_code == 200
    objectives = [d["objective"] for d in response.json()]
    assert objectives == ["Pick a database"]
