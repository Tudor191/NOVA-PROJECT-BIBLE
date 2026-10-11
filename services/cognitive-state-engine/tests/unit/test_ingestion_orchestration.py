"""One ingestion step -- Phase 4F.P, A-4FP-1, A-4FP-2 and A-4FP-9 (TDD 4F.P
§30.2, §13).

**Duplicates are the point.** Every row of TDD 4F.P §13's duplicate table that
this engine owns has a test here: a re-published observation, a later
observation of the same file, a second sensor, concurrent deliveries -- each
writes nothing and promotes nothing after the first. The store is an in-memory
one that keeps the two statements' semantics (insert-if-absent, and the
compare-and-set), so every assertion is about the resulting state and the
number of trigger requests. The same properties are proven against real
Postgres in `tests/integration/test_ingestion_real_postgres.py`.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import PurePath
from uuid import UUID, uuid4

import pytest
from nova_cognitive_state_engine.domain.authoring import T1
from nova_cognitive_state_engine.domain.ingestion import thought_id_for
from nova_cognitive_state_engine.domain.models import ActiveThought, AttentionLayer
from nova_cognitive_state_engine.domain.ports import ThoughtNotFoundError, TriggerDelivery
from nova_cognitive_state_engine.ingestion_orchestration import ingest_workspace_observation
from nova_contracts.events.autonomy import AutonomyDecisionRequestedPayload
from nova_contracts.events.perception import PerceptionWorkspaceObservedPayload

PRIMARY = UUID("00000000-0000-0000-0000-000000000001")
SOMEONE_ELSE = UUID("00000000-0000-0000-0000-0000000000aa")
NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


class Store:
    """Keeps thoughts, with A-4FP-1's and A-4FP-8's statement semantics. Neither
    method awaits between its check and its write, so each is atomic on the
    event loop as the statement is in Postgres."""

    def __init__(self) -> None:
        self.thoughts: dict[UUID, ActiveThought] = {}
        self.inserts = 0
        self.compare_and_sets = 0

    async def get_thought(self, thought_id: UUID) -> ActiveThought:
        await asyncio.sleep(0)
        if thought_id not in self.thoughts:
            raise ThoughtNotFoundError(thought_id)
        return self.thoughts[thought_id]

    async def insert_thought_if_absent(self, thought: ActiveThought) -> ActiveThought | None:
        await asyncio.sleep(0)
        if thought.thought_id in self.thoughts:
            return None
        self.inserts += 1
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
        self.compare_and_sets += 1
        current = self.thoughts.get(thought_id)
        if current is None or current.attention_layer is not expected:
            return None
        moved = current.model_copy(update={"attention_layer": target, "updated_at": updated_at})
        self.thoughts[thought_id] = moved
        return moved

    async def upsert_thought(self, thought: ActiveThought) -> ActiveThought:
        raise AssertionError("ingestion must never upsert (TDD 4F.P NP-8)")

    async def move_layer(self, thought_id: UUID, layer: AttentionLayer) -> ActiveThought:
        raise AssertionError("promotion must never move unconditionally (TDD 4F.P NP-7)")


class FailingPromotionStore(Store):
    """The insert succeeds; the promotion's read raises -- FP-15's window."""

    async def get_thought(self, thought_id: UUID) -> ActiveThought:
        raise ConnectionError("database went away after the insert")


class FailingInsertStore(Store):
    async def insert_thought_if_absent(self, thought: ActiveThought) -> ActiveThought | None:
        raise ConnectionError("database unavailable")


class RecordingTrigger:
    def __init__(self, reply: TriggerDelivery | None = None) -> None:
        self.requests: list[AutonomyDecisionRequestedPayload] = []
        self._reply = reply or TriggerDelivery(status="decided", outcome="propose")

    async def request_decision(
        self, payload: AutonomyDecisionRequestedPayload, *, correlation_id: UUID
    ) -> TriggerDelivery:
        self.requests.append(payload)
        return self._reply


def _fresh_path() -> str:
    """A path no other test uses, so no test can pass on another's thought."""
    return f"/workspace/{uuid4()}/notes.md"


def _object_id(path: str) -> str:
    return "ws-" + hashlib.sha256(PurePath(path.strip()).as_posix().encode()).hexdigest()


def _observation(
    path: str | None = None, **overrides: object
) -> PerceptionWorkspaceObservedPayload:
    fields: dict = {
        "object_id": _object_id(path or _fresh_path()),
        "label": "notes.md",
        "user_id": PRIMARY,
        "object_type": "project",
        "project_id": None,
        "sensor_id": "companion-filesystem",
        "observed_at": NOW,
    }
    fields.update(overrides)
    return PerceptionWorkspaceObservedPayload(**fields)


async def _ingest(observation, store, trigger, now=NOW):  # type: ignore[no-untyped-def]
    return await ingest_workspace_observation(
        observation, repository=store, trigger=trigger, user_id=PRIMARY, now=now
    )


# --- a new object: one thought, one promotion, one trigger -------------------------------


async def test_a_new_object_is_inserted_promoted_once_and_triggers_once() -> None:
    store, trigger = Store(), RecordingTrigger()
    observation = _observation(label="nova")

    result = await _ingest(observation, store, trigger)

    assert result.outcome == "created"
    assert result.thought_id == thought_id_for(observation.object_id)
    assert result.promotion is not None and result.promotion.moved is True
    assert result.promotion.trigger == TriggerDelivery(status="decided", outcome="propose")
    stored = store.thoughts[result.thought_id]
    assert stored.attention_layer is AttentionLayer.IMMEDIATE
    assert stored.proposed_action == T1.author(label="nova")
    assert len(trigger.requests) == 1
    assert trigger.requests[0].thought_id == result.thought_id
    assert trigger.requests[0].title == "Review the workspace after activity in nova"


async def test_the_one_instant_is_written_to_both_timestamps_and_the_promotion() -> None:
    store = Store()
    result = await _ingest(_observation(), store, RecordingTrigger())
    stored = store.thoughts[result.thought_id]  # type: ignore[index]
    assert stored.created_at == NOW
    assert stored.updated_at == NOW


async def test_the_thought_is_this_engines_user_s_not_the_payload_s() -> None:
    store = Store()
    result = await _ingest(_observation(), store, RecordingTrigger())
    assert store.thoughts[result.thought_id].user_id == PRIMARY  # type: ignore[index]


async def test_a_project_id_is_fixed_at_creation() -> None:
    store, path = Store(), _fresh_path()
    project = uuid4()
    first = await _ingest(_observation(path, project_id=project), store, RecordingTrigger())
    await _ingest(_observation(path, project_id=uuid4()), store, RecordingTrigger())
    assert store.thoughts[first.thought_id].related_projects == (project,)  # type: ignore[index]


# --- duplicates write nothing and promote nothing (TDD 4F.P §13) --------------------------


async def test_a_repeated_observation_writes_nothing_and_triggers_nothing() -> None:
    """§13 rows 1 and 4: an outbox re-publish, or a later observation of the
    same file, carrying a different label, project and clock reading."""
    store, trigger, path = Store(), RecordingTrigger(), _fresh_path()
    first = await _ingest(_observation(path, label="a.md"), store, trigger)
    before = store.thoughts[first.thought_id]  # type: ignore[index]

    repeat = await _ingest(
        _observation(path, label="b.md", project_id=uuid4(), sensor_id="second-sensor"),
        store,
        trigger,
        now=NOW + timedelta(hours=1),
    )

    assert repeat.outcome == "duplicate"
    assert repeat.thought_id == first.thought_id
    assert repeat.promotion is None
    assert store.thoughts[first.thought_id] == before  # type: ignore[index]
    assert store.inserts == 1
    assert store.compare_and_sets == 1
    assert len(trigger.requests) == 1


async def test_a_duplicate_of_a_thought_still_at_active_is_not_promoted() -> None:
    """A-4FP-2 (and NP-9): promotion belongs to the step whose insert created
    the thought, never to a later observation -- even one that finds the
    thought un-promoted after a lost initiative."""
    store, trigger, path = FailingPromotionStore(), RecordingTrigger(), _fresh_path()
    lost = await _ingest(_observation(path), store, trigger)
    assert lost.outcome == "initiative_lost"
    left_behind = store.thoughts[lost.thought_id]  # type: ignore[index]
    assert left_behind.attention_layer is AttentionLayer.ACTIVE

    # A working store holding exactly what the lost step left behind.
    working = Store()
    working.thoughts[left_behind.thought_id] = left_behind
    repeat = await _ingest(_observation(path), working, trigger, now=NOW + timedelta(hours=1))

    assert repeat.outcome == "duplicate"
    assert working.thoughts[left_behind.thought_id] == left_behind
    assert working.compare_and_sets == 0
    assert trigger.requests == []


async def test_concurrent_deliveries_of_one_object_create_one_thought_and_one_trigger() -> None:
    """§13 row 2: only the step whose insert returned the row promotes."""
    store, trigger, path = Store(), RecordingTrigger(), _fresh_path()

    results = await asyncio.gather(
        *(_ingest(_observation(path), store, trigger) for _ in range(10))
    )

    assert sorted(result.outcome for result in results) == ["created"] + ["duplicate"] * 9
    assert len(store.thoughts) == 1
    assert len(trigger.requests) == 1


async def test_a_new_file_path_is_a_new_initiative() -> None:
    store, trigger = Store(), RecordingTrigger()
    first = await _ingest(_observation(_fresh_path()), store, trigger)
    second = await _ingest(_observation(_fresh_path()), store, trigger)
    assert first.outcome == second.outcome == "created"
    assert first.thought_id != second.thought_id
    assert len(trigger.requests) == 2


# --- nothing is written for a foreign user (SD-1) ----------------------------------------


async def test_a_foreign_users_observation_writes_nothing() -> None:
    store, trigger = Store(), RecordingTrigger()
    result = await _ingest(_observation(user_id=SOMEONE_ELSE), store, trigger)
    assert result.outcome == "foreign_user"
    assert result.thought_id is None
    assert store.thoughts == {}
    assert store.inserts == 0
    assert trigger.requests == []


# --- failure windows: reported, never retried (A-4FP-2, FP-15) ----------------------------


async def test_a_promotion_that_raises_after_the_insert_loses_the_initiative() -> None:
    store, trigger = FailingPromotionStore(), RecordingTrigger()
    result = await _ingest(_observation(), store, trigger)

    assert result.outcome == "initiative_lost"
    assert result.thought_id in store.thoughts
    assert result.error is not None and "ConnectionError" in result.error
    assert store.thoughts[result.thought_id].attention_layer is AttentionLayer.ACTIVE  # type: ignore[index]
    assert store.compare_and_sets == 0
    assert trigger.requests == []


async def test_an_insert_that_raises_propagates_and_writes_nothing() -> None:
    store, trigger = FailingInsertStore(), RecordingTrigger()
    with pytest.raises(ConnectionError):
        await _ingest(_observation(), store, trigger)
    assert store.thoughts == {}
    assert trigger.requests == []


@pytest.mark.parametrize(
    "status", ["decided", "rejected", "degraded", "unavailable", "unconfirmed", "failed"]
)
async def test_no_trigger_outcome_is_retried(status: str) -> None:
    trigger = RecordingTrigger(TriggerDelivery(status=status, error="x"))  # type: ignore[arg-type]
    store = Store()
    result = await _ingest(_observation(), store, trigger)
    assert result.outcome == "created"
    assert len(trigger.requests) == 1
    assert result.promotion is not None and result.promotion.trigger is not None
    assert result.promotion.trigger.status == status
    # The promotion stands whatever became of the trigger: nothing demotes.
    assert store.thoughts[result.thought_id].attention_layer is AttentionLayer.IMMEDIATE  # type: ignore[index]
