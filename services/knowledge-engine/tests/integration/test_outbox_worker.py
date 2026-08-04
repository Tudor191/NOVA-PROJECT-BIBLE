"""`workers/outbox_worker.py`'s degraded-threshold check (docs/design/phase-1/
02-knowledge-engine.md §17 step 4) -- a row stuck pending its Neo4j write past
the configured threshold trips a metric, without ever publishing a bus event for
it (an operational signal, not a domain fact).
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus
from nova_graphstore_sdk.backends.in_memory import InMemoryGraphStore
from nova_knowledge_engine.domain import graph_operations
from nova_knowledge_engine.domain.models import KnowledgeNode, SourceAttribution
from nova_knowledge_engine.workers.outbox_worker import run_outbox_dispatch

from tests.fakes.metadata_repository import FakeKnowledgeMetadataRepository


async def _acquire_node(repository: FakeKnowledgeMetadataRepository) -> KnowledgeNode:
    node = KnowledgeNode(node_id="technology:postgresql", label="Technology", name="PostgreSQL")
    source = SourceAttribution(node_id=node.node_id, source_type="user")
    return await graph_operations.create_node(
        repository, node=node, source=source, actor="test", correlation_id=uuid4()
    )


async def test_fresh_pending_graph_write_is_not_flagged_degraded() -> None:
    repository = FakeKnowledgeMetadataRepository()
    await _acquire_node(repository)
    stale = await repository.count_stale_pending_graph_writes(
        older_than=datetime.now(UTC) - timedelta(minutes=15)
    )
    assert stale == 0


async def test_old_pending_graph_write_is_flagged_degraded() -> None:
    repository = FakeKnowledgeMetadataRepository()
    node = await _acquire_node(repository)
    [outbox_record] = repository.outbox.values()
    outbox_record.created_at = datetime.now(UTC) - timedelta(minutes=30)

    stale = await repository.count_stale_pending_graph_writes(
        older_than=datetime.now(UTC) - timedelta(minutes=15)
    )
    assert stale == 1
    assert node.node_id  # sanity: node was actually created


async def test_run_outbox_dispatch_applies_before_checking_degraded_status() -> None:
    """A row that's actually processed within a single `run_outbox_dispatch`
    call should never be flagged degraded even if it happened to be old --
    `apply_pending_graph_writes` runs first, so nothing stays pending to check."""
    repository = FakeKnowledgeMetadataRepository()
    await _acquire_node(repository)
    [outbox_record] = repository.outbox.values()
    outbox_record.created_at = datetime.now(UTC) - timedelta(minutes=30)

    graph_store = InMemoryGraphStore()
    await graph_store.connect()
    bus = InMemoryEventBus()
    await bus.connect()

    applied, dispatched = await run_outbox_dispatch(
        repository, graph_store, bus, degraded_threshold_minutes=15
    )

    assert applied == 1
    assert dispatched == 1
