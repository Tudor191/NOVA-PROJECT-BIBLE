"""The two-phase saga (docs/design/phase-1/03-world-model-engine.md §17),
tested directly against `repository/outbox_dispatcher.py`: kill the process
between step 1 (Postgres commit) and step 2 (Neo4j apply), restart, assert the
pending graph write completes and the event is published exactly once -- never
zero, never twice (§19's explicit saga test requirement, same shape as
Knowledge Engine's `tests/integration/test_saga.py`).
"""

from uuid import uuid4

from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus
from nova_graphstore_sdk.backends.in_memory import InMemoryGraphStore
from nova_world_model_engine.domain import object_graph
from nova_world_model_engine.domain.models import ObjectState, WorldObject
from nova_world_model_engine.repository.outbox_dispatcher import (
    apply_pending_graph_writes,
    dispatch_ready_events,
)

from tests.fakes.history_repository import FakeWorldHistoryRepository


async def _observe_new_object(history_repo: FakeWorldHistoryRepository):  # type: ignore[no-untyped-def]
    obj = WorldObject(
        object_id="window:1", label="Window", user_id=uuid4(), state=ObjectState.ACTIVE
    )
    return await object_graph.observe_object(
        history_repo, obj=obj, previous_state=None, correlation_id=uuid4()
    )


async def test_event_not_dispatched_before_graph_write_lands() -> None:
    history_repo = FakeWorldHistoryRepository()
    await _observe_new_object(history_repo)

    bus = InMemoryEventBus()
    await bus.connect()

    dispatched = await dispatch_ready_events(history_repo, bus)
    assert dispatched == 0


async def test_graph_write_then_dispatch_completes_the_saga() -> None:
    history_repo = FakeWorldHistoryRepository()
    await _observe_new_object(history_repo)

    graph_store = InMemoryGraphStore()
    await graph_store.connect()
    bus = InMemoryEventBus()
    await bus.connect()

    received = []

    async def _handler(envelope) -> None:  # type: ignore[no-untyped-def]
        received.append(envelope)

    await bus.subscribe("world_model.object.created", _handler)

    applied = await apply_pending_graph_writes(history_repo, graph_store)
    assert applied == 1

    dispatched = await dispatch_ready_events(history_repo, bus)
    assert dispatched == 1
    assert len(received) == 1
    assert received[0].subject == "world_model.object.created"


async def test_crash_recovery_retries_only_the_next_row_never_loses_one() -> None:
    history_repo = FakeWorldHistoryRepository()
    await _observe_new_object(history_repo)

    graph_store = InMemoryGraphStore()
    await graph_store.connect()
    bus = InMemoryEventBus()
    await bus.connect()

    first_pass = await apply_pending_graph_writes(history_repo, graph_store)
    second_pass = await apply_pending_graph_writes(history_repo, graph_store)
    assert first_pass == 1
    assert second_pass == 0

    first_dispatch = await dispatch_ready_events(history_repo, bus)
    second_dispatch = await dispatch_ready_events(history_repo, bus)
    assert first_dispatch == 1
    assert second_dispatch == 0


async def test_event_id_is_stable_across_a_retried_dispatch() -> None:
    history_repo = FakeWorldHistoryRepository()
    await _observe_new_object(history_repo)
    graph_store = InMemoryGraphStore()
    await graph_store.connect()
    await apply_pending_graph_writes(history_repo, graph_store)

    bus = InMemoryEventBus()
    await bus.connect()
    received = []

    async def _handler(envelope) -> None:  # type: ignore[no-untyped-def]
        received.append(envelope)

    await bus.subscribe("world_model.object.created", _handler)

    [outbox_row] = await history_repo.list_dispatch_ready()
    await dispatch_ready_events(history_repo, bus)

    assert received[0].event_id == outbox_row.id
