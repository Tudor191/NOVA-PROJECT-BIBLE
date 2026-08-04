"""End-to-end tests through the real FastAPI routes -- `api/memories.py` ->
`domain/*` -> `FakeMemoryRepository`, with a real app boot (lifespan, Event Bus
connect, subscriptions registered) exactly as `test_health.py` establishes.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from nova_embeddings_sdk.backends.in_memory import InMemoryEmbeddingProvider
from nova_memory_engine.config import Settings
from nova_memory_engine.main import create_app
from nova_vectorstore_sdk.backends.in_memory import InMemoryVectorStore

from tests.fakes.memory_repository import FakeMemoryRepository


@pytest.fixture
def client(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(),
        memory_repository=FakeMemoryRepository(),
        vector_index=InMemoryVectorStore(),
        embedding_provider=InMemoryEmbeddingProvider(),
    )
    with TestClient(app) as test_client:
        yield test_client


def test_create_and_get_memory(client: TestClient) -> None:
    user_id = str(uuid4())
    created = client.post(
        "/v1/memories",
        json={
            "user_id": user_id,
            "memory_type": "semantic",
            "content": "Python is a language",
            "type_data": {"concept": "Python"},
        },
    )
    assert created.status_code == 201
    memory_id = created.json()["id"]

    fetched = client.get(f"/v1/memories/{memory_id}", params={"user_id": user_id})
    assert fetched.status_code == 200
    assert fetched.json()["content"] == "Python is a language"
    assert fetched.json()["lifecycle_state"] == "active"


def test_get_memory_scoped_to_owning_user(client: TestClient) -> None:
    owner = str(uuid4())
    stranger = str(uuid4())
    created = client.post(
        "/v1/memories",
        json={"user_id": owner, "memory_type": "semantic", "content": "secret"},
    )
    memory_id = created.json()["id"]

    response = client.get(f"/v1/memories/{memory_id}", params={"user_id": stranger})

    assert response.status_code == 404


def test_get_missing_memory_returns_404(client: TestClient) -> None:
    response = client.get(f"/v1/memories/{uuid4()}", params={"user_id": str(uuid4())})
    assert response.status_code == 404


def test_update_memory_bumps_version(client: TestClient) -> None:
    user_id = str(uuid4())
    created = client.post(
        "/v1/memories",
        json={"user_id": user_id, "memory_type": "semantic", "content": "original"},
    )
    memory_id = created.json()["id"]
    assert created.json()["version"] == 1

    updated = client.patch(
        f"/v1/memories/{memory_id}",
        params={"user_id": user_id},
        json={"content": "corrected"},
    )

    assert updated.status_code == 200
    assert updated.json()["content"] == "corrected"
    assert updated.json()["version"] == 2


def test_update_with_no_fields_is_rejected(client: TestClient) -> None:
    user_id = str(uuid4())
    created = client.post(
        "/v1/memories", json={"user_id": user_id, "memory_type": "semantic", "content": "x"}
    )
    memory_id = created.json()["id"]

    response = client.patch(f"/v1/memories/{memory_id}", params={"user_id": user_id}, json={})

    assert response.status_code == 400


def test_delete_schedules_deletion_not_hard_delete(client: TestClient) -> None:
    user_id = str(uuid4())
    created = client.post(
        "/v1/memories", json={"user_id": user_id, "memory_type": "semantic", "content": "x"}
    )
    memory_id = created.json()["id"]

    deleted = client.delete(f"/v1/memories/{memory_id}", params={"user_id": user_id})

    assert deleted.status_code == 200
    assert deleted.json()["lifecycle_state"] == "scheduled_for_deletion"
    # Still fetchable -- "never disappear immediately" (Bible Part 3).
    fetched = client.get(f"/v1/memories/{memory_id}", params={"user_id": user_id})
    assert fetched.status_code == 200


def test_reactivate_returns_scheduled_memory_to_active(client: TestClient) -> None:
    user_id = str(uuid4())
    created = client.post(
        "/v1/memories", json={"user_id": user_id, "memory_type": "semantic", "content": "x"}
    )
    memory_id = created.json()["id"]
    client.delete(f"/v1/memories/{memory_id}", params={"user_id": user_id})

    reactivated = client.post(f"/v1/memories/{memory_id}/reactivate", params={"user_id": user_id})

    assert reactivated.status_code == 200
    assert reactivated.json()["lifecycle_state"] == "active"


def test_reactivate_missing_memory_returns_404(client: TestClient) -> None:
    response = client.post(
        f"/v1/memories/{uuid4()}/reactivate", params={"user_id": str(uuid4())}
    )
    assert response.status_code == 404


def test_timeline_scoped_to_project(client: TestClient) -> None:
    user_id = str(uuid4())
    project_id = str(uuid4())
    other_project_id = str(uuid4())
    client.post(
        "/v1/memories",
        json={
            "user_id": user_id,
            "project_id": project_id,
            "memory_type": "project",
            "content": "in project",
        },
    )
    client.post(
        "/v1/memories",
        json={
            "user_id": user_id,
            "project_id": other_project_id,
            "memory_type": "project",
            "content": "different project",
        },
    )

    response = client.get(
        "/v1/memories/timeline", params={"user_id": user_id, "project_id": project_id}
    )

    assert response.status_code == 200
    contents = [m["content"] for m in response.json()]
    assert contents == ["in project"]


def test_search_falls_back_to_timeline_without_query_text(client: TestClient) -> None:
    user_id = str(uuid4())
    client.post(
        "/v1/memories",
        json={"user_id": user_id, "memory_type": "semantic", "content": "findable by timeline"},
    )

    response = client.get("/v1/memories/search", params={"user_id": user_id})

    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is False
    assert any(r["content"] == "findable by timeline" for r in body["results"])
