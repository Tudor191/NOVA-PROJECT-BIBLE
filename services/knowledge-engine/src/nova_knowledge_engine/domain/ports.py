"""Protocols this package depends on -- implements nothing itself
(docs/design/phase-1/02-knowledge-engine.md §1). `domain/` may only import this
module, `domain/models.py`, and other `domain/` modules -- never FastAPI,
SQLAlchemy, Neo4j/pgvector clients, or the Event Bus SDK directly
(docs/architecture/03-backend-architecture.md §1).

`GraphStore`, `VectorIndex`, and `EmbeddingProvider` are re-exports of the shared
SDK Protocols (`nova-graphstore-sdk`, `nova-vectorstore-sdk`, `nova-embeddings-sdk`)
rather than reinvented here -- importing a Protocol type is not importing a
concrete backend, so this does not violate the framework-free rule.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from nova_contracts import EventEnvelope
from nova_embeddings_sdk import EmbeddingProvider
from nova_graphstore_sdk import GraphStore
from nova_vectorstore_sdk import VectorStore as VectorIndex
from pydantic import BaseModel

from nova_knowledge_engine.domain.models import (
    Contradiction,
    GraphWriteIntent,
    KnowledgeLayer,
    KnowledgeNode,
    KnowledgeScope,
    NodeVersionHistoryEntry,
    SourceAttribution,
    UsageSummary,
)

__all__ = [
    "EmbeddingProvider",
    "EventPublisher",
    "GraphStore",
    "KnowledgeMetadataRepository",
    "OutboxEvent",
    "OutboxRow",
    "VectorIndex",
    "VersionConflictError",
]


class OutboxEvent(BaseModel):
    """One row to insert into `knowledge.outbox_event` in the same Postgres
    transaction as the entity write it accompanies (docs/design/phase-1/
    00-shared-foundations.md's transactional outbox pattern). `graph_write`, when
    set, additionally makes this row the durable "intent" record for the two-phase
    Neo4j saga (docs/design/phase-1/02-knowledge-engine.md §17) -- `domain/` only
    describes what to enqueue; `KnowledgeMetadataRepository` implementations own
    the atomicity."""

    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None
    graph_write: GraphWriteIntent | None = None


class OutboxRow(BaseModel):
    """A previously-enqueued outbox row, as read back by the saga dispatcher."""

    id: UUID
    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None
    graph_write: GraphWriteIntent | None


@runtime_checkable
class KnowledgeMetadataRepository(Protocol):
    """Persistence port for `node_metadata`, `source_attribution`,
    `node_version_history`, `contradiction`, `node_usage`, and `outbox_event`
    (docs/design/phase-1/02-knowledge-engine.md §4). Implemented by
    `repository/postgres_metadata_repository.py` against SQLAlchemy async; never
    imported directly by `domain/`. Never touches Neo4j -- that is
    `GraphStore`'s job, driven by `graph_write` intents this port only stores and
    hands back.
    """

    async def create_node(
        self,
        node: KnowledgeNode,
        *,
        source: SourceAttribution | None = None,
        outbox_event: OutboxEvent | None = None,
    ) -> KnowledgeNode: ...

    async def get_node(self, node_id: str) -> KnowledgeNode | None: ...

    async def update_node(
        self,
        node: KnowledgeNode,
        *,
        expected_version: int,
        source: SourceAttribution | None = None,
        outbox_event: OutboxEvent | None = None,
    ) -> KnowledgeNode:
        """Optimistic-concurrency update (`WHERE version = expected_version`).
        Raises `VersionConflictError` if the row moved under us."""
        ...

    async def list_nodes(
        self,
        *,
        scope: KnowledgeScope | None = None,
        project_id: UUID | None = None,
        user_id: UUID | None = None,
        label: str | None = None,
        layer: KnowledgeLayer | None = None,
        name_contains: str | None = None,
        limit: int = 100,
    ) -> list[KnowledgeNode]: ...

    async def list_needing_embedding(
        self, *, current_model: str, limit: int = 100
    ) -> list[KnowledgeNode]:
        """Rows where `embedding IS NULL`, or where `embedding_model !=
        current_model` (a re-embedding due to ADR-010's model changing) --
        docs/design/phase-1/02-knowledge-engine.md §10. The embedding *write*
        itself goes through `VectorIndex.upsert_batch`, not this port."""
        ...

    async def list_sources(self, node_id: str) -> list[SourceAttribution]: ...

    async def append_version_history(self, entry: NodeVersionHistoryEntry) -> None: ...

    async def record_usage(self, node_id: str, *, project_id: UUID | None = None) -> None:
        """Fire-and-forget usage bookkeeping feeding `domain/evolution.py`'s
        Applied/Expert/Strategic transitions (docs/design/phase-1/
        02-knowledge-engine.md §6, §13) -- never raises in a way that fails the
        triggering event handler."""
        ...

    async def usage_summary(self, node_id: str) -> UsageSummary: ...

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID:
        """Insert a standalone outbox row with no accompanying entity write --
        used for edge (relationship) creation, which has no Postgres-side row of
        its own (Neo4j is the sole source of truth for edges, §4)."""
        ...

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        """Rows ready to publish: `dispatched_at IS NULL AND (graph_write IS NULL
        OR graph_applied_at IS NOT NULL)` -- an event with a pending graph write is
        never published before that write actually lands (docs/design/phase-1/
        02-knowledge-engine.md §17 step 3)."""
        ...

    async def mark_dispatched(self, outbox_id: UUID) -> None: ...

    async def list_pending_graph_writes(self, *, limit: int = 100) -> list[OutboxRow]:
        """Rows where `graph_write IS NOT NULL AND graph_applied_at IS NULL`."""
        ...

    async def mark_graph_applied(self, outbox_id: UUID) -> None: ...

    async def count_stale_pending_graph_writes(self, *, older_than: datetime) -> int:
        """Rows still pending a graph write past `older_than` -- feeds the
        `knowledge.graph_write.degraded` operational metric (docs/design/phase-1/
        02-knowledge-engine.md §17 step 4)."""
        ...

    async def create_contradiction(
        self, contradiction: Contradiction, *, outbox_event: OutboxEvent | None = None
    ) -> Contradiction: ...

    async def get_contradiction(self, contradiction_id: UUID) -> Contradiction | None: ...

    async def list_contradictions(
        self, *, status: str | None = None, limit: int = 50
    ) -> list[Contradiction]: ...

    async def resolve_contradiction(
        self,
        contradiction_id: UUID,
        *,
        resolution: str,
        outbox_event: OutboxEvent | None = None,
    ) -> Contradiction: ...


@runtime_checkable
class EventPublisher(Protocol):
    """Structurally identical to `nova_eventbus_sdk.interface.EventBus.request` so
    the real `BoundEventBus` satisfies this Protocol without an adapter --
    `domain/` still never imports `nova_eventbus_sdk` itself, only this narrower
    shape. Unused by any Phase 1 request/reply flow today (Knowledge Engine only
    *serves* requests in this phase, per docs/design/phase-1/02-knowledge-engine.md
    §13) -- declared per §1's component table for the Phase 2 extension point noted
    in §20 (Reasoning Engine calling back with a contradiction resolution)."""

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
    """Raised by `KnowledgeMetadataRepository.update_node` when `expected_version`
    no longer matches the stored row -- a concurrent writer (e.g. the maintenance
    worker) got there first."""

    def __init__(self, node_id: str, *, expected_version: int) -> None:
        super().__init__(
            f"Node {node_id} was not at version {expected_version}; "
            f"concurrent update detected."
        )
        self.node_id = node_id
        self.expected_version = expected_version
