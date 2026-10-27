"""`FakeDigitalTwinRepository` -- an in-memory `domain.ports.
DigitalTwinRepository`, mirroring `PostgresDigitalTwinRepository`'s own
behavior closely enough that swapping one for the other in a test changes
nothing observable."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from nova_digital_twin_engine.domain.models import (
    CommunicationProfile,
    CompletedSessionEvidence,
    DomainEvidence,
    DomainModel,
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


class FakeDigitalTwinRepository:
    def __init__(self) -> None:
        self.profiles: dict[UUID, CommunicationProfile] = {}
        self.evolution_entries: list[PreferenceEvolutionEntry] = []
        self.habit_signals: list[HabitSignal] = []
        self.completed_sessions: list[CompletedSessionEvidence] = []
        self.trust_metrics: dict[UUID, TrustMetric] = {}
        self.trust_metric_history: list[TrustMetricHistoryEntry] = []
        self.proactive_policies: dict[UUID, ProactiveBoundaryPolicy] = {}
        self.proactive_deliveries: list[ProactiveDeliveryRecord] = []
        self.outbox: list[OutboxEvent] = []
        self._dispatched: set[int] = set()
        # Phase 4E. Keyed exactly as the real tables are, so a test that passes
        # here is testing the same uniqueness the database enforces.
        self.domain_models: dict[tuple[UUID, TwinDomain], DomainModel] = {}
        self.domain_evidence: dict[tuple[UUID, TwinDomain, UUID], DomainEvidence] = {}
        self.project_models: dict[tuple[UUID, UUID], ProjectModel] = {}

    async def get_communication_profile(self, user_id: UUID) -> CommunicationProfile | None:
        return self.profiles.get(user_id)

    async def upsert_communication_profile(
        self, profile: CommunicationProfile
    ) -> CommunicationProfile:
        self.profiles[profile.user_id] = profile
        return profile

    async def create_preference_evolution_entry(
        self, entry: PreferenceEvolutionEntry
    ) -> PreferenceEvolutionEntry:
        self.evolution_entries.append(entry)
        return entry

    async def count_preference_evolution_entries(self, user_id: UUID) -> int:
        return sum(1 for e in self.evolution_entries if e.user_id == user_id)

    async def record_habit_signal(self, signal: HabitSignal) -> HabitSignal:
        self.habit_signals.append(signal)
        return signal

    async def record_completed_session_evidence(
        self, evidence: CompletedSessionEvidence
    ) -> CompletedSessionEvidence:
        self.completed_sessions.append(evidence)
        return evidence

    async def list_recent_completed_sessions(
        self, user_id: UUID, *, limit: int
    ) -> list[CompletedSessionEvidence]:
        matching = [s for s in self.completed_sessions if s.user_id == user_id]
        matching.sort(key=lambda s: s.closed_at, reverse=True)
        return matching[:limit]

    async def get_trust_metric(self, user_id: UUID) -> TrustMetric | None:
        return self.trust_metrics.get(user_id)

    async def upsert_trust_metric(self, metric: TrustMetric) -> TrustMetric:
        self.trust_metrics[metric.user_id] = metric
        return metric

    async def create_trust_metric_history_entry(
        self, entry: TrustMetricHistoryEntry
    ) -> TrustMetricHistoryEntry:
        self.trust_metric_history.append(entry)
        return entry

    async def get_proactive_boundary_policy(
        self, user_id: UUID
    ) -> ProactiveBoundaryPolicy | None:
        return self.proactive_policies.get(user_id)

    async def upsert_proactive_boundary_policy(
        self, policy: ProactiveBoundaryPolicy
    ) -> ProactiveBoundaryPolicy:
        self.proactive_policies[policy.user_id] = policy
        return policy

    async def record_proactive_delivery(
        self, record: ProactiveDeliveryRecord
    ) -> ProactiveDeliveryRecord:
        self.proactive_deliveries.append(record)
        return record

    async def list_recent_proactive_deliveries(
        self, user_id: UUID, *, since: datetime
    ) -> list[ProactiveDeliveryRecord]:
        return [
            record
            for record in self.proactive_deliveries
            if record.user_id == user_id and record.delivered_at >= since
        ]

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID:
        self.outbox.append(event)
        return uuid4()

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        rows = []
        for i, event in enumerate(self.outbox):
            if i in self._dispatched:
                continue
            rows.append(
                OutboxRow(
                    id=UUID(int=i + 1),
                    subject=event.subject,
                    payload=event.payload,
                    correlation_id=event.correlation_id,
                    causation_id=event.causation_id,
                    created_at=datetime.now(UTC),
                )
            )
            if len(rows) >= limit:
                break
        return rows

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        index = outbox_id.int - 1
        self._dispatched.add(index)


    # --- Phase 4E: Bible Part 16's nine remaining domains (TDD 4E Sec9) --------

    async def record_domain_derivation(
        self,
        *,
        models: Sequence[DomainModel],
        evidence: Sequence[DomainEvidence] = (),
        projects: Sequence[ProjectModel] = (),
    ) -> None:
        for model in models:
            self.domain_models[(model.user_id, model.domain)] = model
        for row in evidence:
            # `on_conflict_do_nothing` in the real repository: first write wins,
            # so a redelivered event does not overwrite the row it created.
            self.domain_evidence.setdefault(
                (row.user_id, row.domain, row.source_record_id), row
            )
        for project in projects:
            self.project_models[(project.user_id, project.project_id)] = project

    async def list_domain_evidence(
        self, user_id: UUID, domain: TwinDomain | None = None
    ) -> list[DomainEvidence]:
        rows = [
            row
            for (row_user, row_domain, _), row in self.domain_evidence.items()
            if row_user == user_id and (domain is None or row_domain == domain)
        ]
        # Oldest source first, untimestamped last -- the real query's ordering.
        rows.sort(key=lambda r: (r.source_created_at is None, r.source_created_at or r.observed_at))
        return rows

    async def get_domain_model(self, user_id: UUID, domain: TwinDomain) -> DomainModel | None:
        return self.domain_models.get((user_id, domain))

    async def list_domain_models(self, user_id: UUID) -> list[DomainModel]:
        return [m for (u, _), m in self.domain_models.items() if u == user_id]

    async def list_project_models(self, user_id: UUID) -> list[ProjectModel]:
        rows = [p for (u, _), p in self.project_models.items() if u == user_id]
        rows.sort(
            key=lambda p: (p.last_activity_at is not None, p.last_activity_at or p.derived_at),
            reverse=True,
        )
        return rows

    async def get_project_model(self, user_id: UUID, project_id: UUID) -> ProjectModel | None:
        return self.project_models.get((user_id, project_id))
