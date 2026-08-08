"""`FakeMemoryRepository` -- an in-memory `domain.ports.MemoryRepository`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from nova_memory_engine.domain.models import (
    DecisionRecord,
    MemoryRecord,
    MemoryType,
    ShortTermRecord,
)
from nova_memory_engine.domain.ports import OutboxEvent, OutboxRow, VersionConflictError


@dataclass
class RecordedOutboxEvent:
    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None


@dataclass
class RecordedAuditEntry:
    memory_id: UUID
    action: str
    actor: str
    detail: dict[str, Any] | None


@dataclass
class ConsolidationRunRecord:
    id: UUID
    status: str = "running"
    records_scanned: int = 0
    records_merged: int = 0
    records_advanced: int = 0
    records_deleted: int = 0


class FakeMemoryRepository:
    """Implements `domain.ports.MemoryRepository` in memory. Every write appends to
    `outbox_events` (mirroring the real transactional-outbox row), so tests can
    assert exactly what an operation would have published without a real Event
    Bus dispatch -- `dispatch_fake_outbox` in this module drains it through a real
    `EventBus` when a test wants that."""

    def __init__(self) -> None:
        self.memories: dict[UUID, MemoryRecord] = {}
        self.short_term: dict[UUID, ShortTermRecord] = {}
        self.decisions: dict[UUID, DecisionRecord] = {}
        self.consolidation_runs: dict[UUID, ConsolidationRunRecord] = {}
        self.outbox_events: list[RecordedOutboxEvent] = []
        self.audit_log: list[RecordedAuditEntry] = []

    def _record_outbox(self, event: OutboxEvent | None) -> None:
        if event is not None:
            self.outbox_events.append(
                RecordedOutboxEvent(
                    subject=event.subject,
                    payload=event.payload,
                    correlation_id=event.correlation_id,
                    causation_id=event.causation_id,
                )
            )

    async def create_long_term(
        self, record: MemoryRecord, *, outbox_event: OutboxEvent | None = None
    ) -> MemoryRecord:
        self.memories[record.id] = record
        self._record_outbox(outbox_event)
        return record

    async def get(self, memory_id: UUID, *, user_id: UUID) -> MemoryRecord | None:
        record = self.memories.get(memory_id)
        if record is None or record.user_id != user_id:
            return None
        return record

    async def update(
        self,
        record: MemoryRecord,
        *,
        expected_version: int,
        outbox_event: OutboxEvent | None = None,
    ) -> MemoryRecord:
        existing = self.memories.get(record.id)
        if existing is None or existing.version != expected_version:
            raise VersionConflictError(record.id, expected_version=expected_version)
        self.memories[record.id] = record
        self._record_outbox(outbox_event)
        return record

    async def list_by_timeline(
        self,
        *,
        user_id: UUID,
        project_id: UUID | None = None,
        memory_type: MemoryType | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        results = [
            r
            for r in self.memories.values()
            if r.user_id == user_id
            and r.lifecycle_state.value != "deleted"
            and (project_id is None or r.project_id == project_id)
            and (memory_type is None or r.memory_type == memory_type)
            and (start is None or r.created_at >= start)
            and (end is None or r.created_at <= end)
        ]
        results.sort(key=lambda r: r.created_at, reverse=True)
        return results[:limit]

    async def list_candidates_for_consolidation(
        self, *, since: datetime, limit: int = 1000
    ) -> list[MemoryRecord]:
        results = [
            r
            for r in self.memories.values()
            if r.lifecycle_state.value in ("active", "weak", "archived")
            and (r.created_at >= since or r.updated_at >= since)
        ]
        return results[:limit]

    async def list_scheduled_for_deletion(self, *, limit: int = 1000) -> list[MemoryRecord]:
        results = [
            r for r in self.memories.values() if r.lifecycle_state.value == "scheduled_for_deletion"
        ]
        return results[:limit]

    async def list_needing_embedding(
        self, *, current_model: str, limit: int = 100
    ) -> list[MemoryRecord]:
        results = [
            r
            for r in self.memories.values()
            if r.embedding is None or r.embedding_model != current_model
        ]
        results.sort(key=lambda r: r.created_at)
        return results[:limit]

    async def record_access(self, memory_id: UUID, *, accessed_at: datetime) -> None:
        record = self.memories.get(memory_id)
        if record is not None:
            record.access_count += 1
            record.last_accessed_at = accessed_at

    async def create_short_term(
        self, record: ShortTermRecord, *, outbox_event: OutboxEvent | None = None
    ) -> ShortTermRecord:
        self.short_term[record.id] = record
        self._record_outbox(outbox_event)
        return record

    async def list_short_term(
        self, *, user_id: UUID, project_id: UUID | None = None, limit: int = 50
    ) -> list[ShortTermRecord]:
        results = [
            r
            for r in self.short_term.values()
            if r.user_id == user_id and (project_id is None or r.project_id == project_id)
        ]
        results.sort(key=lambda r: r.created_at, reverse=True)
        return results[:limit]

    async def delete_expired_short_term(self, *, now: datetime) -> int:
        expired = [rid for rid, r in self.short_term.items() if r.expires_at <= now]
        for rid in expired:
            del self.short_term[rid]
        return len(expired)

    async def create_decision(
        self, decision: DecisionRecord, *, outbox_event: OutboxEvent | None = None
    ) -> DecisionRecord:
        self.decisions[decision.id] = decision
        self._record_outbox(outbox_event)
        return decision

    async def get_decision(self, decision_id: UUID) -> DecisionRecord | None:
        return self.decisions.get(decision_id)

    async def search_decisions(self, *, user_id: UUID, limit: int = 50) -> list[DecisionRecord]:
        owned_memory_ids = {m.id for m in self.memories.values() if m.user_id == user_id}
        results = [d for d in self.decisions.values() if d.memory_record_id in owned_memory_ids]
        results.sort(key=lambda d: d.created_at, reverse=True)
        return results[:limit]

    async def start_consolidation_run(self) -> UUID:
        run_id = uuid4()
        self.consolidation_runs[run_id] = ConsolidationRunRecord(id=run_id)
        return run_id

    async def complete_consolidation_run(
        self,
        run_id: UUID,
        *,
        records_scanned: int,
        records_merged: int,
        records_advanced: int,
        records_deleted: int,
        status: str,
    ) -> None:
        run = self.consolidation_runs[run_id]
        run.status = status
        run.records_scanned = records_scanned
        run.records_merged = records_merged
        run.records_advanced = records_advanced
        run.records_deleted = records_deleted

    async def append_audit_log(
        self, *, memory_id: UUID, action: str, actor: str, detail: dict[str, Any] | None = None
    ) -> None:
        self.audit_log.append(
            RecordedAuditEntry(memory_id=memory_id, action=action, actor=actor, detail=detail)
        )

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        return []

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        return None
