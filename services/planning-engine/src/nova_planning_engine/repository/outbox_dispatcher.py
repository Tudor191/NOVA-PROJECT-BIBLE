"""Thin wrapper binding this engine's `source_engine` default onto the shared
transactional-outbox dispatch loop (`nova_service_kit.outbox`, Extraction C)
-- mirrors `memory-engine`'s own `repository/outbox_dispatcher.py` exactly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nova_service_kit import dispatch_ready_events as _dispatch_ready_events

from nova_planning_engine.domain.ports import PlanningRepository

if TYPE_CHECKING:
    from nova_eventbus_sdk import EventBus

    from nova_planning_engine.observability import PlanningEngineMetrics

DEFAULT_BATCH_SIZE = 100


async def dispatch_ready_events(
    repository: PlanningRepository,
    bus: EventBus,
    *,
    source_engine: str = "planning-engine",
    batch_size: int = DEFAULT_BATCH_SIZE,
    metrics: PlanningEngineMetrics | None = None,
) -> int:
    """Returns the number of rows dispatched."""
    return await _dispatch_ready_events(
        repository, bus, source_engine=source_engine, batch_size=batch_size, metrics=metrics
    )
