from uuid import uuid4

import pytest
from nova_contracts import (
    AttentionShiftedPayload,
    ContextChangedPayload,
    ContextRequestPayload,
    ObjectState,
    PredictionPayload,
    WorldObjectChangedPayload,
    known_subjects,
    validate_payload,
)
from pydantic import ValidationError


def test_all_world_model_subjects_are_registered() -> None:
    subjects = known_subjects()
    for subject in (
        "world_model.object.created",
        "world_model.object.updated",
        "world_model.object.deleted",
        "world_model.context.changed",
        "world_model.attention.shifted",
        "world_model.prediction.generated",
        "world_model.context.request",
    ):
        assert subject in subjects


def test_object_created_updated_deleted_share_one_payload_model() -> None:
    from nova_contracts.registry import payload_model_for

    assert payload_model_for("world_model.object.created") is WorldObjectChangedPayload
    assert payload_model_for("world_model.object.updated") is WorldObjectChangedPayload
    assert payload_model_for("world_model.object.deleted") is WorldObjectChangedPayload


def test_world_object_changed_validates_against_registry() -> None:
    validated = validate_payload(
        "world_model.object.created",
        {
            "object_id": "window:abc123",
            "label": "Window",
            "user_id": str(uuid4()),
            "new_state": "active",
        },
    )
    assert isinstance(validated, WorldObjectChangedPayload)
    assert validated.new_state is ObjectState.ACTIVE
    assert validated.previous_state is None


def test_context_changed_confidence_must_be_in_unit_interval() -> None:
    with pytest.raises(ValidationError):
        ContextChangedPayload(user_id=uuid4(), confidence=1.5)


def test_attention_shifted_score_must_be_non_negative() -> None:
    with pytest.raises(ValidationError):
        AttentionShiftedPayload(user_id=uuid4(), entity_id="window:abc", attention_score=-0.1)

    shifted = AttentionShiftedPayload(user_id=uuid4(), entity_id="window:abc", attention_score=0.7)
    assert shifted.attention_score == 0.7


def test_prediction_payload_round_trips() -> None:
    payload = PredictionPayload(
        prediction_id=uuid4(), user_id=uuid4(), prediction="meeting will run over", confidence=0.6
    )
    assert payload.prediction == "meeting will run over"
    assert payload.predicted_for is None


def test_context_request_scope_is_optional() -> None:
    request = ContextRequestPayload(user_id=uuid4())
    assert request.scope is None

    scoped = ContextRequestPayload(user_id=uuid4(), scope="agent:coding-agent")
    assert scoped.scope == "agent:coding-agent"
