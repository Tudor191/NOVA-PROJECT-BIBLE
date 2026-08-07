"""`AIModelOrchestrationClient` -- `domain.ports.AIModelOrchestrationPort`
implementation, calling `ai_model.detect_wake_phrase.request`/`ai_model.
embed_voice.request`/`ai_model.embed_face.request`/`ai_model.estimate_gaze.
request` (docs/design/phase-2d/03-perception-engine.md Sec0.2) -- never a
wake-word/embedding model SDK directly (ADR-020). The same served-RPC
pattern `communication-engine` already uses for `ai_model.transcribe`/
`ai_model.synthesize`.

A `TimeoutError`, or a reply whose `error` field is set (the Model Router's
fallback chain was exhausted), both resolve to `None` -- Sec12's documented
degraded-mode behavior (the signal is simply absent from that correlation
window) lives in `domain/identity_fusion.py`, not here; this client only
translates the RPC call and its outcome.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_contracts import (
    FaceEmbedReplyPayload,
    FaceEmbedRequestPayload,
    GazeEstimateReplyPayload,
    GazeEstimateRequestPayload,
    VoiceEmbedReplyPayload,
    VoiceEmbedRequestPayload,
    WakePhraseDetectReplyPayload,
    WakePhraseDetectRequestPayload,
)
from nova_perception_engine.domain.ports import (
    EventPublisher,
    FaceEmbedResult,
    GazeEstimateResult,
    VoiceEmbedResult,
    WakePhraseResult,
)

__all__ = ["AIModelOrchestrationClient"]

SOURCE_ENGINE = "perception-engine"


class AIModelOrchestrationClient:
    def __init__(self, event_publisher: EventPublisher, *, timeout_ms: int = 5000) -> None:
        self._event_publisher = event_publisher
        self._timeout_ms = timeout_ms

    async def detect_wake_phrase(
        self, *, audio: bytes, wake_phrase: str | None, correlation_id: UUID | None = None
    ) -> WakePhraseResult | None:
        try:
            reply = await self._event_publisher.request(
                "ai_model.detect_wake_phrase.request",
                WakePhraseDetectRequestPayload(
                    audio_bytes=audio,
                    wake_phrase=wake_phrase,
                    requesting_engine=SOURCE_ENGINE,
                    correlation_id=correlation_id or uuid4(),
                ),
                source_engine=SOURCE_ENGINE,
                correlation_id=correlation_id,
                timeout_ms=self._timeout_ms,
            )
        except TimeoutError:
            return None
        parsed = WakePhraseDetectReplyPayload.model_validate(reply.payload)
        if parsed.error is not None:
            return None
        return WakePhraseResult(matched=parsed.matched, confidence=parsed.structural_confidence)

    async def embed_voice(
        self, *, audio: bytes, correlation_id: UUID | None = None
    ) -> VoiceEmbedResult | None:
        try:
            reply = await self._event_publisher.request(
                "ai_model.embed_voice.request",
                VoiceEmbedRequestPayload(
                    audio_bytes=audio,
                    requesting_engine=SOURCE_ENGINE,
                    correlation_id=correlation_id or uuid4(),
                ),
                source_engine=SOURCE_ENGINE,
                correlation_id=correlation_id,
                timeout_ms=self._timeout_ms,
            )
        except TimeoutError:
            return None
        parsed = VoiceEmbedReplyPayload.model_validate(reply.payload)
        if parsed.error is not None or not parsed.embedding:
            return None
        return VoiceEmbedResult(embedding=parsed.embedding, confidence=1.0)

    async def embed_face(
        self, *, image: bytes, correlation_id: UUID | None = None
    ) -> FaceEmbedResult | None:
        try:
            reply = await self._event_publisher.request(
                "ai_model.embed_face.request",
                FaceEmbedRequestPayload(
                    image_bytes=image,
                    requesting_engine=SOURCE_ENGINE,
                    correlation_id=correlation_id or uuid4(),
                ),
                source_engine=SOURCE_ENGINE,
                correlation_id=correlation_id,
                timeout_ms=self._timeout_ms,
            )
        except TimeoutError:
            return None
        parsed = FaceEmbedReplyPayload.model_validate(reply.payload)
        if parsed.error is not None or not parsed.embedding:
            return None
        return FaceEmbedResult(embedding=parsed.embedding, confidence=1.0)

    async def estimate_gaze(
        self, *, image: bytes, correlation_id: UUID | None = None
    ) -> GazeEstimateResult | None:
        try:
            reply = await self._event_publisher.request(
                "ai_model.estimate_gaze.request",
                GazeEstimateRequestPayload(
                    image_bytes=image,
                    requesting_engine=SOURCE_ENGINE,
                    correlation_id=correlation_id or uuid4(),
                ),
                source_engine=SOURCE_ENGINE,
                correlation_id=correlation_id,
                timeout_ms=self._timeout_ms,
            )
        except TimeoutError:
            return None
        parsed = GazeEstimateReplyPayload.model_validate(reply.payload)
        if parsed.error is not None:
            return None
        return GazeEstimateResult(
            gaze_direction=parsed.gaze_direction, confidence=parsed.structural_confidence
        )
