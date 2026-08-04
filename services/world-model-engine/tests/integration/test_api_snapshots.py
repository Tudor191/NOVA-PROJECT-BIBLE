from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from nova_graphstore_sdk.backends.in_memory import InMemoryGraphStore
from nova_world_model_engine.config import Settings
from nova_world_model_engine.domain.models import ActiveContext, Prediction
from nova_world_model_engine.main import create_app

from tests.fakes.context_repository import FakeContextRepository
from tests.fakes.history_repository import FakeWorldHistoryRepository


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    context_repo = FakeContextRepository()
    history_repo = FakeWorldHistoryRepository()
    app = create_app(
        Settings(),
        context_repository=context_repo,
        history_repository=history_repo,
        graph_store=InMemoryGraphStore(),
    )
    with TestClient(app) as client:
        yield client, context_repo, history_repo


def test_trigger_snapshot_captures_current_context(harness) -> None:  # type: ignore[no-untyped-def]
    client, context_repo, _history_repo = harness
    user_id = uuid4()
    context_repo.contexts[user_id] = ActiveContext(user_id=user_id, activity="meeting")

    response = client.post("/v1/world/snapshot", json={"user_id": str(user_id)})

    assert response.status_code == 201
    body = response.json()
    assert body["trigger"] == "manual"
    assert body["snapshot_data"]["activity"] == "meeting"


def test_list_snapshots_scoped_to_user(harness) -> None:  # type: ignore[no-untyped-def]
    client, _context_repo, _history_repo = harness
    user_id = str(uuid4())
    other_user_id = str(uuid4())
    client.post("/v1/world/snapshot", json={"user_id": user_id})
    client.post("/v1/world/snapshot", json={"user_id": other_user_id})

    response = client.get("/v1/world/snapshots", params={"user_id": user_id})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1


def test_list_predictions_scoped_to_user(harness) -> None:  # type: ignore[no-untyped-def]
    client, _context_repo, history_repo = harness
    user_id = uuid4()
    prediction = Prediction(user_id=user_id, prediction="test prediction", confidence=0.5)
    history_repo.predictions[prediction.id] = prediction

    response = client.get("/v1/world/predictions", params={"user_id": str(user_id)})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["prediction"] == "test prediction"
