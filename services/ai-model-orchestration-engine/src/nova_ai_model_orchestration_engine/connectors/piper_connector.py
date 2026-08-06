"""The default, zero-budget text-to-speech connector (docs/design/phase-2d/
01-communication-engine.md §0.3). Talks to a local Piper-class server over its
OpenAI-audio-API-compatible `POST /v1/audio/speech` endpoint -- the same
lazily-imported-`httpx` convention as `OllamaConnector`/`WhisperConnector`.

Speech-to-text is `WhisperConnector`'s job, not this connector's -- `synthesize`/
`synthesize_stream` only.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from nova_ai_model_orchestration_engine.domain.models import (
    AudioChunk,
    ConnectorHealth,
    GenerateRequest,
    GenerateResult,
    SynthesizeRequest,
    SynthesizeResult,
    TranscribeRequest,
    TranscribeResult,
)
from nova_ai_model_orchestration_engine.domain.ports import NotSupportedError

if TYPE_CHECKING:
    import httpx

__all__ = ["PiperConnector"]

_STREAM_CHUNK_BYTES = 4096
"""Read granularity for `synthesize_stream`'s HTTP response body -- an
arbitrary but reasonable buffer size, not derived from any audio-format
property (the server, not this connector, owns audio framing)."""


class PiperConnector:
    connector_type = "piper"

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8083",
        default_voice: str = "en_US-default",
        timeout_s: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._default_voice = default_voice
        self._timeout_s = timeout_s
        self._client = client

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout_s)
        return self._client

    def _payload(self, request: SynthesizeRequest) -> dict[str, str]:
        return {
            "input": request.text,
            "voice": request.voice_profile or self._default_voice,
            "response_format": request.audio_format,
        }

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        raise NotSupportedError(self.connector_type, "text_generation")

    def stream(self, request: GenerateRequest) -> Any:
        raise NotSupportedError(self.connector_type, "streaming")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotSupportedError(self.connector_type, "embedding")

    async def transcribe(self, request: TranscribeRequest) -> TranscribeResult:
        raise NotSupportedError(self.connector_type, "speech_to_text")

    async def synthesize(self, request: SynthesizeRequest) -> SynthesizeResult:
        client = self._ensure_client()
        response = await client.post("/v1/audio/speech", json=self._payload(request))
        response.raise_for_status()
        return SynthesizeResult(
            audio_bytes=response.content,
            audio_format=request.audio_format,
            structural_confidence=1.0 if response.content else 0.0,
        )

    async def synthesize_stream(self, request: SynthesizeRequest) -> AsyncIterator[AudioChunk]:
        client = self._ensure_client()
        async with client.stream(
            "POST", "/v1/audio/speech", json=self._payload(request)
        ) as response:
            response.raise_for_status()
            async for raw_chunk in response.aiter_bytes(_STREAM_CHUNK_BYTES):
                if raw_chunk:
                    yield AudioChunk(delta_audio_bytes=raw_chunk)
            yield AudioChunk(finished=True)

    async def health(self) -> ConnectorHealth:
        client = self._ensure_client()
        try:
            import time

            start = time.perf_counter()
            response = await client.get("/health")
            response.raise_for_status()
            latency_ms = (time.perf_counter() - start) * 1000
            return ConnectorHealth(available=True, latency_ms=latency_ms, error_rate=0.0)
        except Exception as exc:  # noqa: BLE001 -- health checks must never raise
            return ConnectorHealth(available=False, detail=str(exc))
