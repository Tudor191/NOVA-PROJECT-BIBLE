"""Maintenance worker -- Arq scheduled job driving `domain/evolution.py`,
`domain/discovery.py`, and `domain/compression.py` against `KnowledgeMetadataRepository`
and `GraphStore` (docs/design/phase-1/02-knowledge-engine.md §1: "relationship
discovery, dedup, confidence updates"). Scheduled every
`Settings.maintenance_interval_hours` (a fixed interval for Phase 1, matching
Memory Engine's `consolidation_worker`'s own accepted tradeoff, §6).

Unlike Memory Engine's `consolidation_run` table, docs/design/phase-1/
02-knowledge-engine.md §4's schema has no equivalent run-tracking table for
Knowledge Engine -- this worker's progress is observable via
`KnowledgeEngineMetrics` and structured logs only, not a persisted run row.

"Confidence updates" (the third responsibility named in §1's component table) are
not a separately-invented decay formula here -- confidence only changes on
corroboration (`domain/validation.py`, at acquisition time) and on structural
contradiction resolution; §6 specifies no periodic confidence-decay predicate the
way Memory Engine's §9 importance formula does, so nothing is guessed at. Noted as
a known limitation, not an oversight.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from nova_graphstore_sdk import GraphStore, TraversalDirection, TraversalSpec
from nova_observability import get_logger

from nova_knowledge_engine.domain import compression, discovery, evolution, graph_operations
from nova_knowledge_engine.domain.models import NodeVersionHistoryEntry
from nova_knowledge_engine.domain.ports import KnowledgeMetadataRepository

if TYPE_CHECKING:
    from nova_knowledge_engine.observability import KnowledgeEngineMetrics

logger = get_logger("knowledge-engine.workers.maintenance")

WORKER_ACTOR = "maintenance_worker"
SCAN_BATCH_SIZE = 500


async def _relationship_count(graph_store: GraphStore, node_id: str) -> int:
    try:
        result = await graph_store.traverse(
            node_id, TraversalSpec(direction=TraversalDirection.BOTH, max_hops=1, limit=100)
        )
    except Exception:
        logger.warning("relationship count degraded", extra={"node_id": node_id}, exc_info=True)
        return 0
    return len({n.id for n in result.nodes if n.id != node_id})


async def _advance_layers(
    repository: KnowledgeMetadataRepository,
    graph_store: GraphStore,
    nodes: list,
    *,
    metrics: KnowledgeEngineMetrics | None,
) -> int:
    advanced = 0
    for node in nodes:
        sources = await repository.list_sources(node.node_id)
        relationship_count = await _relationship_count(graph_store, node.node_id)
        usage = await repository.usage_summary(node.node_id)
        decision = evolution.next_layer(
            node.node_id,
            evolution.EvolutionInput(
                layer=node.layer,
                confidence=node.confidence,
                source_count=len(sources),
                relationship_count=relationship_count,
                usage=usage,
            ),
        )
        if decision is None:
            continue
        await graph_operations.advance_layer(
            repository,
            node=node,
            expected_version=node.version,
            new_layer=decision.to_layer,
            reason=decision.reason,
            actor=WORKER_ACTOR,
            correlation_id=uuid4(),
        )
        if metrics is not None:
            metrics.layer_advances_total.add(1, {"to_layer": decision.to_layer.value})
        advanced += 1
    return advanced


async def _discover_relationships(repository: KnowledgeMetadataRepository, nodes: list) -> int:
    embedded = [n for n in nodes if n.embedding is not None]
    discovered = 0
    for candidate in embedded:
        others = [n for n in embedded if n.node_id != candidate.node_id]
        for rel in discovery.discover_related_to(candidate, others):
            await graph_operations.create_relationship(
                repository,
                from_id=rel.from_id,
                to_id=rel.to_id,
                relationship_type=rel.relationship_type,
                confidence=rel.confidence,
                source="discovery",
                correlation_id=uuid4(),
            )
            discovered += 1
    return discovered


async def _flag_duplicates(repository: KnowledgeMetadataRepository, nodes: list) -> int:
    """Detection only -- never merges or deletes (docs/design/phase-1/
    02-knowledge-engine.md §12: "nothing important should disappear permanently").
    Each superseded node gets an auditable `node_version_history` row pointing at
    its cluster's `keep_id`; a human or future Reasoning Engine (Phase 2) decides
    whether/how to act on it."""
    by_id = {n.node_id: n for n in nodes}
    flagged = 0
    for merge in compression.find_duplicate_clusters(nodes):
        for superseded_id in merge.superseded_ids:
            await repository.append_version_history(
                NodeVersionHistoryEntry(
                    node_id=superseded_id,
                    version=by_id[superseded_id].version,
                    change_type="duplicate_detected",
                    new_value={"keep_id": merge.keep_id},
                    changed_by=WORKER_ACTOR,
                )
            )
            flagged += 1
    return flagged


async def run_maintenance(
    repository: KnowledgeMetadataRepository,
    graph_store: GraphStore,
    *,
    now: datetime | None = None,
    metrics: KnowledgeEngineMetrics | None = None,
) -> None:
    now = now or datetime.now(UTC)
    nodes = await repository.list_nodes(limit=SCAN_BATCH_SIZE)
    logger.info("maintenance run started", extra={"nodes_scanned": len(nodes)})

    advanced = await _advance_layers(repository, graph_store, nodes, metrics=metrics)
    discovered = await _discover_relationships(repository, nodes)
    flagged = await _flag_duplicates(repository, nodes)

    logger.info(
        "maintenance run completed",
        extra={
            "nodes_scanned": len(nodes),
            "layers_advanced": advanced,
            "relationships_discovered": discovered,
            "duplicates_flagged": flagged,
        },
    )


async def arq_run_maintenance(ctx: dict) -> None:  # noqa: ARG001 -- Arq's job signature
    """Arq entrypoint (`WorkerSettings.cron_jobs` in `workers/__init__.py`)."""
    await run_maintenance(ctx["repository"], ctx["graph_store"], metrics=ctx.get("metrics"))
