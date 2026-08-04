"""Outbox worker -- Arq job driving `repository/outbox_dispatcher.py`'s two-phase
saga (docs/design/phase-1/02-knowledge-engine.md §17) on a short, fixed poll
interval: apply pending Neo4j writes, then dispatch events ready to publish.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from nova_eventbus_sdk.interface import EventBus
from nova_graphstore_sdk import GraphStore
from nova_observability import get_logger

from nova_knowledge_engine.domain.ports import KnowledgeMetadataRepository
from nova_knowledge_engine.repository.outbox_dispatcher import (
    apply_pending_graph_writes,
    dispatch_ready_events,
)

if TYPE_CHECKING:
    from nova_knowledge_engine.observability import KnowledgeEngineMetrics

logger = get_logger("knowledge-engine.workers.outbox")

DEFAULT_DEGRADED_THRESHOLD_MINUTES = 15


async def run_outbox_dispatch(
    repository: KnowledgeMetadataRepository,
    graph_store: GraphStore,
    bus: EventBus,
    *,
    degraded_threshold_minutes: int = DEFAULT_DEGRADED_THRESHOLD_MINUTES,
    metrics: KnowledgeEngineMetrics | None = None,
) -> tuple[int, int]:
    applied = await apply_pending_graph_writes(repository, graph_store, metrics=metrics)
    dispatched = await dispatch_ready_events(repository, bus, metrics=metrics)
    if applied or dispatched:
        logger.info("outbox dispatch", extra={"applied": applied, "dispatched": dispatched})

    await _check_degraded_graph_writes(
        repository, degraded_threshold_minutes=degraded_threshold_minutes, metrics=metrics
    )
    return applied, dispatched


async def _check_degraded_graph_writes(
    repository: KnowledgeMetadataRepository,
    *,
    degraded_threshold_minutes: int,
    metrics: KnowledgeEngineMetrics | None,
) -> None:
    """docs/design/phase-1/02-knowledge-engine.md §17 step 4: a row stuck pending
    its Neo4j write past `degraded_threshold_minutes` is an operational signal
    (Prometheus metric + log), not a domain fact -- never a bus event."""
    older_than = datetime.now(UTC) - timedelta(minutes=degraded_threshold_minutes)
    stale = await repository.count_stale_pending_graph_writes(older_than=older_than)
    if stale == 0:
        return
    logger.warning(
        "graph writes stuck pending past degraded threshold",
        extra={"stale_count": stale, "threshold_minutes": degraded_threshold_minutes},
    )
    if metrics is not None:
        metrics.graph_write_degraded_total.add(stale)


async def arq_run_outbox_dispatch(ctx: dict) -> None:
    """Arq entrypoint (`WorkerSettings.cron_jobs` in `workers/__init__.py`)."""
    await run_outbox_dispatch(
        ctx["repository"],
        ctx["graph_store"],
        ctx["bus"],
        degraded_threshold_minutes=ctx.get(
            "graph_write_degraded_threshold_minutes", DEFAULT_DEGRADED_THRESHOLD_MINUTES
        ),
        metrics=ctx.get("metrics"),
    )
