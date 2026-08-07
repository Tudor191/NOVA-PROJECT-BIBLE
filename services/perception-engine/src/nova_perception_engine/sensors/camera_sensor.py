"""`CameraSensor` -- the camera modality's `Sensor` implementation
(docs/design/phase-2d/03-perception-engine.md Sec5, Sec7). Implements the
full Sensor Abstraction Layer lifecycle contract; `match_faceprint`/
`estimate_gaze` are the actual per-frame orchestration (Sec7.1, Sec7.3),
invoked once per already-captured, already-detected face crop.

**Scope boundary, stated explicitly rather than left implicit (Doc 23
Sec6): this sensor never performs raw OS-level camera capture or face
detection itself.** `image_bytes` is always an already-detected face crop
(mirrors `ai_model.embed_face`/`ai_model.estimate_gaze`'s own request
contract, Sec0.2) -- face *detection* (finding a face region in a full
frame) and camera capture are both out of this phase's scope, a future
desktop/companion client's responsibility (Sec0.1)."""

from __future__ import annotations

from uuid import UUID

from nova_observability import get_logger
from nova_perception_engine.domain.identity_fusion import ModalitySignal
from nova_perception_engine.domain.matching import best_match
from nova_perception_engine.domain.models import AttentionObservation
from nova_perception_engine.domain.ports import AIModelOrchestrationPort, PerceptionRepository
from nova_perception_engine.domain.sensor import (
    CalibrationResult,
    PermissionStatus,
    SensorConfig,
    SensorErrorReport,
    SensorHealth,
    SensorState,
    next_state,
)

__all__ = ["CameraSensor"]

logger = get_logger("perception-engine.sensors.camera")

_FRAME_DIFF_PRESENCE_THRESHOLD = 30.0
"""Signal-processing-only presence trigger (Sec0.2's exception, mirroring
Transport VAD and `VoiceSensor`'s own energy check) -- a simple frame-
difference magnitude, never a model call. Per-pixel-byte differences range
[0, 255], so the threshold must sit within that range to ever be reachable
(a starting, calibratable value, not a scientifically tuned one -- the same
honesty `VoiceSensor`'s own energy threshold and `identity_fusion.ALPHA`
apply). Gates whether the comparatively expensive face-embedding/gaze model
calls run at all (Sec7.2's cost-avoidance discipline)."""


def _frame_difference(previous: bytes | None, current: bytes) -> float:
    if previous is None or len(previous) != len(current):
        return float(_FRAME_DIFF_PRESENCE_THRESHOLD)  # first frame: assume presence-worth checking
    return sum(abs(a - b) for a, b in zip(previous, current, strict=True)) / max(len(current), 1)


class CameraSensor:
    sensor_id = "camera-sensor-1"

    def __init__(
        self,
        *,
        repository: PerceptionRepository,
        ai_model_port: AIModelOrchestrationPort,
        encryption_key: bytes,
    ) -> None:
        self._repository = repository
        self._ai_model_port = ai_model_port
        self._encryption_key = encryption_key
        self._state: SensorState = "uninitialized"
        self._consent_active = False
        self._last_frame: bytes | None = None

    def _transition(self, action: str) -> None:
        next_ = next_state(self._state, action)
        if next_ is None:
            raise ValueError(f"Illegal transition {action!r} from state {self._state!r}")
        self._state = next_

    async def initialize(self) -> None:
        self._transition("initialize")

    async def start(self) -> None:
        self._transition("start")

    async def pause(self) -> None:
        self._transition("pause")

    async def resume(self) -> None:
        self._transition("resume")

    async def stop(self) -> None:
        self._transition("stop")

    async def health_check(self) -> SensorHealth:
        available = self._state in ("running", "paused")
        await self._repository.record_sensor_health(
            sensor_id=self.sensor_id,
            sensor_type="camera",
            status="healthy" if available else "unhealthy",
            capabilities=sorted(self.capabilities()),
        )
        return SensorHealth(available=available)

    def configuration(self) -> SensorConfig:
        return SensorConfig(sensor_id=self.sensor_id, sensor_type="camera")

    async def calibrate(self) -> CalibrationResult:
        return CalibrationResult(success=True)

    def permission_status(self) -> PermissionStatus:
        return PermissionStatus(granted=self._consent_active, source="camera")

    def report_error(self, error: SensorErrorReport) -> None:
        logger.warning("camera sensor error", extra={"sensor_id": error.sensor_id})
        self._transition("fail")

    def capabilities(self) -> frozenset[str]:
        return frozenset({"face_embedding", "gaze_estimation", "presence"})

    def state(self) -> SensorState:
        return self._state

    def detect_presence(self, frame: bytes) -> bool:
        """Sec7.2's cost-avoidance discipline: a cheap frame-difference check
        gates whether face-embedding/gaze model calls run at all."""
        changed = _frame_difference(self._last_frame, frame) >= _FRAME_DIFF_PRESENCE_THRESHOLD
        self._last_frame = frame
        return changed

    async def match_faceprint(
        self, face_crop: bytes, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> ModalitySignal | None:
        """Sec7.1 -- extracts a face embedding and scores it against every
        enrolled `modality="face"` template via cosine similarity."""
        embed_result = await self._ai_model_port.embed_face(
            image=face_crop, correlation_id=correlation_id
        )
        if embed_result is None:
            return None

        templates = await self._repository.get_identity_templates(
            user_id=user_id, modality="face"
        )
        match = best_match(embed_result.embedding, templates, encryption_key=self._encryption_key)
        if match is None:
            return None
        identity_id, score = match
        return ModalitySignal(modality="face", candidate_identity_id=identity_id, confidence=score)

    async def estimate_attention(
        self, face_crop: bytes, *, identity_id: UUID | None, correlation_id: UUID | None = None
    ) -> AttentionObservation:
        """Sec7.3 -- a candidate signal for addressee detection (Sec10),
        never a verdict."""
        result = await self._ai_model_port.estimate_gaze(
            image=face_crop, correlation_id=correlation_id
        )
        if result is None:
            return AttentionObservation(
                identity_id=identity_id,
                attention_state="unknown",
                gaze_direction="unknown",
                confidence=0.0,
            )
        attention_state = "engaged" if result.gaze_direction == "toward_device" else "disengaged"
        return AttentionObservation(
            identity_id=identity_id,
            attention_state=attention_state,
            gaze_direction=result.gaze_direction,
            confidence=result.confidence,
        )
