"""End-to-end tests through `api/synthesize.py` -- exercises `domain/router.py`'s
`synthesize_and_record` (non-streaming) and the HTTP/SSE-only `/synthesize/stream`
against a registered `connector_type="fake"` text-to-speech model
(docs/design/phase-2d/01-communication-engine.md §0.3)."""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient
from nova_ai_model_orchestration_engine.config import Settings
from nova_ai_model_orchestration_engine.connectors.factory import ConnectorFactory
from nova_ai_model_orchestration_engine.domain.models import CapabilityScores, ModelDescriptor
from nova_ai_model_orchestration_engine.main import create_app

from tests.fakes.registry_repository import FakeModelRegistryRepository
from tests.fakes.usage_repository import FakeUsageRepository


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    registry_repo = FakeModelRegistryRepository()
    usage_repo = FakeUsageRepository()
    app = create_app(
        Settings(),
        registry_repository=registry_repo,
        usage_repository=usage_repo,
        connector_factory=ConnectorFactory(ollama_base_url="unused", anthropic_api_key=None),
    )
    with TestClient(app) as client:
        yield client, registry_repo, usage_repo


def _register_tts_model(registry_repo) -> ModelDescriptor:  # type: ignore[no-untyped-def]
    model = ModelDescriptor(
        name="tts-model",
        version="1.0",
        provider="fake",
        connector_type="fake",
        is_local=True,
        modalities=["text_to_speech"],
        capability_scores=CapabilityScores(scores={"speech_synthesis_quality": 0.9}),
        context_window=0,
        max_output_tokens=0,
        health_status="healthy",
    )
    registry_repo.models[model.id] = model
    return model


def test_synthesize_returns_audio_and_records_usage(harness) -> None:  # type: ignore[no-untyped-def]
    client, registry_repo, usage_repo = harness
    model = _register_tts_model(registry_repo)

    response = client.post(
        "/v1/models/synthesize",
        json={"text": "Hello there.", "requesting_engine": "test"},
    )

    assert response.status_code == 200
    body = response.json()
    assert base64.b64decode(body["audio_bytes"]) == b"Hello there."
    assert body["model_id"]
    assert len(usage_repo.records) == 1
    _ = model


def test_synthesize_returns_503_when_no_eligible_model(harness) -> None:  # type: ignore[no-untyped-def]
    client, _registry_repo, _usage_repo = harness
    response = client.post(
        "/v1/models/synthesize", json={"text": "Hello.", "requesting_engine": "test"}
    )
    assert response.status_code == 503


def test_synthesize_stream_returns_sse_chunks(harness) -> None:  # type: ignore[no-untyped-def]
    client, registry_repo, usage_repo = harness
    _register_tts_model(registry_repo)

    with client.stream(
        "POST",
        "/v1/models/synthesize/stream",
        json={"text": "Hello there.", "requesting_engine": "test"},
    ) as response:
        assert response.status_code == 200
        body = b"".join(response.iter_bytes())

    assert b"data:" in body
    assert len(usage_repo.records) == 1
