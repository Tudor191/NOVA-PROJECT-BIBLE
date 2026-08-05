"""Outbox worker -- Arq job driving `repository/outbox_dispatcher.py`'s
`dispatch_ready_events` on a short, fixed poll interval, so a usage record's
associated event reaches the bus within a bounded delay under normal operation
(docs/design/phase-2a/00-ai-model-orchestration-engine.md §17). This engine
owns no graph (§4), so there is no two-phase saga step here, unlike Knowledge/
World Model Engine's own outbox workers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nova_eventbus_sdk.interface import EventBus
from nova_observability import get_logger

from nova_ai_model_orchestration_engine.domain.ports import UsageRepository
from nova_ai_model_orchestration_engine.repository.outbox_dispatcher import dispatch_ready_events

if TYPE_CHECKING:
    from nova_ai_model_orchestration_engine.observability import AiModelOrchestrationEngineMetrics

logger = get_logger("ai-model-orchestration-engine.workers.outbox")


async def run_outbox_dispatch(
    repository: UsageRepository,
    bus: EventBus,
    *,
    metrics: AiModelOrchestrationEngineMetrics | None = None,
) -> int:
    dispatched = await dispatch_ready_events(repository, bus, metrics=metrics)
    if dispatched:
        logger.info("outbox dispatch", extra={"dispatched": dispatched})
    return dispatched


async def arq_run_outbox_dispatch(ctx: dict) -> None:
    """Arq entrypoint (`WorkerSettings.cron_jobs` in `workers/__init__.py`)."""
    await run_outbox_dispatch(ctx["usage_repository"], ctx["bus"], metrics=ctx.get("metrics"))
