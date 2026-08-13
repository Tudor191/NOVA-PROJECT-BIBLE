"""`PostgresDigitalTwinRepository` -- implements
`domain.ports.DigitalTwinRepository` against SQLAlchemy async, per the
schema in `repository/models.py`.

Every state-changing write commits synchronously, one transaction per call
(mirroring every prior engine's own repository convention) -- never
batched, so restart recovery can trust that any persisted row reflects the
last write that actually completed.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_digital_twin_engine.domain.models import (
    CommunicationProfile,
    CompletedSessionEvidence,
    HabitSignal,
    PreferenceEvolutionEntry,
    ProactiveBoundaryPolicy,
    ProactiveDeliveryRecord,
    TrustMetric,
    TrustMetricHistoryEntry,
)
from nova_digital_twin_engine.domain.ports import OutboxEvent, OutboxRow
from nova_digital_twin_engine.repository.models import (
    CommunicationProfileORM,
    CompletedSessionEvidenceORM,
    HabitSignalORM,
    OutboxEventORM,
    PreferenceEvolutionHistoryORM,
    ProactiveBoundaryPolicyORM,
    ProactiveDeliveryRecordORM,
    TrustMetricHistoryORM,
    TrustMetricORM,
)

__all__ = ["PostgresDigitalTwinRepository"]


def _profile_to_domain(row: CommunicationProfileORM) -> CommunicationProfile:
    return CommunicationProfile(
        user_id=row.user_id,
        verbosity=row.verbosity,
        technical_depth=row.technical_depth,
        terminology_preference=row.terminology_preference,
        conversation_pacing=row.conversation_pacing,
        habit_timing_hint=row.habit_timing_hint,
        source=row.source,
        updated_at=row.updated_at,
    )


def _evolution_entry_to_domain(row: PreferenceEvolutionHistoryORM) -> PreferenceEvolutionEntry:
    return PreferenceEvolutionEntry(
        id=row.id,
        user_id=row.user_id,
        field=row.field,
        previous_value=row.previous_value,
        new_value=row.new_value,
        confidence=row.confidence,
        source=row.source,
        reason=row.reason,
        changed_at=row.changed_at,
    )


def _habit_signal_to_domain(row: HabitSignalORM) -> HabitSignal:
    return HabitSignal(
        id=row.id,
        user_id=row.user_id,
        session_id=row.session_id,
        turn_count=row.turn_count,
        session_duration_seconds=row.session_duration_seconds,
        observed_at=row.observed_at,
    )


def _evidence_to_domain(row: CompletedSessionEvidenceORM) -> CompletedSessionEvidence:
    return CompletedSessionEvidence(
        session_id=row.session_id,
        user_id=row.user_id,
        turn_count=row.turn_count,
        corrections=list(row.corrections),
        preferences=list(row.preferences),
        feedback=list(row.feedback),
        decisions=list(row.decisions),
        closed_at=row.closed_at,
    )


def _trust_metric_to_domain(row: TrustMetricORM) -> TrustMetric:
    return TrustMetric(
        user_id=row.user_id,
        correction_frequency=row.correction_frequency,
        window_session_count=row.window_session_count,
        clarification_acceptance_rate=row.clarification_acceptance_rate,
        proactive_suggestion_acceptance_rate=row.proactive_suggestion_acceptance_rate,
        computed_at=row.computed_at,
    )


def _trust_history_entry_to_domain(row: TrustMetricHistoryORM) -> TrustMetricHistoryEntry:
    return TrustMetricHistoryEntry(
        id=row.id,
        user_id=row.user_id,
        correction_frequency=row.correction_frequency,
        window_session_count=row.window_session_count,
        computed_at=row.computed_at,
    )


def _policy_to_domain(row: ProactiveBoundaryPolicyORM) -> ProactiveBoundaryPolicy:
    return ProactiveBoundaryPolicy(
        user_id=row.user_id,
        enabled=row.enabled,
        max_per_topic_per_window=dict(row.max_per_topic_per_window),
        window_hours=row.window_hours,
    )


def _delivery_record_to_domain(row: ProactiveDeliveryRecordORM) -> ProactiveDeliveryRecord:
    return ProactiveDeliveryRecord(
        user_id=row.user_id, topic=row.topic, delivered_at=row.delivered_at
    )


def _outbox_orm(event: OutboxEvent) -> OutboxEventORM:
    return OutboxEventORM(
        subject=event.subject,
        payload=event.payload,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
    )


class PostgresDigitalTwinRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_communication_profile(self, user_id: UUID) -> CommunicationProfile | None:
        async with self._session_factory() as session:
            row = await session.get(CommunicationProfileORM, user_id)
            return _profile_to_domain(row) if row is not None else None

    async def upsert_communication_profile(
        self, profile: CommunicationProfile
    ) -> CommunicationProfile:
        async with self._session_factory() as session, session.begin():
            row = await session.get(CommunicationProfileORM, profile.user_id)
            if row is None:
                row = CommunicationProfileORM(user_id=profile.user_id)
                session.add(row)
            row.verbosity = profile.verbosity
            row.technical_depth = profile.technical_depth
            row.terminology_preference = profile.terminology_preference
            row.conversation_pacing = profile.conversation_pacing
            row.habit_timing_hint = profile.habit_timing_hint
            row.source = profile.source
            await session.flush()
            await session.refresh(row)
            return _profile_to_domain(row)

    async def create_preference_evolution_entry(
        self, entry: PreferenceEvolutionEntry
    ) -> PreferenceEvolutionEntry:
        async with self._session_factory() as session, session.begin():
            row = PreferenceEvolutionHistoryORM(
                id=entry.id,
                user_id=entry.user_id,
                field=entry.field,
                previous_value=entry.previous_value,
                new_value=entry.new_value,
                confidence=entry.confidence,
                source=entry.source,
                reason=entry.reason,
            )
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return _evolution_entry_to_domain(row)

    async def record_habit_signal(self, signal: HabitSignal) -> HabitSignal:
        async with self._session_factory() as session, session.begin():
            row = HabitSignalORM(
                id=signal.id,
                user_id=signal.user_id,
                session_id=signal.session_id,
                turn_count=signal.turn_count,
                session_duration_seconds=signal.session_duration_seconds,
                observed_at=signal.observed_at,
            )
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return _habit_signal_to_domain(row)

    async def record_completed_session_evidence(
        self, evidence: CompletedSessionEvidence
    ) -> CompletedSessionEvidence:
        async with self._session_factory() as session, session.begin():
            row = CompletedSessionEvidenceORM(
                session_id=evidence.session_id,
                user_id=evidence.user_id,
                turn_count=evidence.turn_count,
                corrections=list(evidence.corrections),
                preferences=list(evidence.preferences),
                feedback=list(evidence.feedback),
                decisions=list(evidence.decisions),
                closed_at=evidence.closed_at,
            )
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return _evidence_to_domain(row)

    async def list_recent_completed_sessions(
        self, user_id: UUID, *, limit: int
    ) -> list[CompletedSessionEvidence]:
        async with self._session_factory() as session:
            stmt = (
                select(CompletedSessionEvidenceORM)
                .where(CompletedSessionEvidenceORM.user_id == user_id)
                .order_by(CompletedSessionEvidenceORM.closed_at.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_evidence_to_domain(row) for row in rows]

    async def get_trust_metric(self, user_id: UUID) -> TrustMetric | None:
        async with self._session_factory() as session:
            row = await session.get(TrustMetricORM, user_id)
            return _trust_metric_to_domain(row) if row is not None else None

    async def upsert_trust_metric(self, metric: TrustMetric) -> TrustMetric:
        async with self._session_factory() as session, session.begin():
            row = await session.get(TrustMetricORM, metric.user_id)
            if row is None:
                row = TrustMetricORM(user_id=metric.user_id)
                session.add(row)
            row.correction_frequency = metric.correction_frequency
            row.window_session_count = metric.window_session_count
            row.clarification_acceptance_rate = metric.clarification_acceptance_rate
            row.proactive_suggestion_acceptance_rate = metric.proactive_suggestion_acceptance_rate
            await session.flush()
            await session.refresh(row)
            return _trust_metric_to_domain(row)

    async def create_trust_metric_history_entry(
        self, entry: TrustMetricHistoryEntry
    ) -> TrustMetricHistoryEntry:
        async with self._session_factory() as session, session.begin():
            row = TrustMetricHistoryORM(
                id=entry.id,
                user_id=entry.user_id,
                correction_frequency=entry.correction_frequency,
                window_session_count=entry.window_session_count,
            )
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return _trust_history_entry_to_domain(row)

    async def get_proactive_boundary_policy(
        self, user_id: UUID
    ) -> ProactiveBoundaryPolicy | None:
        async with self._session_factory() as session:
            row = await session.get(ProactiveBoundaryPolicyORM, user_id)
            return _policy_to_domain(row) if row is not None else None

    async def upsert_proactive_boundary_policy(
        self, policy: ProactiveBoundaryPolicy
    ) -> ProactiveBoundaryPolicy:
        async with self._session_factory() as session, session.begin():
            row = await session.get(ProactiveBoundaryPolicyORM, policy.user_id)
            if row is None:
                row = ProactiveBoundaryPolicyORM(user_id=policy.user_id)
                session.add(row)
            row.enabled = policy.enabled
            row.max_per_topic_per_window = dict(policy.max_per_topic_per_window)
            row.window_hours = policy.window_hours
            await session.flush()
            await session.refresh(row)
            return _policy_to_domain(row)

    async def record_proactive_delivery(
        self, record: ProactiveDeliveryRecord
    ) -> ProactiveDeliveryRecord:
        async with self._session_factory() as session, session.begin():
            row = ProactiveDeliveryRecordORM(
                user_id=record.user_id, topic=record.topic, delivered_at=record.delivered_at
            )
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return _delivery_record_to_domain(row)

    async def list_recent_proactive_deliveries(
        self, user_id: UUID, *, since: datetime
    ) -> list[ProactiveDeliveryRecord]:
        async with self._session_factory() as session:
            stmt = select(ProactiveDeliveryRecordORM).where(
                ProactiveDeliveryRecordORM.user_id == user_id,
                ProactiveDeliveryRecordORM.delivered_at >= since,
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_delivery_record_to_domain(row) for row in rows]

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID:
        async with self._session_factory() as session, session.begin():
            row = _outbox_orm(event)
            session.add(row)
            await session.flush()
            return row.id

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
