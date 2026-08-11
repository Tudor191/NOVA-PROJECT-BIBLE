"""Outbox worker -- Arq job driving `repository/outbox_dispatcher.py`'s
`dispatch_ready_events` on a short, fixed poll interval (Priority 1's
precedent, docs/design/phase-2d/05-conversation-intelligence-closure.md
Sec3.5: wired from day one even before this engine has anything real to
publish -- Step 9's Fork D warm-case delivery is the first real enqueue)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nova_eventbus_sdk.interface import EventBus
from nova_observability import get_logger

from nova_digital_twin_engine.domain.ports import DigitalTwinRepository
from nova_digital_twin_engine.repository.outbox_dispatcher import dispatch_ready_events

if TYPE_CHECKING:
    from nova_digital_twin_engine.observability import DigitalTwinEngineMetrics

logger = get_logger("digital-twin-engine.workers.outbox")


async def run_outbox_dispatch(
    repository: DigitalTwinRepository,
    bus: EventBus,
    *,
    metrics: DigitalTwinEngineMetrics | None = None,
) -> int:
    dispatched = await dispatch_ready_events(repository, bus, metrics=metrics)
    if dispatched:
        logger.info("outbox dispatch", extra={"dispatched": dispatched})
    return dispatched


async def arq_run_outbox_dispatch(ctx: dict) -> None:
    """Arq entrypoint (`WorkerSettings.cron_jobs` in `workers/__init__.py`)."""
    await run_outbox_dispatch(ctx["repository"], ctx["bus"], metrics=ctx.get("metrics"))
