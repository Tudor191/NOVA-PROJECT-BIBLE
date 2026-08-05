"""Protocols this package depends on -- implements nothing itself
(docs/design/phase-2b/00-reasoning-engine.md §1, §7). `domain/` may only import
this module, `domain/models.py`, and other `domain/` modules -- never FastAPI,
SQLAlchemy, `nova_eventbus_sdk`, or (per ADR-020) any LLM/AI provider SDK
directly.

Six upstream ports (§7) plus `ModelOrchestrationPort` (ADR-020's sole legal
channel to any model) are satisfied by exactly one adapter each in `clients/`
-- the identical Dependency-Inversion shape every prior engine's `domain/
ports.py` already established, renamed `clients/` rather than `connectors/`
because every upstream dependency here is reached over the Event Bus (ADR-004),
never a provider SDK (design doc §1).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from nova_contracts import EventEnvelope, GenerateReplyPayload, GenerateRequestPayload
from pydantic import BaseModel

from nova_reasoning_engine.domain.models import (
    Alternative,
    Decision,
    Evidence,
    Goal,
    HumanOverrideRequest,
    Hypothesis,
    KnowledgeReference,
    LifecycleStatus,
    MemoryReference,
    PersonalContext,
    ReasoningProcess,
    ReasoningTrace,
    WorldModelSnapshot,
)

__all__ = [
    "EventPublisher",
    "GoalsPort",
    "KnowledgePort",
    "MemoryPort",
    "ModelOrchestrationPort",
    "OutboxEvent",
    "OutboxRow",
    "PersonalContextPort",
    "ReasoningRepository",
    "WorldModelPort",
]


@runtime_checkable
class MemoryPort(Protocol):
    """§7.3 -- the "Load memories" pipeline step (§4). Implemented by
    `clients/memory_client.py`, calling `memory.retrieve.request`.
    `correlation_id` ties the call back to the parent `ReasoningProcess`, the
    same cross-service tracing convention `domain/relationship.py` already
    established for Memory Engine's own outbound calls to Knowledge Engine."""

    async def retrieve(
        self, *, user_id: UUID, query: str, limit: int = 10, correlation_id: UUID | None = None
    ) -> list[MemoryReference]: ...


@runtime_checkable
class KnowledgePort(Protocol):
    """§7.4 -- the "Retrieve knowledge" pipeline step (§4), also used during
    Hypothesis Verification (§13). Implemented by `clients/knowledge_client.py`,
    calling `knowledge.retrieve.request` / `knowledge.traverse.request`."""

    async def retrieve(
        self, *, query: str, limit: int = 10, correlation_id: UUID | None = None
    ) -> list[KnowledgeReference]: ...

    async def traverse(
        self, *, seed_node_id: str, depth: int = 2, correlation_id: UUID | None = None
    ) -> list[KnowledgeReference]: ...


@runtime_checkable
class WorldModelPort(Protocol):
    """§7.2 -- the "Load World Model" pipeline step (§4). Implemented by
    `clients/world_model_client.py`, calling `world_model.context.request`. A
    `None` result is not an error -- the pipeline proceeds with reduced
    confidence (§10) rather than failing."""

    async def get_context(
        self, *, user_id: UUID, scope: str | None = None, correlation_id: UUID | None = None
    ) -> WorldModelSnapshot | None: ...


@runtime_checkable
class PersonalContextPort(Protocol):
    """§7.5 -- Phase 2B's honest placeholder for Bible Part 16's future Digital
    Twin Engine. Implemented by `clients/personal_context_client.py`, a thin
    wrapper around `WorldModelPort.get_context`."""

    async def get_personal_context(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> PersonalContext | None: ...


@runtime_checkable
class GoalsPort(Protocol):
    """§7.1 -- Current Goals, used by Goal Evaluation (§8). Phase 2B's honest
    placeholder: `clients/goals_client.py` returns the caller-supplied
    `ReasoningRequest.goals` rather than a real Planning Engine RPC, since
    Planning Engine (Phase 3) does not exist yet."""

    async def current_goals(
        self, *, user_id: UUID, scope: str | None = None, correlation_id: UUID | None = None
    ) -> list[Goal]: ...


@runtime_checkable
class ModelOrchestrationPort(Protocol):
    """ADR-020's sole legal channel to any model -- a thin Protocol wrapping
    `ai_model.generate.request`, used only by Hypothesis Generation (§12), the
    one pipeline step that legitimately calls a model. Every other scoring
    mechanism in this engine (§8, §9, §10, §15, §16) is deliberately structural,
    never a model call."""

    async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload: ...


class OutboxEvent(BaseModel):
    """One row to insert into `reasoning.outbox_event` in the same transaction
    as the write it accompanies -- the identical transactional outbox pattern
    as the AI Model Orchestration Engine's own (§20): no `graph_write` column,
    since this engine owns no graph."""

    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None


class OutboxRow(BaseModel):
    """A persisted, not-yet-dispatched outbox row, as read back by
    `list_dispatch_ready` -- carries its own `id`, reused as `EventEnvelope.
    event_id` for exactly-once delivery, the same convention as every prior
    engine's outbox dispatcher."""

    id: UUID
    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None
    created_at: datetime


@runtime_checkable
class ReasoningRepository(Protocol):
    """Persistence port for the `reasoning` schema (§20) -- `reasoning_process`,
    `hypothesis`, `evidence`, `alternative`, `decision`, `reasoning_trace`, and
    the transactional outbox. The one narrow exception to "never owns data"
    (§0): every row here describes a reasoning process this engine itself ran,
    never a copy of another engine's owned data."""

    async def create_process(self, process: ReasoningProcess) -> ReasoningProcess: ...

    async def transition_process(
        self,
        process_id: UUID,
        *,
        status: LifecycleStatus,
        completed_at: datetime | None = None,
    ) -> None: ...

    async def get_process(self, process_id: UUID) -> ReasoningProcess | None: ...

    async def record_hypotheses(self, hypotheses: list[Hypothesis]) -> None: ...

    async def update_hypothesis_status(
        self, hypothesis_id: UUID, *, status: Literal["investigating", "supported", "unsupported"]
    ) -> None: ...

    async def record_evidence(self, evidence: list[Evidence]) -> None: ...

    async def record_alternatives(self, alternatives: list[Alternative]) -> None: ...

    async def finalize(
        self,
        *,
        process: ReasoningProcess,
        decision: Decision,
        trace: ReasoningTrace,
        outbox_event: OutboxEvent | None = None,
    ) -> Decision:
        """One transaction: persists the terminal `Decision` and its
        `ReasoningTrace`, transitions the process to its terminal status, and
        enqueues the accompanying outbox event -- mirroring `record_usage`'s
        single-transaction shape in the AI Model Orchestration Engine."""
        ...

    async def get_decision(self, decision_id: UUID) -> Decision | None: ...

    async def get_decision_for_process(self, reasoning_process_id: UUID) -> Decision | None: ...

    async def get_trace(self, trace_id: UUID) -> ReasoningTrace | None: ...

    async def get_trace_for_process(self, reasoning_process_id: UUID) -> ReasoningTrace | None: ...

    async def list_traces(
        self, *, user_id: UUID | None = None, limit: int = 100
    ) -> list[ReasoningTrace]: ...

    async def apply_override(
        self,
        decision_id: UUID,
        override: HumanOverrideRequest,
        *,
        outbox_event: OutboxEvent | None = None,
    ) -> Decision: ...

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID: ...

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]: ...

    async def mark_dispatched(self, outbox_id: UUID) -> None: ...


@runtime_checkable
class EventPublisher(Protocol):
    """Declared for symmetry with every other engine's `domain/ports.py`.
    Unused by `domain/` itself -- every outbound RPC this engine makes is
    reached through one of the six typed ports above; `EventPublisher` exists
    only in case a future domain module needs a generic request/reply call this
    design doesn't yet anticipate."""

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope: ...
