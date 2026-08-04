"""Outbox worker -- Arq job driving `repository/outbox_dispatcher.py`'s
two-phase saga (docs/design/phase-1/03-world-model-engine.md §17) on a short,
fixed poll interval: apply pending Neo4j writes, then dispatch events ready to
publish. Identical mechanism to Knowledge Engine's own `workers/
outbox_worker.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from nova_eventbus_sdk.interface import EventBus
from nova_graphstore_sdk import GraphStore
from nova_observability import get_logger

from nova_world_model_engine.domain.ports import WorldHistoryRepository
from nova_world_model_engine.repository.outbox_dispatcher import (
    apply_pending_graph_writes,
    dispatch_ready_events,
)

if TYPE_CHECKING:
    from nova_world_model_engine.observability import WorldModelEngineMetrics

logger = get_logger("world-model-engine.workers.outbox")

DEFAULT_DEGRADED_THRESHOLD_MINUTES = 15


async def run_outbox_dispatch(
    repository: WorldHistoryRepository,
    graph_store: GraphStore,
    bus: EventBus,
    *,
    degraded_threshold_minutes: int = DEFAULT_DEGRADED_THRESHOLD_MINUTES,
    metrics: WorldModelEngineMetrics | None = None,
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
    repository: WorldHistoryRepository,
    *,
    degraded_threshold_minutes: int,
    metrics: WorldModelEngineMetrics | None,
) -> None:
    """docs/design/phase-1/03-world-model-engine.md §17 (Knowledge Engine's
    §02 §17 step 4, same mechanism): a row stuck pending its Neo4j write past
    `degraded_threshold_minutes` is an operational signal, not a domain fact."""
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
        ctx["history_repository"],
        ctx["graph_store"],
        ctx["bus"],
        degraded_threshold_minutes=ctx.get(
            "graph_write_degraded_threshold_minutes", DEFAULT_DEGRADED_THRESHOLD_MINUTES
        ),
        metrics=ctx.get("metrics"),
    )
