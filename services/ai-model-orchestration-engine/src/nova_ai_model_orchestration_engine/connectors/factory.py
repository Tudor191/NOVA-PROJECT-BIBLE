"""Builds and caches a live `ModelConnector` for a given `ModelDescriptor`,
keyed by the registry's own `connector_type` field (design doc §1). Registry
rows are data -- which connector a model needs; this factory is what turns
that data into the runtime object that actually speaks to a provider.

Connectors are cached per `model.id`, not rebuilt per request -- `OllamaConnector`/
`AnthropicConnector` already defer real HTTP/SDK client construction to first use
via their own lazy `_ensure_client()`, so caching here only avoids re-creating
that lazy wrapper on every call, not opening a connection eagerly.
"""

from __future__ import annotations

from uuid import UUID

from nova_ai_model_orchestration_engine.connectors.anthropic_connector import AnthropicConnector
from nova_ai_model_orchestration_engine.connectors.face_embedding_connector import (
    FaceEmbeddingConnector,
)
from nova_ai_model_orchestration_engine.connectors.fake_connector import FakeConnector
from nova_ai_model_orchestration_engine.connectors.gaze_estimation_connector import (
    GazeEstimationConnector,
)
from nova_ai_model_orchestration_engine.connectors.ollama_connector import OllamaConnector
from nova_ai_model_orchestration_engine.connectors.piper_connector import PiperConnector
from nova_ai_model_orchestration_engine.connectors.voice_embedding_connector import (
    VoiceEmbeddingConnector,
)
from nova_ai_model_orchestration_engine.connectors.wake_word_connector import WakeWordConnector
from nova_ai_model_orchestration_engine.connectors.whisper_connector import WhisperConnector
from nova_ai_model_orchestration_engine.domain.models import ModelDescriptor
from nova_ai_model_orchestration_engine.domain.ports import ModelConnector

__all__ = ["ConnectorFactory", "ConnectorUnavailableError"]


class ConnectorUnavailableError(Exception):
    """Raised when a model's registered `connector_type` has no live,
    constructible implementation right now -- either the type is unrecognized,
    or (Anthropic) its required credential isn't configured (§18: an absent
    connector, not a surprise failure at first request)."""

    def __init__(self, connector_type: str, reason: str) -> None:
        super().__init__(f"{connector_type!r} connector unavailable: {reason}")
        self.connector_type = connector_type
        self.reason = reason


class ConnectorFactory:
    def __init__(
        self,
        *,
        ollama_base_url: str,
        anthropic_api_key: str | None,
        whisper_base_url: str = "http://localhost:8082",
        piper_base_url: str = "http://localhost:8083",
        wake_word_base_url: str = "http://localhost:8084",
        voice_embedding_base_url: str = "http://localhost:8085",
        face_embedding_base_url: str = "http://localhost:8086",
        gaze_estimation_base_url: str = "http://localhost:8087",
        timeout_s: float = 60.0,
    ) -> None:
        self._ollama_base_url = ollama_base_url
        self._anthropic_api_key = anthropic_api_key
        self._whisper_base_url = whisper_base_url
        self._piper_base_url = piper_base_url
        self._wake_word_base_url = wake_word_base_url
        self._voice_embedding_base_url = voice_embedding_base_url
        self._face_embedding_base_url = face_embedding_base_url
        self._gaze_estimation_base_url = gaze_estimation_base_url
        self._timeout_s = timeout_s
        self._cache: dict[UUID, ModelConnector] = {}

    def get_connector(self, model: ModelDescriptor) -> ModelConnector:
        cached = self._cache.get(model.id)
        if cached is not None:
            return cached
        connector = self._build(model)
        self._cache[model.id] = connector
        return connector

    def _build(self, model: ModelDescriptor) -> ModelConnector:
        if model.connector_type == "ollama":
            return OllamaConnector(
                base_url=self._ollama_base_url, model=model.name, timeout_s=self._timeout_s
            )
        if model.connector_type == "anthropic":
            if not self._anthropic_api_key:
                raise ConnectorUnavailableError(
                    model.connector_type, "ANTHROPIC_API_KEY is not configured"
                )
            return AnthropicConnector(
                api_key=self._anthropic_api_key, model=model.name, timeout_s=self._timeout_s
            )
        if model.connector_type == "whisper":
            return WhisperConnector(
                base_url=self._whisper_base_url, model=model.name, timeout_s=self._timeout_s
            )
        if model.connector_type == "piper":
            return PiperConnector(base_url=self._piper_base_url, timeout_s=self._timeout_s)
        if model.connector_type == "wake_word":
            return WakeWordConnector(base_url=self._wake_word_base_url, timeout_s=self._timeout_s)
        if model.connector_type == "voice_embedding":
            return VoiceEmbeddingConnector(
                base_url=self._voice_embedding_base_url, timeout_s=self._timeout_s
            )
        if model.connector_type == "face_embedding":
            return FaceEmbeddingConnector(
                base_url=self._face_embedding_base_url, timeout_s=self._timeout_s
            )
        if model.connector_type == "gaze_estimation":
            return GazeEstimationConnector(
                base_url=self._gaze_estimation_base_url, timeout_s=self._timeout_s
            )
        if model.connector_type == "fake":
            return FakeConnector()
        raise ConnectorUnavailableError(model.connector_type, "no implementation registered")
