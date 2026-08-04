"""Outbox dispatcher -- docs/design/phase-1/00-shared-foundations.md's
transactional outbox pattern, driven by `workers/outbox_worker.py`. Polls
undispatched `memory.outbox_event` rows, publishes them via `nova-eventbus-sdk`,
and marks each dispatched immediately after a successful publish. This is the only
place Memory Engine calls `EventBus.publish()` -- `domain/` writes never publish
directly; they enqueue an `OutboxEvent` that `MemoryRepository` persists atomically
with the entity row.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from nova_contracts import EventEnvelope
from nova_eventbus_sdk.interface import EventBus
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_memory_engine.repository.models import OutboxEventORM

if TYPE_CHECKING:
    from nova_memory_engine.observability import MemoryEngineMetrics

DEFAULT_BATCH_SIZE = 100


async def dispatch_pending(
    session_factory: async_sessionmaker[AsyncSession],
    bus: EventBus,
    *,
    source_engine: str = "memory-engine",
    batch_size: int = DEFAULT_BATCH_SIZE,
    metrics: MemoryEngineMetrics | None = None,
) -> int:
    """Publish every undispatched row, oldest first; mark each dispatched right
    after its own publish succeeds -- never batched at the commit level, so a crash
    partway through only risks re-publishing the *next* unmarked row, never
    silently loses one (docs/design/phase-1/01-memory-engine.md §17).

    The outbox row's own `id` is reused as `EventEnvelope.event_id` (not a fresh
    UUID) specifically so a retried publish after a crash carries the *same*
    `event_id` -- that stability is what makes "exactly-once delivery via
    `event_id` dedup on the consumer side" (docs/design/phase-1/
    01-memory-engine.md §19) actually achievable; a fresh id per attempt would
    silently break that contract.

    Returns the number of rows dispatched.
    """
    dispatched = 0
    async with session_factory() as session:
        stmt = (
            select(OutboxEventORM)
            .where(OutboxEventORM.dispatched_at.is_(None))
            .order_by(OutboxEventORM.created_at)
            .limit(batch_size)
        )
        rows = (await session.execute(stmt)).scalars().all()
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
            await session.execute(
                update(OutboxEventORM)
                .where(OutboxEventORM.id == row.id)
                .values(dispatched_at=datetime.now(UTC))
            )
            await session.commit()
            dispatched += 1
            if metrics is not None:
                metrics.outbox_dispatched_total.add(1, {"subject": row.subject})
    return dispatched
