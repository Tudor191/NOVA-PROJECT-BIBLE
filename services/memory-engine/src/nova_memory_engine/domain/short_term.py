"""Short Term Memory -- docs/design/phase-1/01-memory-engine.md §2. Postgres
`short_term_record`, hours-to-days TTL, enforced by `workers/consolidation_worker.py`
(not a Postgres-native TTL, per the schema's own comment).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from nova_contracts import ShortTermMemoryCreatedPayload

from nova_memory_engine.domain.models import ShortTermRecord
from nova_memory_engine.domain.ports import MemoryRepository, OutboxEvent

DEFAULT_TTL = timedelta(hours=24)


async def remember(
    repository: MemoryRepository,
    *,
    user_id: UUID,
    content: str,
    category: str,
    correlation_id: UUID,
    project_id: UUID | None = None,
    source_ref: UUID | None = None,
    ttl: timedelta = DEFAULT_TTL,
) -> ShortTermRecord:
    record = ShortTermRecord(
        content=content,
        category=category,
        project_id=project_id,
        user_id=user_id,
        source_ref=source_ref,
        expires_at=datetime.now(UTC) + ttl,
    )
    outbox_event = OutboxEvent(
        subject="memory.short_term.created",
        payload=ShortTermMemoryCreatedPayload(
            short_term_id=record.id,
            user_id=record.user_id,
            project_id=record.project_id,
            category=record.category,
            expires_at=record.expires_at,
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    return await repository.create_short_term(record, outbox_event=outbox_event)


async def recall_recent(
    repository: MemoryRepository,
    *,
    user_id: UUID,
    project_id: UUID | None = None,
    limit: int = 50,
) -> list[ShortTermRecord]:
    return await repository.list_short_term(user_id=user_id, project_id=project_id, limit=limit)


async def expire_due(repository: MemoryRepository, *, now: datetime | None = None) -> int:
    """Deletes every `short_term_record` whose `expires_at` has passed. Called by
    `workers/consolidation_worker.py`; returns the number of rows removed."""
    return await repository.delete_expired_short_term(now=now or datetime.now(UTC))
