"""Protocols this package depends on -- implements nothing itself
(docs/design/phase-1/01-memory-engine.md §1). `domain/` may only import this module,
`domain/models.py`, and other `domain/` modules -- never FastAPI, SQLAlchemy, Redis,
or a concrete backend (docs/architecture/03-backend-architecture.md §1).

`VectorIndex` and `EmbeddingProvider` are re-exports of the shared SDK Protocols
(`nova-vectorstore-sdk`, `nova-embeddings-sdk`) rather than reinvented here --
importing a Protocol type is not importing a concrete backend, so this does not
violate the framework-free rule, and it keeps one definition of each interface
instead of two that could drift.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from nova_contracts import EventEnvelope
from nova_embeddings_sdk import EmbeddingProvider
from nova_vectorstore_sdk import VectorStore as VectorIndex
from pydantic import BaseModel

from nova_memory_engine.domain.models import (
    DecisionRecord,
    MemoryRecord,
    MemoryType,
    ShortTermRecord,
)

__all__ = [
    "EmbeddingProvider",
    "EventPublisher",
    "MemoryRepository",
    "OutboxEvent",
    "OutboxRow",
    "VectorIndex",
    "WorkingMemoryStore",
]


class OutboxEvent(BaseModel):
    """One row to insert into `memory.outbox_event` in the same transaction as the
    entity write it accompanies (docs/design/phase-1/00-shared-foundations.md's
    transactional outbox pattern). `MemoryRepository` implementations are
    responsible for the atomicity; `domain/` only describes what to enqueue."""

    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None


class OutboxRow(BaseModel):
    """A persisted, not-yet-dispatched outbox row, as read back by
    `list_dispatch_ready` -- carries its own `id`, reused as `EventEnvelope.
    event_id` for exactly-once delivery, the same convention every other
    engine's outbox dispatcher already uses. Added per the Project Health
    Review (August 2026)/`docs/design/nova-service-kit/
    boilerplate-extraction-proposal.md` Extraction C prerequisite: this
    engine's outbox dispatcher previously bypassed the repository-port
    abstraction entirely, talking to SQLAlchemy directly instead of going
    through `list_dispatch_ready`/`mark_dispatched` like every other engine.
    """

    id: UUID
    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None
    created_at: datetime


@runtime_checkable
class MemoryRepository(Protocol):
    """Persistence port for `memory_record`, `short_term_record`, `decision_record`,
    `consolidation_run`, and `audit_log` (docs/design/phase-1/01-memory-engine.md
    §4). Implemented by `repository/postgres_memory_repository.py` against
    SQLAlchemy async; never imported directly by `domain/`.
    """

    async def create_long_term(
        self, record: MemoryRecord, *, outbox_event: OutboxEvent | None = None
    ) -> MemoryRecord: ...

    async def get(self, memory_id: UUID, *, user_id: UUID) -> MemoryRecord | None: ...

    async def update(
        self,
        record: MemoryRecord,
        *,
        expected_version: int,
        outbox_event: OutboxEvent | None = None,
    ) -> MemoryRecord:
        """Optimistic-concurrency update (`WHERE version = expected_version`).
        Raises `VersionConflictError` if the row moved under us."""
        ...

    async def list_by_timeline(
        self,
        *,
        user_id: UUID,
        project_id: UUID | None = None,
        memory_type: MemoryType | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]: ...

    async def list_candidates_for_consolidation(
        self, *, since: datetime, limit: int = 1000
    ) -> list[MemoryRecord]: ...

    async def list_scheduled_for_deletion(
        self, *, limit: int = 1000
    ) -> list[MemoryRecord]:
        """Every `scheduled_for_deletion` record, for the grace-period check
        (docs/design/phase-1/01-memory-engine.md §6) -- deliberately not filtered
        by `updated_at` the way `list_candidates_for_consolidation` is, since a
        record that has sat scheduled for a long time is exactly the one this
        query needs to find."""
        ...

    async def list_needing_embedding(
        self, *, current_model: str, limit: int = 100
    ) -> list[MemoryRecord]:
        """Rows where `embedding IS NULL`, or where `embedding_model != current_model`
        (a re-embedding due to ADR-010's model changing) -- docs/design/phase-1/
        01-memory-engine.md §10. Ordered oldest-created first.

        The embedding *write* itself goes through `VectorIndex.upsert_batch`
        (`nova-vectorstore-sdk`), not a `MemoryRepository` method -- `VectorIndex`
        already owns writing to the `embedding`/`embedding_model` columns of a row
        this schema's own Alembic migration created; a second write path here would
        duplicate that responsibility (docs/design/phase-1/00-shared-foundations.md).
        """
        ...

    async def record_access(self, memory_id: UUID, *, accessed_at: datetime) -> None:
        """Fire-and-forget access bookkeeping (docs/design/phase-1/
        01-memory-engine.md §7 step 6) -- never raises in a way that fails a read."""
        ...

    async def create_short_term(
        self, record: ShortTermRecord, *, outbox_event: OutboxEvent | None = None
    ) -> ShortTermRecord: ...

    async def list_short_term(
        self, *, user_id: UUID, project_id: UUID | None = None, limit: int = 50
    ) -> list[ShortTermRecord]: ...

    async def delete_expired_short_term(self, *, now: datetime) -> int:
        """Returns the number of rows deleted."""
        ...

    async def create_decision(
        self, decision: DecisionRecord, *, outbox_event: OutboxEvent | None = None
    ) -> DecisionRecord: ...

    async def get_decision(self, decision_id: UUID) -> DecisionRecord | None: ...

    async def search_decisions(self, *, user_id: UUID, limit: int = 50) -> list[DecisionRecord]: ...

    async def start_consolidation_run(self) -> UUID: ...

    async def complete_consolidation_run(
        self,
        run_id: UUID,
        *,
        records_scanned: int,
        records_merged: int,
        records_advanced: int,
        records_deleted: int,
        status: str,
    ) -> None: ...

    async def append_audit_log(
        self, *, memory_id: UUID, action: str, actor: str, detail: dict[str, Any] | None = None
    ) -> None: ...

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]: ...

    async def mark_dispatched(self, outbox_id: UUID) -> None: ...


@runtime_checkable
class WorkingMemoryStore(Protocol):
    """Redis-backed, task-scoped primary store for Working Memory
    (docs/design/phase-1/01-memory-engine.md §2) -- not a cache of anything else."""

    async def put(self, *, user_id: UUID, session_id: str, key: str, value: str) -> None: ...

    async def get_all(self, *, user_id: UUID, session_id: str) -> dict[str, str]: ...

    async def clear(self, *, user_id: UUID, session_id: str) -> None: ...


@runtime_checkable
class EventPublisher(Protocol):
    """The one synchronous cross-engine call `domain/relationship.py` makes
    (`knowledge.link.request` / `knowledge.traverse.request`), never a direct Neo4j
    write (docs/design/phase-1/01-memory-engine.md §5). Structurally identical to
    `nova_eventbus_sdk.interface.EventBus.request` so the real `BoundEventBus`
    satisfies this Protocol without an adapter -- `domain/` still never imports
    `nova_eventbus_sdk` itself, only this narrower shape.
    """

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope: ...


class VersionConflictError(RuntimeError):
    """Raised by `MemoryRepository.update` when `expected_version` no longer
    matches the stored row -- a concurrent writer (e.g. the consolidation worker)
    got there first."""

    def __init__(self, memory_id: UUID, *, expected_version: int) -> None:
        super().__init__(
            f"Memory {memory_id} was not at version {expected_version}; "
            f"concurrent update detected."
        )
        self.memory_id = memory_id
        self.expected_version = expected_version
