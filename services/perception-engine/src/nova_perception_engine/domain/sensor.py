"""The Sensor Abstraction Layer -- Bible Part 11's "Sensor Abstraction Layer"
and Master Blueprint Sec9.1, implemented per docs/design/phase-2d/
03-perception-engine.md Sec5. Every sensor this engine registers -- the two
shipped this phase (`sensors/voice_sensor.py`, `sensors/camera_sensor.py`)
and every one Phase 4 adds -- implements the same `Sensor` Protocol and the
same lifecycle state machine, in full, from day one: minimal sensing breadth
this phase (Sec0.1), full interface contract regardless, so a future
`nova-companion` sensor registering behind this layer in Phase 4 is a matter
of implementing an already-correct Protocol, never a redesign.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

__all__ = [
    "CalibrationResult",
    "PermissionStatus",
    "Sensor",
    "SensorConfig",
    "SensorErrorReport",
    "SensorHealth",
    "SensorState",
    "next_state",
]

SensorState = Literal["uninitialized", "initialized", "running", "paused", "stopped", "failed"]

_TRANSITIONS: dict[tuple[SensorState, str], SensorState] = {
    ("uninitialized", "initialize"): "initialized",
    ("initialized", "start"): "running",
    ("running", "pause"): "paused",
    ("paused", "resume"): "running",
    ("running", "stop"): "stopped",
    ("paused", "stop"): "stopped",
    ("running", "fail"): "failed",
    ("failed", "initialize"): "initialized",
}
"""Sec5's state diagram, as data -- `initialized -> running -> {paused,
stopped, failed}`, `paused -> {running, stopped}`, `failed -> initialized`
(restart, Sec12). Every other `(state, action)` pair is an illegal
transition, rejected by `next_state` rather than silently permitted."""


def next_state(current: SensorState, action: str) -> SensorState | None:
    """Pure. Returns the resulting state, or `None` if `(current, action)` is
    not a defined transition -- callers treat `None` as a no-op, the same
    "no defined transition is not an error" convention World Model's own
    `state_management.py` already establishes for object states."""
    return _TRANSITIONS.get((current, action))


class SensorHealth(BaseModel):
    available: bool
    error_rate: float = 0.0
    detail: str | None = None


class SensorConfig(BaseModel):
    sensor_id: str
    sensor_type: Literal["voice", "camera"]
    parameters: dict[str, object] = {}


class CalibrationResult(BaseModel):
    success: bool
    detail: str | None = None


class PermissionStatus(BaseModel):
    granted: bool
    source: Literal["microphone", "camera"]


class SensorErrorReport(BaseModel):
    sensor_id: str
    message: str
    occurred_at: str


@runtime_checkable
class Sensor(Protocol):
    """Bible Part 11's full "Required capabilities" list (Sec5): Initialize,
    Start, Pause, Resume, Stop, Health Check, Configuration, Calibration,
    Permission Status, Error Reporting, Capability Discovery -- every one
    present, none deferred, satisfying Master Blueprint Risk Sec11.3's
    explicit requirement."""

    sensor_id: str

    async def initialize(self) -> None: ...

    async def start(self) -> None: ...

    async def pause(self) -> None: ...

    async def resume(self) -> None: ...

    async def stop(self) -> None: ...

    async def health_check(self) -> SensorHealth: ...

    def configuration(self) -> SensorConfig: ...

    async def calibrate(self) -> CalibrationResult: ...

    def permission_status(self) -> PermissionStatus: ...

    def report_error(self, error: SensorErrorReport) -> None: ...

    def capabilities(self) -> frozenset[str]: ...

    def state(self) -> SensorState: ...
