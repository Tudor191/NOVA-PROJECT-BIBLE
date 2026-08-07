"""`FakeAIModelOrchestrationPort` -- an in-process double for
`domain.ports.AIModelOrchestrationPort`, so sensor/API tests never need a
live `ai-model-orchestration-engine` reachable over the bus (docs/design/
phase-2d/03-perception-engine.md §0.2, §12: a `None` result is this port's
own documented degraded-mode outcome, exercised directly here rather than
only in prose).
"""

from __future__ import annotations

from uuid import UUID

from nova_perception_engine.domain.ports import (
    FaceEmbedResult,
    GazeEstimateResult,
    VoiceEmbedResult,
    WakePhraseResult,
)

__all__ = ["FakeAIModelOrchestrationPort"]


class FakeAIModelOrchestrationPort:
    def __init__(
        self,
        *,
        wake_phrase_matched: bool = True,
        wake_phrase_confidence: float = 0.9,
        voice_embedding: list[float] | None = None,
        face_embedding: list[float] | None = None,
        gaze_direction: str = "toward_device",
        gaze_confidence: float = 0.9,
        available: bool = True,
    ) -> None:
        self.wake_phrase_matched = wake_phrase_matched
        self.wake_phrase_confidence = wake_phrase_confidence
        self.voice_embedding = voice_embedding if voice_embedding is not None else [1.0, 0.0, 0.0]
        self.face_embedding = face_embedding if face_embedding is not None else [1.0, 0.0, 0.0]
        self.gaze_direction = gaze_direction
        self.gaze_confidence = gaze_confidence
        self.available = available
        self.calls: list[str] = []

    async def detect_wake_phrase(
        self, *, audio: bytes, wake_phrase: str | None, correlation_id: UUID | None = None
    ) -> WakePhraseResult | None:
        self.calls.append("detect_wake_phrase")
        if not self.available:
            return None
        return WakePhraseResult(
            matched=self.wake_phrase_matched, confidence=self.wake_phrase_confidence
        )

    async def embed_voice(
        self, *, audio: bytes, correlation_id: UUID | None = None
    ) -> VoiceEmbedResult | None:
        self.calls.append("embed_voice")
        if not self.available:
            return None
        return VoiceEmbedResult(embedding=self.voice_embedding, confidence=1.0)

    async def embed_face(
        self, *, image: bytes, correlation_id: UUID | None = None
    ) -> FaceEmbedResult | None:
        self.calls.append("embed_face")
        if not self.available:
            return None
        return FaceEmbedResult(embedding=self.face_embedding, confidence=1.0)

    async def estimate_gaze(
        self, *, image: bytes, correlation_id: UUID | None = None
    ) -> GazeEstimateResult | None:
        self.calls.append("estimate_gaze")
        if not self.available:
            return None
        return GazeEstimateResult(
            gaze_direction=self.gaze_direction, confidence=self.gaze_confidence
        )
