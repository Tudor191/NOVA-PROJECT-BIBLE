"""`VoiceSensor` -- the voice modality's `Sensor` implementation (docs/design/
phase-2d/03-perception-engine.md Sec5, Sec6). Implements the full Sensor
Abstraction Layer lifecycle contract; `detect_wake_phrase`/`match_voiceprint`
are the actual per-window orchestration (Sec6.1, Sec6.2), invoked once per
already-captured, already-bounded audio window.

**Scope boundary, stated explicitly rather than left implicit (Doc 23 Sec6):
this sensor never performs raw OS-level audio capture itself.** Exactly like
`ai-model-orchestration-engine`'s `WhisperConnector`/`PiperConnector` (never
touch an audio device, only already-supplied bytes) and
`communication-engine`'s `VoiceChannelAdapter` (reads from an already-
connected WebSocket, never opens a microphone), this sensor's detection
methods accept an already-captured window from whatever upstream transport
supplies it -- a future desktop/companion client, out of this phase's own
scope (Sec0.1: two sensing modalities this phase, not a raw device-driver
integration). Claiming a live microphone integration this environment
cannot actually verify working would be exactly the fabricated capability
Doc 23 Sec6 forbids.
"""

from __future__ import annotations

from uuid import UUID

from nova_observability import get_logger
from nova_perception_engine.domain.identity_fusion import ModalitySignal
from nova_perception_engine.domain.matching import best_match
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

__all__ = ["VoiceSensor"]

logger = get_logger("perception-engine.sensors.voice")

_ENERGY_PRESENCE_THRESHOLD = 30.0
"""Signal-processing-only presence trigger (Sec0.2's exception, mirroring
Transport VAD) -- a simple mean-amplitude energy check over raw bytes, never
a model call. `audio` bytes range [0, 255], so the threshold must sit within
that range to ever be reachable -- a starting, calibratable value (mirrors
`identity_fusion.ALPHA`'s own "considered starting point, not a scientifically
validated calibration" honesty), not real-audio-engineering RMS."""


def _rms_energy(audio: bytes) -> float:
    if not audio:
        return 0.0
    return sum(audio) / len(audio)


class VoiceSensor:
    sensor_id = "voice-sensor-1"

    def __init__(
        self,
        *,
        repository: PerceptionRepository,
        ai_model_port: AIModelOrchestrationPort,
        encryption_key: bytes,
        wake_phrase: str | None = None,
    ) -> None:
        self._repository = repository
        self._ai_model_port = ai_model_port
        self._encryption_key = encryption_key
        self._wake_phrase = wake_phrase
        self._state: SensorState = "uninitialized"
        self._consent_active = False

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
            sensor_type="voice",
            status="healthy" if available else "unhealthy",
            capabilities=sorted(self.capabilities()),
        )
        return SensorHealth(available=available)

    def configuration(self) -> SensorConfig:
        return SensorConfig(sensor_id=self.sensor_id, sensor_type="voice")

    async def calibrate(self) -> CalibrationResult:
        return CalibrationResult(success=True)

    def permission_status(self) -> PermissionStatus:
        return PermissionStatus(granted=self._consent_active, source="microphone")

    def report_error(self, error: SensorErrorReport) -> None:
        logger.warning("voice sensor error", extra={"sensor_id": error.sensor_id})
        self._transition("fail")

    def capabilities(self) -> frozenset[str]:
        return frozenset({"wake_phrase_detection", "voice_embedding", "presence"})

    def state(self) -> SensorState:
        return self._state

    def detect_presence(self, audio: bytes) -> bool:
        """Sec7.2's cost-avoidance discipline, applied to voice: a cheap
        energy check gates whether the (comparatively expensive) wake/
        voiceprint model calls run at all."""
        return _rms_energy(audio) >= _ENERGY_PRESENCE_THRESHOLD

    async def detect_wake_phrase(
        self, audio: bytes, *, correlation_id: UUID | None = None
    ) -> bool:
        result = await self._ai_model_port.detect_wake_phrase(
            audio=audio, wake_phrase=self._wake_phrase, correlation_id=correlation_id
        )
        return result is not None and result.matched

    async def match_voiceprint(
        self, audio: bytes, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> ModalitySignal | None:
        """Sec6.2 -- extracts a voice embedding and scores it against every
        enrolled `modality="voice"` template via cosine similarity."""
        embed_result = await self._ai_model_port.embed_voice(
            audio=audio, correlation_id=correlation_id
        )
        if embed_result is None:
            return None

        templates = await self._repository.get_identity_templates(
            user_id=user_id, modality="voice"
        )
        match = best_match(embed_result.embedding, templates, encryption_key=self._encryption_key)
        if match is None:
            return None
        identity_id, score = match
        return ModalitySignal(modality="voice", candidate_identity_id=identity_id, confidence=score)
