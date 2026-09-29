"""The `perception.workspace.observed` handler -- Phase 4F.P, A-4FP-1 and
A-4FP-10 (SD-6) (TDD 4F.P §30.2).

What this tier proves without a broker or a database: an envelope becomes at
most one thought and at most one trigger, an invalid or foreign observation
writes nothing, and **the handler never raises**. The store keeps the two
statements' semantics (`test_ingestion_orchestration.Store`'s, restated); the
real statements and a real broker are proven in
`tests/integration/test_ingestion_real_postgres.py`.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import PurePath
from uuid import UUID, uuid4

import pytest
from nova_cognitive_state_engine.domain.models import ActiveThought, AttentionLayer
from nova_cognitive_state_engine.domain.ports import ThoughtNotFoundError, TriggerDelivery
from nova_cognitive_state_engine.events.handlers import (
    WORKSPACE_OBSERVED_SUBJECT,
    make_workspace_observation_handler,
)
from nova_contracts import EventEnvelope
from nova_contracts.events.autonomy import AutonomyDecisionRequestedPayload

PRIMARY = UUID("00000000-0000-0000-0000-000000000001")


class Store:
    def __init__(self) -> None:
        self.thoughts: dict[UUID, ActiveThought] = {}

    async def get_thought(self, thought_id: UUID) -> ActiveThought:
        if thought_id not in self.thoughts:
            raise ThoughtNotFoundError(thought_id)
        return self.thoughts[thought_id]

    async def insert_thought_if_absent(self, thought: ActiveThought) -> ActiveThought | None:
        if thought.thought_id in self.thoughts:
            return None
        self.thoughts[thought.thought_id] = thought
        return thought

    async def compare_and_set_layer(
        self,
        thought_id: UUID,
        *,
        expected: AttentionLayer,
        target: AttentionLayer,
        updated_at: datetime,
    ) -> ActiveThought | None:
        current = self.thoughts.get(thought_id)
        if current is None or current.attention_layer is not expected:
            return None
        moved = current.model_copy(update={"attention_layer": target, "updated_at": updated_at})
        self.thoughts[thought_id] = moved
        return moved


class BrokenStore(Store):
    async def insert_thought_if_absent(self, thought: ActiveThought) -> ActiveThought | None:
        raise ConnectionError("store unavailable")


class RecordingTrigger:
    def __init__(self) -> None:
        self.requests: list[AutonomyDecisionRequestedPayload] = []

    async def request_decision(
        self, payload: AutonomyDecisionRequestedPayload, *, correlation_id: UUID
    ) -> TriggerDelivery:
        self.requests.append(payload)
        return TriggerDelivery(status="decided", outcome="propose", subject_id=uuid4())


def _payload(path: str, **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "object_id": "ws-" + hashlib.sha256(PurePath(path).as_posix().encode()).hexdigest(),
        "label": PurePath(path).name,
        "user_id": str(PRIMARY),
        "object_type": "project",
        "project_id": None,
        "sensor_id": "companion-filesystem",
        "observed_at": datetime.now(UTC).isoformat(),
        "schema_version": 1,
    }
    body.update(overrides)
    return body


def _envelope(payload: dict[str, object], *, event_id: UUID | None = None) -> EventEnvelope:
    values: dict[str, object] = {
        "subject": WORKSPACE_OBSERVED_SUBJECT,
        "source_engine": "perception-engine",
        "correlation_id": uuid4(),
        "payload": payload,
    }
    if event_id is not None:
        values["event_id"] = event_id
    return EventEnvelope(**values)  # type: ignore[arg-type]


def _fresh_path() -> str:
    return f"/workspace/{uuid4()}/notes.md"


def test_the_subject_is_the_existing_internal_one() -> None:
    assert WORKSPACE_OBSERVED_SUBJECT == "perception.workspace.observed"


async def test_an_observation_becomes_one_promoted_thought_and_one_trigger() -> None:
    store, trigger = Store(), RecordingTrigger()
    handle = make_workspace_observation_handler(store, trigger, user_id=PRIMARY)

    await handle(_envelope(_payload(_fresh_path())))

    assert len(store.thoughts) == 1
    (thought,) = store.thoughts.values()
    assert thought.attention_layer is AttentionLayer.IMMEDIATE
    assert len(trigger.requests) == 1


async def test_the_same_envelope_twice_and_a_new_envelope_for_the_same_file_add_nothing() -> None:
    """A-4FP-9: a re-published envelope (same `event_id`) and a later
    observation (new `event_id`) of the same file both write nothing."""
    store, trigger = Store(), RecordingTrigger()
    handle = make_workspace_observation_handler(store, trigger, user_id=PRIMARY)
    path = _fresh_path()
    first = _envelope(_payload(path))

    await handle(first)
    await handle(first)
    await handle(_envelope(_payload(path, label="renamed.md")))

    assert len(store.thoughts) == 1
    assert len(trigger.requests) == 1


async def test_an_invalid_payload_is_dropped_and_nothing_is_written(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store, trigger = Store(), RecordingTrigger()
    handle = make_workspace_observation_handler(store, trigger, user_id=PRIMARY)

    with caplog.at_level(logging.WARNING):
        await handle(_envelope(_payload(_fresh_path(), object_type="window")))
        await handle(_envelope({"label": "notes.md"}))

    assert store.thoughts == {}
    assert trigger.requests == []
    assert "workspace_observation_rejected_invalid_payload" in caplog.text


async def test_a_foreign_users_observation_is_dropped_and_nothing_is_written(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store, trigger = Store(), RecordingTrigger()
    handle = make_workspace_observation_handler(store, trigger, user_id=PRIMARY)

    with caplog.at_level(logging.WARNING):
        await handle(_envelope(_payload(_fresh_path(), user_id=str(uuid4()))))

    assert store.thoughts == {}
    assert trigger.requests == []
    assert "workspace_observation_dropped_foreign_user" in caplog.text


async def test_a_store_failure_is_logged_never_raised(caplog: pytest.LogCaptureFixture) -> None:
    trigger = RecordingTrigger()
    handle = make_workspace_observation_handler(BrokenStore(), trigger, user_id=PRIMARY)

    with caplog.at_level(logging.ERROR):
        await handle(_envelope(_payload(_fresh_path())))  # must not raise

    assert trigger.requests == []
    assert "workspace_observation_not_ingested" in caplog.text


async def test_the_label_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    """Checked over every attribute of every record -- the structured `extra`
    fields included, which `caplog.text` does not show."""
    store, trigger = Store(), RecordingTrigger()
    handle = make_workspace_observation_handler(store, trigger, user_id=PRIMARY)
    with caplog.at_level(logging.DEBUG):
        await handle(_envelope(_payload(_fresh_path(), label="private-plan.md")))
        # ... nor when the payload is rejected: a missing field's error would
        # otherwise carry the whole payload as its input.
        rejected = _payload(_fresh_path(), label="private-plan.md")
        del rejected["object_id"]
        await handle(_envelope(rejected))

    records = {record.getMessage(): vars(record) for record in caplog.records}
    assert set(records) == {
        "workspace_observation_ingested",
        "workspace_observation_rejected_invalid_payload",
    }
    everything = " ".join(str(fields) for fields in records.values())
    assert "private-plan.md" not in everything
    # The rejection itself is still reported, by field.
    assert "object_id" in str(records["workspace_observation_rejected_invalid_payload"]["detail"])
