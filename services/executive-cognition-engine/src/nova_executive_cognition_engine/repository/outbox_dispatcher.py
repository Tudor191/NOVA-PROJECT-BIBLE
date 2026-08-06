"""The transactional outbox dispatcher (docs/design/phase-2c/
00-executive-cognition-engine.md §19). This engine owns no graph, so there
is no two-phase saga to run -- an `executive_decision` write and its outbox
row commit together in one Postgres transaction (`finalize_decision`); this
dispatcher's only job is publishing rows that are ready, exactly once.

The outbox row's own `id` is reused as `EventEnvelope.event_id` so a retried
publish after a crash carries the same `event_id`, enabling exactly-once
delivery via consumer-side `event_id` dedup -- the same convention every
prior engine's outbox dispatcher uses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nova_contracts import EventEnvelope
from nova_eventbus_sdk.interface import EventBus

from nova_executive_cognition_engine.domain.ports import ExecutiveRepository

if TYPE_CHECKING:
    from nova_executive_cognition_engine.observability import ExecutiveCognitionEngineMetrics

DEFAULT_BATCH_SIZE = 100


async def dispatch_ready_events(
    repository: ExecutiveRepository,
    bus: EventBus,
    *,
    source_engine: str = "executive-cognition-engine",
    batch_size: int = DEFAULT_BATCH_SIZE,
    metrics: ExecutiveCognitionEngineMetrics | None = None,
) -> int:
    """Returns the number of rows dispatched."""
    dispatched = 0
    rows = await repository.list_dispatch_ready(limit=batch_size)
    for row in rows:
        envelope = EventEnvelope(
            event_id=row.id,
            subject=row.subject,
            source_engine=source_engine,
            correlation_id=row.correlation_id,
            causation_id=row.causation_id,
            payload=row.payload,
        )
        await bus.publish(envelope)
        await repository.mark_dispatched(row.id)
        dispatched += 1
        if metrics is not None:
            metrics.outbox_dispatched_total.add(1, {"subject": row.subject})
    return dispatched
