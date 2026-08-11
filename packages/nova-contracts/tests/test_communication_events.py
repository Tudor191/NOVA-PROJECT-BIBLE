from datetime import UTC, datetime
from uuid import uuid4

import pytest
from nova_contracts import (
    ChannelType,
    CommunicationIntentDeliverReplyPayload,
    CommunicationIntentDeliverRequestPayload,
    CommunicationSessionCompletedPayload,
    CommunicationSessionCreateRequestPayload,
    CommunicationSessionStateChangedPayload,
    CommunicationTurnReceivedPayload,
    ConversationState,
    DigitalTwinPreferencesGetReplyPayload,
    known_subjects,
    validate_payload,
)
from pydantic import ValidationError


def test_all_communication_subjects_are_registered() -> None:
    subjects = known_subjects()
    for subject in (
        "communication.intent.deliver.request",
        "communication.intent.deliver.reply",
        "communication.session.create.request",
        "communication.session.create.reply",
        "communication.session.close.request",
        "communication.session.close.reply",
        "communication.session.created",
        "communication.session.state_changed",
        "communication.session.completed",
        "communication.turn.received",
        "digital_twin.preferences.get.request",
        "digital_twin.preferences.get.reply",
    ):
        assert subject in subjects


def test_intent_deliver_request_defaults_confidence_tier_and_schema_version() -> None:
    request = CommunicationIntentDeliverRequestPayload(
        session_id=uuid4(),
        content="The build finished successfully.",
        requesting_engine="reasoning-engine",
    )
    assert request.confidence_tier == "unknown"
    assert request.schema_version == 1
    assert request.correlation_id is not None


def test_intent_deliver_reply_distinguishes_hard_stop_from_degraded_delivery() -> None:
    hard_stop = CommunicationIntentDeliverReplyPayload(
        delivered=False,
        personality_validated=True,
        rejection_reason="forbidden_pattern: manufactured_urgency",
    )
    assert hard_stop.degraded is False

    degraded_delivery = CommunicationIntentDeliverReplyPayload(
        delivered=True,
        personality_validated=False,
        degraded=True,
    )
    assert degraded_delivery.rejection_reason is None


def test_session_create_request_channel_is_a_closed_set() -> None:
    with pytest.raises(ValidationError):
        CommunicationSessionCreateRequestPayload(
            user_id=uuid4(),
            channel="carrier_pigeon",  # type: ignore[arg-type]
            device_id=uuid4(),
            requesting_engine="ws-gateway",
        )

    request = CommunicationSessionCreateRequestPayload(
        user_id=uuid4(),
        channel=ChannelType.VOICE,
        device_id=uuid4(),
        requesting_engine="ws-gateway",
    )
    assert request.channel is ChannelType.VOICE


def test_session_state_changed_carries_both_states() -> None:
    changed = CommunicationSessionStateChangedPayload(
        session_id=uuid4(),
        from_state=ConversationState.THINKING,
        to_state=ConversationState.SPEAKING,
        changed_at="2026-08-07T12:00:00Z",
    )
    assert changed.from_state is ConversationState.THINKING
    assert changed.to_state is ConversationState.SPEAKING


def test_session_completed_validates_against_registry() -> None:
    validated = validate_payload(
        "communication.session.completed",
        {
            "session_id": str(uuid4()),
            "user_id": str(uuid4()),
            "objective": None,
            "turn_count": 4,
            "closed_at": "2026-08-07T12:05:00Z",
        },
    )
    assert isinstance(validated, CommunicationSessionCompletedPayload)
    assert validated.turn_count == 4
    assert validated.corrections == []
    assert validated.preferences == []
    assert validated.feedback == []
    assert validated.decisions == []


def test_session_completed_carries_conversation_memory_evidence() -> None:
    """Phase 2D-D (06-personal-companion.md Sec6) -- additive, sourced from
    ConversationMemory; digital-twin-engine's own learning input."""
    completed = CommunicationSessionCompletedPayload(
        session_id=uuid4(),
        user_id=uuid4(),
        turn_count=6,
        closed_at=datetime.now(UTC),
        corrections=["It's Tuesday, not Wednesday."],
        preferences=["Prefers concise responses."],
        feedback=["That was helpful."],
        decisions=["Proceed with option B."],
    )
    assert completed.corrections == ["It's Tuesday, not Wednesday."]
    assert completed.preferences == ["Prefers concise responses."]
    assert completed.feedback == ["That was helpful."]
    assert completed.decisions == ["Proceed with option B."]


def test_turn_received_round_trip() -> None:
    turn = CommunicationTurnReceivedPayload(
        session_id=uuid4(),
        turn_id=uuid4(),
        user_id=uuid4(),
        content="What's on my calendar today?",
        channel=ChannelType.TEXT,
        created_at="2026-08-07T12:00:00Z",
    )
    assert turn.channel is ChannelType.TEXT
    assert turn.schema_version == 1


def test_digital_twin_preferences_reply_is_optional_and_unused_this_phase() -> None:
    reply = DigitalTwinPreferencesGetReplyPayload(user_id=uuid4())
    assert reply.preferences is None
