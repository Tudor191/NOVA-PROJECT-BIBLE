"""`PostgresMetadataRepository` -- implements `domain.ports.KnowledgeMetadataRepository`
against SQLAlchemy async, per the schema in docs/design/phase-1/02-knowledge-engine.md
§4 (plus `NodeUsageORM`, see `repository/models.py`).

One session per operation (never held open across a request), and every write that
must also enqueue an event does so in the same transaction as the entity write --
the transactional outbox pattern (docs/design/phase-1/00-shared-foundations.md),
extended here with `graph_write`/`graph_applied_at` for the two-phase Neo4j saga
(§17). Never touches Neo4j -- that is `repository/outbox_dispatcher.py`'s job, via
`domain.graph_operations.apply_graph_write`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_knowledge_engine.domain.models import (
    Contradiction,
    GraphWriteIntent,
    KnowledgeLayer,
    KnowledgeNode,
    KnowledgeScope,
    NodeVersionHistoryEntry,
    PrivacyLevel,
    SourceAttribution,
    UsageSummary,
)
from nova_knowledge_engine.domain.ports import OutboxEvent, OutboxRow, VersionConflictError
from nova_knowledge_engine.repository.models import (
    ContradictionORM,
    NodeMetadataORM,
    NodeUsageORM,
    NodeVersionHistoryORM,
    OutboxEventORM,
    SourceAttributionORM,
)


def _outbox_orm(event: OutboxEvent) -> OutboxEventORM:
    return OutboxEventORM(
        subject=event.subject,
        payload=event.payload,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
        graph_write=event.graph_write.model_dump(mode="json") if event.graph_write else None,
    )


def _outbox_to_domain(row: OutboxEventORM) -> OutboxRow:
    return OutboxRow(
        id=row.id,
        subject=row.subject,
        payload=row.payload,
        correlation_id=row.correlation_id,
        causation_id=row.causation_id,
        graph_write=GraphWriteIntent.model_validate(row.graph_write) if row.graph_write else None,
    )


def _node_to_domain(row: NodeMetadataORM) -> KnowledgeNode:
    return KnowledgeNode(
        node_id=row.node_id,
        label=row.label,
        name=row.name,
        domain=row.domain,
        scope=KnowledgeScope(row.scope),
        project_id=row.project_id,
        user_id=row.user_id,
        embedding=list(row.embedding) if row.embedding is not None else None,
        embedding_model=row.embedding_model,
        confidence=row.confidence,
        privacy_level=PrivacyLevel(row.privacy_level),
        layer=KnowledgeLayer(row.layer),
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _source_to_domain(row: SourceAttributionORM) -> SourceAttribution:
    return SourceAttribution(
        id=row.id,
        node_id=row.node_id,
        source_type=row.source_type,
        source_ref=row.source_ref,
        excerpt=row.excerpt,
        confidence_contribution=row.confidence_contribution,
        recorded_at=row.recorded_at,
    )


def _contradiction_to_domain(row: ContradictionORM) -> Contradiction:
    return Contradiction(
        id=row.id,
        node_a_id=row.node_a_id,
        node_b_id=row.node_b_id,
        description=row.description,
        status=row.status,
        resolution=row.resolution,
        detected_at=row.detected_at,
        resolved_at=row.resolved_at,
    )


class PostgresMetadataRepository:
    """`domain.ports.KnowledgeMetadataRepository` implementation. Never imported by
    `domain/` or `api/` -- constructed once in `main.py` and passed in as the
    port."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_node(
        self,
        node: KnowledgeNode,
        *,
        source: SourceAttribution | None = None,
        outbox_event: OutboxEvent | None = None,
    ) -> KnowledgeNode:
        async with self._session_factory() as session, session.begin():
            orm = NodeMetadataORM(
                node_id=node.node_id,
                label=node.label,
                name=node.name,
                domain=node.domain,
                scope=node.scope.value,
                project_id=node.project_id,
                user_id=node.user_id,
                embedding=node.embedding,
                embedding_model=node.embedding_model,
                confidence=node.confidence,
                privacy_level=node.privacy_level.value,
                layer=node.layer.value,
                version=node.version,
            )
            session.add(orm)
            if source is not None:
                session.add(
                    SourceAttributionORM(
                        id=source.id,
                        node_id=source.node_id,
                        source_type=source.source_type,
                        source_ref=source.source_ref,
                        excerpt=source.excerpt,
                        confidence_contribution=source.confidence_contribution,
                    )
                )
            if outbox_event is not None:
                session.add(_outbox_orm(outbox_event))
            await session.flush()
            await session.refresh(orm)
            return _node_to_domain(orm)

    async def get_node(self, node_id: str) -> KnowledgeNode | None:
        async with self._session_factory() as session:
            row = await session.get(NodeMetadataORM, node_id)
            return _node_to_domain(row) if row is not None else None

    async def update_node(
        self,
        node: KnowledgeNode,
        *,
        expected_version: int,
        source: SourceAttribution | None = None,
        outbox_event: OutboxEvent | None = None,
    ) -> KnowledgeNode:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                update(NodeMetadataORM)
                .where(
                    NodeMetadataORM.node_id == node.node_id,
                    NodeMetadataORM.version == expected_version,
                )
                .values(
                    name=node.name,
                    domain=node.domain,
                    embedding=node.embedding,
                    embedding_model=node.embedding_model,
                    confidence=node.confidence,
                    privacy_level=node.privacy_level.value,
                    layer=node.layer.value,
                    updated_at=node.updated_at,
                    version=node.version,
                )
            )
            if cast(CursorResult, result).rowcount == 0:
                raise VersionConflictError(node.node_id, expected_version=expected_version)
            if source is not None:
                session.add(
                    SourceAttributionORM(
                        id=source.id,
                        node_id=source.node_id,
                        source_type=source.source_type,
                        source_ref=source.source_ref,
                        excerpt=source.excerpt,
                        confidence_contribution=source.confidence_contribution,
                    )
                )
            if outbox_event is not None:
                session.add(_outbox_orm(outbox_event))
            row = await session.get(NodeMetadataORM, node.node_id)
            assert row is not None
            return _node_to_domain(row)

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
        async with self._session_factory() as session:
            stmt = select(NodeMetadataORM)
            if scope is not None:
                stmt = stmt.where(NodeMetadataORM.scope == scope.value)
            if project_id is not None:
                stmt = stmt.where(NodeMetadataORM.project_id == project_id)
            if user_id is not None:
                stmt = stmt.where(NodeMetadataORM.user_id == user_id)
            if label is not None:
                stmt = stmt.where(NodeMetadataORM.label == label)
            if layer is not None:
                stmt = stmt.where(NodeMetadataORM.layer == layer.value)
            if name_contains is not None:
                stmt = stmt.where(NodeMetadataORM.name.ilike(f"%{name_contains}%"))
            stmt = stmt.order_by(NodeMetadataORM.created_at.desc()).limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            return [_node_to_domain(row) for row in rows]

    async def list_needing_embedding(
        self, *, current_model: str, limit: int = 100
    ) -> list[KnowledgeNode]:
        async with self._session_factory() as session:
            stmt = (
                select(NodeMetadataORM)
                .where(
                    NodeMetadataORM.embedding.is_(None)
                    | (NodeMetadataORM.embedding_model != current_model)
                )
                .order_by(NodeMetadataORM.created_at)
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_node_to_domain(row) for row in rows]

    async def list_sources(self, node_id: str) -> list[SourceAttribution]:
        async with self._session_factory() as session:
            stmt = select(SourceAttributionORM).where(SourceAttributionORM.node_id == node_id)
            rows = (await session.execute(stmt)).scalars().all()
            return [_source_to_domain(row) for row in rows]

    async def append_version_history(self, entry: NodeVersionHistoryEntry) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                NodeVersionHistoryORM(
                    id=entry.id,
                    node_id=entry.node_id,
                    version=entry.version,
                    change_type=entry.change_type,
                    previous_value=entry.previous_value,
                    new_value=entry.new_value,
                    changed_by=entry.changed_by,
                )
            )

    async def record_usage(self, node_id: str, *, project_id: UUID | None = None) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(NodeUsageORM(node_id=node_id, project_id=project_id))

    async def usage_summary(self, node_id: str) -> UsageSummary:
        async with self._session_factory() as session:
            stmt = select(NodeUsageORM).where(NodeUsageORM.node_id == node_id)
            rows = (await session.execute(stmt)).scalars().all()
            distinct_projects = {row.project_id for row in rows if row.project_id is not None}
            return UsageSummary(usage_count=len(rows), distinct_project_ids=list(distinct_projects))

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID:
        async with self._session_factory() as session, session.begin():
            orm = _outbox_orm(event)
            session.add(orm)
            await session.flush()
            return orm.id

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        async with self._session_factory() as session:
            stmt = (
                select(OutboxEventORM)
                .where(OutboxEventORM.dispatched_at.is_(None))
                .where(
                    OutboxEventORM.graph_write.is_(None)
                    | OutboxEventORM.graph_applied_at.is_not(None)
                )
                .order_by(OutboxEventORM.created_at)
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_outbox_to_domain(row) for row in rows]

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(OutboxEventORM)
                .where(OutboxEventORM.id == outbox_id)
                .values(dispatched_at=func.now())
            )

    async def list_pending_graph_writes(self, *, limit: int = 100) -> list[OutboxRow]:
        async with self._session_factory() as session:
            stmt = (
                select(OutboxEventORM)
                .where(
                    OutboxEventORM.graph_write.is_not(None),
                    OutboxEventORM.graph_applied_at.is_(None),
                )
                .order_by(OutboxEventORM.created_at)
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_outbox_to_domain(row) for row in rows]

    async def mark_graph_applied(self, outbox_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(OutboxEventORM)
                .where(OutboxEventORM.id == outbox_id)
                .values(graph_applied_at=func.now())
            )

    async def count_stale_pending_graph_writes(self, *, older_than: datetime) -> int:
        async with self._session_factory() as session:
            stmt = select(func.count()).where(
                OutboxEventORM.graph_write.is_not(None),
                OutboxEventORM.graph_applied_at.is_(None),
                OutboxEventORM.created_at < older_than,
            )
            result = await session.execute(stmt)
            return result.scalar_one()

    async def create_contradiction(
        self, contradiction: Contradiction, *, outbox_event: OutboxEvent | None = None
    ) -> Contradiction:
        async with self._session_factory() as session, session.begin():
            orm = ContradictionORM(
                id=contradiction.id,
                node_a_id=contradiction.node_a_id,
                node_b_id=contradiction.node_b_id,
                description=contradiction.description,
                status=contradiction.status,
                resolution=contradiction.resolution,
            )
            session.add(orm)
            if outbox_event is not None:
                session.add(_outbox_orm(outbox_event))
            await session.flush()
            await session.refresh(orm)
            return _contradiction_to_domain(orm)

    async def get_contradiction(self, contradiction_id: UUID) -> Contradiction | None:
        async with self._session_factory() as session:
            row = await session.get(ContradictionORM, contradiction_id)
            return _contradiction_to_domain(row) if row is not None else None

    async def list_contradictions(
        self, *, status: str | None = None, limit: int = 50
    ) -> list[Contradiction]:
        async with self._session_factory() as session:
            stmt = select(ContradictionORM)
            if status is not None:
                stmt = stmt.where(ContradictionORM.status == status)
            stmt = stmt.order_by(ContradictionORM.detected_at.desc()).limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            return [_contradiction_to_domain(row) for row in rows]

    async def resolve_contradiction(
        self,
        contradiction_id: UUID,
        *,
        resolution: str,
        outbox_event: OutboxEvent | None = None,
    ) -> Contradiction:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(ContradictionORM)
                .where(ContradictionORM.id == contradiction_id)
                .values(status="resolved", resolution=resolution, resolved_at=datetime.now(UTC))
            )
            if outbox_event is not None:
                session.add(_outbox_orm(outbox_event))
            row = await session.get(ContradictionORM, contradiction_id)
            assert row is not None
            return _contradiction_to_domain(row)
