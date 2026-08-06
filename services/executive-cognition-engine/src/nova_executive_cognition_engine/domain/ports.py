"""Protocols this package depends on -- implements nothing itself
(docs/design/phase-2c/00-executive-cognition-engine.md §1, §5). `domain/` may
only import this module, `domain/models.py`, and other `domain/` modules --
never FastAPI, SQLAlchemy, `nova_eventbus_sdk`, or (per ADR-020) any LLM/AI
provider SDK directly. Unlike Reasoning Engine, this engine defines no
`ModelOrchestrationPort` at all -- it has no occasion to generate content
(§0.2), so no such channel exists to abstract.

Four ports are defined, each reusing an upstream port's shape Reasoning
Engine already established (§5.3, §5.5-§5.7) -- structurally identical,
independently implemented, per ADR-004 (services never import each other's
internals). `KnowledgePort` and a `CapabilityPort` are deliberately absent
this phase (§5.4, §5.8) -- named, honest scope decisions, not oversights.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from nova_contracts import EventEnvelope
from pydantic import BaseModel

from nova_executive_cognition_engine.domain.models import (
    ExecutiveDecisionTrace,
    ExecutiveRequest,
    Goal,
    HumanOverrideRequest,
    MemoryReference,
    PersonalContext,
    WorldModelSnapshot,
)

__all__ = [
    "EventPublisher",
    "ExecutiveRepository",
    "GoalsPort",
    "MemoryPort",
    "OutboxEvent",
    "OutboxRow",
    "PersonalContextPort",
    "WorldModelPort",
]


@runtime_checkable
class MemoryPort(Protocol):
    """§5.3 -- used narrowly for historical-outcome lookups (§7.3), never
    general recall. Implemented by `clients/memory_client.py`, calling
    `memory.retrieve.request`."""

    async def retrieve(
        self, *, user_id: UUID, query: str, limit: int = 10, correlation_id: UUID | None = None
    ) -> list[MemoryReference]: ...


@runtime_checkable
class WorldModelPort(Protocol):
    """§5.5 -- situational grounding during arbitration. Implemented by
    `clients/world_model_client.py`, calling `world_model.context.request`.
    A `None` result is not an error -- arbitration proceeds without
    situational grounding rather than failing."""

    async def get_context(
        self, *, user_id: UUID, scope: str | None = None, correlation_id: UUID | None = None
    ) -> WorldModelSnapshot | None: ...


@runtime_checkable
class PersonalContextPort(Protocol):
    """§5.6 -- Personal Context has no dedicated engine yet, the identical
    placeholder Reasoning Engine already established. Implemented by
    `clients/personal_context_client.py`, a thin wrapper around
    `WorldModelPort.get_context`."""

    async def get_personal_context(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> PersonalContext | None: ...


@runtime_checkable
class GoalsPort(Protocol):
    """§5.7, §8 -- Current Goals. The identical honest placeholder ADR-026
    established for Reasoning Engine: `clients/goals_client.py` returns
    caller-supplied goals rather than a real Planning Engine RPC, since
    Planning Engine (Phase 3) does not exist yet."""

    async def current_goals(
        self, *, user_id: UUID, scope: str | None = None, correlation_id: UUID | None = None
    ) -> list[Goal]: ...


class OutboxEvent(BaseModel):
    """One row to insert into `executive.outbox_event` in the same
    transaction as the write it accompanies -- the identical transactional
    outbox pattern every prior engine's own repository already uses: no
    `graph_write` column, since this engine owns no graph."""

    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None


class OutboxRow(BaseModel):
    """A persisted, not-yet-dispatched outbox row, as read back by
    `list_dispatch_ready` -- carries its own `id`, reused as
    `EventEnvelope.event_id` for exactly-once delivery, the same convention
    as every prior engine's outbox dispatcher."""

    id: UUID
    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None
    created_at: datetime


@runtime_checkable
class ExecutiveRepository(Protocol):
    """Persistence port for the `executive` schema (§19) --
    `executive_request`, `executive_decision`, `executive_outcome_report`,
    `human_override`, and the transactional outbox. The one narrow exception
    to "never owns data" (§0.1): every row here describes an arbitration
    decision this engine itself made, never a copy of another engine's
    owned data."""

    async def record_request(self, request: ExecutiveRequest) -> None: ...

    async def requests_for_goal(
        self, goal_id: UUID, *, exclude_correlation_id: UUID | None = None, limit: int = 20
    ) -> list[ExecutiveRequest]:
        """§8 -- other recent requests sharing `goal_id`, used to compute the
        goal-correlation priority boost and `long_term_alignment` (§6.1)."""
        ...

    async def finalize_decision(
        self,
        *,
        trace: ExecutiveDecisionTrace,
        outbox_event: OutboxEvent | None = None,
    ) -> ExecutiveDecisionTrace:
        """One transaction: persists the terminal `ExecutiveDecisionTrace`
        and enqueues the accompanying outbox event -- mirroring
        `ReasoningRepository.finalize`'s single-transaction shape."""
        ...

    async def get_decision(self, decision_id: UUID) -> ExecutiveDecisionTrace | None: ...

    async def list_decisions(
        self, *, requesting_engine: str | None = None, limit: int = 100
    ) -> list[ExecutiveDecisionTrace]: ...

    async def record_outcome_report(
        self,
        *,
        correlation_id: UUID,
        outcome: str,
        actual_duration_ms: float | None,
        note: str | None,
    ) -> None: ...

    async def apply_override(
        self,
        decision_id: UUID,
        override: HumanOverrideRequest,
        *,
        outbox_event: OutboxEvent | None = None,
    ) -> ExecutiveDecisionTrace: ...

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID: ...

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]: ...

    async def mark_dispatched(self, outbox_id: UUID) -> None: ...


@runtime_checkable
class EventPublisher(Protocol):
    """Declared for symmetry with every other engine's `domain/ports.py`.
    Unused by `domain/` itself -- every outbound RPC this engine makes is
    reached through one of the three typed ports above; `EventPublisher`
    exists only in case a future domain module needs a generic
    request/reply call this design doesn't yet anticipate."""

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope: ...
