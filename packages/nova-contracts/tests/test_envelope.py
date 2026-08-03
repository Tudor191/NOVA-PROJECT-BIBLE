from uuid import uuid4

import pytest
from nova_contracts import (
    EventEnvelope,
    HeartbeatPayload,
    ModuleStatus,
    known_subjects,
    register_payload,
    validate_payload,
)
from pydantic import BaseModel, ValidationError


def test_event_envelope_requires_subject_source_and_correlation() -> None:
    with pytest.raises(ValidationError):
        EventEnvelope()  # type: ignore[call-arg]


def test_event_envelope_defaults_event_id_and_timestamp() -> None:
    envelope = EventEnvelope(
        subject="nova.heartbeat",
        source_engine="nova-core",
        correlation_id=uuid4(),
    )
    assert envelope.event_id is not None
    assert envelope.occurred_at is not None
    assert envelope.confidence is None
    assert envelope.payload == {}


def test_event_envelope_is_frozen() -> None:
    envelope = EventEnvelope(
        subject="nova.heartbeat", source_engine="nova-core", correlation_id=uuid4()
    )
    with pytest.raises(ValidationError):
        envelope.subject = "changed"  # type: ignore[misc]  # verifying the runtime enforcement


def test_confidence_must_be_between_zero_and_one() -> None:
    with pytest.raises(ValidationError):
        EventEnvelope(
            subject="nova.heartbeat",
            source_engine="nova-core",
            correlation_id=uuid4(),
            confidence=1.5,
        )


def test_heartbeat_payload_is_registered_and_validated() -> None:
    assert "nova.heartbeat" in known_subjects()
    validated = validate_payload(
        "nova.heartbeat", {"module": "nova-core", "status": "healthy", "uptime_seconds": 12.5}
    )
    assert isinstance(validated, HeartbeatPayload)
    assert validated.status is ModuleStatus.HEALTHY


def test_unregistered_subject_passes_through_unvalidated() -> None:
    raw = {"anything": "goes"}
    assert validate_payload("not.yet.registered", raw) is raw


def test_registering_same_subject_twice_with_different_models_raises() -> None:
    class ModelA(BaseModel):
        pass

    class ModelB(BaseModel):
        pass

    register_payload("test.duplicate.subject")(ModelA)
    with pytest.raises(ValueError, match="already registered"):
        register_payload("test.duplicate.subject")(ModelB)
