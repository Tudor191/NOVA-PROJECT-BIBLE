"""`FakeDigitalTwinRepository` -- an in-memory `domain.ports.
DigitalTwinRepository`, mirroring `PostgresDigitalTwinRepository`'s own
behavior closely enough that swapping one for the other in a test changes
nothing observable."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from nova_digital_twin_engine.domain.models import (
    CommunicationProfile,
    CompletedSessionEvidence,
    HabitSignal,
    PreferenceEvolutionEntry,
    ProactiveBoundaryPolicy,
    TrustMetric,
    TrustMetricHistoryEntry,
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
        self.outbox: list[OutboxEvent] = []
        self._dispatched: set[int] = set()

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
