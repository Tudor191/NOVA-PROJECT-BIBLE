"""The sensor lifecycle vocabulary -- Phase 4F.7, A-4F7-2 (TDD 4F.7 §28.2, P-10′).

The six values are `perception-engine`'s `SensorState`, used exactly.
Acceptance is exact membership: case-sensitive, no trimming, no aliases, no
health words, no sentinel. Anything else is rejected -- and a record cannot even
be *built* with it, which is the structural half of "never stored".
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from nova_cognitive_state_engine.domain.sensor_state import (
    SENSOR_LIFECYCLE_STATES,
    SensorStateRecord,
    accept_lifecycle_state,
)
from pydantic import ValidationError

SIX = ("uninitialized", "initialized", "running", "paused", "stopped", "failed")


def test_the_vocabulary_is_exactly_the_six_lifecycle_states_in_order() -> None:
    assert SIX == SENSOR_LIFECYCLE_STATES


@pytest.mark.parametrize("value", SIX)
def test_each_lifecycle_state_is_accepted_and_returned_unchanged(value: str) -> None:
    assert accept_lifecycle_state(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "healthy",  # the health string `health_check()` writes -- a different vocabulary
        "unhealthy",
        "unrecognized",  # the sentinel A-4F7-2 withdrew
        "degraded",
        "Running",  # case-sensitive
        "RUNNING",
        " running",  # no trimming
        "running ",
        "",
        "stopping",
    ],
)
def test_anything_else_is_rejected_not_coerced(value: str) -> None:
    assert accept_lifecycle_state(value) is None


@pytest.mark.parametrize("value", ["healthy", "unrecognized", "Running", ""])
def test_a_record_cannot_be_built_with_an_unknown_state(value: str) -> None:
    """So an unknown value cannot reach the table through the domain type."""
    with pytest.raises(ValidationError):
        SensorStateRecord(
            sensor_id="companion-filesystem",
            sensor_type="filesystem",
            state=value,  # type: ignore[arg-type]
            reported_at=datetime.now(UTC),
            last_event_id=uuid4(),
        )


@pytest.mark.parametrize("value", SIX)
def test_a_record_holds_any_of_the_six(value: str) -> None:
    record = SensorStateRecord(
        sensor_id="camera-sensor-1",
        sensor_type="camera",
        state=value,  # type: ignore[arg-type]
        reported_at=datetime.now(UTC),
        last_event_id=uuid4(),
    )
    assert record.state == value


def test_a_record_has_exactly_the_five_ratified_fields() -> None:
    """TDD 4F.7 §28.1: current-state storage, five columns, nothing else --
    no history, heartbeat or audit field."""
    assert set(SensorStateRecord.model_fields) == {
        "sensor_id",
        "sensor_type",
        "state",
        "reported_at",
        "last_event_id",
    }
