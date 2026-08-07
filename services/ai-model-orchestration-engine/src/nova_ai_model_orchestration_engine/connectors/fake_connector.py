"""A deterministic, in-memory `ModelConnector` -- no network, no provider SDK.
Used by integration tests and, per design doc §19, as the connector every
domain test and the ADR-023 compliance suite runs against to prove the rest of
the engine (and every other connector) behaves identically regardless of which
connector is in use (SAD 06 §6's `test_connector_swap.py` requirement).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Literal

from nova_ai_model_orchestration_engine.domain.models import (
    AudioChunk,
    ConnectorHealth,
    FaceEmbedRequest,
    FaceEmbedResult,
    GazeEstimateRequest,
    GazeEstimateResult,
    GenerateChunk,
    GenerateRequest,
    GenerateResult,
    SynthesizeRequest,
    SynthesizeResult,
    ToolCall,
    TranscribeRequest,
    TranscribeResult,
    VoiceEmbedRequest,
    VoiceEmbedResult,
    WakePhraseRequest,
    WakePhraseResult,
)
from nova_ai_model_orchestration_engine.domain.ports import NotSupportedError

__all__ = ["FakeConnector"]


class FakeConnector:
    connector_type = "fake"

    def __init__(
        self,
        *,
        response_text: str = "This is a fake response.",
        should_fail: bool = False,
        supports_embedding: bool = True,
        supports_speech: bool = True,
        supports_biometrics: bool = True,
        transcript_text: str = "this is a fake transcript",
        wake_phrase_matches: bool = True,
        gaze_direction: Literal["toward_device", "away", "unknown"] = "toward_device",
        available: bool = True,
    ) -> None:
        self.response_text = response_text
        self.should_fail = should_fail
        self.supports_embedding = supports_embedding
        self.supports_speech = supports_speech
        self.supports_biometrics = supports_biometrics
        self.transcript_text = transcript_text
        self.wake_phrase_matches = wake_phrase_matches
        self.gaze_direction = gaze_direction
        self.available = available
        self.calls = 0

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        self.calls += 1
        if self.should_fail:
            raise RuntimeError("FakeConnector configured to fail")
        tool_calls = [
            ToolCall(id=f"call_{i}", tool_name=tool.name, arguments={})
            for i, tool in enumerate(request.tools)
        ]
        return GenerateResult(
            text=self.response_text,
            tool_calls=tool_calls,
            input_tokens=sum(c.token_estimate for c in request.context),
            output_tokens=len(self.response_text.split()),
            finish_reason="tool_calls" if tool_calls else "stop",
            structural_confidence=1.0,
        )

    async def stream(self, request: GenerateRequest) -> AsyncIterator[GenerateChunk]:
        if self.should_fail:
            raise RuntimeError("FakeConnector configured to fail")
        words = self.response_text.split()
        for word in words:
            yield GenerateChunk(delta_text=word + " ")
        yield GenerateChunk(finished=True, finish_reason="stop")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.supports_embedding:
            raise NotSupportedError(self.connector_type, "embedding")
        # Deterministic, content-derived "embedding" -- not semantically
        # meaningful, but stable across calls for the same input, which is all
        # a fake needs to be for testing.
        return [[float(len(t)), float(sum(ord(c) for c in t) % 997)] for t in texts]

    async def transcribe(self, request: TranscribeRequest) -> TranscribeResult:
        if not self.supports_speech:
            raise NotSupportedError(self.connector_type, "speech_to_text")
        if self.should_fail:
            raise RuntimeError("FakeConnector configured to fail")
        return TranscribeResult(
            text=self.transcript_text, detected_language="en", structural_confidence=1.0
        )

    async def synthesize(self, request: SynthesizeRequest) -> SynthesizeResult:
        if not self.supports_speech:
            raise NotSupportedError(self.connector_type, "text_to_speech")
        if self.should_fail:
            raise RuntimeError("FakeConnector configured to fail")
        # Deterministic, content-derived "audio" -- not real audio, but stable
        # across calls for the same input, the same fidelity standard as the
        # fake embedding vectors above.
        return SynthesizeResult(
            audio_bytes=request.text.encode("utf-8"),
            audio_format=request.audio_format,
            structural_confidence=1.0,
        )

    async def synthesize_stream(self, request: SynthesizeRequest) -> AsyncIterator[AudioChunk]:
        if not self.supports_speech:
            raise NotSupportedError(self.connector_type, "text_to_speech")
        if self.should_fail:
            raise RuntimeError("FakeConnector configured to fail")
        for word in request.text.split():
            yield AudioChunk(delta_audio_bytes=word.encode("utf-8"))
        yield AudioChunk(finished=True)

    async def detect_wake_phrase(self, request: WakePhraseRequest) -> WakePhraseResult:
        if not self.supports_biometrics:
            raise NotSupportedError(self.connector_type, "wake_phrase_detection")
        if self.should_fail:
            raise RuntimeError("FakeConnector configured to fail")
        return WakePhraseResult(matched=self.wake_phrase_matches, structural_confidence=1.0)

    async def embed_voice(self, request: VoiceEmbedRequest) -> VoiceEmbedResult:
        if not self.supports_biometrics:
            raise NotSupportedError(self.connector_type, "voice_embedding")
        if self.should_fail:
            raise RuntimeError("FakeConnector configured to fail")
        # Deterministic, content-derived "embedding" -- the same fidelity
        # standard as the fake text-embedding vectors above.
        return VoiceEmbedResult(
            embedding=[float(len(request.audio_bytes)), float(sum(request.audio_bytes) % 997)],
            structural_confidence=1.0,
        )

    async def embed_face(self, request: FaceEmbedRequest) -> FaceEmbedResult:
        if not self.supports_biometrics:
            raise NotSupportedError(self.connector_type, "face_embedding")
        if self.should_fail:
            raise RuntimeError("FakeConnector configured to fail")
        return FaceEmbedResult(
            embedding=[float(len(request.image_bytes)), float(sum(request.image_bytes) % 997)],
            structural_confidence=1.0,
        )

    async def estimate_gaze(self, request: GazeEstimateRequest) -> GazeEstimateResult:
        if not self.supports_biometrics:
            raise NotSupportedError(self.connector_type, "gaze_estimation")
        if self.should_fail:
            raise RuntimeError("FakeConnector configured to fail")
        return GazeEstimateResult(gaze_direction=self.gaze_direction, structural_confidence=1.0)

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(available=self.available, latency_ms=1.0, error_rate=0.0)
