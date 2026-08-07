"""Outbox-event construction for every subject this engine publishes
(docs/design/phase-2d/03-perception-engine.md Sec13.2) -- pure functions
only; the actual write-with-outbox-row call happens at each domain call site
(the same "domain/ writes, this module only shapes the payload" split every
prior engine's own outbox usage follows, e.g. World Model's `domain/
context.py` constructing `ContextChangedPayload` inline).

`schema_version: 1` is implicit here since these payloads are not yet
registered in `nova-contracts` (Sec13.2's own precedent: World Model's
`perception.*.observed` handlers were built the same way, "a contract this
engine is ready to serve... not a live upstream producer," before Perception
Engine existed) -- registering them formally in `nova_contracts.events.
perception` is this engine's own first real producer act, tracked as a
near-term follow-up (Sec24) rather than blocking this phase's own build.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

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
    return OutboxEvent(
        subject="perception.presence.observed",
        payload={
            "user_id": str(observation.user_id) if observation.user_id else None,
            "present": observation.present,
            "confidence": observation.confidence,
            "source": observation.source,
            "schema_version": 1,
        },
        correlation_id=correlation_id,
    )


def identity_observed(state: IdentityConfidenceState, *, correlation_id: UUID) -> OutboxEvent:
    """Sec13.2: published on every correlation window that changes
    `smoothed_tier`, not on every window -- the caller (the correlation-
    window orchestration) is responsible for that gating; this function only
    shapes the payload once the caller has decided to publish."""
    return OutboxEvent(
        subject="perception.identity.observed",
        payload={
            "user_id": str(state.user_id),
            "identity_id": str(state.identity_id) if state.identity_id else None,
            "confidence": state.smoothed_confidence,
            "confidence_tier": state.smoothed_tier,
            "modality_summary": "voice+face",
            "schema_version": 1,
        },
        correlation_id=correlation_id,
    )


def attention_observed(observation: AttentionObservation, *, correlation_id: UUID) -> OutboxEvent:
    return OutboxEvent(
        subject="perception.attention.observed",
        payload={
            "identity_id": str(observation.identity_id) if observation.identity_id else None,
            "attention_state": observation.attention_state,
            "gaze_direction": observation.gaze_direction,
            "confidence": observation.confidence,
            "schema_version": 1,
        },
        correlation_id=correlation_id,
    )


def wake_detected(*, matched: bool, confidence: float, correlation_id: UUID) -> OutboxEvent:
    """Deliberately subject-named `.detected`, not `.observed` (Sec13.2) --
    never matches World Model's `perception.*.observed` wildcard."""
    return OutboxEvent(
        subject="perception.wake.detected",
        payload={"matched": matched, "confidence": confidence, "schema_version": 1},
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
    `communication-engine`'s future 2D-C addressee fusion."""
    payload: dict[str, Any] = {
        "wake_word_matched": wake_word_matched,
        "wake_word_confidence": wake_word_confidence,
        "identity_id": str(identity_id) if identity_id else None,
        "identity_confidence": identity_confidence,
        "gaze_direction": gaze_direction,
        "session_active": session_active,
        "schema_version": 1,
    }
    return OutboxEvent(
        subject="perception.addressee_signal.candidate",
        payload=payload,
        correlation_id=correlation_id,
    )


def consent_changed(
    *, user_id: UUID, source: str, granted: bool, correlation_id: UUID
) -> OutboxEvent:
    return OutboxEvent(
        subject="perception.consent.changed",
        payload={
            "user_id": str(user_id),
            "source": source,
            "granted": granted,
            "schema_version": 1,
        },
        correlation_id=correlation_id,
    )


def sensor_health_changed(
    *, sensor_id: str, sensor_type: str, status: str, correlation_id: UUID
) -> OutboxEvent:
    return OutboxEvent(
        subject="perception.sensor.health_changed",
        payload={
            "sensor_id": sensor_id,
            "sensor_type": sensor_type,
            "status": status,
            "schema_version": 1,
        },
        correlation_id=correlation_id,
    )
