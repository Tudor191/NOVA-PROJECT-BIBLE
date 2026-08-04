"""World Object CRUD orchestration -- the only module that ever produces a
`GraphWriteIntent`, and the only module that ever calls a live `GraphStore` (via
`apply_graph_write`, invoked exclusively by the saga dispatcher) (docs/design/
phase-1/03-world-model-engine.md §1). Delegates to `GraphStore`; must never
contain confidence/validation business rules of its own -- state transitions
come from `state_management.py`, conflict resolution from
`conflict_resolution.py`; this module only translates an already-decided
transition into graph operations and Postgres history persistence.

Relationships (`-[:CONTAINS]->`, `-[:BELONGS_TO]->`, etc., §5) are established
as additional ops on the *same* outbox row as the object upsert that implies
them, never as a standalone write -- §13's event table has no dedicated
"relationship created" subject for World Model (unlike Knowledge Engine's
`knowledge.edge.created`), so a relationship's creation is communicated as part
of whichever object's `world_model.object.created`/`.updated` event it
accompanies, not as its own fabricated event.
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts import WorldObjectChangedPayload

from nova_world_model_engine.domain.models import ObjectState, ObjectStateHistoryEntry, WorldObject
from nova_world_model_engine.domain.ports import (
    GraphStore,
    GraphWriteIntent,
    GraphWriteOp,
    OutboxEvent,
    WorldHistoryRepository,
)


class ObjectRelationship:
    """A relationship to establish alongside an object upsert -- not a
    dataclass with its own identity, just a bundle of the fields
    `plan_object_relationship` needs."""

    __slots__ = ("confidence", "from_id", "relationship_type", "source", "to_id")

    def __init__(
        self, *, from_id: str, to_id: str, relationship_type: str, confidence: float, source: str
    ) -> None:
        self.from_id = from_id
        self.to_id = to_id
        self.relationship_type = relationship_type
        self.confidence = confidence
        self.source = source


def plan_object_upsert(obj: WorldObject) -> GraphWriteOp:
    return GraphWriteOp(
        kind="upsert_node",
        object_id=obj.object_id,
        label=obj.label,
        properties={"state": obj.state.value, "confidence": obj.confidence, **obj.properties},
    )


def plan_object_relationship(rel: ObjectRelationship) -> GraphWriteOp:
    return GraphWriteOp(
        kind="upsert_relationship",
        from_id=rel.from_id,
        to_id=rel.to_id,
        relationship_type=rel.relationship_type,
        properties={"confidence": rel.confidence, "source": rel.source},
    )


def plan_object_removal(object_id: str) -> GraphWriteIntent:
    return GraphWriteIntent(ops=[GraphWriteOp(kind="delete_node", object_id=object_id)])


async def apply_graph_write(graph_store: GraphStore, intent: GraphWriteIntent) -> None:
    """Executes `intent` against a live `GraphStore` -- called exclusively by
    `repository/outbox_dispatcher.py`'s saga step 2 (docs/design/phase-1/
    03-world-model-engine.md §17), never from the synchronous request path."""
    for op in intent.ops:
        if op.kind == "upsert_node":
            if op.object_id is None or op.label is None:
                raise ValueError(f"upsert_node op missing object_id/label: {op!r}")
            await graph_store.upsert_node(op.label, op.object_id, op.properties)
        elif op.kind == "upsert_relationship":
            if op.from_id is None or op.to_id is None or op.relationship_type is None:
                raise ValueError(f"upsert_relationship op missing endpoints/type: {op!r}")
            await graph_store.upsert_relationship(
                op.from_id, op.relationship_type, op.to_id, op.properties
            )
        elif op.kind == "delete_node":
            if op.object_id is None:
                raise ValueError(f"delete_node op missing object_id: {op!r}")
            await graph_store.delete_node(op.object_id)


async def observe_object(
    history_repo: WorldHistoryRepository,
    *,
    obj: WorldObject,
    previous_state: ObjectState | None,
    relationships: list[ObjectRelationship] | None = None,
    correlation_id: UUID,
) -> ObjectStateHistoryEntry:
    """Step 1 of the saga (§17): appends `object_state_history` +
    `outbox_event` (with `graph_write` populated) in one Postgres transaction --
    the "Object write path" (§3). This commit is the durable record of intent;
    the Neo4j write happens later, from the outbox row, never here.

    `previous_state=None` means this is the object's first-ever observation
    (`world_model.object.created`); any other value means an update. Any
    `relationships` implied by this observation ride along in the same
    `GraphWriteIntent` (see module docstring)."""
    ops = [plan_object_upsert(obj)]
    ops.extend(plan_object_relationship(rel) for rel in relationships or [])

    outbox = OutboxEvent(
        subject="world_model.object.created"
        if previous_state is None
        else "world_model.object.updated",
        payload=WorldObjectChangedPayload(
            object_id=obj.object_id,
            label=obj.label,
            user_id=obj.user_id,
            previous_state=previous_state,
            new_state=obj.state,
            confidence=obj.confidence,
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
        graph_write=GraphWriteIntent(ops=ops),
    )
    entry = ObjectStateHistoryEntry(
        object_id=obj.object_id,
        object_label=obj.label,
        user_id=obj.user_id,
        previous_state=previous_state,
        new_state=obj.state,
        confidence=obj.confidence,
        correlation_id=correlation_id,
    )
    return await history_repo.append_object_history(entry, outbox_event=outbox)


async def remove_object(
    history_repo: WorldHistoryRepository,
    *,
    object_id: str,
    label: str,
    user_id: UUID,
    last_known_state: ObjectState,
    correlation_id: UUID,
) -> UUID:
    """`world_model.object.deleted` -- e.g. a window closed, a file deleted from
    disk. Object *removal* from current reality, not a state transition (no
    state in §6's diagram represents "no longer exists"), so this bypasses
    `state_management.py` entirely and enqueues a `delete_node` graph write
    directly. Returns the enqueued outbox row's id."""
    outbox = OutboxEvent(
        subject="world_model.object.deleted",
        payload=WorldObjectChangedPayload(
            object_id=object_id,
            label=label,
            user_id=user_id,
            previous_state=last_known_state,
            new_state=last_known_state,
            confidence=None,
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
        graph_write=plan_object_removal(object_id),
    )
    return await history_repo.enqueue_outbox(outbox)
