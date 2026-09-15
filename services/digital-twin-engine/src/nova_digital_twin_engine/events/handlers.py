"""`communication.session.completed` subscribed handler and
`digital_twin.preferences.get.request` served RPC handler (docs/design/
phase-2d/06-personal-companion.md Sec7.1, Sec9, Sec11.1).

`make_session_completed_handler` is this engine's one real evidence-
processing path this phase: records the session's raw evidence and a
structural habit signal (never an inferred label -- `domain/models.py`'s
own `HabitSignal` docstring), then recomputes the correction-frequency
trust metric (Fork C's real, evidence-based formula) over the configured
rolling window. It does **not** touch `CommunicationProfile` -- Fork F
(`domain/models.py`'s own module docstring) means no evidence source for
`verbosity`/`technical_depth`/`terminology_preference`/`conversation_pacing`/
`habit_timing_hint` is approved yet, so this handler never calls
`preference_evolution.evolve_field`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

from fastapi import FastAPI
from nova_contracts import (
    CommunicationSessionCompletedPayload,
    DecisionRecordedPayload,
    DigitalTwinPreferencesGetReplyPayload,
    DigitalTwinPreferencesGetRequestPayload,
    EventEnvelope,
    LongTermMemoryCreatedPayload,
    PerceptionAttentionObservedPayload,
)

from nova_digital_twin_engine import domain_derivation
from nova_digital_twin_engine.domain import derivation, trust_metric
from nova_digital_twin_engine.domain.models import (
    CommunicationProfile,
    CompletedSessionEvidence,
    HabitSignal,
    TrustMetricHistoryEntry,
)

__all__ = [
    "make_attention_observed_handler",
    "make_decision_recorded_handler",
    "make_memory_created_handler",
    "make_preferences_get_handler",
    "make_session_completed_handler",
]


def make_session_completed_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> None:
        state = app.state
        payload = CommunicationSessionCompletedPayload.model_validate(envelope.payload)

        evidence = CompletedSessionEvidence(
            session_id=payload.session_id,
            user_id=payload.user_id,
            turn_count=payload.turn_count,
            corrections=payload.corrections,
            preferences=payload.preferences,
            feedback=payload.feedback,
            decisions=payload.decisions,
            closed_at=payload.closed_at,
        )
        await state.repository.record_completed_session_evidence(evidence)
        await state.repository.record_habit_signal(
            HabitSignal(
                user_id=payload.user_id,
                session_id=payload.session_id,
                turn_count=payload.turn_count,
                observed_at=payload.closed_at,
            )
        )

        recent_sessions = await state.repository.list_recent_completed_sessions(
            payload.user_id, limit=state.settings.trust_metric_window_size
        )
        previous_metric = await state.repository.get_trust_metric(payload.user_id)
        new_metric = trust_metric.compute_trust_metric(
            user_id=payload.user_id, sessions=recent_sessions
        )
        await state.repository.upsert_trust_metric(new_metric)

        changed = (
            previous_metric is None
            or previous_metric.correction_frequency != new_metric.correction_frequency
        )
        if changed:
            await state.repository.create_trust_metric_history_entry(
                TrustMetricHistoryEntry(
                    user_id=payload.user_id,
                    correction_frequency=new_metric.correction_frequency,
                    window_session_count=new_metric.window_session_count,
                )
            )
        state.metrics.trust_metric_recomputed_total.add(
            1, {"outcome": "changed" if changed else "unchanged"}
        )

    return handle


async def _get_or_default_profile(app: FastAPI, user_id: UUID) -> CommunicationProfile:
    profile = await app.state.repository.get_communication_profile(user_id)
    return profile if profile is not None else CommunicationProfile(user_id=user_id)


def make_preferences_get_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> DigitalTwinPreferencesGetReplyPayload:
        payload = DigitalTwinPreferencesGetRequestPayload.model_validate(envelope.payload)
        profile = await _get_or_default_profile(app, payload.user_id)

        # Fork A (Sec8): this RPC serves only digital-twin-owned fields --
        # verbosity/technical_depth/terminology_preference stay on the
        # personality.memory.update-mediated path (personality-engine's own
        # MemoryProfile), never duplicated here.
        return DigitalTwinPreferencesGetReplyPayload(
            user_id=payload.user_id,
            preferences={
                "conversation_pacing": profile.conversation_pacing,
                "habit_timing_hint": profile.habit_timing_hint,
            },
        )

    return handle


# ---------------------------------------------------------------------------
# Phase 4E -- the three subscribed evidence sources (TDD 4E Sec8.1)
# ---------------------------------------------------------------------------
#
# All three handlers are **read-and-derive only**. None of them publishes, none
# replies, and none writes into `memory-engine` or `perception-engine` (TDD 4E
# Sec14.5 control 4). Each folds one real event into this engine's own evidence
# and re-derives the domains that event touches; `domain_derivation.record_evidence`
# does both in one transaction.


def make_memory_created_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    """`memory.long_term.created` -> five Part 16 domains.

    **The privacy allow-list runs before anything is recorded**, inside
    `derivation.evidence_from_memory_created`: a `CONFIDENTIAL` or
    `HIGHLY_SENSITIVE` memory yields no evidence rows at all, so there is nothing
    to leak at any layer above (ratified Sec19.3, read per Sec0.1.6). That is
    stronger than filtering at the rendering edge, where a later reader could
    forget the filter.

    `payload.created_at` is the memory's own timestamp and may be `None` on an
    envelope published before the field existed. It is passed through as-is --
    `derive_domain` reports `SOURCE_TIMESTAMP_MISSING` rather than substituting
    the delivery time, which would quietly collapse AC-6's gap to zero.
    """

    async def handle(envelope: EventEnvelope) -> None:
        payload = LongTermMemoryCreatedPayload.model_validate(envelope.payload)
        evidence = derivation.evidence_from_memory_created(
            user_id=payload.user_id,
            memory_id=payload.memory_id,
            memory_type=payload.memory_type.value,
            privacy_level=payload.privacy_level,
            project_id=payload.project_id,
            knowledge_node_id=payload.knowledge_node_id,
            source_created_at=payload.created_at,
            observed_at=datetime.now(UTC),
        )
        await domain_derivation.record_evidence(
            app.state.repository, evidence, user_id=payload.user_id
        )

    return handle


def make_decision_recorded_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    """`memory.decision.recorded` -> the Goals domain.

    `source_created_at` is the envelope's `occurred_at`, and that is correct
    *here* specifically: unlike `memory.long_term.created`, this payload announces
    a decision being recorded now, and carries no historical timestamp of its own.
    Using the envelope where the payload has nothing is not the substitution the
    memory handler avoids -- there, a real field exists and may be absent.
    """

    async def handle(envelope: EventEnvelope) -> None:
        payload = DecisionRecordedPayload.model_validate(envelope.payload)
        evidence = derivation.evidence_from_decision_recorded(
            user_id=payload.user_id,
            decision_id=payload.decision_id,
            confidence_at_decision=payload.confidence_at_decision,
            source_created_at=envelope.occurred_at,
            observed_at=datetime.now(UTC),
        )
        await domain_derivation.record_evidence(
            app.state.repository, evidence, user_id=payload.user_id
        )

    return handle


def make_attention_observed_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    """`perception.attention.observed` -> the Productivity Patterns domain.

    **Two things this payload does not carry, and how each is handled honestly:**

    *No `user_id`.* `PerceptionAttentionObservedPayload` has only a nullable
    `identity_id`. Under ADR-025 there is exactly one trusted user per instance,
    so the observation is attributed to the configured `primary_user_id`. That is
    not an inference about *whose* attention it was -- there is only one
    candidate; it is the same single-user assumption every other engine already
    makes, made explicit rather than smuggled in.

    *No observation id.* The subject is a stream of observations, not records, so
    there is no natural deduplication key. One is derived deterministically from
    the envelope's own `event_id` (`uuid5`), which makes a redelivery of the *same
    event* idempotent -- the property the at-least-once bus actually requires --
    without pretending two genuinely distinct observations are one.
    """

    async def handle(envelope: EventEnvelope) -> None:
        payload = PerceptionAttentionObservedPayload.model_validate(envelope.payload)
        state = app.state
        evidence = derivation.evidence_from_attention_observed(
            user_id=state.settings.primary_user_id,
            observation_id=uuid5(_ATTENTION_NAMESPACE, str(envelope.event_id)),
            attention_state=payload.attention_state.value,
            gaze_direction=payload.gaze_direction.value,
            confidence=payload.confidence,
            observed_at=envelope.occurred_at,
        )
        await domain_derivation.record_evidence(
            state.repository, evidence, user_id=state.settings.primary_user_id
        )

    return handle


_ATTENTION_NAMESPACE = UUID("6f9d4a52-1c3f-5b8e-9f21-0a7d2c4e6b10")
"""A fixed namespace for deriving an attention observation's deduplication key
from its envelope `event_id`. Constant so the same event always maps to the same
row across restarts and replays."""
