"""`PostgresDigitalTwinRepository` -- implements
`domain.ports.DigitalTwinRepository` against SQLAlchemy async, per the
schema in `repository/models.py`.

Every state-changing write commits synchronously, one transaction per call
(mirroring every prior engine's own repository convention) -- never
batched, so restart recovery can trust that any persisted row reflects the
last write that actually completed.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_digital_twin_engine.domain.models import (
    CommunicationProfile,
    CompletedSessionEvidence,
    DomainEvidence,
    DomainModel,
    DomainReason,
    DomainReasonCode,
    DomainState,
    EvidenceKind,
    HabitSignal,
    PreferenceEvolutionEntry,
    ProactiveBoundaryPolicy,
    ProactiveDeliveryRecord,
    ProjectModel,
    TrustMetric,
    TrustMetricHistoryEntry,
    TwinDomain,
)
from nova_digital_twin_engine.domain.ports import OutboxEvent, OutboxRow
from nova_digital_twin_engine.repository.models import (
    CommunicationProfileORM,
    CompletedSessionEvidenceORM,
    DomainEvidenceORM,
    DomainModelORM,
    HabitSignalORM,
    OutboxEventORM,
    PreferenceEvolutionHistoryORM,
    ProactiveBoundaryPolicyORM,
    ProactiveDeliveryRecordORM,
    ProjectModelORM,
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


# --- Phase 4E: Bible Part 16's nine remaining domains (TDD 4E Sec9) --------


def _domain_model_to_domain(row: DomainModelORM) -> DomainModel:
    reason = (
        DomainReason(
            code=DomainReasonCode(row.reason_code), detail=row.reason_detail or ""
        )
        if row.reason_code is not None
        else None
    )
    return DomainModel(
        user_id=row.user_id,
        domain=TwinDomain(row.domain),
        state=DomainState(row.state),
        reason=reason,
        evidence_count=row.evidence_count,
        facts=dict(row.facts),
        unavailable_fields=list(row.unavailable_fields),
        derived_at=row.derived_at,
    )


def _domain_evidence_to_domain(row: DomainEvidenceORM) -> DomainEvidence:
    return DomainEvidence(
        id=row.id,
        user_id=row.user_id,
        domain=TwinDomain(row.domain),
        kind=EvidenceKind(row.kind),
        source_record_id=row.source_record_id,
        source_created_at=row.source_created_at,
        observed_at=row.observed_at,
        attributes=dict(row.attributes),
    )


def _project_model_to_domain(row: ProjectModelORM) -> ProjectModel:
    return ProjectModel(
        user_id=row.user_id,
        project_id=row.project_id,
        memory_count=row.memory_count,
        memory_type_counts=dict(row.memory_type_counts),
        first_activity_at=row.first_activity_at,
        last_activity_at=row.last_activity_at,
        gap_days=row.gap_days,
        derived_at=row.derived_at,
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

    async def count_preference_evolution_entries(self, user_id: UUID) -> int:
        async with self._session_factory() as session:
            result = await session.execute(
                select(func.count())
                .select_from(PreferenceEvolutionHistoryORM)
                .where(PreferenceEvolutionHistoryORM.user_id == user_id)
            )
            return int(result.scalar_one())

    # --- Phase 4E: Bible Part 16's nine remaining domains (TDD 4E Sec9) ----

    async def record_domain_derivation(
        self,
        *,
        models: Sequence[DomainModel],
        evidence: Sequence[DomainEvidence] = (),
        projects: Sequence[ProjectModel] = (),
    ) -> None:
        async with self._session_factory() as session, session.begin():
            # Parents first: `domain_evidence` has a composite FK into this table,
            # so an evidence row for a never-derived domain is rejected by the
            # database rather than by a convention someone has to remember.
            for model in models:
                await session.execute(
                    pg_insert(DomainModelORM)
                    .values(
                        user_id=model.user_id,
                        domain=model.domain.value,
                        state=model.state.value,
                        reason_code=model.reason.code.value if model.reason else None,
                        reason_detail=model.reason.detail if model.reason else None,
                        evidence_count=model.evidence_count,
                        facts=model.facts,
                        unavailable_fields=model.unavailable_fields,
                        derived_at=model.derived_at,
                    )
                    .on_conflict_do_update(
                        index_elements=[DomainModelORM.user_id, DomainModelORM.domain],
                        set_={
                            "state": model.state.value,
                            "reason_code": model.reason.code.value if model.reason else None,
                            "reason_detail": model.reason.detail if model.reason else None,
                            "evidence_count": model.evidence_count,
                            "facts": model.facts,
                            "unavailable_fields": model.unavailable_fields,
                            "derived_at": model.derived_at,
                        },
                    )
                )

            for row in evidence:
                # Idempotent on redelivery: the Event Bus is at-least-once, and the
                # primary key is what makes a duplicate a no-op rather than an
                # inflated count.
                await session.execute(
                    pg_insert(DomainEvidenceORM)
                    .values(
                        user_id=row.user_id,
                        domain=row.domain.value,
                        source_record_id=row.source_record_id,
                        id=row.id,
                        kind=row.kind.value,
                        source_created_at=row.source_created_at,
                        observed_at=row.observed_at,
                        attributes=row.attributes,
                    )
                    .on_conflict_do_nothing(
                        index_elements=[
                            DomainEvidenceORM.user_id,
                            DomainEvidenceORM.domain,
                            DomainEvidenceORM.source_record_id,
                        ]
                    )
                )

            for project in projects:
                await session.execute(
                    pg_insert(ProjectModelORM)
                    .values(
                        user_id=project.user_id,
                        project_id=project.project_id,
                        memory_count=project.memory_count,
                        memory_type_counts=project.memory_type_counts,
                        first_activity_at=project.first_activity_at,
                        last_activity_at=project.last_activity_at,
                        gap_days=project.gap_days,
                        derived_at=project.derived_at,
                    )
                    .on_conflict_do_update(
                        index_elements=[ProjectModelORM.user_id, ProjectModelORM.project_id],
                        set_={
                            "memory_count": project.memory_count,
                            "memory_type_counts": project.memory_type_counts,
                            "first_activity_at": project.first_activity_at,
                            "last_activity_at": project.last_activity_at,
                            "gap_days": project.gap_days,
                            "derived_at": project.derived_at,
                        },
                    )
                )

    async def list_domain_evidence(
        self, user_id: UUID, domain: TwinDomain | None = None
    ) -> list[DomainEvidence]:
        async with self._session_factory() as session:
            stmt = select(DomainEvidenceORM).where(DomainEvidenceORM.user_id == user_id)
            if domain is not None:
                stmt = stmt.where(DomainEvidenceORM.domain == domain.value)
            # Oldest source first: a reconstruction reads as a history, and the
            # ordering key is the source's own timestamp, not this row's.
            stmt = stmt.order_by(DomainEvidenceORM.source_created_at.asc().nullslast())
            rows = (await session.execute(stmt)).scalars().all()
            return [_domain_evidence_to_domain(row) for row in rows]

    async def get_domain_model(self, user_id: UUID, domain: TwinDomain) -> DomainModel | None:
        async with self._session_factory() as session:
            row = await session.get(DomainModelORM, (user_id, domain.value))
            return _domain_model_to_domain(row) if row is not None else None

    async def list_domain_models(self, user_id: UUID) -> list[DomainModel]:
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(DomainModelORM).where(DomainModelORM.user_id == user_id)
                    )
                )
                .scalars()
                .all()
            )
            return [_domain_model_to_domain(row) for row in rows]

    async def list_project_models(self, user_id: UUID) -> list[ProjectModel]:
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ProjectModelORM)
                        .where(ProjectModelORM.user_id == user_id)
                        # Most recently active first; a project with no timestamped
                        # evidence sorts last rather than oldest -- unplaceable is
                        # not the same claim as stale.
                        .order_by(ProjectModelORM.last_activity_at.desc().nullslast())
                    )
                )
                .scalars()
                .all()
            )
            return [_project_model_to_domain(row) for row in rows]

    async def get_project_model(self, user_id: UUID, project_id: UUID) -> ProjectModel | None:
        async with self._session_factory() as session:
            row = await session.get(ProjectModelORM, (user_id, project_id))
            return _project_model_to_domain(row) if row is not None else None
