"""End-to-end tests through `api/usage.py` -- Part 7 "Retrieve Statistics"."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from nova_ai_model_orchestration_engine.config import Settings
from nova_ai_model_orchestration_engine.connectors.factory import ConnectorFactory
from nova_ai_model_orchestration_engine.domain.models import (
    PrivacyLevel,
    RoutingDecision,
    UsageRecord,
)
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
        yield client, usage_repo


def _usage_record(**overrides: object) -> UsageRecord:
    model_id = overrides.pop("model_id", uuid4())
    defaults: dict[str, object] = {
        "correlation_id": uuid4(),
        "requesting_engine": "test",
        "provider": "fake",
        "model_id": model_id,
        "routing_decision": RoutingDecision(
            candidates=[],
            selected_model_id=model_id,
            privacy_constraint_applied=False,
            estimated_complexity=0.1,
            explanation="test",
        ),
        "estimated_complexity": 0.1,
        "latency_ms": 10.0,
        "input_tokens": 5,
        "output_tokens": 5,
        "estimated_cost": 0.0,
        "retry_count": 0,
        "fallback_used": False,
        "privacy_classification": PrivacyLevel.INTERNAL,
        "outcome": "success",
    }
    defaults.update(overrides)
    return UsageRecord(**defaults)


async def test_list_usage_returns_recorded_entries(harness) -> None:  # type: ignore[no-untyped-def]
    client, usage_repo = harness
    await usage_repo.record_usage(_usage_record())
    await usage_repo.record_usage(_usage_record())

    response = client.get("/v1/usage")

    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_list_usage_filters_by_requesting_engine(harness) -> None:  # type: ignore[no-untyped-def]
    client, usage_repo = harness
    await usage_repo.record_usage(_usage_record(requesting_engine="reasoning-engine"))
    await usage_repo.record_usage(_usage_record(requesting_engine="other-engine"))

    response = client.get("/v1/usage", params={"requesting_engine": "reasoning-engine"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["requesting_engine"] == "reasoning-engine"


async def test_list_usage_filters_by_model_id(harness) -> None:  # type: ignore[no-untyped-def]
    client, usage_repo = harness
    target_model_id = uuid4()
    await usage_repo.record_usage(_usage_record(model_id=target_model_id))
    await usage_repo.record_usage(_usage_record())

    response = client.get("/v1/usage", params={"model_id": str(target_model_id)})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["model_id"] == str(target_model_id)
