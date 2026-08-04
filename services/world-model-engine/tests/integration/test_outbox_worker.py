"""`workers/outbox_worker.py`'s degraded-threshold check (docs/design/phase-1/
03-world-model-engine.md §17 step 4, same mechanism as Knowledge Engine) -- a
row stuck pending its Neo4j write past the configured threshold trips a
metric, without ever publishing a bus event for it.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus
from nova_graphstore_sdk.backends.in_memory import InMemoryGraphStore
from nova_world_model_engine.domain import object_graph
from nova_world_model_engine.domain.models import ObjectState, WorldObject
from nova_world_model_engine.workers.outbox_worker import run_outbox_dispatch

from tests.fakes.history_repository import FakeWorldHistoryRepository


async def _observe_new_object(history_repo: FakeWorldHistoryRepository):  # type: ignore[no-untyped-def]
    obj = WorldObject(
        object_id="window:1", label="Window", user_id=uuid4(), state=ObjectState.ACTIVE
    )
    return await object_graph.observe_object(
        history_repo, obj=obj, previous_state=None, correlation_id=uuid4()
    )


async def test_fresh_pending_graph_write_is_not_flagged_degraded() -> None:
    history_repo = FakeWorldHistoryRepository()
    await _observe_new_object(history_repo)
    stale = await history_repo.count_stale_pending_graph_writes(
        older_than=datetime.now(UTC) - timedelta(minutes=15)
    )
    assert stale == 0


async def test_old_pending_graph_write_is_flagged_degraded() -> None:
    history_repo = FakeWorldHistoryRepository()
    await _observe_new_object(history_repo)
    [outbox_record] = history_repo.outbox.values()
    outbox_record.created_at = datetime.now(UTC) - timedelta(minutes=30)

    stale = await history_repo.count_stale_pending_graph_writes(
        older_than=datetime.now(UTC) - timedelta(minutes=15)
    )
    assert stale == 1


async def test_run_outbox_dispatch_applies_before_checking_degraded_status() -> None:
    history_repo = FakeWorldHistoryRepository()
    await _observe_new_object(history_repo)
    [outbox_record] = history_repo.outbox.values()
    outbox_record.created_at = datetime.now(UTC) - timedelta(minutes=30)

    graph_store = InMemoryGraphStore()
    await graph_store.connect()
    bus = InMemoryEventBus()
    await bus.connect()

    applied, dispatched = await run_outbox_dispatch(
        history_repo, graph_store, bus, degraded_threshold_minutes=15
    )

    assert applied == 1
    assert dispatched == 1
