"""Thin wrapper binding this engine's `source_engine` default onto the shared
transactional-outbox dispatch loop (Project Health Review, August 2026;
`docs/design/nova-service-kit/boilerplate-extraction-proposal.md`
Extraction C) -- the loop itself now lives once in `nova_service_kit.outbox`.

**Renamed from `dispatch_pending` to `dispatch_ready_events`** as part of this
extraction, resolving the naming drift the Project Health Review flagged
(every other engine already used `dispatch_ready_events`): this function
previously bypassed the repository-port abstraction entirely, issuing raw
`select`/`update` statements against `OutboxEventORM` directly through a
`session_factory` parameter instead of going through
`MemoryRepository.list_dispatch_ready`/`.mark_dispatched` like every other
engine's dispatcher already did. Those two port methods were added to
`MemoryRepository` (`domain/ports.py`) and `PostgresMemoryRepository` as this
extraction's explicitly-scoped prerequisite, so this dispatcher can now take
`repository: MemoryRepository` like every other engine's, rather than a raw
`session_factory`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nova_service_kit import dispatch_ready_events as _dispatch_ready_events

from nova_memory_engine.domain.ports import MemoryRepository

if TYPE_CHECKING:
    from nova_eventbus_sdk import EventBus

    from nova_memory_engine.observability import MemoryEngineMetrics

DEFAULT_BATCH_SIZE = 100


async def dispatch_ready_events(
    repository: MemoryRepository,
    bus: EventBus,
    *,
    source_engine: str = "memory-engine",
    batch_size: int = DEFAULT_BATCH_SIZE,
    metrics: MemoryEngineMetrics | None = None,
) -> int:
    """Returns the number of rows dispatched."""
    return await _dispatch_ready_events(
        repository, bus, source_engine=source_engine, batch_size=batch_size, metrics=metrics
    )
