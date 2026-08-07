"""`PostgresPerceptionRepository` -- implements
`domain.ports.PerceptionRepository` against SQLAlchemy async, per the schema
in docs/design/phase-2d/03-perception-engine.md Sec15.

Every write commits synchronously, one transaction per call, the same
"never batched" discipline every prior engine's repository layer follows.
`template_ciphertext` passes through this layer as opaque bytes -- encryption
and decryption both happen in `domain/enrollment.py`, never here (Sec16).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_perception_engine.domain.models import (
    ConsentGrant,
    EnrolledIdentity,
    IdentityObservation,
    Modality,
    Source,
)
from nova_perception_engine.domain.ports import OutboxEvent, OutboxRow
from nova_perception_engine.repository.models import (
    ConsentGrantORM,
    EnrolledIdentityORM,
    IdentityObservationORM,
    OutboxEventORM,
    SensorRegistrationORM,
)

__all__ = ["PostgresPerceptionRepository"]


def _identity_to_domain(row: EnrolledIdentityORM) -> EnrolledIdentity:
    return EnrolledIdentity(
        identity_id=row.identity_id,
        user_id=row.user_id,
        modality=row.modality,
        template_ciphertext=row.template_ciphertext,
        enrolled_at=row.enrolled_at,
        revoked_at=row.revoked_at,
    )


def _consent_to_domain(row: ConsentGrantORM) -> ConsentGrant:
    return ConsentGrant(
        consent_id=row.consent_id,
        user_id=row.user_id,
        source=row.source,
        scope=row.scope,
        granted_at=row.granted_at,
        revoked_at=row.revoked_at,
    )


def _observation_to_domain(row: IdentityObservationORM) -> IdentityObservation:
    return IdentityObservation(
        observation_id=row.observation_id,
        user_id=row.user_id,
        identity_id=row.identity_id,
        fused_confidence=row.fused_confidence,
        confidence_tier=row.confidence_tier,
        per_modality_signals=row.per_modality_signals,
        correlation_id=row.correlation_id,
        observed_at=row.observed_at,
    )


def _outbox_orm(event: OutboxEvent) -> OutboxEventORM:
    return OutboxEventORM(
        subject=event.subject,
        payload=event.payload,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
    )


class PostgresPerceptionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def enroll_identity(self, identity: EnrolledIdentity) -> EnrolledIdentity:
        async with self._session_factory() as db_session, db_session.begin():
            orm = EnrolledIdentityORM(
                identity_id=identity.identity_id,
                user_id=identity.user_id,
                modality=identity.modality,
                template_ciphertext=identity.template_ciphertext,
            )
            db_session.add(orm)
            await db_session.flush()
            await db_session.refresh(orm)
            return _identity_to_domain(orm)

    async def list_identities(self, *, user_id: UUID) -> list[EnrolledIdentity]:
        async with self._session_factory() as db_session:
            stmt = select(EnrolledIdentityORM).where(
                EnrolledIdentityORM.user_id == user_id,
                EnrolledIdentityORM.revoked_at.is_(None),
            )
            rows = (await db_session.execute(stmt)).scalars().all()
            return [_identity_to_domain(row) for row in rows]

    async def get_identity_templates(
        self, *, user_id: UUID, modality: Modality
    ) -> list[EnrolledIdentity]:
        async with self._session_factory() as db_session:
            stmt = select(EnrolledIdentityORM).where(
                EnrolledIdentityORM.user_id == user_id,
                EnrolledIdentityORM.modality == modality,
                EnrolledIdentityORM.revoked_at.is_(None),
            )
            rows = (await db_session.execute(stmt)).scalars().all()
            return [_identity_to_domain(row) for row in rows]

    async def revoke_identity(self, identity_id: UUID) -> bool:
        async with self._session_factory() as db_session, db_session.begin():
            stmt = select(EnrolledIdentityORM).where(
                EnrolledIdentityORM.identity_id == identity_id
            )
            row = (await db_session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return False
            await db_session.delete(row)  # hard delete, Sec11 -- never a soft-delete flag
            return True

    async def grant_consent(self, grant: ConsentGrant) -> ConsentGrant:
        async with self._session_factory() as db_session, db_session.begin():
            orm = ConsentGrantORM(
                consent_id=grant.consent_id,
                user_id=grant.user_id,
                source=grant.source,
                scope=grant.scope,
            )
            db_session.add(orm)
            await db_session.flush()
            await db_session.refresh(orm)
            return _consent_to_domain(orm)

    async def revoke_consent(self, *, user_id: UUID, source: Source) -> ConsentGrant | None:
        async with self._session_factory() as db_session, db_session.begin():
            stmt = (
                select(ConsentGrantORM)
                .where(
                    ConsentGrantORM.user_id == user_id,
                    ConsentGrantORM.source == source,
                    ConsentGrantORM.revoked_at.is_(None),
                )
                .order_by(ConsentGrantORM.granted_at.desc())
            )
            row = (await db_session.execute(stmt)).scalars().first()
            if row is None:
                return None
            await db_session.execute(
                update(ConsentGrantORM)
                .where(ConsentGrantORM.consent_id == row.consent_id)
                .values(revoked_at=func.now())
            )
            await db_session.refresh(row)
            return _consent_to_domain(row)

    async def consent_status(self, *, user_id: UUID) -> list[ConsentGrant]:
        async with self._session_factory() as db_session:
            stmt = select(ConsentGrantORM).where(ConsentGrantORM.user_id == user_id)
            rows = (await db_session.execute(stmt)).scalars().all()
            return [_consent_to_domain(row) for row in rows]

    async def has_active_consent(self, *, user_id: UUID, source: Source) -> bool:
        async with self._session_factory() as db_session:
            stmt = select(ConsentGrantORM).where(
                ConsentGrantORM.user_id == user_id,
                ConsentGrantORM.source == source,
                ConsentGrantORM.revoked_at.is_(None),
            )
            row = (await db_session.execute(stmt)).scalars().first()
            return row is not None

    async def record_identity_observation(
        self, observation: IdentityObservation, *, outbox_event: OutboxEvent | None = None
    ) -> IdentityObservation:
        async with self._session_factory() as db_session, db_session.begin():
            orm = IdentityObservationORM(
                observation_id=observation.observation_id,
                user_id=observation.user_id,
                identity_id=observation.identity_id,
                fused_confidence=observation.fused_confidence,
                confidence_tier=observation.confidence_tier,
                per_modality_signals=observation.per_modality_signals,
                correlation_id=observation.correlation_id,
            )
            db_session.add(orm)
            if outbox_event is not None:
                db_session.add(_outbox_orm(outbox_event))
            await db_session.flush()
            await db_session.refresh(orm)
            return _observation_to_domain(orm)

    async def record_sensor_health(
        self, *, sensor_id: str, sensor_type: str, status: str, capabilities: list[str]
    ) -> None:
        async with self._session_factory() as db_session, db_session.begin():
            stmt = select(SensorRegistrationORM).where(
                SensorRegistrationORM.sensor_id == sensor_id
            )
            row = (await db_session.execute(stmt)).scalar_one_or_none()
            if row is None:
                db_session.add(
                    SensorRegistrationORM(
                        sensor_id=sensor_id,
                        sensor_type=sensor_type,
                        status=status,
                        capabilities=capabilities,
                        last_health_check_at=func.now(),
                    )
                )
            else:
                await db_session.execute(
                    update(SensorRegistrationORM)
                    .where(SensorRegistrationORM.sensor_id == sensor_id)
                    .values(
                        status=status,
                        capabilities=capabilities,
                        last_health_check_at=func.now(),
                    )
                )

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
