from datetime import UTC, datetime
from uuid import uuid4

from nova_world_model_engine.domain.models import ObjectState, ObjectStateHistoryEntry
from nova_world_model_engine.domain.prediction import MIN_OCCURRENCES, predict_from_history


def _entry(**overrides: object) -> ObjectStateHistoryEntry:
    defaults: dict[str, object] = {
        "object_id": "window:1",
        "object_label": "Window",
        "user_id": uuid4(),
        "previous_state": ObjectState.ACTIVE,
        "new_state": ObjectState.IDLE,
        "changed_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return ObjectStateHistoryEntry(**defaults)


def test_no_prediction_below_min_occurrences() -> None:
    user_id = uuid4()
    history = [
        _entry(user_id=user_id) for _ in range(MIN_OCCURRENCES - 1)
    ]
    assert predict_from_history(history, user_id=user_id) == []


def test_prediction_generated_at_min_occurrences() -> None:
    user_id = uuid4()
    history = [_entry(user_id=user_id) for _ in range(MIN_OCCURRENCES)]
    predictions = predict_from_history(history, user_id=user_id)
    assert len(predictions) == 1
    assert predictions[0].user_id == user_id
    assert "Window" in predictions[0].prediction


def test_confidence_never_exceeds_cap() -> None:
    user_id = uuid4()
    history = [_entry(user_id=user_id) for _ in range(50)]
    predictions = predict_from_history(history, user_id=user_id)
    assert predictions[0].confidence <= 0.8


def test_distinct_transitions_produce_distinct_predictions() -> None:
    user_id = uuid4()
    history = [
        *[_entry(user_id=user_id, object_label="Window") for _ in range(MIN_OCCURRENCES)],
        *[
            _entry(
                user_id=user_id,
                object_label="File",
                previous_state=ObjectState.ACTIVE,
                new_state=ObjectState.COMPLETED,
            )
            for _ in range(MIN_OCCURRENCES)
        ],
    ]
    predictions = predict_from_history(history, user_id=user_id)
    assert len(predictions) == 2
