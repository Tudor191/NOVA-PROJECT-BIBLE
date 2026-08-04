"""Working Memory -- docs/design/phase-1/01-memory-engine.md §2. Redis-backed,
task-scoped; "old information should leave automatically" (Bible Part 3), so this
module never writes to Postgres and has no lifecycle state of its own -- it is
cleared wholesale on task completion, not decayed field-by-field.
"""

from __future__ import annotations

from uuid import UUID

from nova_memory_engine.domain.ports import WorkingMemoryStore


async def remember(
    store: WorkingMemoryStore, *, user_id: UUID, session_id: str, key: str, value: str
) -> None:
    await store.put(user_id=user_id, session_id=session_id, key=key, value=value)


async def recall_all(
    store: WorkingMemoryStore, *, user_id: UUID, session_id: str
) -> dict[str, str]:
    return await store.get_all(user_id=user_id, session_id=session_id)


async def clear(store: WorkingMemoryStore, *, user_id: UUID, session_id: str) -> None:
    """Called on task completion -- Working Memory has no other exit path."""
    await store.clear(user_id=user_id, session_id=session_id)
