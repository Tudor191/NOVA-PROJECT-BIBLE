"""Outbox worker -- Arq job driving `repository/outbox_dispatcher.py` on a short,
fixed poll interval, so a write's associated event (`planning.task_graph.created`)
reaches the bus within a bounded delay under normal operation
(`phase-3b-planning-persistence` precursor, TDD 3B §4/§6.2/§11) -- mirrors
`memory-engine`'s own `workers/outbox_worker.py` exactly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nova_eventbus_sdk.interface import EventBus
from nova_observability import get_logger

from nova_planning_engine.domain.ports import PlanningRepository
from nova_planning_engine.repository.outbox_dispatcher import dispatch_ready_events

if TYPE_CHECKING:
    from nova_planning_engine.observability import PlanningEngineMetrics

logger = get_logger("planning-engine.workers.outbox")


async def run_outbox_dispatch(
    repository: PlanningRepository,
    bus: EventBus,
    *,
    metrics: PlanningEngineMetrics | None = None,
) -> int:
    dispatched = await dispatch_ready_events(repository, bus, metrics=metrics)
    if dispatched:
        logger.info("outbox dispatch", extra={"dispatched": dispatched})
    return dispatched


async def arq_run_outbox_dispatch(ctx: dict) -> None:
    """Arq entrypoint (`WorkerSettings.cron_jobs` in `workers/__init__.py`)."""
    await run_outbox_dispatch(ctx["repository"], ctx["bus"], metrics=ctx.get("metrics"))
