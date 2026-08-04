"""Protocols this package depends on -- implements nothing itself
(docs/design/phase-1/03-world-model-engine.md §1). `domain/` may only import this
module, `domain/models.py`, and other `domain/` modules -- never FastAPI,
SQLAlchemy, Redis/Neo4j clients, or the Event Bus SDK directly
(docs/architecture/03-backend-architecture.md §1).

`GraphStore` is a re-export of the shared SDK Protocol (`nova-graphstore-sdk`)
rather than reinvented here. Deliberately **no** `VectorIndex`/`EmbeddingProvider`
port -- §10: "World Model Engine does not generate embeddings." Its data is
either current-state (Redis, direct key access) or graph-shaped (traversal), and
adding a vector search capability here would blur the boundary with Knowledge
Engine (the engine that already owns semantic search over validated concepts).

`GraphWriteIntent`/`GraphWriteOp`/`OutboxEvent`/`OutboxRow` intentionally
duplicate Knowledge Engine's shapes rather than importing them -- ADR-004 forbids
one engine importing another's internals, and these types are the "how does a
Postgres-then-Neo4j saga describe a pending write" answer both engines happen to
share the same solution to, not a shared library concern (each could evolve
independently, e.g. if World Model's graph writes ever needed a shape Knowledge's
don't).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from nova_contracts import EventEnvelope
from nova_graphstore_sdk import GraphStore
from pydantic import BaseModel, Field

from nova_world_model_engine.domain.models import (
    ActiveContext,
    AttentionEntry,
    ConflictLogEntry,
    ObjectStateHistoryEntry,
    Prediction,
    Snapshot,
)

__all__ = [
    "ContextRepository",
    "EventPublisher",
    "GraphStore",
    "GraphWriteIntent",
    "GraphWriteOp",
    "OutboxEvent",
    "OutboxRow",
    "VersionConflictError",
    "WorldHistoryRepository",
]


class GraphWriteOp(BaseModel):
    """One Neo4j operation, backend-agnostic enough to serialize into
    `outbox_event.graph_write` JSONB and be replayed later by the saga
    dispatcher (docs/design/phase-1/03-world-model-engine.md §17, same
    mechanism as Knowledge Engine §02 §17)."""

    kind: Literal["upsert_node", "upsert_relationship", "delete_node"]
    object_id: str | None = None
    label: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    from_id: str | None = None
    to_id: str | None = None
    relationship_type: str | None = None


class GraphWriteIntent(BaseModel):
    ops: list[GraphWriteOp] = Field(default_factory=list)


class OutboxEvent(BaseModel):
    """One row to insert into `world_model.outbox_event` in the same Postgres
    transaction as the entity write it accompanies (docs/design/phase-1/
    00-shared-foundations.md's transactional outbox pattern). `graph_write`,
    when set, additionally makes this row the durable "intent" record for the
    two-phase Neo4j saga -- only `object_graph.py`'s writes carry one; Active
    Context updates never do (Redis is not graph-backed)."""

    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None
    graph_write: GraphWriteIntent | None = None


class OutboxRow(BaseModel):
    id: UUID
    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None
    graph_write: GraphWriteIntent | None


@runtime_checkable
class WorldHistoryRepository(Protocol):
    """Persistence port for `object_state_history`, `snapshot`, `prediction`,
    `conflict_log`, and `outbox_event` (docs/design/phase-1/
    03-world-model-engine.md §4). Implemented by `repository/
    postgres_history_repository.py` against SQLAlchemy async; never imported
    directly by `domain/`. Never touches Redis (that's `ContextRepository`) or
    Neo4j (that's `GraphStore`, driven by `graph_write` intents this port only
    stores and hands back).
    """

    async def append_object_history(
        self, entry: ObjectStateHistoryEntry, *, outbox_event: OutboxEvent | None = None
    ) -> ObjectStateHistoryEntry: ...

    async def list_object_history(
        self,
        object_id: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[ObjectStateHistoryEntry]: ...

    async def list_recent_history_for_user(
        self, *, user_id: UUID, limit: int = 1000
    ) -> list[ObjectStateHistoryEntry]:
        """Every object's history for `user_id`, most recent first -- backed by
        the `osh_user_idx (user_id, changed_at DESC)` index (§4), which exists
        specifically to make this query pattern (as opposed to
        `list_object_history`'s single-object scope) efficient. Feeds
        `workers/prediction_worker.py`'s pattern detection, which needs
        cross-object history for one user, not one object's history alone."""
        ...

    async def create_snapshot(self, snapshot: Snapshot) -> Snapshot: ...

    async def list_snapshots(self, *, user_id: UUID, limit: int = 50) -> list[Snapshot]: ...

    async def create_prediction(
        self, prediction: Prediction, *, outbox_event: OutboxEvent | None = None
    ) -> Prediction: ...

    async def list_predictions(self, *, user_id: UUID, limit: int = 50) -> list[Prediction]: ...

    async def log_conflict(self, entry: ConflictLogEntry) -> ConflictLogEntry: ...

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID:
        """Insert a standalone outbox row with no accompanying Postgres entity
        write -- used for `world_model.object.*` events, whose graph write has
        no `object_state_history` row of its own beyond the one already
        appended by the same call site (kept separate so callers that only need
        to enqueue an event, e.g. Active Context updates, don't need a history
        row to hang it off)."""
        ...

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        """Rows ready to publish: `dispatched_at IS NULL AND (graph_write IS
        NULL OR graph_applied_at IS NOT NULL)`."""
        ...

    async def mark_dispatched(self, outbox_id: UUID) -> None: ...

    async def list_pending_graph_writes(self, *, limit: int = 100) -> list[OutboxRow]: ...

    async def mark_graph_applied(self, outbox_id: UUID) -> None: ...

    async def count_stale_pending_graph_writes(self, *, older_than: datetime) -> int: ...


@runtime_checkable
class ContextRepository(Protocol):
    """Redis-backed, primary store (not a cache) for Active Context and
    Attention (docs/design/phase-1/03-world-model-engine.md §4, §9). The single
    highest-QPS port in Phase 1 -- `get_context` backs `world_model.context.
    request`, budgeted at p95 < 20ms (§15) as a direct `HGETALL`, never a
    fan-out to another store.
    """

    async def get_context(self, user_id: UUID) -> ActiveContext | None: ...

    async def put_context(self, context: ActiveContext) -> None: ...

    async def get_attention(self, user_id: UUID) -> list[AttentionEntry]: ...

    async def boost_attention(
        self, *, user_id: UUID, entity_id: str, boost: float, at: datetime
    ) -> None: ...

    async def put_presence(
        self, *, user_id: UUID, device: str, platform: str, at: datetime
    ) -> None: ...


@runtime_checkable
class EventPublisher(Protocol):
    """Structurally identical to `nova_eventbus_sdk.interface.EventBus.request`
    so the real `BoundEventBus` satisfies this Protocol without an adapter.
    Declared per §1's component table; unused by any Phase 1 domain flow today
    (World Model calls no other engine synchronously in this phase, matching
    Knowledge Engine's own `EventPublisher` -- see its docstring)."""

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope: ...


class VersionConflictError(RuntimeError):
    """Raised when a World Object's optimistic-concurrency `version` no longer
    matches the value a caller expected -- a concurrent writer (e.g. two
    perception sources updating the same object near-simultaneously, §12) got
    there first."""

    def __init__(self, object_id: str, *, expected_version: int) -> None:
        super().__init__(
            f"World Object {object_id} was not at version {expected_version}; "
            f"concurrent update detected."
        )
        self.object_id = object_id
        self.expected_version = expected_version
