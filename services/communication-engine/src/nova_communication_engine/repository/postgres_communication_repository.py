"""`PostgresCommunicationRepository` -- implements
`domain.ports.CommunicationRepository` against SQLAlchemy async, per the
schema in docs/design/phase-2d/01-communication-engine.md Sec10.

Every state-transition write commits synchronously, one transaction per call
(design doc Sec3.5) -- never batched, so restart recovery can trust that any
session's persisted `state` reflects the last transition that actually
completed.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from nova_communication_engine.domain.models import (
    ChannelType,
    ConversationSession,
    ConversationState,
    ConversationTurn,
    Notification,
    NotificationPriority,
    TurnDirection,
)
from nova_communication_engine.domain.ports import OutboxEvent, OutboxRow
from nova_communication_engine.repository.models import (
    ConversationSessionORM,
    ConversationTurnORM,
    NotificationORM,
    OutboxEventORM,
)

__all__ = ["PostgresCommunicationRepository"]


def _session_to_domain(row: ConversationSessionORM) -> ConversationSession:
    return ConversationSession(
        session_id=row.session_id,
        user_id=row.user_id,
        channel=ChannelType(row.channel),
        device_id=row.device_id,
        state=ConversationState(row.state),
        created_at=row.created_at,
        updated_at=row.updated_at,
        turns=[_turn_to_domain(t) for t in row.turns],
        objective=row.objective,
        pending_questions=row.pending_questions,
        closed_at=row.closed_at,
    )


def _turn_to_domain(row: ConversationTurnORM) -> ConversationTurn:
    return ConversationTurn(
        turn_id=row.turn_id,
        session_id=row.session_id,
        direction=TurnDirection(row.direction),
        content=row.content,
        channel=ChannelType(row.channel),
        personality_validated=row.personality_validated,
        created_at=row.created_at,
    )


def _notification_to_domain(row: NotificationORM) -> Notification:
    return Notification(
        notification_id=row.notification_id,
        user_id=row.user_id,
        content=row.content,
        priority=NotificationPriority(row.priority),
        delivered_at=row.delivered_at,
        created_at=row.created_at,
    )


def _outbox_orm(event: OutboxEvent) -> OutboxEventORM:
    return OutboxEventORM(
        subject=event.subject,
        payload=event.payload,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
    )


class PostgresCommunicationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_session(self, session: ConversationSession) -> ConversationSession:
        async with self._session_factory() as db_session, db_session.begin():
            orm = ConversationSessionORM(
                session_id=session.session_id,
                user_id=session.user_id,
                channel=session.channel.value,
                device_id=session.device_id,
                state=session.state.value,
                objective=session.objective,
                pending_questions=session.pending_questions,
            )
            db_session.add(orm)
            await db_session.flush()
            await db_session.refresh(orm, attribute_names=["turns"])
            return _session_to_domain(orm)

    async def get_session(self, session_id: UUID) -> ConversationSession | None:
        async with self._session_factory() as db_session:
            stmt = (
                select(ConversationSessionORM)
                .where(ConversationSessionORM.session_id == session_id)
                .options(selectinload(ConversationSessionORM.turns))
            )
            row = (await db_session.execute(stmt)).scalar_one_or_none()
            return _session_to_domain(row) if row is not None else None

    async def update_session_state(
        self,
        session_id: UUID,
        *,
        state: str,
        closed_at: datetime | None = None,
        outbox_event: OutboxEvent | None = None,
    ) -> ConversationSession:
        async with self._session_factory() as db_session, db_session.begin():
            values: dict[str, object] = {"state": state}
            if closed_at is not None:
                values["closed_at"] = closed_at
            await db_session.execute(
                update(ConversationSessionORM)
                .where(ConversationSessionORM.session_id == session_id)
                .values(**values)
            )
            if outbox_event is not None:
                db_session.add(_outbox_orm(outbox_event))
            stmt = (
                select(ConversationSessionORM)
                .where(ConversationSessionORM.session_id == session_id)
                .options(selectinload(ConversationSessionORM.turns))
            )
            row = (await db_session.execute(stmt)).scalar_one()
            return _session_to_domain(row)

    async def append_turn(
        self, turn: ConversationTurn, *, outbox_event: OutboxEvent | None = None
    ) -> ConversationTurn:
        async with self._session_factory() as db_session, db_session.begin():
            orm = ConversationTurnORM(
                turn_id=turn.turn_id,
                session_id=turn.session_id,
                direction=turn.direction.value,
                content=turn.content,
                channel=turn.channel.value,
                personality_validated=turn.personality_validated,
            )
            db_session.add(orm)
            if outbox_event is not None:
                db_session.add(_outbox_orm(outbox_event))
            await db_session.flush()
            await db_session.refresh(orm)
            return _turn_to_domain(orm)

    async def list_non_terminal_sessions(self) -> list[ConversationSession]:
        async with self._session_factory() as db_session:
            stmt = (
                select(ConversationSessionORM)
                .where(ConversationSessionORM.state != ConversationState.COMPLETED.value)
                .options(selectinload(ConversationSessionORM.turns))
            )
            rows = (await db_session.execute(stmt)).scalars().all()
            return [_session_to_domain(row) for row in rows]

    async def create_notification(self, notification: Notification) -> Notification:
        async with self._session_factory() as db_session, db_session.begin():
            orm = NotificationORM(
                notification_id=notification.notification_id,
                user_id=notification.user_id,
                content=notification.content,
                priority=notification.priority.value,
                delivered_at=notification.delivered_at,
            )
            db_session.add(orm)
            await db_session.flush()
            await db_session.refresh(orm)
            return _notification_to_domain(orm)

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID:
        async with self._session_factory() as db_session, db_session.begin():
            orm = _outbox_orm(event)
            db_session.add(orm)
            await db_session.flush()
            return orm.id

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        async with self._session_factory() as db_session:
            stmt = (
                select(OutboxEventORM)
                .where(OutboxEventORM.dispatched_at.is_(None))
                .order_by(OutboxEventORM.created_at)
                .limit(limit)
            )
            rows = (await db_session.execute(stmt)).scalars().all()
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
        async with self._session_factory() as db_session, db_session.begin():
            await db_session.execute(
                update(OutboxEventORM)
                .where(OutboxEventORM.id == outbox_id)
                .values(dispatched_at=func.now())
            )
