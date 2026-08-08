"""`FakeSensor` -- a configurable double covering only the surface
`observation_orchestration.handle_observation_window` actually calls
(`state`, `detect_presence`, `detect_wake_phrase`, `estimate_attention`,
`report_error`) -- deliberately narrower than the real `Sensor` Protocol,
since the real `VoiceSensor`/`CameraSensor` (exercised through
`create_app`+`TestClient` in `tests/integration/test_api_observations.py`)
already cover the full lifecycle contract elsewhere. This double exists to
make failure/edge-case branches (non-`running` state, a raising detection
call) deterministic and precise, without driving the real consent/lifecycle
flow just to reach them.
"""

from __future__ import annotations

from uuid import UUID

from nova_perception_engine.domain.models import AttentionObservation
from nova_perception_engine.domain.sensor import SensorErrorReport, SensorState

__all__ = ["FakeSensor"]


class FakeSensor:
    sensor_id = "fake-sensor-1"

    def __init__(
        self,
        *,
        state: SensorState = "running",
        presence: bool = True,
        wake_matched: bool = True,
        attention: AttentionObservation | None = None,
        raise_on_detect: bool = False,
    ) -> None:
        self._state = state
        self.presence = presence
        self.wake_matched = wake_matched
        self.attention = attention or AttentionObservation(
            identity_id=None,
            attention_state="engaged",
            gaze_direction="toward_device",
            confidence=0.9,
        )
        self.raise_on_detect = raise_on_detect
        self.errors: list[SensorErrorReport] = []
        self.presence_calls: list[bytes] = []

    def state(self) -> SensorState:
        return self._state

    def detect_presence(self, window: bytes) -> bool:
        self.presence_calls.append(window)
        return self.presence

    async def detect_wake_phrase(
        self, window: bytes, *, correlation_id: UUID | None = None
    ) -> bool:
        if self.raise_on_detect:
            raise RuntimeError("simulated detection failure")
        return self.wake_matched

    async def estimate_attention(
        self, window: bytes, *, identity_id: UUID | None, correlation_id: UUID | None = None
    ) -> AttentionObservation:
        if self.raise_on_detect:
            raise RuntimeError("simulated detection failure")
        return self.attention

    def report_error(self, error: SensorErrorReport) -> None:
        self.errors.append(error)
        self._state = "failed"
