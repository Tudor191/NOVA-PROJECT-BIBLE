from typing import Any
from uuid import UUID

from nova_ai_model_orchestration_engine.connectors.factory import ConnectorFactory
from nova_ai_model_orchestration_engine.domain.models import (
    CapabilityScores,
    ConnectorHealth,
    ModelDescriptor,
)
from nova_ai_model_orchestration_engine.domain.ports import OutboxEvent
from nova_ai_model_orchestration_engine.workers.health_monitor_worker import run_health_checks


def _model(**overrides: object) -> ModelDescriptor:
    defaults: dict[str, object] = {
        "name": "m",
        "version": "1.0",
        "provider": "fake",
        "connector_type": "fake",
        "is_local": True,
        "modalities": ["text_generation"],
        "capability_scores": CapabilityScores(scores={}),
        "context_window": 8192,
        "max_output_tokens": 2048,
        "health_status": "unknown",
    }
    defaults.update(overrides)
    return ModelDescriptor(**defaults)


class _FakeRegistryRepository:
    def __init__(self, models: list[ModelDescriptor]) -> None:
        self._models = {m.id: m for m in models}
        self.updates: list[tuple[UUID, str, OutboxEvent | None]] = []

    async def list_all(self, **kwargs: object) -> list[ModelDescriptor]:
        return list(self._models.values())

    async def update_health(
        self,
        model_id: UUID,
        *,
        status: str,
        snapshot: ConnectorHealth,
        outbox_event: OutboxEvent | None = None,
    ) -> None:
        self.updates.append((model_id, status, outbox_event))

    async def get(self, model_id: UUID) -> Any:
        raise NotImplementedError

    async def register(self, model: Any, **kwargs: object) -> Any:
        raise NotImplementedError

    async def deregister(self, model_id: UUID, **kwargs: object) -> None:
        raise NotImplementedError

    async def update_benchmark(self, model_id: UUID, **kwargs: object) -> None:
        raise NotImplementedError


async def test_health_check_publishes_event_on_status_change() -> None:
    model = _model(health_status="unknown")
    repository = _FakeRegistryRepository([model])
    factory = ConnectorFactory(ollama_base_url="unused", anthropic_api_key=None)

    checked = await run_health_checks(repository, factory)

    assert checked == 1
    model_id, status, outbox_event = repository.updates[0]
    assert status == "healthy"
    assert outbox_event is not None
    assert outbox_event.subject == "ai_model.model.health_changed"


async def test_health_check_does_not_publish_when_status_unchanged() -> None:
    model = _model(health_status="healthy")
    repository = _FakeRegistryRepository([model])
    factory = ConnectorFactory(ollama_base_url="unused", anthropic_api_key=None)

    await run_health_checks(repository, factory)

    _model_id, status, outbox_event = repository.updates[0]
    assert status == "healthy"
    assert outbox_event is None
