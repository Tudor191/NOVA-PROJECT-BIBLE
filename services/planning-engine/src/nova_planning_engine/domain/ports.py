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

from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from nova_contracts import EventEnvelope, GenerateReplyPayload, GenerateRequestPayload
from pydantic import BaseModel

from nova_planning_engine.domain.models import TaskGraph, TaskNode, TaskNodeStatus

__all__ = [
    "EventPublisher",
    "ModelOrchestrationPort",
    "OutboxEvent",
    "OutboxRow",
    "PlanningRepository",
    "TaskGraphNotFoundError",
    "TaskNodeNotFoundError",
]


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


class OutboxEvent(BaseModel):
    """One row to insert into `planning.outbox_event` in the same
    transaction as the `task_graph`/`task_node` write it accompanies (TDD
    3B §4's "outbox_event table follows the standard transactional-outbox
    pattern") -- mirrors `memory-engine`'s own `OutboxEvent` field-for-field,
    the same "domain describes what to enqueue, the repository owns
    atomicity" split."""

    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None


class OutboxRow(BaseModel):
    """A persisted, not-yet-dispatched outbox row, as read back by
    `list_dispatch_ready` -- satisfies `nova_service_kit.outbox.OutboxRow`'s
    structural Protocol."""

    id: UUID
    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None
    created_at: datetime


@runtime_checkable
class PlanningRepository(Protocol):
    """Persistence port for the `planning` Postgres schema (TDD 3B §4):
    `task_graph`, `task_node`, `outbox_event`. Implemented by
    `repository/postgres_planning_repository.py` against SQLAlchemy async;
    never imported directly by `domain/`."""

    async def find_by_id(self, task_graph_id: UUID) -> TaskGraph | None: ...

    async def find_node(self, task_node_id: UUID) -> tuple[TaskGraph, TaskNode] | None:
        """Locates the `TaskGraph` containing `task_node_id` and that node
        itself -- the lookup `planning.decompose.request`'s handler needs
        (the request payload names only the node, per doc 12 §11's own
        "a Supervisor receiving a Task Graph node..." framing, not the
        graph). `None` if no persisted graph contains this node id."""
        ...

    async def insert(self, graph: TaskGraph, *, outbox_event: OutboxEvent) -> TaskGraph:
        """Inserts a new `task_graph` row and every one of its `task_node`
        rows, plus the accompanying outbox row, in one transaction --
        `reasoning.process.completed` -> `decompose()` always produces a
        brand-new graph (§4 of `docs/design/phase-3/14-3e-agent-os-research.md`'s
        own resolution note in `05-tdd-3b-planning-engine.md` never claims
        otherwise); this is the only insert path."""
        ...

    async def append_nodes(
        self,
        task_graph_id: UUID,
        new_nodes: list[TaskNode],
        *,
        outbox_event_builder: Callable[[TaskGraph], OutboxEvent],
    ) -> TaskGraph:
        """Appends `new_nodes` to an already-persisted graph's `nodes`,
        recomputes `critical_path`, then calls `outbox_event_builder` with
        the fully-updated `TaskGraph` (so the enqueued
        `planning.task_graph.created` payload reflects the post-mutation
        state, e.g. the recomputed `critical_path`) and writes the result
        -- all in one transaction. "Mutation, not regeneration" (TDD 3B
        §4), the `planning.decompose.request` path's own write.
        `task_graph_id` must already exist; raises `TaskGraphNotFoundError`
        otherwise. Returns the full, updated `TaskGraph`."""
        ...

    async def set_approved_at(self, task_graph_id: UUID, *, approved_at: datetime) -> TaskGraph:
        """§5: `POST /v1/plans/{id}/approve`. Raises `TaskGraphNotFoundError`
        if `task_graph_id` does not exist."""
        ...

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]: ...

    async def mark_dispatched(self, outbox_id: UUID) -> None: ...

    async def list_all(self, *, limit: int = 1000) -> list[TaskGraph]:
        """TDD 3E §8 -- every persisted `TaskGraph`, needed by
        `planning.goals.current.request`'s own handler to compute "a user's
        active `TaskGraph`s." **Disclosed gap, not silently invented**: the
        `task_graph` table (TDD 3B §4) carries no `user_id`/ownership column
        -- nothing upstream of this engine (`reasoning.process.completed`'s
        own `decompose()` call site) ever threads `ReasoningProcessCompletedPayload.user_id`
        through to a persisted field, unlike every other "current state for
        a user" port in this codebase (e.g. `WorldModelPort.list_history`,
        `MemoryPort.get`). Adding that column is a schema/migration change
        TDD 3E §8 itself never describes and is out of this slice's own
        authorized scope (GoalsPort migration only) -- so this method
        returns every graph, unfiltered, and the RPC handler that calls it
        (`events/goals_handler.py`) filters only by "active," never by
        `user_id`. Flagged for a follow-on slice, not silently worked
        around."""
        ...

    async def reset_node_status(
        self,
        task_node_id: UUID,
        *,
        status: TaskNodeStatus,
        outbox_event_builder: Callable[[TaskGraph], OutboxEvent],
    ) -> TaskGraph:
        """TDD 3E §4/§12, TDD 3B §6.1's own "`planning-engine` subscribes to
        mutate the corresponding `TaskNode.status`" -- the `agent_os.task.
        completed` consumer's own write. Mutates exactly one `TaskNode`'s
        `status` in place (never its other fields, never `critical_path` --
        a status change alone doesn't affect the graph's shape, unlike
        `append_nodes`'s own node-set change), then calls
        `outbox_event_builder` with the fully-updated `TaskGraph` and writes
        both in one transaction -- the identical "mutation, not
        regeneration" pattern `append_nodes` already establishes for the
        `planning.decompose.request` path (TDD 3B §4), applied to a status
        mutation instead of a node-set mutation. Raises
        `TaskNodeNotFoundError` if `task_node_id` does not exist in any
        persisted graph."""
        ...


class TaskGraphNotFoundError(Exception):
    """Raised by `PlanningRepository.append_nodes`/`set_approved_at` when
    `task_graph_id` does not exist -- the caller (the `planning.decompose.
    request` handler / `POST /v1/plans/{id}/approve`) translates this into
    a defined, non-500 failure response rather than a bare, unhandled
    `KeyError`-shaped surprise."""


class TaskNodeNotFoundError(Exception):
    """Raised by `PlanningRepository.reset_node_status` when `task_node_id`
    does not exist in any persisted graph -- a distinct condition/class
    from `TaskGraphNotFoundError` since the caller (`events/
    task_completed_handler.py`) already resolves node existence via
    `find_node` before ever calling `reset_node_status`, so this is a
    narrow, defensive raise for the rare read-then-write race, not the
    primary "unknown node" signal (that one is `find_node` returning
    `None`, handled as a defined no-op, never an exception)."""
