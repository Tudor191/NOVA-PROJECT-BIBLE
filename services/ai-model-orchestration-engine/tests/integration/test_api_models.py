"""End-to-end tests through `api/models.py` -- registry CRUD, dry-run select,
and the out-of-cycle benchmark trigger."""

from __future__ import annotations

from uuid import uuid4

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


_REGISTER_BODY = {
    "name": "test-model",
    "version": "1.0",
    "provider": "fake",
    "connector_type": "fake",
    "is_local": True,
    "modalities": ["text_generation"],
    "capability_scores": {"general_conversation": 0.7},
    "context_window": 8192,
    "max_output_tokens": 2048,
}


def test_register_then_list_then_get(harness) -> None:  # type: ignore[no-untyped-def]
    client, registry_repo, _usage_repo = harness

    created = client.post("/v1/models", json=_REGISTER_BODY)
    assert created.status_code == 201
    model_id = created.json()["id"]
    assert len(registry_repo.outbox) == 1
    assert registry_repo.outbox[0].subject == "ai_model.model.registered"

    listed = client.get("/v1/models")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = client.get(f"/v1/models/{model_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "test-model"


def test_get_missing_model_returns_404(harness) -> None:  # type: ignore[no-untyped-def]
    client, _registry_repo, _usage_repo = harness
    response = client.get(f"/v1/models/{uuid4()}")
    assert response.status_code == 404


def test_deregister_removes_from_list(harness) -> None:  # type: ignore[no-untyped-def]
    client, registry_repo, _usage_repo = harness
    created = client.post("/v1/models", json=_REGISTER_BODY)
    model_id = created.json()["id"]

    deleted = client.delete(f"/v1/models/{model_id}")
    assert deleted.status_code == 204
    assert model_id not in {str(k) for k in registry_repo.models}

    listed = client.get("/v1/models")
    assert listed.json() == []


def test_select_dry_run_returns_routing_decision(harness) -> None:  # type: ignore[no-untyped-def]
    client, registry_repo, _usage_repo = harness
    model = ModelDescriptor(
        name="strong",
        version="1.0",
        provider="fake",
        connector_type="fake",
        is_local=True,
        modalities=["text_generation"],
        capability_scores=CapabilityScores(scores={"general_conversation": 0.9}),
        context_window=8192,
        max_output_tokens=2048,
        health_status="healthy",
    )
    registry_repo.models[model.id] = model

    response = client.get("/v1/models/select", params={"task_type": "general_conversation"})

    assert response.status_code == 200
    assert response.json()["selected_model_id"] == str(model.id)


def test_select_dry_run_404_when_nothing_eligible(harness) -> None:  # type: ignore[no-untyped-def]
    client, _registry_repo, _usage_repo = harness
    response = client.get("/v1/models/select")
    assert response.status_code == 404


def test_benchmark_trigger_updates_registry(harness) -> None:  # type: ignore[no-untyped-def]
    client, registry_repo, _usage_repo = harness
    model = ModelDescriptor(
        name="bench-me",
        version="1.0",
        provider="fake",
        connector_type="fake",
        is_local=True,
        modalities=["text_generation"],
        capability_scores=CapabilityScores(scores={}),
        context_window=8192,
        max_output_tokens=2048,
        health_status="healthy",
    )
    registry_repo.models[model.id] = model

    response = client.post(f"/v1/models/{model.id}/benchmark")

    assert response.status_code == 200
    body = response.json()
    assert body["success_rate"] == 1.0
    assert registry_repo.models[model.id].avg_latency_ms is not None
