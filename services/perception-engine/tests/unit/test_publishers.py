"""`events/publishers.py` -- pure `OutboxEvent` construction (docs/design/
phase-2d/03-perception-engine.md §13.2).

Includes §20's authorization-signal precision test (§0.9, ADR-032): every
`perception.identity.observed` payload must carry the full confidence float
alongside its tier, never the tier alone -- a regression test guarding the
property a future privileged-capability engine will depend on.
"""

from __future__ import annotations

from uuid import uuid4

from nova_perception_engine.domain.models import (
    AttentionObservation,
    IdentityConfidenceState,
    PresenceObservation,
)
from nova_perception_engine.events.publishers import (
    addressee_signal_candidate,
    attention_observed,
    consent_changed,
    identity_observed,
    presence_observed,
    sensor_health_changed,
    wake_detected,
)


def test_presence_observed_subject_and_payload() -> None:
    user_id = uuid4()
    observation = PresenceObservation(
        user_id=user_id, present=True, confidence=0.8, source="camera"
    )
    event = presence_observed(observation, correlation_id=uuid4())
    assert event.subject == "perception.presence.observed"
    assert event.payload["user_id"] == str(user_id)
    assert event.payload["present"] is True
    assert event.payload["schema_version"] == 1


def test_identity_observed_carries_full_confidence_float_alongside_tier() -> None:
    """§0.9/ADR-032/§20: never the tier alone -- a future authorization
    consumer needs the precise float, not just a coarse bucket."""
    state = IdentityConfidenceState(
        presence_session_id=uuid4(),
        user_id=uuid4(),
        identity_id=uuid4(),
        smoothed_confidence=0.7231,
        smoothed_tier="medium",
        observation_count=3,
    )
    event = identity_observed(state, correlation_id=uuid4())
    assert event.subject == "perception.identity.observed"
    assert event.payload["confidence"] == 0.7231
    assert event.payload["confidence_tier"] == "medium"


def test_attention_observed_payload() -> None:
    observation = AttentionObservation(
        identity_id=uuid4(),
        attention_state="engaged",
        gaze_direction="toward_device",
        confidence=0.6,
    )
    event = attention_observed(observation, correlation_id=uuid4())
    assert event.subject == "perception.attention.observed"
    assert event.payload["attention_state"] == "engaged"


def test_wake_detected_payload() -> None:
    event = wake_detected(matched=True, confidence=0.95, correlation_id=uuid4())
    assert event.subject == "perception.wake.detected"
    assert event.payload["matched"] is True


def test_addressee_signal_candidate_carries_no_verdict_field() -> None:
    """§0.3/§10: raw candidate signals only -- no field named anything like
    'should_respond' or 'is_addressed' may ever appear here."""
    event = addressee_signal_candidate(
        wake_word_matched=True,
        wake_word_confidence=0.9,
        identity_id=uuid4(),
        identity_confidence=0.7,
        gaze_direction="toward_device",
        session_active=True,
        correlation_id=uuid4(),
    )
    assert event.subject == "perception.addressee_signal.candidate"
    forbidden_keys = {"should_respond", "is_addressed", "verdict", "decision"}
    assert forbidden_keys.isdisjoint(event.payload.keys())


def test_consent_changed_payload() -> None:
    event = consent_changed(
        user_id=uuid4(), source="microphone", granted=False, correlation_id=uuid4()
    )
    assert event.subject == "perception.consent.changed"
    assert event.payload["granted"] is False


def test_sensor_health_changed_payload() -> None:
    event = sensor_health_changed(
        sensor_id="voice-sensor-1",
        sensor_type="voice",
        status="healthy",
        correlation_id=uuid4(),
    )
    assert event.subject == "perception.sensor.health_changed"
    assert event.payload["status"] == "healthy"
