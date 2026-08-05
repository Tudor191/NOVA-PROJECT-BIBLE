"""`FakeModelRegistryRepository` -- an in-memory `domain.ports.
ModelRegistryRepository`."""

from __future__ import annotations

from uuid import UUID

from nova_ai_model_orchestration_engine.domain.models import ConnectorHealth, ModelDescriptor
from nova_ai_model_orchestration_engine.domain.ports import OutboxEvent


class FakeModelRegistryRepository:
    def __init__(self) -> None:
        self.models: dict[UUID, ModelDescriptor] = {}
        self.outbox: list[OutboxEvent] = []
        self.health_snapshots: list[tuple[UUID, str, ConnectorHealth]] = []

    async def register(
        self, model: ModelDescriptor, *, outbox_event: OutboxEvent | None = None
    ) -> ModelDescriptor:
        self.models[model.id] = model
        if outbox_event is not None:
            self.outbox.append(outbox_event)
        return model

    async def get(self, model_id: UUID) -> ModelDescriptor | None:
        return self.models.get(model_id)

    async def list_all(
        self,
        *,
        provider: str | None = None,
        modality: str | None = None,
        health_status: str | None = None,
    ) -> list[ModelDescriptor]:
        results = list(self.models.values())
        if provider is not None:
            results = [m for m in results if m.provider == provider]
        if modality is not None:
            results = [m for m in results if modality in m.modalities]
        if health_status is not None:
            results = [m for m in results if m.health_status == health_status]
        return results

    async def deregister(
        self, model_id: UUID, *, outbox_event: OutboxEvent | None = None
    ) -> None:
        self.models.pop(model_id, None)
        if outbox_event is not None:
            self.outbox.append(outbox_event)

    async def update_health(
        self,
        model_id: UUID,
        *,
        status: str,
        snapshot: ConnectorHealth,
        outbox_event: OutboxEvent | None = None,
    ) -> None:
        model = self.models.get(model_id)
        if model is not None:
            self.models[model_id] = model.model_copy(update={"health_status": status})
        self.health_snapshots.append((model_id, status, snapshot))
        if outbox_event is not None:
            self.outbox.append(outbox_event)

    async def update_benchmark(
        self, model_id: UUID, *, avg_latency_ms: float, avg_quality_score: float
    ) -> None:
        model = self.models.get(model_id)
        if model is not None:
            self.models[model_id] = model.model_copy(
                update={"avg_latency_ms": avg_latency_ms, "avg_quality_score": avg_quality_score}
            )
