"""`PostgresMemoryRepository` -- implements `domain.ports.MemoryRepository` against
SQLAlchemy async, per the schema in docs/design/phase-1/01-memory-engine.md §4.

One session per operation (never held open across a request), and every write that
must also enqueue an event does so in the same transaction as the entity write --
the transactional outbox pattern (docs/design/phase-1/00-shared-foundations.md).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import func

from nova_memory_engine.domain.models import (
    DecisionRecord,
    MemoryRecord,
    MemoryType,
    ShortTermRecord,
)
from nova_memory_engine.domain.ports import OutboxEvent, OutboxRow, VersionConflictError
from nova_memory_engine.repository.models import (
    AuditLogORM,
    ConsolidationRunORM,
    DecisionRecordORM,
    MemoryRecordORM,
    OutboxEventORM,
    ShortTermRecordORM,
)

_ACTIVE_LIFECYCLE_STATES = ("active", "weak", "archived")


def _outbox_orm(event: OutboxEvent) -> OutboxEventORM:
    return OutboxEventORM(
        subject=event.subject,
        payload=event.payload,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
    )


def _memory_to_domain(row: MemoryRecordORM) -> MemoryRecord:
    return MemoryRecord(
        id=row.id,
        memory_type=MemoryType(row.memory_type),
        content=row.content,
        embedding=list(row.embedding) if row.embedding is not None else None,
        embedding_model=row.embedding_model,
        importance_score=row.importance_score,
        confidence=row.confidence,
        privacy_level=row.privacy_level,
        lifecycle_state=row.lifecycle_state,
        source=row.source,
        source_ref=row.source_ref,
        project_id=row.project_id,
        user_id=row.user_id,
        knowledge_node_id=row.knowledge_node_id,
        type_data=row.type_data,
        access_count=row.access_count,
        last_accessed_at=row.last_accessed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        version=row.version,
    )


def _short_term_to_domain(row: ShortTermRecordORM) -> ShortTermRecord:
    return ShortTermRecord(
        id=row.id,
        content=row.content,
        category=row.category,
        project_id=row.project_id,
        user_id=row.user_id,
        source_ref=row.source_ref,
        expires_at=row.expires_at,
        created_at=row.created_at,
    )


def _decision_to_domain(row: DecisionRecordORM) -> DecisionRecord:
    return DecisionRecord(
        id=row.id,
        memory_record_id=row.memory_record_id,
        objective=row.objective,
        alternatives=list(row.alternatives),
        chosen_alternative=row.chosen_alternative,
        reasoning=row.reasoning,
        tradeoffs=list(row.tradeoffs),
        risks=list(row.risks),
        outcome=row.outcome,
        outcome_recorded_at=row.outcome_recorded_at,
        confidence_at_decision=row.confidence_at_decision,
        created_at=row.created_at,
    )


class PostgresMemoryRepository:
    """`domain.ports.MemoryRepository` implementation. Never imported by `domain/`
    or `api/` -- constructed once in `main.py` and passed in as the port."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_long_term(
        self, record: MemoryRecord, *, outbox_event: OutboxEvent | None = None
    ) -> MemoryRecord:
        async with self._session_factory() as session, session.begin():
            orm = MemoryRecordORM(
                id=record.id,
                memory_type=record.memory_type.value,
                content=record.content,
                embedding=record.embedding,
                embedding_model=record.embedding_model,
                importance_score=record.importance_score,
                confidence=record.confidence,
                privacy_level=record.privacy_level.value,
                lifecycle_state=record.lifecycle_state.value,
                source=record.source,
                source_ref=record.source_ref,
                project_id=record.project_id,
                user_id=record.user_id,
                knowledge_node_id=record.knowledge_node_id,
                type_data=record.type_data,
                access_count=record.access_count,
                last_accessed_at=record.last_accessed_at,
                version=record.version,
            )
            session.add(orm)
            if outbox_event is not None:
                session.add(_outbox_orm(outbox_event))
            await session.flush()
            await session.refresh(orm)
            return _memory_to_domain(orm)

    async def get(self, memory_id: UUID, *, user_id: UUID) -> MemoryRecord | None:
        async with self._session_factory() as session:
            row = await session.get(MemoryRecordORM, memory_id)
            if row is None or row.user_id != user_id:
                return None
            return _memory_to_domain(row)

    async def update(
        self,
        record: MemoryRecord,
        *,
        expected_version: int,
        outbox_event: OutboxEvent | None = None,
    ) -> MemoryRecord:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                update(MemoryRecordORM)
                .where(
                    MemoryRecordORM.id == record.id, MemoryRecordORM.version == expected_version
                )
                .values(
                    content=record.content,
                    importance_score=record.importance_score,
                    confidence=record.confidence,
                    privacy_level=record.privacy_level.value,
                    lifecycle_state=record.lifecycle_state.value,
                    project_id=record.project_id,
                    knowledge_node_id=record.knowledge_node_id,
                    type_data=record.type_data,
                    updated_at=record.updated_at,
                    version=record.version,
                )
            )
            if cast(CursorResult, result).rowcount == 0:
                raise VersionConflictError(record.id, expected_version=expected_version)
            if outbox_event is not None:
                session.add(_outbox_orm(outbox_event))
            row = await session.get(MemoryRecordORM, record.id)
            assert row is not None
            return _memory_to_domain(row)

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
        async with self._session_factory() as session:
            stmt = select(MemoryRecordORM).where(
                MemoryRecordORM.user_id == user_id, MemoryRecordORM.lifecycle_state != "deleted"
            )
            if project_id is not None:
                stmt = stmt.where(MemoryRecordORM.project_id == project_id)
            if memory_type is not None:
                stmt = stmt.where(MemoryRecordORM.memory_type == memory_type.value)
            if start is not None:
                stmt = stmt.where(MemoryRecordORM.created_at >= start)
            if end is not None:
                stmt = stmt.where(MemoryRecordORM.created_at <= end)
            stmt = stmt.order_by(MemoryRecordORM.created_at.desc()).limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            return [_memory_to_domain(row) for row in rows]

    async def list_candidates_for_consolidation(
        self, *, since: datetime, limit: int = 1000
    ) -> list[MemoryRecord]:
        async with self._session_factory() as session:
            stmt = (
                select(MemoryRecordORM)
                .where(MemoryRecordORM.lifecycle_state.in_(_ACTIVE_LIFECYCLE_STATES))
                .where(
                    (MemoryRecordORM.created_at >= since) | (MemoryRecordORM.updated_at >= since)
                )
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_memory_to_domain(row) for row in rows]

    async def list_needing_embedding(
        self, *, current_model: str, limit: int = 100
    ) -> list[MemoryRecord]:
        async with self._session_factory() as session:
            stmt = (
                select(MemoryRecordORM)
                .where(
                    MemoryRecordORM.embedding.is_(None)
                    | (MemoryRecordORM.embedding_model != current_model)
                )
                .order_by(MemoryRecordORM.created_at)
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_memory_to_domain(row) for row in rows]

    async def list_scheduled_for_deletion(self, *, limit: int = 1000) -> list[MemoryRecord]:
        async with self._session_factory() as session:
            stmt = (
                select(MemoryRecordORM)
                .where(MemoryRecordORM.lifecycle_state == "scheduled_for_deletion")
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_memory_to_domain(row) for row in rows]

    async def record_access(self, memory_id: UUID, *, accessed_at: datetime) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(MemoryRecordORM)
                .where(MemoryRecordORM.id == memory_id)
                .values(
                    access_count=MemoryRecordORM.access_count + 1, last_accessed_at=accessed_at
                )
            )

    async def create_short_term(
        self, record: ShortTermRecord, *, outbox_event: OutboxEvent | None = None
    ) -> ShortTermRecord:
        async with self._session_factory() as session, session.begin():
            orm = ShortTermRecordORM(
                id=record.id,
                content=record.content,
                category=record.category,
                project_id=record.project_id,
                user_id=record.user_id,
                source_ref=record.source_ref,
                expires_at=record.expires_at,
            )
            session.add(orm)
            if outbox_event is not None:
                session.add(_outbox_orm(outbox_event))
            await session.flush()
            await session.refresh(orm)
            return _short_term_to_domain(orm)

    async def list_short_term(
        self, *, user_id: UUID, project_id: UUID | None = None, limit: int = 50
    ) -> list[ShortTermRecord]:
        async with self._session_factory() as session:
            stmt = select(ShortTermRecordORM).where(ShortTermRecordORM.user_id == user_id)
            if project_id is not None:
                stmt = stmt.where(ShortTermRecordORM.project_id == project_id)
            stmt = stmt.order_by(ShortTermRecordORM.created_at.desc()).limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            return [_short_term_to_domain(row) for row in rows]

    async def delete_expired_short_term(self, *, now: datetime) -> int:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                delete(ShortTermRecordORM).where(ShortTermRecordORM.expires_at <= now)
            )
            return cast(CursorResult, result).rowcount or 0

    async def create_decision(
        self, decision: DecisionRecord, *, outbox_event: OutboxEvent | None = None
    ) -> DecisionRecord:
        async with self._session_factory() as session, session.begin():
            orm = DecisionRecordORM(
                id=decision.id,
                memory_record_id=decision.memory_record_id,
                objective=decision.objective,
                alternatives=decision.alternatives,
                chosen_alternative=decision.chosen_alternative,
                reasoning=decision.reasoning,
                tradeoffs=decision.tradeoffs,
                risks=decision.risks,
                outcome=decision.outcome,
                outcome_recorded_at=decision.outcome_recorded_at,
                confidence_at_decision=decision.confidence_at_decision,
            )
            session.add(orm)
            if outbox_event is not None:
                session.add(_outbox_orm(outbox_event))
            await session.flush()
            await session.refresh(orm)
            return _decision_to_domain(orm)

    async def get_decision(self, decision_id: UUID) -> DecisionRecord | None:
        async with self._session_factory() as session:
            row = await session.get(DecisionRecordORM, decision_id)
            return _decision_to_domain(row) if row is not None else None

    async def search_decisions(self, *, user_id: UUID, limit: int = 50) -> list[DecisionRecord]:
        async with self._session_factory() as session:
            stmt = (
                select(DecisionRecordORM)
                .join(MemoryRecordORM, MemoryRecordORM.id == DecisionRecordORM.memory_record_id)
                .where(MemoryRecordORM.user_id == user_id)
                .order_by(DecisionRecordORM.created_at.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_decision_to_domain(row) for row in rows]

    async def start_consolidation_run(self) -> UUID:
        async with self._session_factory() as session, session.begin():
            orm = ConsolidationRunORM(status="running")
            session.add(orm)
            await session.flush()
            return orm.id

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
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(ConsolidationRunORM)
                .where(ConsolidationRunORM.id == run_id)
                .values(
                    finished_at=func.now(),
                    records_scanned=records_scanned,
                    records_merged=records_merged,
                    records_advanced=records_advanced,
                    records_deleted=records_deleted,
                    status=status,
                )
            )

    async def append_audit_log(
        self, *, memory_id: UUID, action: str, actor: str, detail: dict[str, Any] | None = None
    ) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                AuditLogORM(
                    memory_record_id=memory_id, action=action, actor=actor, detail=detail
                )
            )

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        async with self._session_factory() as session:
            stmt = (
                select(OutboxEventORM)
                .where(OutboxEventORM.dispatched_at.is_(None))
                .order_by(OutboxEventORM.created_at)
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [
                OutboxRow(
                    id=row.id,
                    subject=row.subject,
                    payload=row.payload,
                    correlation_id=row.correlation_id,
                    causation_id=row.causation_id,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(OutboxEventORM)
                .where(OutboxEventORM.id == outbox_id)
                .values(dispatched_at=func.now())
            )
