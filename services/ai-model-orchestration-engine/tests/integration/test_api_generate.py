"""End-to-end tests through `api/generate.py` -- exercises `domain/router.py`'s
`execute_and_record` against `FakeModelRegistryRepository`/`FakeUsageRepository`
and a registered `connector_type="fake"` model (`ConnectorFactory` resolves
`"fake"` to `FakeConnector`, no real network/provider SDK involved).
"""

from __future__ import annotations

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


def _register(registry_repo: FakeModelRegistryRepository, **overrides: object) -> ModelDescriptor:
    defaults: dict[str, object] = {
        "name": "test-model",
        "version": "1.0",
        "provider": "fake",
        "connector_type": "fake",
        "is_local": True,
        "modalities": ["text_generation", "tool_calling"],
        "capability_scores": CapabilityScores(scores={"general_conversation": 0.8}),
        "context_window": 8192,
        "max_output_tokens": 2048,
        "health_status": "healthy",
    }
    defaults.update(overrides)
    model = ModelDescriptor(**defaults)
    registry_repo.models[model.id] = model
    return model


def test_generate_returns_result_and_records_usage(harness) -> None:  # type: ignore[no-untyped-def]
    client, registry_repo, usage_repo = harness
    _register(registry_repo)

    response = client.post(
        "/v1/models/generate",
        json={
            "context": [{"source": "user_request", "text": "hi", "token_estimate": 1}],
            "requesting_engine": "test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"]
    assert body["finish_reason"] == "stop"
    assert len(usage_repo.records) == 1
    assert usage_repo.records[0].outcome == "success"
    assert len(usage_repo.outbox) == 1


def test_generate_returns_503_when_no_eligible_model(harness) -> None:  # type: ignore[no-untyped-def]
    client, _registry_repo, _usage_repo = harness
    response = client.post(
        "/v1/models/generate",
        json={
            "context": [{"source": "user_request", "text": "hi", "token_estimate": 1}],
            "requesting_engine": "test",
        },
    )
    assert response.status_code == 503


def test_generate_stream_emits_chunks(harness) -> None:  # type: ignore[no-untyped-def]
    client, registry_repo, usage_repo = harness
    _register(registry_repo)

    with client.stream(
        "POST",
        "/v1/models/generate/stream",
        json={
            "context": [{"source": "user_request", "text": "hi", "token_estimate": 1}],
            "requesting_engine": "test",
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert "data:" in body
    assert len(usage_repo.records) == 1
    assert usage_repo.records[0].outcome == "success"
