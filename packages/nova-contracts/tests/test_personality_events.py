from uuid import uuid4

from nova_contracts import (
    CommunicationStyle,
    ConfidenceTier,
    PersonalityMemoryUpdatePayload,
    PersonalityStyleSelectReplyPayload,
    PersonalityStyleSelectRequestPayload,
    PersonalityValidateResponseReplyPayload,
    PersonalityValidateResponseRequestPayload,
    ViolationCheckFamily,
    ViolationRecordPayload,
    known_subjects,
    validate_payload,
)


def test_all_personality_subjects_are_registered() -> None:
    subjects = known_subjects()
    for subject in (
        "personality.validate_response.request",
        "personality.validate_response.reply",
        "personality.style.select.request",
        "personality.style.select.reply",
        "personality.memory.update",
    ):
        assert subject in subjects


def test_validate_response_request_defaults_and_schema_version() -> None:
    request = PersonalityValidateResponseRequestPayload(
        content="The build finished successfully.",
        session_id=uuid4(),
        requesting_engine="communication-engine",
        correlation_id=uuid4(),
    )
    assert request.confidence_tier == ConfidenceTier.UNKNOWN
    assert request.schema_version == 1


def test_validate_response_reply_round_trips_with_violations() -> None:
    reply = PersonalityValidateResponseReplyPayload(
        passed=False,
        adjusted_content=None,
        violations=[
            ViolationRecordPayload(
                check_family=ViolationCheckFamily.FORBIDDEN_PATTERN,
                detail="Matched forbidden pattern 'manufactured_urgency'.",
            )
        ],
    )
    assert reply.violations[0].check_family is ViolationCheckFamily.FORBIDDEN_PATTERN


def test_style_select_reply_validates_against_registry() -> None:
    validated = validate_payload(
        "personality.style.select.reply",
        {"style": "analytical", "verbosity": "concise", "technical_depth": "deep"},
    )
    assert isinstance(validated, PersonalityStyleSelectReplyPayload)
    assert validated.style is CommunicationStyle.ANALYTICAL


def test_style_select_request_situation_hint_and_channel_are_optional() -> None:
    request = PersonalityStyleSelectRequestPayload(
        requesting_engine="communication-engine", correlation_id=uuid4()
    )
    assert request.situation_hint is None
    assert request.channel is None


def test_memory_update_defaults_to_digital_twin_source() -> None:
    update = PersonalityMemoryUpdatePayload()
    assert update.source == "digital_twin"
    assert update.verbosity is None
    assert update.schema_version == 1
