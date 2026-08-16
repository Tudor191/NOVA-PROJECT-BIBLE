"""Protocols this package depends on -- implements nothing itself
(docs/design/phase-3/05-tdd-3b-planning-engine.md §3, ADR-020). `domain/`
may only import this module, `domain/models.py`, and other `domain/`
modules -- never FastAPI, SQLAlchemy, `nova_eventbus_sdk`, or (per
ADR-020) any LLM/AI provider SDK directly.

`ModelOrchestrationPort` is ADR-020's sole legal channel to any model,
satisfied by exactly one adapter in `clients/model_orchestration_client.py`
-- the identical Dependency-Inversion shape `reasoning-engine`'s own
`domain/ports.py` already established for the same port (the direction
research doc `docs/design/phase-3/11-3b-decomposition-architecture-research.md`
§6/§13 recommended and this engine's Gate Review confirms was followed).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from nova_contracts import EventEnvelope, GenerateReplyPayload, GenerateRequestPayload
from pydantic import BaseModel

__all__ = ["EventPublisher", "ModelOrchestrationPort"]


@runtime_checkable
class ModelOrchestrationPort(Protocol):
    """ADR-020's sole legal channel to any model -- a thin Protocol wrapping
    `ai_model.generate.request`, used only by `domain/decomposition.py`, the
    one domain module in this engine that legitimately calls a model."""

    async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload: ...


@runtime_checkable
class EventPublisher(Protocol):
    """The subset of `BoundEventBus` `clients/model_orchestration_client.py`
    needs -- declared here, not imported from `nova_eventbus_sdk`, so
    `domain/` never depends on the event-bus package directly (module
    docstring's own boundary rule). Matches `BoundEventBus.request()`'s
    signature exactly."""

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope: ...
