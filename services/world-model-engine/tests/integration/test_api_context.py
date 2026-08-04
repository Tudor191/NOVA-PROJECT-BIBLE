"""End-to-end tests through the real FastAPI routes -- `api/context.py` ->
`domain/context.py` -> `FakeContextRepository`, with a real app boot exactly
as `test_health.py` establishes.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from nova_graphstore_sdk.backends.in_memory import InMemoryGraphStore
from nova_world_model_engine.config import Settings
from nova_world_model_engine.domain.models import ActiveContext
from nova_world_model_engine.main import create_app

from tests.fakes.context_repository import FakeContextRepository
from tests.fakes.history_repository import FakeWorldHistoryRepository


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    context_repo = FakeContextRepository()
    app = create_app(
        Settings(),
        context_repository=context_repo,
        history_repository=FakeWorldHistoryRepository(),
        graph_store=InMemoryGraphStore(),
    )
    with TestClient(app) as client:
        yield client, context_repo


def test_get_context_with_no_data_returns_zero_confidence(harness) -> None:  # type: ignore[no-untyped-def]
    client, _repo = harness
    user_id = str(uuid4())

    response = client.get("/v1/world/context", params={"user_id": user_id})

    assert response.status_code == 200
    body = response.json()
    assert body["confidence"] == 0.0


def test_get_context_returns_stored_context(harness) -> None:  # type: ignore[no-untyped-def]
    client, repo = harness
    user_id = uuid4()
    repo.contexts[user_id] = ActiveContext(user_id=user_id, activity="meeting", confidence=0.8)

    response = client.get("/v1/world/context", params={"user_id": str(user_id)})

    assert response.status_code == 200
    body = response.json()
    assert body["activity"] == "meeting"
    assert body["confidence"] == 0.8


def test_get_context_scoped_to_agent_filters_fields(harness) -> None:  # type: ignore[no-untyped-def]
    client, repo = harness
    user_id = uuid4()
    project_id = uuid4()
    repo.contexts[user_id] = ActiveContext(
        user_id=user_id,
        activity="coding",
        task="implement feature",
        project_id=project_id,
        objective="ship the release",
        confidence=0.9,
    )

    response = client.get(
        "/v1/world/context", params={"user_id": str(user_id), "scope": "agent:coding-agent"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task"] == "implement feature"
    assert body["project_id"] == str(project_id)
    assert "objective" not in body  # not in coding-agent's whitelist


def test_context_unavailable_returns_503(harness) -> None:  # type: ignore[no-untyped-def]
    client, repo = harness
    repo.unavailable = True

    response = client.get("/v1/world/context", params={"user_id": str(uuid4())})

    assert response.status_code == 503
