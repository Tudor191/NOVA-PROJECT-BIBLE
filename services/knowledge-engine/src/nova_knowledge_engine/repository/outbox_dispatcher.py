"""The two-phase saga dispatcher (docs/design/phase-1/02-knowledge-engine.md §17):

1. `apply_pending_graph_writes` -- rows where `graph_write IS NOT NULL AND
   graph_applied_at IS NULL` get their Neo4j write applied (via
   `domain.graph_operations.apply_graph_write`), then `graph_applied_at` is set.
   A failed Neo4j write leaves the row pending, retried on the next poll -- never
   lost, never double-reported. Genuinely engine-specific (touches
   `nova_graphstore_sdk` and this engine's own `domain.graph_operations`), so it
   stays here rather than moving to `nova_service_kit`.
2. `dispatch_ready_events` -- rows ready to publish (`dispatched_at IS NULL AND
   (graph_write IS NULL OR graph_applied_at IS NOT NULL)`) get published via
   `nova-eventbus-sdk`, then `dispatched_at` is set. An event with a pending graph
   write is never published before that write actually lands -- consumers never see
   a node "created" before it's queryable in the graph. The dispatch loop itself is
   now a thin wrapper around the shared `nova_service_kit.dispatch_ready_events`
   (Project Health Review, August 2026; `docs/design/nova-service-kit/
   boilerplate-extraction-proposal.md` Extraction C) -- identical to every other
   engine's own dispatch loop before this extraction.

Both phases mark each row immediately after its own step succeeds (never batched
at the commit level), so a crash partway through only risks reapplying/republishing
the *next* row, never silently drops one -- the same reasoning Memory Engine's
outbox dispatcher documents, extended here to the graph-apply step.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nova_graphstore_sdk import GraphStore
from nova_service_kit import dispatch_ready_events as _dispatch_ready_events

from nova_knowledge_engine.domain import graph_operations
from nova_knowledge_engine.domain.ports import KnowledgeMetadataRepository

if TYPE_CHECKING:
    from nova_eventbus_sdk import EventBus

    from nova_knowledge_engine.observability import KnowledgeEngineMetrics

DEFAULT_BATCH_SIZE = 100


async def apply_pending_graph_writes(
    repository: KnowledgeMetadataRepository,
    graph_store: GraphStore,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    metrics: KnowledgeEngineMetrics | None = None,
) -> int:
    """Saga step 2 (§17). Returns the number of rows applied."""
    applied = 0
    rows = await repository.list_pending_graph_writes(limit=batch_size)
    for row in rows:
        assert row.graph_write is not None
        await graph_operations.apply_graph_write(graph_store, row.graph_write)
        await repository.mark_graph_applied(row.id)
        applied += 1
        if metrics is not None:
            metrics.graph_writes_applied_total.add(1)
    return applied


async def dispatch_ready_events(
    repository: KnowledgeMetadataRepository,
    bus: EventBus,
    *,
    source_engine: str = "knowledge-engine",
    batch_size: int = DEFAULT_BATCH_SIZE,
    metrics: KnowledgeEngineMetrics | None = None,
) -> int:
    """Saga step 3 (§17). Returns the number of rows dispatched."""
    return await _dispatch_ready_events(
        repository, bus, source_engine=source_engine, batch_size=batch_size, metrics=metrics
    )
