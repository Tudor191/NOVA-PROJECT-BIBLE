"""Protocols this package depends on -- implements nothing itself
(docs/design/phase-2a/00-ai-model-orchestration-engine.md §1). `domain/` may only
import this module, `domain/models.py`, and other `domain/` modules -- never
FastAPI, SQLAlchemy, or (per ADR-020) any LLM/AI provider SDK directly.

`ModelConnector` is defined here, not promoted to a shared package the way
`GraphStore`/`VectorStore`/`EmbeddingProvider` were (ADR-006/007/009) -- per
ADR-020, this engine is the only legitimate consumer, so there is no
cross-engine sharing need to justify a separate package (design doc §1).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from nova_contracts import EventEnvelope
from pydantic import BaseModel

from nova_ai_model_orchestration_engine.domain.models import (
    Budget,
    ConnectorHealth,
    GenerateRequest,
    GenerateResult,
    ModelDescriptor,
    UsageRecord,
)

__all__ = [
    "EventPublisher",
    "ModelConnector",
    "ModelRegistryRepository",
    "NotSupportedError",
    "OutboxEvent",
    "OutboxRow",
    "UsageRepository",
]


class NotSupportedError(Exception):
    """Raised by a `ModelConnector` when asked for a modality it doesn't
    implement (e.g. `embed()` on a text-only connector) -- never an unhandled,
    connector-specific exception (ADR-023: identical, catchable behavior across
    every connector)."""

    def __init__(self, connector_type: str, modality: str) -> None:
        super().__init__(f"{connector_type} does not support {modality!r}.")
        self.connector_type = connector_type
        self.modality = modality


@runtime_checkable
class ModelConnector(Protocol):
    """One provider's implementation of every modality this engine can route to
    (design doc §5). Every method must raise `NotSupportedError` -- never a
    provider-SDK-specific exception -- for a modality the connector doesn't
    implement; verified identically for every connector by the ADR-023 compliance
    suite, not assumed from the type signature alone."""

    connector_type: str

    async def generate(self, request: GenerateRequest) -> GenerateResult: ...

    def stream(self, request: GenerateRequest) -> Any:
        """Returns an `AsyncIterator[GenerateChunk]`. Typed `Any` here (not
        `AsyncIterator[GenerateChunk]` directly) because `Protocol` methods
        returning async generators need the implementation to be an `async def`
        with `yield`, which mypy's Protocol checking handles more reliably via a
        loosely-typed signature than a strictly-typed async generator return --
        every real implementation's docstring states the true return type."""
        ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def health(self) -> ConnectorHealth: ...


class OutboxEvent(BaseModel):
    """One row to insert into `model_orchestration.outbox_event` in the same
    transaction as the usage-record write it accompanies (the same transactional
    outbox pattern as Memory Engine's, per design doc §4 -- no `graph_write`
    column, since this engine owns no graph)."""

    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None


class OutboxRow(BaseModel):
    """A persisted, not-yet-dispatched outbox row, as read back by
    `list_dispatch_ready` -- carries its own `id` (reused as `EventEnvelope.
    event_id` for exactly-once delivery, the same convention as every Phase 1
    engine's outbox dispatcher) alongside `OutboxEvent`'s fields."""

    id: UUID
    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None
    created_at: datetime


@runtime_checkable
class ModelRegistryRepository(Protocol):
    """Persistence port for `model_registry` and `model_health_snapshot`
    (design doc §4)."""

    async def register(
        self, model: ModelDescriptor, *, outbox_event: OutboxEvent | None = None
    ) -> ModelDescriptor: ...

    async def get(self, model_id: UUID) -> ModelDescriptor | None: ...

    async def list_all(
        self,
        *,
        provider: str | None = None,
        modality: str | None = None,
        health_status: str | None = None,
    ) -> list[ModelDescriptor]: ...

    async def deregister(
        self, model_id: UUID, *, outbox_event: OutboxEvent | None = None
    ) -> None: ...

    async def update_health(
        self, model_id: UUID, *, status: str, snapshot: ConnectorHealth
    ) -> None: ...

    async def update_benchmark(
        self, model_id: UUID, *, avg_latency_ms: float, avg_quality_score: float
    ) -> None: ...


@runtime_checkable
class UsageRepository(Protocol):
    """Persistence port for `usage_record`, `budget`, and the transactional
    outbox (design doc §4)."""

    async def record_usage(
        self, record: UsageRecord, *, outbox_event: OutboxEvent | None = None
    ) -> UsageRecord: ...

    async def list_usage(
        self,
        *,
        model_id: UUID | None = None,
        requesting_engine: str | None = None,
        correlation_id: UUID | None = None,
        limit: int = 100,
    ) -> list[UsageRecord]: ...

    async def spend_this_period(self, *, scope: str, scope_ref: str | None) -> float: ...

    async def get_budget(self, *, scope: str, scope_ref: str | None) -> Budget | None: ...

    async def list_budgets(self) -> list[Budget]: ...

    async def upsert_budget(self, budget: Budget) -> Budget: ...

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID: ...

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]: ...

    async def mark_dispatched(self, outbox_id: UUID) -> None: ...


@runtime_checkable
class EventPublisher(Protocol):
    """Declared for symmetry with every other engine's `domain/ports.py`; unused
    in Phase 2A (this engine has no outbound RPC calls to make -- ADR-022, it
    depends on nothing external at request time)."""

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope: ...
