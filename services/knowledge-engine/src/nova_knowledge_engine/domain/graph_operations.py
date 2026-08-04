"""Graph write orchestration -- the only module that ever produces a
`GraphWriteIntent`, and the only module that ever calls a live `GraphStore` (via
`apply_graph_write`, invoked exclusively by the saga dispatcher) (docs/design/
phase-1/02-knowledge-engine.md §1). Must never contain confidence/validation
business rules -- those are `validation.py`'s and `contradiction.py`'s job; this
module only translates an already-decided write into graph operations and Postgres
persistence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from nova_contracts import (
    KnowledgeEdgeCreatedPayload,
    KnowledgeNodeChangedPayload,
    LayerAdvancedPayload,
)
from nova_graphstore_sdk import GraphStore

from nova_knowledge_engine.domain.models import (
    GraphWriteIntent,
    GraphWriteOp,
    KnowledgeLayer,
    KnowledgeNode,
    NodeVersionHistoryEntry,
    SourceAttribution,
)
from nova_knowledge_engine.domain.ports import KnowledgeMetadataRepository, OutboxEvent


class NodeNotFoundError(RuntimeError):
    def __init__(self, node_id: str) -> None:
        super().__init__(f"Knowledge node {node_id} not found")
        self.node_id = node_id


def plan_node_upsert(node: KnowledgeNode) -> GraphWriteIntent:
    return GraphWriteIntent(
        ops=[
            GraphWriteOp(
                kind="upsert_node",
                node_id=node.node_id,
                label=node.label,
                properties={
                    "name": node.name,
                    "domain": node.domain,
                    "confidence": node.confidence,
                },
            )
        ]
    )


def plan_relationship_upsert(
    *, from_id: str, to_id: str, relationship_type: str, confidence: float, source: str
) -> GraphWriteIntent:
    return GraphWriteIntent(
        ops=[
            GraphWriteOp(
                kind="upsert_relationship",
                from_id=from_id,
                to_id=to_id,
                relationship_type=relationship_type,
                properties={
                    "confidence": confidence,
                    "source": source,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )
        ]
    )


async def apply_graph_write(graph_store: GraphStore, intent: GraphWriteIntent) -> None:
    """Executes `intent` against a live `GraphStore` -- called exclusively by
    `repository/outbox_dispatcher.py`'s saga step 2 (docs/design/phase-1/
    02-knowledge-engine.md §17), never from the synchronous request path."""
    for op in intent.ops:
        if op.kind == "upsert_node":
            if op.node_id is None or op.label is None:
                raise ValueError(f"upsert_node op missing node_id/label: {op!r}")
            await graph_store.upsert_node(op.label, op.node_id, op.properties)
        elif op.kind == "upsert_relationship":
            if op.from_id is None or op.to_id is None or op.relationship_type is None:
                raise ValueError(f"upsert_relationship op missing endpoints/type: {op!r}")
            await graph_store.upsert_relationship(
                op.from_id, op.relationship_type, op.to_id, op.properties
            )


async def create_node(
    repository: KnowledgeMetadataRepository,
    *,
    node: KnowledgeNode,
    source: SourceAttribution,
    actor: str,
    correlation_id: UUID,
) -> KnowledgeNode:
    """Step 1 of the saga (§17): writes `node_metadata` + `source_attribution` +
    `outbox_event` (with `graph_write` populated) in one Postgres transaction. This
    commit is the durable record of intent -- the Neo4j write happens later, from
    the outbox row, never here."""
    outbox = OutboxEvent(
        subject="knowledge.node.created",
        payload=KnowledgeNodeChangedPayload(
            node_id=node.node_id,
            label=node.label,
            name=node.name,
            domain=node.domain,
            scope=node.scope,
            confidence=node.confidence,
            layer=node.layer,
            version=node.version,
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
        graph_write=plan_node_upsert(node),
    )
    created = await repository.create_node(node, source=source, outbox_event=outbox)
    await repository.append_version_history(
        NodeVersionHistoryEntry(
            node_id=created.node_id,
            version=created.version,
            change_type="created",
            new_value=created.model_dump(mode="json"),
            changed_by=actor,
        )
    )
    return created


async def corroborate_node(
    repository: KnowledgeMetadataRepository,
    *,
    node: KnowledgeNode,
    expected_version: int,
    source: SourceAttribution,
    actor: str,
    correlation_id: UUID,
) -> KnowledgeNode:
    """An existing node acquired again from a new source -- updates `confidence`
    (already recomputed by `validation.py`) and appends the new
    `source_attribution` row, without re-touching Neo4j (the node already exists
    there; only its Postgres-side confidence changed, so this write carries no
    `graph_write` intent)."""
    previous_confidence = node.confidence
    updated = node.model_copy(
        update={"updated_at": datetime.now(UTC), "version": node.version + 1}
    )
    outbox = OutboxEvent(
        subject="knowledge.node.updated",
        payload=KnowledgeNodeChangedPayload(
            node_id=updated.node_id,
            label=updated.label,
            name=updated.name,
            domain=updated.domain,
            scope=updated.scope,
            confidence=updated.confidence,
            layer=updated.layer,
            version=updated.version,
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    result = await repository.update_node(
        updated, expected_version=expected_version, source=source, outbox_event=outbox
    )
    await repository.append_version_history(
        NodeVersionHistoryEntry(
            node_id=result.node_id,
            version=result.version,
            change_type="confidence_changed",
            previous_value={"confidence": previous_confidence},
            new_value={"confidence": result.confidence},
            changed_by=actor,
        )
    )
    return result


async def advance_layer(
    repository: KnowledgeMetadataRepository,
    *,
    node: KnowledgeNode,
    expected_version: int,
    new_layer: KnowledgeLayer,
    reason: str,
    actor: str,
    correlation_id: UUID,
) -> KnowledgeNode:
    """Executes a `domain/evolution.py` decision -- evolution.py decides, this
    module writes (§1's component table split)."""
    previous_layer = node.layer
    updated = node.model_copy(
        update={
            "layer": new_layer,
            "updated_at": datetime.now(UTC),
            "version": node.version + 1,
        }
    )
    outbox = OutboxEvent(
        subject="knowledge.layer.advanced",
        payload=LayerAdvancedPayload(
            node_id=node.node_id,
            previous_layer=previous_layer,
            new_layer=new_layer,
            reason=reason,
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    result = await repository.update_node(
        updated, expected_version=expected_version, outbox_event=outbox
    )
    await repository.append_version_history(
        NodeVersionHistoryEntry(
            node_id=result.node_id,
            version=result.version,
            change_type="layer_advanced",
            previous_value={"layer": previous_layer.value},
            new_value={"layer": new_layer.value},
            changed_by=actor,
        )
    )
    return result


async def create_relationship(
    repository: KnowledgeMetadataRepository,
    *,
    from_id: str,
    to_id: str,
    relationship_type: str,
    confidence: float,
    source: str,
    correlation_id: UUID,
) -> UUID:
    """Edges have no Postgres-side row of their own (Neo4j is the sole source of
    truth for edges, §4) -- just a standalone outbox row carrying the graph write
    intent. Returns the enqueued outbox row's id."""
    outbox = OutboxEvent(
        subject="knowledge.edge.created",
        payload=KnowledgeEdgeCreatedPayload(
            from_node_id=from_id,
            to_node_id=to_id,
            relationship_type=relationship_type,
            confidence=confidence,
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
        graph_write=plan_relationship_upsert(
            from_id=from_id,
            to_id=to_id,
            relationship_type=relationship_type,
            confidence=confidence,
            source=source,
        ),
    )
    return await repository.enqueue_outbox(outbox)


async def correct_node(
    repository: KnowledgeMetadataRepository,
    node_id: str,
    *,
    updates: dict[str, Any],
    expected_version: int,
    actor: str,
    correlation_id: UUID,
) -> KnowledgeNode:
    """A manual, user/operator-initiated correction (`PATCH /v1/knowledge/nodes/{id}`)
    -- distinct from `corroborate_node` (a new *source* re-acquiring the same
    concept). Always re-upserts the Neo4j copy (`plan_node_upsert`, `MERGE`
    semantics, safe to re-apply) since any of `updates` may have changed a
    graph-visible property."""
    existing = await repository.get_node(node_id)
    if existing is None:
        raise NodeNotFoundError(node_id)
    updated = existing.model_copy(
        update={**updates, "updated_at": datetime.now(UTC), "version": existing.version + 1}
    )
    outbox = OutboxEvent(
        subject="knowledge.node.updated",
        payload=KnowledgeNodeChangedPayload(
            node_id=updated.node_id,
            label=updated.label,
            name=updated.name,
            domain=updated.domain,
            scope=updated.scope,
            confidence=updated.confidence,
            layer=updated.layer,
            version=updated.version,
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
        graph_write=plan_node_upsert(updated),
    )
    result = await repository.update_node(
        updated, expected_version=expected_version, outbox_event=outbox
    )
    changed_fields = set(updates)
    await repository.append_version_history(
        NodeVersionHistoryEntry(
            node_id=result.node_id,
            version=result.version,
            change_type="updated",
            # `mode="json"` guarantees JSON-safe values (enums -> .value, etc.)
            # before this reaches `NodeVersionHistoryORM`'s JSONB columns.
            previous_value=existing.model_dump(mode="json", include=changed_fields),
            new_value=result.model_dump(mode="json", include=changed_fields),
            changed_by=actor,
        )
    )
    return result


def plan_memory_link(
    *, concept_node_id: str, memory_id: UUID, confidence: float, source: str
) -> GraphWriteIntent:
    """`(:MemoryRecord {id})` is a lightweight graph-only reference (docs/design/
    phase-1/01-memory-engine.md §5) -- never backed by a `node_metadata` row, so it
    can't go through `create_node`. Both the reference node and the relationship to
    it are queued in a single intent since `GraphStore.upsert_relationship`
    requires both endpoints to already exist."""
    memory_node_id = f"memory:{memory_id}"
    return GraphWriteIntent(
        ops=[
            GraphWriteOp(
                kind="upsert_node", node_id=memory_node_id, label="MemoryRecord", properties={}
            ),
            GraphWriteOp(
                kind="upsert_relationship",
                from_id=concept_node_id,
                to_id=memory_node_id,
                relationship_type="MENTIONED_IN",
                properties={
                    "confidence": confidence,
                    "source": source,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            ),
        ]
    )


async def link_memory_reference(
    repository: KnowledgeMetadataRepository,
    *,
    concept_node_id: str,
    memory_id: UUID,
    confidence: float,
    source: str,
    correlation_id: UUID,
) -> UUID:
    """Served for `knowledge.link.request` (Memory Engine's `domain/relationship.py`
    calling in, §01 §5). Returns the enqueued outbox row's id."""
    outbox = OutboxEvent(
        subject="knowledge.edge.created",
        payload=KnowledgeEdgeCreatedPayload(
            from_node_id=concept_node_id,
            to_node_id=f"memory:{memory_id}",
            relationship_type="MENTIONED_IN",
            confidence=confidence,
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
        graph_write=plan_memory_link(
            concept_node_id=concept_node_id,
            memory_id=memory_id,
            confidence=confidence,
            source=source,
        ),
    )
    return await repository.enqueue_outbox(outbox)
