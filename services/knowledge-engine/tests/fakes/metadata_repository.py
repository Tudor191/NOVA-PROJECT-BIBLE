"""`FakeKnowledgeMetadataRepository` -- an in-memory `domain.ports.
KnowledgeMetadataRepository`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import count
from uuid import UUID, uuid4

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
from nova_knowledge_engine.domain.ports import OutboxEvent, OutboxRow, VersionConflictError


@dataclass
class _OutboxRecord:
    id: UUID
    subject: str
    payload: dict
    correlation_id: UUID
    causation_id: UUID | None
    graph_write: GraphWriteIntent | None
    created_at: datetime
    graph_applied_at: datetime | None = None
    dispatched_at: datetime | None = None


class FakeKnowledgeMetadataRepository:
    """Implements `domain.ports.KnowledgeMetadataRepository` in memory. Every
    write appends to `outbox` (mirroring the real transactional-outbox row), so
    tests can assert exactly what an operation would have enqueued, including its
    `graph_write` intent, without a real Postgres/Neo4j."""

    def __init__(self) -> None:
        self.nodes: dict[str, KnowledgeNode] = {}
        self.sources: dict[str, list[SourceAttribution]] = {}
        self.version_history: list[NodeVersionHistoryEntry] = []
        self.usage: dict[str, list[UUID | None]] = {}
        self.contradictions: dict[UUID, Contradiction] = {}
        self.outbox: dict[UUID, _OutboxRecord] = {}
        self._seq = count()

    def _record_outbox(self, event: OutboxEvent | None) -> UUID | None:
        if event is None:
            return None
        record_id = uuid4()
        self.outbox[record_id] = _OutboxRecord(
            id=record_id,
            subject=event.subject,
            payload=event.payload,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            graph_write=event.graph_write,
            created_at=datetime.now(UTC).replace(microsecond=next(self._seq)),
        )
        return record_id

    async def create_node(
        self,
        node: KnowledgeNode,
        *,
        source: SourceAttribution | None = None,
        outbox_event: OutboxEvent | None = None,
    ) -> KnowledgeNode:
        self.nodes[node.node_id] = node
        if source is not None:
            self.sources.setdefault(node.node_id, []).append(source)
        self._record_outbox(outbox_event)
        return node

    async def get_node(self, node_id: str) -> KnowledgeNode | None:
        return self.nodes.get(node_id)

    async def update_node(
        self,
        node: KnowledgeNode,
        *,
        expected_version: int,
        source: SourceAttribution | None = None,
        outbox_event: OutboxEvent | None = None,
    ) -> KnowledgeNode:
        existing = self.nodes.get(node.node_id)
        if existing is None or existing.version != expected_version:
            raise VersionConflictError(node.node_id, expected_version=expected_version)
        self.nodes[node.node_id] = node
        if source is not None:
            self.sources.setdefault(node.node_id, []).append(source)
        self._record_outbox(outbox_event)
        return node

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
    ) -> list[KnowledgeNode]:
        results = [
            n
            for n in self.nodes.values()
            if (scope is None or n.scope == scope)
            and (project_id is None or n.project_id == project_id)
            and (user_id is None or n.user_id == user_id)
            and (label is None or n.label == label)
            and (layer is None or n.layer == layer)
            and (name_contains is None or name_contains.lower() in n.name.lower())
        ]
        results.sort(key=lambda n: n.created_at, reverse=True)
        return results[:limit]

    async def list_needing_embedding(
        self, *, current_model: str, limit: int = 100
    ) -> list[KnowledgeNode]:
        results = [
            n
            for n in self.nodes.values()
            if n.embedding is None or n.embedding_model != current_model
        ]
        results.sort(key=lambda n: n.created_at)
        return results[:limit]

    async def list_sources(self, node_id: str) -> list[SourceAttribution]:
        return list(self.sources.get(node_id, []))

    async def append_version_history(self, entry: NodeVersionHistoryEntry) -> None:
        self.version_history.append(entry)

    async def record_usage(self, node_id: str, *, project_id: UUID | None = None) -> None:
        self.usage.setdefault(node_id, []).append(project_id)

    async def usage_summary(self, node_id: str) -> UsageSummary:
        entries = self.usage.get(node_id, [])
        distinct = {p for p in entries if p is not None}
        return UsageSummary(usage_count=len(entries), distinct_project_ids=list(distinct))

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID:
        record_id = self._record_outbox(event)
        assert record_id is not None
        return record_id

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        rows = [
            r
            for r in self.outbox.values()
            if r.dispatched_at is None and (r.graph_write is None or r.graph_applied_at is not None)
        ]
        rows.sort(key=lambda r: r.created_at)
        return [_to_row(r) for r in rows[:limit]]

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        self.outbox[outbox_id].dispatched_at = datetime.now(UTC)

    async def list_pending_graph_writes(self, *, limit: int = 100) -> list[OutboxRow]:
        rows = [
            r
            for r in self.outbox.values()
            if r.graph_write is not None and r.graph_applied_at is None
        ]
        rows.sort(key=lambda r: r.created_at)
        return [_to_row(r) for r in rows[:limit]]

    async def mark_graph_applied(self, outbox_id: UUID) -> None:
        self.outbox[outbox_id].graph_applied_at = datetime.now(UTC)

    async def count_stale_pending_graph_writes(self, *, older_than: datetime) -> int:
        return len(
            [
                r
                for r in self.outbox.values()
                if r.graph_write is not None
                and r.graph_applied_at is None
                and r.created_at < older_than
            ]
        )

    async def create_contradiction(
        self, contradiction: Contradiction, *, outbox_event: OutboxEvent | None = None
    ) -> Contradiction:
        self.contradictions[contradiction.id] = contradiction
        self._record_outbox(outbox_event)
        return contradiction

    async def get_contradiction(self, contradiction_id: UUID) -> Contradiction | None:
        return self.contradictions.get(contradiction_id)

    async def list_contradictions(
        self, *, status: str | None = None, limit: int = 50
    ) -> list[Contradiction]:
        results = [
            c for c in self.contradictions.values() if status is None or c.status == status
        ]
        results.sort(key=lambda c: c.detected_at, reverse=True)
        return results[:limit]

    async def resolve_contradiction(
        self,
        contradiction_id: UUID,
        *,
        resolution: str,
        outbox_event: OutboxEvent | None = None,
    ) -> Contradiction:
        existing = self.contradictions[contradiction_id]
        resolved = existing.model_copy(
            update={
                "status": "resolved",
                "resolution": resolution,
                "resolved_at": datetime.now(UTC),
            }
        )
        self.contradictions[contradiction_id] = resolved
        self._record_outbox(outbox_event)
        return resolved


def _to_row(record: _OutboxRecord) -> OutboxRow:
    return OutboxRow(
        id=record.id,
        subject=record.subject,
        payload=record.payload,
        correlation_id=record.correlation_id,
        causation_id=record.causation_id,
        graph_write=record.graph_write,
    )
