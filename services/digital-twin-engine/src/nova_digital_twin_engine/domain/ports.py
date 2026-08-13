"""Protocols this package depends on -- implements nothing itself
(docs/design/phase-2d/06-personal-companion.md Sec11.1). `domain/` may only
import this module, `domain/models.py`, and other `domain/` modules --
never FastAPI, SQLAlchemy, or `nova_eventbus_sdk` directly.

`completed_session_evidence`'s own persistence is an implementation-time
addition beyond Sec11.1's named table list (`communication_profile`/
`preference_evolution_history`/`habit_signal`/`trust_metric`/
`proactive_boundary_policy`) -- realizing Sec9's own "average corrections
per completed session over a rolling window" formula requires the raw,
per-session evidence to compute that average from; the TDD itself names the
exact window size "an implementation-time parameter, not an architectural
fork," and storing the evidence a window is computed over is the same kind
of implementation-time necessity.

`proactive_delivery_record`'s persistence (Phase 2D-D Step 9, Sec10.2, Fork
D) is the same kind of implementation-time necessity: `domain/
proactive_boundary.py::evaluate_proactive_suggestion`'s own frequency-limit
check needs genuine, per-user delivery history to compute against, not a
fabricated or empty list.

`CommunicationPort` (Sec10.2, Fork D) is this engine's first synchronous
upstream RPC caller -- `EventPublisher` below was declared for symmetry
with every other engine's `domain/ports.py` since Phase 2D-D Step 5/6, but
had no real caller until now."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from nova_contracts import EventEnvelope
from pydantic import BaseModel

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

__all__ = [
    "CommunicationPort",
    "DigitalTwinRepository",
    "EventPublisher",
    "OutboxEvent",
    "OutboxRow",
]


class OutboxEvent(BaseModel):
    """One row to insert into `digital_twin.outbox_event` in the same
    transaction as the write it accompanies -- the same transactional
    outbox pattern every prior publishing engine's own repository uses."""

    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None


class OutboxRow(BaseModel):
    id: UUID
    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None
    created_at: datetime


@runtime_checkable
class DigitalTwinRepository(Protocol):
    """Persistence port for the `digital_twin` schema (Sec11.1):
    `communication_profile`, `preference_evolution_history`, `habit_signal`,
    `completed_session_evidence`, `trust_metric` (+ history),
    `proactive_boundary_policy`, `proactive_delivery_record` (Step 9), plus
    the transactional outbox."""

    async def get_communication_profile(self, user_id: UUID) -> CommunicationProfile | None:
        """`None` when no row exists yet -- the caller (API/event handler)
        constructs a fresh `CommunicationProfile(user_id=...)` default,
        mirroring `PersonalityRepository.get_memory_profile`'s own
        config-default-on-missing-row convention."""
        ...

    async def upsert_communication_profile(
        self, profile: CommunicationProfile
    ) -> CommunicationProfile: ...

    async def create_preference_evolution_entry(
        self, entry: PreferenceEvolutionEntry
    ) -> PreferenceEvolutionEntry:
        """Append-only. No production call site enqueues one this phase
        (Fork F, `domain/models.py`'s own module docstring) -- exercised
        directly by tests and ready for a future evidence source."""
        ...

    async def record_habit_signal(self, signal: HabitSignal) -> HabitSignal: ...

    async def record_completed_session_evidence(
        self, evidence: CompletedSessionEvidence
    ) -> CompletedSessionEvidence: ...

    async def list_recent_completed_sessions(
        self, user_id: UUID, *, limit: int
    ) -> list[CompletedSessionEvidence]:
        """Most-recent-first, bounded to `limit` -- `trust_metric.
        compute_trust_metric`'s own rolling-window input (Sec9)."""
        ...

    async def get_trust_metric(self, user_id: UUID) -> TrustMetric | None: ...

    async def upsert_trust_metric(self, metric: TrustMetric) -> TrustMetric: ...

    async def create_trust_metric_history_entry(
        self, entry: TrustMetricHistoryEntry
    ) -> TrustMetricHistoryEntry: ...

    async def get_proactive_boundary_policy(
        self, user_id: UUID
    ) -> ProactiveBoundaryPolicy | None:
        """`None` when the user has not configured one yet -- the caller
        constructs a fresh `ProactiveBoundaryPolicy(user_id=...)` default
        (`enabled=True`, no per-topic limits, so every suggestion is
        declined until the user explicitly sets one -- Sec10.1's
        fail-closed discipline, `domain/proactive_boundary.py`)."""
        ...

    async def upsert_proactive_boundary_policy(
        self, policy: ProactiveBoundaryPolicy
    ) -> ProactiveBoundaryPolicy: ...

    async def record_proactive_delivery(
        self, record: ProactiveDeliveryRecord
    ) -> ProactiveDeliveryRecord: ...

    async def list_recent_proactive_deliveries(
        self, user_id: UUID, *, since: datetime
    ) -> list[ProactiveDeliveryRecord]:
        """`proactive_boundary.evaluate_proactive_suggestion`'s own
        `recent_deliveries` input (Sec10.1) -- scoped to `since` (the
        policy's own configured window) so this port never returns
        unbounded history."""
        ...

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID: ...

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]: ...

    async def mark_dispatched(self, outbox_id: UUID) -> None: ...


@runtime_checkable
class EventPublisher(Protocol):
    """Declared for symmetry with every other engine's `domain/ports.py` --
    now genuinely used: `clients/communication_client.py` (Fork D, Step 9)
    is the first real caller."""

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope: ...


@runtime_checkable
class CommunicationPort(Protocol):
    """Phase 2D-D Sec10.2, Fork D -- this engine's own first synchronous
    upstream RPC caller. `get_connected_session` answers "does this user
    have a currently-connected session, and if so, which one" (the new,
    small `communication.session.lookup_by_user.request` RPC);
    `deliver_intent` reuses the existing, already-tested `communication.
    intent.deliver.request` gate (ADR-005) -- no new delivery mechanism,
    per Sec1.1's own "Fork D's warm-case delivery needs no new
    communication-engine delivery mechanism either" finding. Implemented by
    `clients/communication_client.py`.

    `TimeoutError` propagates uncaught from both methods, mirroring every
    other client's documented convention in this project --
    `proactive_delivery.attempt_proactive_delivery` is the one place that
    catches it and treats a timeout the same as "not deliverable right
    now," never a crash."""

    async def get_connected_session(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> UUID | None: ...

    async def deliver_intent(
        self, *, session_id: UUID, content: str, correlation_id: UUID | None = None
    ) -> bool:
        """`True` only when `CommunicationIntentDeliverReplyPayload.
        delivered` is `True` -- a personality rejection or channel-level
        failure both return `False`, and this engine's own rate-limit
        bookkeeping (`ProactiveDeliveryRecord`) only counts an actual
        delivery, never a mere attempt."""
        ...
