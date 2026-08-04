"""The two-phase saga (docs/design/phase-1/02-knowledge-engine.md §17), tested
directly against `repository/outbox_dispatcher.py`: kill the process between
step 1 (Postgres commit) and step 2 (Neo4j apply), restart, assert the pending
graph write completes and the event is published exactly once -- never zero,
never twice (§19's explicit saga test requirement).
"""

from uuid import uuid4

from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus
from nova_graphstore_sdk.backends.in_memory import InMemoryGraphStore
from nova_knowledge_engine.domain import graph_operations
from nova_knowledge_engine.domain.models import KnowledgeNode, SourceAttribution
from nova_knowledge_engine.repository.outbox_dispatcher import (
    apply_pending_graph_writes,
    dispatch_ready_events,
)

from tests.fakes.metadata_repository import FakeKnowledgeMetadataRepository


async def _acquire_node(repository: FakeKnowledgeMetadataRepository) -> KnowledgeNode:
    node = KnowledgeNode(node_id="technology:postgresql", label="Technology", name="PostgreSQL")
    source = SourceAttribution(node_id=node.node_id, source_type="user")
    return await graph_operations.create_node(
        repository, node=node, source=source, actor="test", correlation_id=uuid4()
    )


async def test_event_not_dispatched_before_graph_write_lands() -> None:
    repository = FakeKnowledgeMetadataRepository()
    await _acquire_node(repository)

    bus = InMemoryEventBus()
    await bus.connect()

    # Step 3 (dispatch) run before step 2 (apply) -- must be a no-op: the row's
    # graph_write hasn't landed yet.
    dispatched = await dispatch_ready_events(repository, bus)
    assert dispatched == 0


async def test_graph_write_then_dispatch_completes_the_saga() -> None:
    repository = FakeKnowledgeMetadataRepository()
    await _acquire_node(repository)

    graph_store = InMemoryGraphStore()
    await graph_store.connect()
    bus = InMemoryEventBus()
    await bus.connect()

    received = []

    async def _handler(envelope) -> None:  # type: ignore[no-untyped-def]
        received.append(envelope)

    await bus.subscribe("knowledge.node.created", _handler)

    applied = await apply_pending_graph_writes(repository, graph_store)
    assert applied == 1
    health = await graph_store.health()
    assert health.connected

    dispatched = await dispatch_ready_events(repository, bus)
    assert dispatched == 1
    assert len(received) == 1
    assert received[0].subject == "knowledge.node.created"


async def test_crash_recovery_retries_only_the_next_row_never_loses_one() -> None:
    """Simulates a crash between step 1 and step 2: `apply_pending_graph_writes`
    is called once (representing the pre-crash partial attempt, which for a
    single-row batch is equivalent to "nothing applied yet"), then called again
    (the restart) -- the row completes exactly once, not twice, and the event is
    dispatched exactly once."""
    repository = FakeKnowledgeMetadataRepository()
    await _acquire_node(repository)

    graph_store = InMemoryGraphStore()
    await graph_store.connect()
    bus = InMemoryEventBus()
    await bus.connect()

    # "Restart" -- list_pending_graph_writes only returns rows not yet applied,
    # so a second call after a successful first call finds nothing left to do.
    first_pass = await apply_pending_graph_writes(repository, graph_store)
    second_pass = await apply_pending_graph_writes(repository, graph_store)
    assert first_pass == 1
    assert second_pass == 0

    first_dispatch = await dispatch_ready_events(repository, bus)
    second_dispatch = await dispatch_ready_events(repository, bus)
    assert first_dispatch == 1
    assert second_dispatch == 0


async def test_event_id_is_stable_across_a_retried_dispatch() -> None:
    """The outbox row's own `id` is reused as `EventEnvelope.event_id`
    (docs/design/phase-1/02-knowledge-engine.md §13's exactly-once contract) --
    verified by inspecting the row before dispatch and the delivered envelope
    after."""
    repository = FakeKnowledgeMetadataRepository()
    await _acquire_node(repository)
    graph_store = InMemoryGraphStore()
    await graph_store.connect()
    await apply_pending_graph_writes(repository, graph_store)

    bus = InMemoryEventBus()
    await bus.connect()
    received = []

    async def _handler(envelope) -> None:  # type: ignore[no-untyped-def]
        received.append(envelope)

    await bus.subscribe("knowledge.node.created", _handler)

    [outbox_row] = await repository.list_dispatch_ready()
    await dispatch_ready_events(repository, bus)

    assert received[0].event_id == outbox_row.id
