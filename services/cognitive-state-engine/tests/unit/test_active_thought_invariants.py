"""`ActiveThought`'s invariants, each demonstrated by constructing the thing the
model forbids and watching it raise.

Phase 4E's lesson, carried forward: the controls that matter are **types, not
tests**. These tests exist to prove the validators are live -- removing any one
of them must make a named test here fail -- not to be the enforcement itself.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from nova_cognitive_state_engine.domain.models import ActiveThought, AttentionLayer
from pydantic import ValidationError

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


def _thought(**overrides: object) -> ActiveThought:
    defaults: dict[str, object] = {
        "thought_id": uuid4(),
        "user_id": uuid4(),
        "description": "Investigate recurring build failures.",
        "priority": 5,
        "confidence": 0.7,
        "current_progress": 0.25,
        "attention_layer": AttentionLayer.ACTIVE,
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(overrides)
    return ActiveThought(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_thought_constructs() -> None:
    thought = _thought()
    assert thought.attention_layer is AttentionLayer.ACTIVE
    assert thought.dependencies == ()


def test_every_part_6_field_is_present() -> None:
    """Part 6:125-137 lists seven things a thought *"should have"*. All seven
    are fields, so a future edit that drops one fails here rather than silently
    shipping an incomplete model."""
    fields = set(ActiveThought.model_fields)
    for required in (
        "priority",
        "confidence",
        "dependencies",
        "estimated_completion",
        "related_memories",
        "related_projects",
        "current_progress",
    ):
        assert required in fields, f"Bible Part 6 names {required!r} and the model lost it"


def test_a_thought_cannot_depend_on_itself() -> None:
    thought_id = uuid4()
    with pytest.raises(ValidationError, match="self-dependency"):
        _thought(thought_id=thought_id, dependencies=(thought_id,))


@pytest.mark.parametrize(
    "field", ["dependencies", "related_memories", "related_projects"]
)
def test_duplicate_relations_are_rejected_not_deduplicated(field: str) -> None:
    repeated = uuid4()
    with pytest.raises(ValidationError, match="duplicate ids"):
        _thought(**{field: (repeated, repeated)})


def test_an_archived_thought_cannot_be_partially_progressed() -> None:
    with pytest.raises(ValidationError, match="no longer requiring active processing"):
        _thought(attention_layer=AttentionLayer.ARCHIVED, current_progress=0.5)


@pytest.mark.parametrize("progress", [0.0, 1.0])
def test_archived_permits_never_started_and_finished(progress: float) -> None:
    """The floor permits what it was written to permit: filed before it began,
    or filed because it finished."""
    thought = _thought(attention_layer=AttentionLayer.ARCHIVED, current_progress=progress)
    assert thought.current_progress == progress


def test_updated_at_cannot_precede_created_at() -> None:
    with pytest.raises(ValidationError, match="before it was created"):
        _thought(created_at=NOW, updated_at=NOW - timedelta(seconds=1))


@pytest.mark.parametrize("progress", [-0.01, 1.01])
def test_progress_is_a_fraction(progress: float) -> None:
    with pytest.raises(ValidationError):
        _thought(current_progress=progress)


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_is_a_fraction(confidence: float) -> None:
    with pytest.raises(ValidationError):
        _thought(confidence=confidence)


def test_priority_is_not_negative() -> None:
    with pytest.raises(ValidationError):
        _thought(priority=-1)


def test_description_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        _thought(description="")


def test_estimated_completion_may_be_unknown() -> None:
    """`None` is an honest "not estimated". A sentinel date would be a
    fabricated timestamp, which TDD 4F §2.2 forbids."""
    assert _thought(estimated_completion=None).estimated_completion is None
