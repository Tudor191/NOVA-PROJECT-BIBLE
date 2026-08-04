"""End-to-end tests through `api/objects.py` -- exercises `domain/temporal.py`
and `domain/object_graph.py`'s history-append path against
`FakeWorldHistoryRepository`.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from nova_graphstore_sdk.backends.in_memory import InMemoryGraphStore
from nova_world_model_engine.config import Settings
from nova_world_model_engine.domain import object_graph
from nova_world_model_engine.domain.models import ObjectState, WorldObject
from nova_world_model_engine.main import create_app

from tests.fakes.context_repository import FakeContextRepository
from tests.fakes.history_repository import FakeWorldHistoryRepository


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    history_repo = FakeWorldHistoryRepository()
    app = create_app(
        Settings(),
        context_repository=FakeContextRepository(),
        history_repository=history_repo,
        graph_store=InMemoryGraphStore(),
    )
    with TestClient(app) as client:
        yield client, history_repo


async def _observe(
    history_repo: FakeWorldHistoryRepository,
    object_id: str,
    user_id: UUID,
    state: ObjectState,
    previous: ObjectState | None = None,
) -> None:
    obj = WorldObject(object_id=object_id, label="Window", user_id=user_id, state=state)
    await object_graph.observe_object(
        history_repo, obj=obj, previous_state=previous, correlation_id=uuid4()
    )


async def test_get_object_returns_latest_state(harness) -> None:  # type: ignore[no-untyped-def]
    client, history_repo = harness
    user_id = uuid4()
    await _observe(history_repo, "window:1", user_id, ObjectState.ACTIVE)

    response = client.get("/v1/world/objects/window:1")

    assert response.status_code == 200
    assert response.json()["new_state"] == "active"


def test_get_object_missing_returns_404(harness) -> None:  # type: ignore[no-untyped-def]
    client, _history_repo = harness
    response = client.get("/v1/world/objects/window:does-not-exist")
    assert response.status_code == 404


async def test_get_object_history_returns_full_trail(harness) -> None:  # type: ignore[no-untyped-def]
    client, history_repo = harness
    user_id = uuid4()
    await _observe(history_repo, "window:1", user_id, ObjectState.ACTIVE)
    await _observe(
        history_repo, "window:1", user_id, ObjectState.IDLE, previous=ObjectState.ACTIVE
    )

    response = client.get("/v1/world/objects/window:1/history")

    assert response.status_code == 200
    states = [row["new_state"] for row in response.json()]
    assert states == ["idle", "active"]
