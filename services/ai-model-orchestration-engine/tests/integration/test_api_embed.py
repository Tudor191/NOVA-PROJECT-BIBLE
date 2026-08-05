"""End-to-end tests through `api/embed.py` -- exercises `domain/router.py`'s
`embed_and_record` against a registered `connector_type="fake"` embedding
model."""

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


def test_embed_returns_embeddings_and_records_usage(harness) -> None:  # type: ignore[no-untyped-def]
    client, registry_repo, usage_repo = harness
    model = ModelDescriptor(
        name="embed-model",
        version="1.0",
        provider="fake",
        connector_type="fake",
        is_local=True,
        modalities=["embedding"],
        capability_scores=CapabilityScores(scores={}),
        context_window=2048,
        max_output_tokens=0,
        health_status="healthy",
    )
    registry_repo.models[model.id] = model

    response = client.post(
        "/v1/models/embed", json={"texts": ["hello", "world"], "requesting_engine": "test"}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["embeddings"]) == 2
    assert body["model_id"] == str(model.id)
    assert len(usage_repo.records) == 1


def test_embed_returns_503_when_no_eligible_model(harness) -> None:  # type: ignore[no-untyped-def]
    client, _registry_repo, _usage_repo = harness
    response = client.post(
        "/v1/models/embed", json={"texts": ["hello"], "requesting_engine": "test"}
    )
    assert response.status_code == 503
