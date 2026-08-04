"""`PostgresHistoryRepository` -- implements `domain.ports.WorldHistoryRepository`
against SQLAlchemy async, per the schema in docs/design/phase-1/
03-world-model-engine.md §4.

Every write that must also enqueue an event does so in the same transaction as
the entity write -- the transactional outbox pattern (docs/design/phase-1/
00-shared-foundations.md), extended with `graph_write`/`graph_applied_at` for
the two-phase Neo4j saga (§17), identical mechanism to Knowledge Engine (§02
§17). Never touches Redis (that's `redis_context_repository.py`) or Neo4j
(that's `repository/outbox_dispatcher.py`'s job, via
`domain.object_graph.apply_graph_write`).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_world_model_engine.domain.models import (
    ConflictLogEntry,
    ObjectState,
    ObjectStateHistoryEntry,
    Prediction,
    Snapshot,
)
from nova_world_model_engine.domain.ports import GraphWriteIntent, OutboxEvent, OutboxRow
from nova_world_model_engine.repository.models import (
    ConflictLogORM,
    ObjectStateHistoryORM,
    OutboxEventORM,
    PredictionORM,
    SnapshotORM,
)


def _outbox_orm(event: OutboxEvent) -> OutboxEventORM:
    return OutboxEventORM(
        subject=event.subject,
        payload=event.payload,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
        graph_write=event.graph_write.model_dump(mode="json") if event.graph_write else None,
    )


def _outbox_to_domain(row: OutboxEventORM) -> OutboxRow:
    return OutboxRow(
        id=row.id,
        subject=row.subject,
        payload=row.payload,
        correlation_id=row.correlation_id,
        causation_id=row.causation_id,
        graph_write=GraphWriteIntent.model_validate(row.graph_write) if row.graph_write else None,
    )


def _history_to_domain(row: ObjectStateHistoryORM) -> ObjectStateHistoryEntry:
    return ObjectStateHistoryEntry(
        id=row.id,
        object_id=row.object_id,
        object_label=row.object_label,
        user_id=row.user_id,
        previous_state=ObjectState(row.previous_state) if row.previous_state else None,
        new_state=ObjectState(row.new_state),
        confidence=row.confidence,
        changed_at=row.changed_at,
        correlation_id=row.correlation_id,
    )


def _snapshot_to_domain(row: SnapshotORM) -> Snapshot:
    return Snapshot(
        id=row.id,
        user_id=row.user_id,
        taken_at=row.taken_at,
        snapshot_data=row.snapshot_data,
        trigger=row.trigger,
    )


def _prediction_to_domain(row: PredictionORM) -> Prediction:
    return Prediction(
        id=row.id,
        user_id=row.user_id,
        prediction=row.prediction,
        confidence=row.confidence,
        predicted_for=row.predicted_for,
        outcome=row.outcome,
        created_at=row.created_at,
    )


def _conflict_to_domain(row: ConflictLogORM) -> ConflictLogEntry:
    return ConflictLogEntry(
        id=row.id,
        object_id=row.object_id,
        observation_a=row.observation_a,
        observation_b=row.observation_b,
        resolution_strategy=row.resolution_strategy,
        resolved_value=row.resolved_value,
        resolved_at=row.resolved_at,
    )


class PostgresHistoryRepository:
    """`domain.ports.WorldHistoryRepository` implementation. Never imported by
    `domain/` or `api/` -- constructed once in `main.py` and passed in as the
    port."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append_object_history(
        self, entry: ObjectStateHistoryEntry, *, outbox_event: OutboxEvent | None = None
    ) -> ObjectStateHistoryEntry:
        async with self._session_factory() as session, session.begin():
            orm = ObjectStateHistoryORM(
                object_id=entry.object_id,
                object_label=entry.object_label,
                user_id=entry.user_id,
                previous_state=entry.previous_state.value if entry.previous_state else None,
                new_state=entry.new_state.value,
                confidence=entry.confidence,
                correlation_id=entry.correlation_id,
            )
            session.add(orm)
            if outbox_event is not None:
                session.add(_outbox_orm(outbox_event))
            await session.flush()
            await session.refresh(orm)
            return _history_to_domain(orm)

    async def list_object_history(
        self,
        object_id: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[ObjectStateHistoryEntry]:
        async with self._session_factory() as session:
            stmt = select(ObjectStateHistoryORM).where(
                ObjectStateHistoryORM.object_id == object_id
            )
            if since is not None:
                stmt = stmt.where(ObjectStateHistoryORM.changed_at >= since)
            if until is not None:
                stmt = stmt.where(ObjectStateHistoryORM.changed_at <= until)
            stmt = stmt.order_by(ObjectStateHistoryORM.changed_at.desc()).limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            return [_history_to_domain(row) for row in rows]

    async def list_recent_history_for_user(
        self, *, user_id: UUID, limit: int = 1000
    ) -> list[ObjectStateHistoryEntry]:
        async with self._session_factory() as session:
            stmt = (
                select(ObjectStateHistoryORM)
                .where(ObjectStateHistoryORM.user_id == user_id)
                .order_by(ObjectStateHistoryORM.changed_at.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_history_to_domain(row) for row in rows]

    async def create_snapshot(self, snapshot: Snapshot) -> Snapshot:
        async with self._session_factory() as session, session.begin():
            orm = SnapshotORM(
                id=snapshot.id,
                user_id=snapshot.user_id,
                snapshot_data=snapshot.snapshot_data,
                trigger=snapshot.trigger,
            )
            session.add(orm)
            await session.flush()
            await session.refresh(orm)
            return _snapshot_to_domain(orm)

    async def list_snapshots(self, *, user_id: UUID, limit: int = 50) -> list[Snapshot]:
        async with self._session_factory() as session:
            stmt = (
                select(SnapshotORM)
                .where(SnapshotORM.user_id == user_id)
                .order_by(SnapshotORM.taken_at.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_snapshot_to_domain(row) for row in rows]

    async def create_prediction(
        self, prediction: Prediction, *, outbox_event: OutboxEvent | None = None
    ) -> Prediction:
        async with self._session_factory() as session, session.begin():
            orm = PredictionORM(
                id=prediction.id,
                user_id=prediction.user_id,
                prediction=prediction.prediction,
                confidence=prediction.confidence,
                predicted_for=prediction.predicted_for,
                outcome=prediction.outcome,
            )
            session.add(orm)
            if outbox_event is not None:
                session.add(_outbox_orm(outbox_event))
            await session.flush()
            await session.refresh(orm)
            return _prediction_to_domain(orm)

    async def list_predictions(self, *, user_id: UUID, limit: int = 50) -> list[Prediction]:
        async with self._session_factory() as session:
            stmt = (
                select(PredictionORM)
                .where(PredictionORM.user_id == user_id)
                .order_by(PredictionORM.created_at.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_prediction_to_domain(row) for row in rows]

    async def log_conflict(self, entry: ConflictLogEntry) -> ConflictLogEntry:
        async with self._session_factory() as session, session.begin():
            orm = ConflictLogORM(
                id=entry.id,
                object_id=entry.object_id,
                observation_a=entry.observation_a,
                observation_b=entry.observation_b,
                resolution_strategy=entry.resolution_strategy,
                resolved_value=entry.resolved_value,
            )
            session.add(orm)
            await session.flush()
            await session.refresh(orm)
            return _conflict_to_domain(orm)

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID:
        async with self._session_factory() as session, session.begin():
            orm = _outbox_orm(event)
            session.add(orm)
            await session.flush()
            return orm.id

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        async with self._session_factory() as session:
            stmt = (
                select(OutboxEventORM)
                .where(OutboxEventORM.dispatched_at.is_(None))
                .where(
                    OutboxEventORM.graph_write.is_(None)
                    | OutboxEventORM.graph_applied_at.is_not(None)
                )
                .order_by(OutboxEventORM.created_at)
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_outbox_to_domain(row) for row in rows]

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(OutboxEventORM)
                .where(OutboxEventORM.id == outbox_id)
                .values(dispatched_at=func.now())
            )

    async def list_pending_graph_writes(self, *, limit: int = 100) -> list[OutboxRow]:
        async with self._session_factory() as session:
            stmt = (
                select(OutboxEventORM)
                .where(
                    OutboxEventORM.graph_write.is_not(None),
                    OutboxEventORM.graph_applied_at.is_(None),
                )
                .order_by(OutboxEventORM.created_at)
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_outbox_to_domain(row) for row in rows]

    async def mark_graph_applied(self, outbox_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(OutboxEventORM)
                .where(OutboxEventORM.id == outbox_id)
                .values(graph_applied_at=func.now())
            )

    async def count_stale_pending_graph_writes(self, *, older_than: datetime) -> int:
        async with self._session_factory() as session:
            stmt = select(func.count()).where(
                OutboxEventORM.graph_write.is_not(None),
                OutboxEventORM.graph_applied_at.is_(None),
                OutboxEventORM.created_at < older_than,
            )
            result = await session.execute(stmt)
            return result.scalar_one()
