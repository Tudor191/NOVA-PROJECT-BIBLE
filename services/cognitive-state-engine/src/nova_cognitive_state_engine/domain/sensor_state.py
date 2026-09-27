"""Normalized sensor state -- Phase 4F.7, ratified decisions A-4F7-1 and A-4F7-2
(docs/design/phase-4/11-tdd-4f7-cognitive-state-panel.md §28).

**The vocabulary is not this engine's.** It is `perception-engine`'s
`SensorState` (`services/perception-engine/src/nova_perception_engine/domain/
sensor.py`), the Sensor Abstraction Layer's lifecycle, used exactly: six values,
case-sensitive, returned unchanged. A-4F7-2: *"Do not invent a parallel
health-status enum. Do not replace lifecycle state with a generic
`healthy/unhealthy` abstraction."*

**Restated, not imported.** ADR-004 and control 7
(`tests/contract/test_boundaries.py::test_control_7_no_cross_engine_import`)
forbid this engine importing `nova_perception_engine`, and `nova-contracts`
types the Event Bus payload's `status` as a plain `str`. So the six values are
written once here, and `tests/contract/test_sensor_vocabulary_drift.py` parses
`perception-engine`'s source as text and fails if the two ever differ -- the
same technique `autonomy-engine`'s `_public_topics()` uses on `ws-gateway`.

**An unknown value is rejected, never coerced.** `accept_lifecycle_state`
returns `None` for anything outside the six, and the caller stores nothing:
the table keeps *"the latest normalized known state"* (A-4F7-1). There is no
sentinel such as `"unrecognized"` -- a value the vocabulary does not contain is
not a state.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "SENSOR_LIFECYCLE_STATES",
    "SensorLifecycleState",
    "SensorStateRecord",
    "accept_lifecycle_state",
]

SensorLifecycleState = Literal[
    "uninitialized", "initialized", "running", "paused", "stopped", "failed"
]
"""`perception-engine`'s `SensorState`, value for value and in its order.

`uninitialized` is included although no transition *enters* it, so it is never
published: the ratified rule is the vocabulary exactly, not a subset of it."""

SENSOR_LIFECYCLE_STATES: tuple[str, ...] = get_args(SensorLifecycleState)


def accept_lifecycle_state(value: str) -> SensorLifecycleState | None:
    """The value itself if it is one of the six, else `None`.

    Exact membership only: no case folding, no trimming, no aliases. `"Running"`,
    `" running"` and `"healthy"` are all rejected -- accepting any of them would
    be a coercion, and A-4F7-2 forbids coercing an unknown value into a state.
    """
    if value in SENSOR_LIFECYCLE_STATES:
        return value  # type: ignore[return-value]
    return None


class SensorStateRecord(BaseModel):
    """One sensor's current record in `cognitive_state.sensor_state` -- the five
    ratified columns (TDD 4F.7 §28.1), and no others."""

    model_config = ConfigDict(frozen=True)

    sensor_id: str = Field(min_length=1)
    """`perception-engine`'s own identifier, from the payload. The identity: one
    record per `sensor_id`."""

    sensor_type: str
    """The payload's `sensor_type`, as last reported. Passed through unchanged."""

    state: SensorLifecycleState
    """A `SensorState` value only. A record cannot be built with anything else,
    so an unknown value cannot reach the table through this type."""

    reported_at: datetime
    """The envelope's `occurred_at` -- when `perception-engine`'s outbox
    **dispatched** the report, not when the transition happened (TDD 4F.7 §7.3).
    Named for what it is."""

    last_event_id: UUID
    """The envelope `event_id` of the report this record came from. An
    idempotency key for the current row only -- not a log of events."""
