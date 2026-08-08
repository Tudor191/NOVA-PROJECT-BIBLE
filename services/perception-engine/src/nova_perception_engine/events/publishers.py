"""Outbox-event construction for every subject this engine publishes
(docs/design/phase-2d/03-perception-engine.md Sec13.2) -- pure functions
only; the actual write-with-outbox-row call happens at each domain call site
(the same "domain/ writes, this module only shapes the payload" split every
prior engine's own outbox usage follows, e.g. World Model's `domain/
context.py` constructing `ContextChangedPayload` inline).

Registered in `nova_contracts.events.perception` per
docs/design/phase-2d/04-conversation-intelligence.md Sec0.6 -- previously
these were raw, unvalidated dicts (`schema_version: 1` implicit, no
registered model), disclosed as this engine's own tracked follow-up
(Sec13.2/Sec24 of this module's own prior revision). Every function below
now constructs the registered Pydantic model first, then serializes it --
the wire shape (field names, values, `schema_version`) is unchanged; only
the construction path is now schema-validated rather than hand-assembled.
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts import (
    PerceptionAddresseeSignalCandidatePayload,
    PerceptionAttentionObservedPayload,
    PerceptionConsentChangedPayload,
    PerceptionIdentityObservedPayload,
    PerceptionPresenceObservedPayload,
    PerceptionSensorHealthChangedPayload,
    PerceptionWakeDetectedPayload,
)

from nova_perception_engine.domain.models import (
    AttentionObservation,
    IdentityConfidenceState,
    PresenceObservation,
)
from nova_perception_engine.domain.ports import OutboxEvent

__all__ = [
    "addressee_signal_candidate",
    "attention_observed",
    "consent_changed",
    "identity_observed",
    "presence_observed",
    "sensor_health_changed",
    "wake_detected",
]


def presence_observed(observation: PresenceObservation, *, correlation_id: UUID) -> OutboxEvent:
    payload = PerceptionPresenceObservedPayload(
        user_id=observation.user_id,
        present=observation.present,
        confidence=observation.confidence,
        source=observation.source,
    )
    return OutboxEvent(
        subject="perception.presence.observed",
        payload=payload.model_dump(mode="json"),
        correlation_id=correlation_id,
    )


def identity_observed(state: IdentityConfidenceState, *, correlation_id: UUID) -> OutboxEvent:
    """Sec13.2: published on every correlation window that changes
    `smoothed_tier`, not on every window -- the caller (the correlation-
    window orchestration) is responsible for that gating; this function only
    shapes the payload once the caller has decided to publish."""
    payload = PerceptionIdentityObservedPayload(
        user_id=state.user_id,
        identity_id=state.identity_id,
        confidence=state.smoothed_confidence,
        confidence_tier=state.smoothed_tier,
        modality_summary="voice+face",
    )
    return OutboxEvent(
        subject="perception.identity.observed",
        payload=payload.model_dump(mode="json"),
        correlation_id=correlation_id,
    )


def attention_observed(observation: AttentionObservation, *, correlation_id: UUID) -> OutboxEvent:
    payload = PerceptionAttentionObservedPayload(
        identity_id=observation.identity_id,
        attention_state=observation.attention_state,
        gaze_direction=observation.gaze_direction,
        confidence=observation.confidence,
    )
    return OutboxEvent(
        subject="perception.attention.observed",
        payload=payload.model_dump(mode="json"),
        correlation_id=correlation_id,
    )


def wake_detected(*, matched: bool, confidence: float, correlation_id: UUID) -> OutboxEvent:
    """Deliberately subject-named `.detected`, not `.observed` (Sec13.2) --
    never matches World Model's `perception.*.observed` wildcard."""
    payload = PerceptionWakeDetectedPayload(matched=matched, confidence=confidence)
    return OutboxEvent(
        subject="perception.wake.detected",
        payload=payload.model_dump(mode="json"),
        correlation_id=correlation_id,
    )


def addressee_signal_candidate(
    *,
    wake_word_matched: bool,
    wake_word_confidence: float,
    identity_id: UUID | None,
    identity_confidence: float,
    gaze_direction: str,
    session_active: bool,
    correlation_id: UUID,
) -> OutboxEvent:
    """Sec10 -- raw candidate signals only, no verdict field of any kind.
    Deliberately subject-named `.candidate`, not `.observed` -- never
    matches World Model's wildcard, consumed directly by
    `communication-engine`'s Phase 2D-C addressee fusion
    (docs/design/phase-2d/04-conversation-intelligence.md Sec4)."""
    payload = PerceptionAddresseeSignalCandidatePayload(
        wake_word_matched=wake_word_matched,
        wake_word_confidence=wake_word_confidence,
        identity_id=identity_id,
        identity_confidence=identity_confidence,
        gaze_direction=gaze_direction,
        session_active=session_active,
    )
    return OutboxEvent(
        subject="perception.addressee_signal.candidate",
        payload=payload.model_dump(mode="json"),
        correlation_id=correlation_id,
    )


def consent_changed(
    *, user_id: UUID, source: str, granted: bool, correlation_id: UUID
) -> OutboxEvent:
    payload = PerceptionConsentChangedPayload(user_id=user_id, source=source, granted=granted)
    return OutboxEvent(
        subject="perception.consent.changed",
        payload=payload.model_dump(mode="json"),
        correlation_id=correlation_id,
    )


def sensor_health_changed(
    *, sensor_id: str, sensor_type: str, status: str, correlation_id: UUID
) -> OutboxEvent:
    payload = PerceptionSensorHealthChangedPayload(
        sensor_id=sensor_id, sensor_type=sensor_type, status=status
    )
    return OutboxEvent(
        subject="perception.sensor.health_changed",
        payload=payload.model_dump(mode="json"),
        correlation_id=correlation_id,
    )
