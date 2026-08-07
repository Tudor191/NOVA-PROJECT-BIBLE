"""The default, zero-budget speech-to-text connector (docs/design/phase-2d/
01-communication-engine.md §0.3; Bible Part 7 "Initial Zero Budget Strategy",
applied to the new speech modality the same way `OllamaConnector` already applies
it to text). Talks to a local Whisper-class server (`faster-whisper-server`,
`whisper.cpp`'s server mode, or equivalent) over its OpenAI-audio-API-compatible
`POST /v1/audio/transcriptions` endpoint -- the same "lazily imported `httpx`,
never required just to import this module" convention as `OllamaConnector`.

Text-to-speech is `PiperConnector`'s job, not this connector's -- `transcribe`
only, mirroring how `OllamaConnector` implements `generate`/`stream`/`embed`
but never `transcribe`/`synthesize`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nova_ai_model_orchestration_engine.domain.models import (
    ConnectorHealth,
    FaceEmbedRequest,
    FaceEmbedResult,
    GazeEstimateRequest,
    GazeEstimateResult,
    GenerateRequest,
    GenerateResult,
    SynthesizeRequest,
    SynthesizeResult,
    TranscribeRequest,
    TranscribeResult,
    VoiceEmbedRequest,
    VoiceEmbedResult,
    WakePhraseRequest,
    WakePhraseResult,
)
from nova_ai_model_orchestration_engine.domain.ports import NotSupportedError

if TYPE_CHECKING:
    import httpx

__all__ = ["WhisperConnector"]


class WhisperConnector:
    connector_type = "whisper"

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8082",
        model: str = "whisper",
        timeout_s: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """`client` is an injection point for tests, same as every other
        connector -- production code always leaves it `None` and lets
        `_ensure_client` build a real one lazily."""
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._client = client

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout_s)
        return self._client

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        raise NotSupportedError(self.connector_type, "text_generation")

    def stream(self, request: GenerateRequest) -> Any:
        raise NotSupportedError(self.connector_type, "streaming")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotSupportedError(self.connector_type, "embedding")

    async def transcribe(self, request: TranscribeRequest) -> TranscribeResult:
        client = self._ensure_client()
        files = {"file": ("audio." + request.audio_format, request.audio_bytes)}
        data: dict[str, str] = {"model": self._model}
        if request.language_hint:
            data["language"] = request.language_hint
        response = await client.post("/v1/audio/transcriptions", files=files, data=data)
        response.raise_for_status()
        body = response.json()
        return TranscribeResult(
            text=body.get("text", ""),
            detected_language=body.get("language") or request.language_hint,
            structural_confidence=1.0 if body.get("text") else 0.0,
        )

    async def synthesize(self, request: SynthesizeRequest) -> SynthesizeResult:
        raise NotSupportedError(self.connector_type, "text_to_speech")

    def synthesize_stream(self, request: SynthesizeRequest) -> Any:
        raise NotSupportedError(self.connector_type, "text_to_speech")

    async def detect_wake_phrase(self, request: WakePhraseRequest) -> WakePhraseResult:
        raise NotSupportedError(self.connector_type, "wake_phrase_detection")

    async def embed_voice(self, request: VoiceEmbedRequest) -> VoiceEmbedResult:
        raise NotSupportedError(self.connector_type, "voice_embedding")

    async def embed_face(self, request: FaceEmbedRequest) -> FaceEmbedResult:
        raise NotSupportedError(self.connector_type, "face_embedding")

    async def estimate_gaze(self, request: GazeEstimateRequest) -> GazeEstimateResult:
        raise NotSupportedError(self.connector_type, "gaze_estimation")

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
