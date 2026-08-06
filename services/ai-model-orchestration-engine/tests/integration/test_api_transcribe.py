"""End-to-end tests through `api/transcribe.py` -- exercises `domain/router.py`'s
`transcribe_and_record` against a registered `connector_type="fake"`
speech-to-text model (docs/design/phase-2d/01-communication-engine.md §0.3)."""

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


def test_transcribe_returns_text_and_records_usage(harness) -> None:  # type: ignore[no-untyped-def]
    client, registry_repo, usage_repo = harness
    model = ModelDescriptor(
        name="stt-model",
        version="1.0",
        provider="fake",
        connector_type="fake",
        is_local=True,
        modalities=["speech_to_text"],
        capability_scores=CapabilityScores(scores={"speech_recognition_accuracy": 0.9}),
        context_window=0,
        max_output_tokens=0,
        health_status="healthy",
    )
    registry_repo.models[model.id] = model

    audio_b64 = base64.b64encode(b"fake-wav-bytes").decode("ascii")
    response = client.post(
        "/v1/models/transcribe",
        json={"audio_bytes": audio_b64, "requesting_engine": "test"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"]
    assert len(usage_repo.records) == 1


def test_transcribe_returns_503_when_no_eligible_model(harness) -> None:  # type: ignore[no-untyped-def]
    client, _registry_repo, _usage_repo = harness
    audio_b64 = base64.b64encode(b"fake-wav-bytes").decode("ascii")
    response = client.post(
        "/v1/models/transcribe",
        json={"audio_bytes": audio_b64, "requesting_engine": "test"},
    )
    assert response.status_code == 503
