"""`/v1/cognitive-state/*` through the real app and lifespan -- TDD 4F.7 §7.

The store is a behavioural in-memory one that returns what it holds, keyed the
way the real one is (thoughts by `user_id`). Every assertion is on the served
body. The same routes are proven against real Postgres over a real socket in
`tests/integration/test_cognitive_state_api_real_infra.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from nova_cognitive_state_engine.config import Settings
from nova_cognitive_state_engine.domain.models import (
    ActiveThought,
    AttentionLayer,
    ProposedAction,
)
from nova_cognitive_state_engine.domain.sensor_state import SensorStateRecord
from nova_cognitive_state_engine.main import create_app

PRIMARY = UUID("00000000-0000-0000-0000-00000000f007")
SOMEONE_ELSE = UUID("00000000-0000-0000-0000-0000000000aa")

PROPOSAL = ProposedAction(
    category="create",  # type: ignore[arg-type]
    risk="low",  # type: ignore[arg-type]
    action_type="terminal",
    execution_target="terminal",
    verification_method="exit_code",
    title="prune stale build artifacts",
    detail="older than thirty days",
)


class InMemoryStore:
    def __init__(self) -> None:
        self.thoughts: list[ActiveThought] = []
        self.sensors: list[SensorStateRecord] = []
        self.fail = False

    async def list_thoughts(
        self, *, user_id: UUID, layer: AttentionLayer | None = None
    ) -> list[ActiveThought]:
        if self.fail:
            raise ConnectionError("store unavailable")
        return [t for t in self.thoughts if t.user_id == user_id]

    async def list_sensor_states(self) -> list[SensorStateRecord]:
        if self.fail:
            raise ConnectionError("store unavailable")
        return sorted(self.sensors, key=lambda r: r.sensor_id)

    async def apply_sensor_report(
        self, record: SensorStateRecord
    ) -> bool:  # subscription wiring only
        self.sensors.append(record)
        return True


def _thought(
    *, user_id: UUID = PRIMARY, layer: AttentionLayer = AttentionLayer.ACTIVE, **overrides: object
) -> ActiveThought:
    moment = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
    values: dict[str, object] = {
        "thought_id": uuid4(),
        "user_id": user_id,
        "description": "Investigate recurring build failures",
        "priority": 4,
        "confidence": 0.7,
        "current_progress": 0.25,
        "attention_layer": layer,
        "created_at": moment,
        "updated_at": moment,
    }
    values.update(overrides)
    return ActiveThought(**values)  # type: ignore[arg-type]


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def client(store: InMemoryStore, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(primary_user_id=PRIMARY, focus_capacity=2), repository=store)  # type: ignore[arg-type]
    with TestClient(app) as running:
        yield running


# --- P-3: empty is empty ---------------------------------------------------------


def test_an_empty_store_serves_empty_lists_and_nothing_synthesized(client: TestClient) -> None:
    assert client.get("/v1/cognitive-state/thoughts").json() == {"thoughts": []}
    assert client.get("/v1/cognitive-state/focus").json() == {"capacity": 2, "entries": []}
    assert client.get("/v1/cognitive-state/sensors").json() == {"sensors": []}


# --- P-4, P-5, P-8: serialization ------------------------------------------------


def test_a_thought_serializes_with_every_part_6_field(
    client: TestClient, store: InMemoryStore
) -> None:
    dep, mem, proj = uuid4(), uuid4(), uuid4()
    completion = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)
    thought = _thought(
        dependencies=(dep,),
        related_memories=(mem,),
        related_projects=(proj,),
        estimated_completion=completion,
    )
    store.thoughts.append(thought)

    body = client.get("/v1/cognitive-state/thoughts").json()
    assert body == {
        "thoughts": [
            {
                "thought_id": str(thought.thought_id),
                "description": "Investigate recurring build failures",
                "priority": 4,
                "confidence": 0.7,
                "dependencies": [str(dep)],
                "estimated_completion": "2026-10-01T09:30:00Z",
                "related_memories": [str(mem)],
                "related_projects": [str(proj)],
                "current_progress": 0.25,
                "attention_layer": "active",
                "created_at": "2026-09-26T12:00:00Z",
                "updated_at": "2026-09-26T12:00:00Z",
                "proposed_action": None,
            }
        ]
    }


def test_not_estimated_is_null_never_a_date(client: TestClient, store: InMemoryStore) -> None:
    store.thoughts.append(_thought())
    thought = client.get("/v1/cognitive-state/thoughts").json()["thoughts"][0]
    assert thought["estimated_completion"] is None


@pytest.mark.parametrize("layer", list(AttentionLayer))
def test_each_attention_layer_serializes_as_its_part_6_value(
    layer: AttentionLayer, client: TestClient, store: InMemoryStore
) -> None:
    store.thoughts.append(_thought(layer=layer, current_progress=0.0))
    served = client.get("/v1/cognitive-state/thoughts").json()["thoughts"][0]
    assert served["attention_layer"] == layer.value


def test_a_proposed_action_serializes_verbatim_as_a_proposal(
    client: TestClient, store: InMemoryStore
) -> None:
    store.thoughts.append(_thought(proposed_action=PROPOSAL))
    served = client.get("/v1/cognitive-state/thoughts").json()["thoughts"][0]["proposed_action"]
    assert served == {
        "category": "create",
        "risk": "low",
        "action_type": "terminal",
        "execution_target": "terminal",
        "verification_method": "exit_code",
        "title": "prune stale build artifacts",
        "detail": "older than thirty days",
    }


# --- P-6, P-7: focus ---------------------------------------------------------------


def test_focus_is_select_focus_over_the_users_thoughts(
    client: TestClient, store: InMemoryStore
) -> None:
    """Capacity 2 of 4 candidates; the archived one is never eligible; order is
    by score, which with no signals is the priority."""
    low = _thought(priority=1)
    high = _thought(priority=9)
    mid = _thought(priority=5, layer=AttentionLayer.IMMEDIATE)
    archived = _thought(priority=99, layer=AttentionLayer.ARCHIVED, current_progress=0.0)
    store.thoughts.extend([low, high, mid, archived])

    body = client.get("/v1/cognitive-state/focus").json()
    assert body["capacity"] == 2
    assert [e["thought"]["thought_id"] for e in body["entries"]] == [
        str(high.thought_id),
        str(mid.thought_id),
    ]
    assert [e["score"] for e in body["entries"]] == [9.0, 5.0]


def test_signals_used_is_returned_empty_not_hidden(
    client: TestClient, store: InMemoryStore
) -> None:
    store.thoughts.append(_thought())
    entry = client.get("/v1/cognitive-state/focus").json()["entries"][0]
    assert entry["signals_used"] == []


# --- sensors -------------------------------------------------------------------------


def test_sensors_serve_the_stored_record_with_its_lifecycle_state(
    client: TestClient, store: InMemoryStore
) -> None:
    moment = datetime(2026, 9, 26, 8, 0, tzinfo=UTC)
    store.sensors.extend(
        [
            SensorStateRecord(
                sensor_id="voice-sensor-1",
                sensor_type="voice",
                state="stopped",
                reported_at=moment + timedelta(seconds=5),
                last_event_id=uuid4(),
            ),
            SensorStateRecord(
                sensor_id="companion-filesystem",
                sensor_type="filesystem",
                state="running",
                reported_at=moment,
                last_event_id=uuid4(),
            ),
        ]
    )
    assert client.get("/v1/cognitive-state/sensors").json() == {
        "sensors": [
            {
                "sensor_id": "companion-filesystem",
                "sensor_type": "filesystem",
                "state": "running",
                "reported_at": "2026-09-26T08:00:00Z",
            },
            {
                "sensor_id": "voice-sensor-1",
                "sensor_type": "voice",
                "state": "stopped",
                "reported_at": "2026-09-26T08:00:05Z",
            },
        ]
    }


# --- P-2: server-side identity ---------------------------------------------------


def test_a_caller_supplied_user_id_is_ignored(client: TestClient, store: InMemoryStore) -> None:
    mine = _thought()
    theirs = _thought(user_id=SOMEONE_ELSE)
    store.thoughts.extend([mine, theirs])

    for path in (
        "/v1/cognitive-state/thoughts",
        f"/v1/cognitive-state/thoughts?user_id={SOMEONE_ELSE}",
    ):
        ids = [t["thought_id"] for t in client.get(path).json()["thoughts"]]
        assert ids == [str(mine.thought_id)]


# --- P-1, §7.4: GET only; an error is never an empty success ---------------------


@pytest.mark.parametrize("path", ["thoughts", "focus", "sensors"])
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_every_other_method_is_405(method: str, path: str, client: TestClient) -> None:
    assert client.request(method, f"/v1/cognitive-state/{path}").status_code == 405


@pytest.mark.parametrize("path", ["thoughts", "focus", "sensors"])
def test_a_store_failure_is_an_error_never_an_empty_list(
    path: str, store: InMemoryStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    store.fail = True
    app = create_app(Settings(primary_user_id=PRIMARY), repository=store)  # type: ignore[arg-type]
    with TestClient(app, raise_server_exceptions=False) as running:
        response = running.get(f"/v1/cognitive-state/{path}")
    assert response.status_code >= 500
