"""The default, zero-budget face-embedding connector (docs/design/phase-2d/
03-perception-engine.md §0.2). Talks to a local ArcFace-class face-embedding
server over a small custom `POST /v1/image/embed` endpoint -- the same
"lazily imported `httpx`, never required just to import this module"
convention as every other connector.

Every other modality raises `NotSupportedError` -- face embedding only.
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

__all__ = ["FaceEmbeddingConnector"]


class FaceEmbeddingConnector:
    connector_type = "face_embedding"

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8086",
        timeout_s: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
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
        raise NotSupportedError(self.connector_type, "speech_to_text")

    async def synthesize(self, request: SynthesizeRequest) -> SynthesizeResult:
        raise NotSupportedError(self.connector_type, "text_to_speech")

    def synthesize_stream(self, request: SynthesizeRequest) -> Any:
        raise NotSupportedError(self.connector_type, "text_to_speech")

    async def detect_wake_phrase(self, request: WakePhraseRequest) -> WakePhraseResult:
        raise NotSupportedError(self.connector_type, "wake_phrase_detection")

    async def embed_voice(self, request: VoiceEmbedRequest) -> VoiceEmbedResult:
        raise NotSupportedError(self.connector_type, "voice_embedding")

    async def embed_face(self, request: FaceEmbedRequest) -> FaceEmbedResult:
        client = self._ensure_client()
        files = {"file": ("image." + request.image_format, request.image_bytes)}
        response = await client.post("/v1/image/embed", files=files)
        response.raise_for_status()
        body = response.json()
        embedding = body.get("embedding", [])
        return FaceEmbedResult(embedding=embedding, structural_confidence=1.0 if embedding else 0.0)

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
