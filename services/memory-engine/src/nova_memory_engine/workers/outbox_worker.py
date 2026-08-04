"""Outbox worker -- Arq job driving `repository/outbox_dispatcher.py` on a short,
fixed poll interval, so a write's associated event reaches the bus within a bounded
delay under normal operation (docs/design/phase-1/00-shared-foundations.md's
transactional outbox pattern).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nova_eventbus_sdk.interface import EventBus
from nova_observability import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_memory_engine.repository.outbox_dispatcher import dispatch_pending

if TYPE_CHECKING:
    from nova_memory_engine.observability import MemoryEngineMetrics

logger = get_logger("memory-engine.workers.outbox")


async def run_outbox_dispatch(
    session_factory: async_sessionmaker[AsyncSession],
    bus: EventBus,
    *,
    metrics: MemoryEngineMetrics | None = None,
) -> int:
    dispatched = await dispatch_pending(session_factory, bus, metrics=metrics)
    if dispatched:
        logger.info("outbox dispatch", extra={"dispatched": dispatched})
    return dispatched


async def arq_run_outbox_dispatch(ctx: dict) -> None:
    """Arq entrypoint (`WorkerSettings.cron_jobs` in `workers/__init__.py`)."""
    await run_outbox_dispatch(ctx["session_factory"], ctx["bus"], metrics=ctx.get("metrics"))
