"""`ModelOrchestrationClient` -- `domain.ports.ModelOrchestrationPort`
implementation, calling `ai_model.transcribe.request`/`ai_model.synthesize.
request` (design doc Sec0.3, Sec8.1) -- never a Whisper/Piper SDK directly
(ADR-020). The same served-RPC pattern `reasoning-engine` already uses for
`ai_model.generate`.

A `TimeoutError`, or a reply whose `error` field is set (the Model Router's
fallback chain was exhausted), both resolve to `None` -- design doc Sec9's
documented degraded-mode behavior lives in `domain.intent_gate`/`domain.
speech`, not here; this client only translates the RPC call and its
outcome.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_contracts import (
    SynthesizeReplyPayload,
    SynthesizeRequestPayload,
    TranscribeReplyPayload,
    TranscribeRequestPayload,
)

from nova_communication_engine.domain.ports import EventPublisher

__all__ = ["ModelOrchestrationClient"]

SOURCE_ENGINE = "communication-engine"


class ModelOrchestrationClient:
    def __init__(
        self,
        event_publisher: EventPublisher,
        *,
        transcribe_timeout_ms: int = 5000,
        synthesize_timeout_ms: int = 5000,
    ) -> None:
        self._event_publisher = event_publisher
        self._transcribe_timeout_ms = transcribe_timeout_ms
        self._synthesize_timeout_ms = synthesize_timeout_ms

    async def transcribe(self, *, audio: bytes, correlation_id: UUID | None = None) -> str | None:
        try:
            reply = await self._event_publisher.request(
                "ai_model.transcribe.request",
                TranscribeRequestPayload(
                    audio_bytes=audio,
                    requesting_engine=SOURCE_ENGINE,
                    correlation_id=correlation_id or uuid4(),
                ),
                source_engine=SOURCE_ENGINE,
                correlation_id=correlation_id,
                timeout_ms=self._transcribe_timeout_ms,
            )
        except TimeoutError:
            return None
        parsed = TranscribeReplyPayload.model_validate(reply.payload)
        if parsed.error is not None:
            return None
        return parsed.text

    async def synthesize(self, *, text: str, correlation_id: UUID | None = None) -> bytes | None:
        try:
            reply = await self._event_publisher.request(
                "ai_model.synthesize.request",
                SynthesizeRequestPayload(
                    text=text,
                    requesting_engine=SOURCE_ENGINE,
                    correlation_id=correlation_id or uuid4(),
                ),
                source_engine=SOURCE_ENGINE,
                correlation_id=correlation_id,
                timeout_ms=self._synthesize_timeout_ms,
            )
        except TimeoutError:
            return None
        parsed = SynthesizeReplyPayload.model_validate(reply.payload)
        if parsed.error is not None:
            return None
        return parsed.audio_bytes
