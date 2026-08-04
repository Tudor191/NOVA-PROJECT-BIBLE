"""Long Term Memory -- docs/design/phase-1/01-memory-engine.md §2. The shared
write/retrieve/correct/delete/reactivate path every other long-term type module
(`semantic.py`, `procedural.py`, `episodic.py`, `project.py`, `preference.py`,
`decision.py`) delegates to, rather than each reimplementing persistence, lifecycle
transitions, and audit logging independently.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from nova_contracts import LongTermMemoryCreatedPayload, LongTermMemoryUpdatedPayload

from nova_memory_engine.domain import lifecycle
from nova_memory_engine.domain.models import LifecycleState, MemoryRecord, MemoryType, PrivacyLevel
from nova_memory_engine.domain.ports import MemoryRepository, OutboxEvent


class MemoryNotFoundError(LookupError):
    def __init__(self, memory_id: UUID) -> None:
        super().__init__(f"Memory {memory_id} not found.")
        self.memory_id = memory_id


async def write(
    repository: MemoryRepository,
    *,
    user_id: UUID,
    memory_type: MemoryType,
    content: str,
    correlation_id: UUID,
    type_data: dict[str, Any] | None = None,
    project_id: UUID | None = None,
    confidence: float | None = None,
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL,
    source: str | None = None,
    source_ref: UUID | None = None,
    importance_score: float = 0.5,
) -> MemoryRecord:
    record = MemoryRecord(
        memory_type=memory_type,
        content=content,
        type_data=type_data or {},
        project_id=project_id,
        user_id=user_id,
        confidence=confidence,
        privacy_level=privacy_level,
        source=source,
        source_ref=source_ref,
        importance_score=importance_score,
    )
    outbox_event = OutboxEvent(
        subject="memory.long_term.created",
        payload=LongTermMemoryCreatedPayload(
            memory_id=record.id,
            user_id=record.user_id,
            project_id=record.project_id,
            memory_type=record.memory_type,
            importance_score=record.importance_score,
            confidence=record.confidence,
            privacy_level=record.privacy_level,
            knowledge_node_id=record.knowledge_node_id,
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    return await repository.create_long_term(record, outbox_event=outbox_event)


async def get(
    repository: MemoryRepository, memory_id: UUID, *, user_id: UUID
) -> MemoryRecord | None:
    return await repository.get(memory_id, user_id=user_id)


async def _require(repository: MemoryRepository, memory_id: UUID, *, user_id: UUID) -> MemoryRecord:
    existing = await repository.get(memory_id, user_id=user_id)
    if existing is None:
        raise MemoryNotFoundError(memory_id)
    return existing


async def correct(
    repository: MemoryRepository,
    memory_id: UUID,
    *,
    user_id: UUID,
    updates: dict[str, Any],
    correlation_id: UUID,
) -> MemoryRecord:
    """User correction (Part 3 "User Control"). `updates` may set `content`,
    `type_data`, `importance_score`, `privacy_level`, or `project_id` -- never
    `id`, `user_id`, `memory_type`, or `lifecycle_state` (those have their own,
    narrower entry points)."""
    existing = await _require(repository, memory_id, user_id=user_id)
    updated = existing.model_copy(
        update={**updates, "updated_at": datetime.now(UTC), "version": existing.version + 1}
    )
    outbox_event = OutboxEvent(
        subject="memory.long_term.updated",
        payload=LongTermMemoryUpdatedPayload(
            memory_id=updated.id,
            user_id=updated.user_id,
            updated_fields=sorted(updates),
            version=updated.version,
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    result = await repository.update(
        updated, expected_version=existing.version, outbox_event=outbox_event
    )
    await repository.append_audit_log(
        memory_id=memory_id, action="updated", actor=str(user_id), detail=updates
    )
    return result


async def transition_lifecycle(
    repository: MemoryRepository,
    memory_id: UUID,
    *,
    user_id: UUID,
    next_state: LifecycleState,
    reason: str,
    action: str,
    actor: str,
    correlation_id: UUID,
) -> MemoryRecord:
    """Apply one validated lifecycle transition, publish `memory.lifecycle.
    transitioned`, and audit-log it. Public (not `_`-prefixed) because
    `workers/consolidation_worker.py` reuses this for both merge-driven and
    idle-driven transitions -- lifecycle-transition correctness (version-conflict
    handling, validity checking, audit logging) belongs in exactly one place, not
    duplicated between the API path and the worker path."""
    existing = await _require(repository, memory_id, user_id=user_id)
    if next_state == existing.lifecycle_state:
        return existing
    if not lifecycle.is_valid_transition(existing.lifecycle_state, next_state):
        raise ValueError(
            f"Invalid lifecycle transition {existing.lifecycle_state} -> {next_state} "
            f"for memory {memory_id}."
        )
    updated = existing.model_copy(
        update={
            "lifecycle_state": next_state,
            "updated_at": datetime.now(UTC),
            "version": existing.version + 1,
        }
    )
    outbox_event = OutboxEvent(
        subject="memory.lifecycle.transitioned",
        payload={
            "memory_id": str(memory_id),
            "user_id": str(user_id),
            "previous_state": existing.lifecycle_state.value,
            "new_state": next_state.value,
            "reason": reason,
        },
        correlation_id=correlation_id,
    )
    result = await repository.update(
        updated, expected_version=existing.version, outbox_event=outbox_event
    )
    await repository.append_audit_log(memory_id=memory_id, action=action, actor=actor)
    return result


async def schedule_deletion(
    repository: MemoryRepository, memory_id: UUID, *, user_id: UUID, correlation_id: UUID
) -> MemoryRecord:
    """`DELETE /v1/memories/{id}` -- always moves to `scheduled_for_deletion`, never
    an immediate hard delete (docs/design/phase-1/01-memory-engine.md §14)."""
    existing = await _require(repository, memory_id, user_id=user_id)
    next_state = lifecycle.next_state_on_explicit_trigger(
        existing.lifecycle_state, lifecycle.ExplicitTrigger.USER_DELETE_REQUEST
    )
    return await transition_lifecycle(
        repository,
        memory_id,
        user_id=user_id,
        next_state=next_state,
        reason="explicit user delete request",
        action="deleted",
        actor=str(user_id),
        correlation_id=correlation_id,
    )


async def reactivate(
    repository: MemoryRepository, memory_id: UUID, *, user_id: UUID, correlation_id: UUID
) -> MemoryRecord:
    """`POST /v1/memories/{id}/reactivate` -- any access to a `weak`, `archived`, or
    `scheduled_for_deletion` (within grace period) memory reactivates it."""
    existing = await _require(repository, memory_id, user_id=user_id)
    next_state = lifecycle.next_state_on_access(existing.lifecycle_state)
    return await transition_lifecycle(
        repository,
        memory_id,
        user_id=user_id,
        next_state=next_state,
        reason="reactivated on access",
        action="reactivated",
        actor=str(user_id),
        correlation_id=correlation_id,
    )
