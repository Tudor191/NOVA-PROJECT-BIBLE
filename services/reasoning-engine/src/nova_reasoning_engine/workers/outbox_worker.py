"""Outbox worker -- Arq job driving `repository/outbox_dispatcher.py`'s
`dispatch_ready_events` on a short, fixed poll interval, so a reasoning
process's associated event reaches the bus within a bounded delay under
normal operation (docs/design/phase-2b/00-reasoning-engine.md §20). This
engine owns no graph, so there is no two-phase saga step here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nova_eventbus_sdk.interface import EventBus
from nova_observability import get_logger

from nova_reasoning_engine.domain.ports import ReasoningRepository
from nova_reasoning_engine.repository.outbox_dispatcher import dispatch_ready_events

if TYPE_CHECKING:
    from nova_reasoning_engine.observability import ReasoningEngineMetrics

logger = get_logger("reasoning-engine.workers.outbox")


async def run_outbox_dispatch(
    repository: ReasoningRepository,
    bus: EventBus,
    *,
    metrics: ReasoningEngineMetrics | None = None,
) -> int:
    dispatched = await dispatch_ready_events(repository, bus, metrics=metrics)
    if dispatched:
        logger.info("outbox dispatch", extra={"dispatched": dispatched})
    return dispatched


async def arq_run_outbox_dispatch(ctx: dict) -> None:
    """Arq entrypoint (`WorkerSettings.cron_jobs` in `workers/__init__.py`)."""
    await run_outbox_dispatch(ctx["repository"], ctx["bus"], metrics=ctx.get("metrics"))
