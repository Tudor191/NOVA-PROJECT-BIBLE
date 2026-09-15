"""`CognitiveStateRepository` against real PostgreSQL.

**`created_at` and `updated_at` are written from the domain object on every
path, never left to the column default.** That is Phase 4E's ratified Option A
applied here from the first line rather than retrofitted: `memory-engine`'s
`create_long_term` shipped building its ORM row from nineteen fields and
omitting exactly these two, so the column defaults fired and a caller's
timestamps were silently discarded while `_memory_to_domain` read different
values back. This engine never has that defect to fix, and
`upsert_thought` returns the **round-tripped** row so a regression would be
visible rather than plausible.

**The only store this engine writes is its own** (TDD 4F §10, §16 control 11).
There is no session factory here pointing at another engine's schema and no
method that could acquire one.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from nova_cognitive_state_engine.domain.models import ActiveThought, AttentionLayer
from nova_cognitive_state_engine.domain.ports import ThoughtNotFoundError
from nova_cognitive_state_engine.repository.models import ActiveThoughtORM

__all__ = ["PostgresCognitiveStateRepository"]


def _to_domain(row: ActiveThoughtORM) -> ActiveThought:
    """The ORM row as the domain type, with its validators re-run.

    Construction is not a formality: a row that somehow violates an invariant
    -- an archived thought at partial progress, a self-dependency -- raises
    here rather than reaching the panel. Reading is the last place to catch a
    write that should never have happened.
    """
    return ActiveThought(
        thought_id=row.thought_id,
        user_id=row.user_id,
        description=row.description,
        priority=row.priority,
        confidence=row.confidence,
        dependencies=tuple(UUID(str(value)) for value in row.dependencies),
        estimated_completion=row.estimated_completion,
        related_memories=tuple(UUID(str(value)) for value in row.related_memories),
        related_projects=tuple(UUID(str(value)) for value in row.related_projects),
        current_progress=row.current_progress,
        attention_layer=AttentionLayer(row.attention_layer),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _values(thought: ActiveThought) -> dict:
    return {
        "thought_id": thought.thought_id,
        "user_id": thought.user_id,
        "description": thought.description,
        "priority": thought.priority,
        "confidence": thought.confidence,
        "current_progress": thought.current_progress,
        "dependencies": [str(value) for value in thought.dependencies],
        "related_memories": [str(value) for value in thought.related_memories],
        "related_projects": [str(value) for value in thought.related_projects],
        "estimated_completion": thought.estimated_completion,
        "attention_layer": thought.attention_layer.value,
        "created_at": thought.created_at,
        "updated_at": thought.updated_at,
    }


class PostgresCognitiveStateRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def upsert_thought(self, thought: ActiveThought) -> ActiveThought:
        """Insert, or replace every mutable column on conflict.

        **`created_at` is excluded from the update set.** A re-upsert of an
        existing thought must not move its creation time -- that field records
        when the reasoning process began, and Part 6's Active Thoughts are
        explicitly *ongoing*, so their age is meaningful. `updated_at` is
        written from the domain object on both paths.
        """
        values = _values(thought)
        statement = (
            pg_insert(ActiveThoughtORM)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[ActiveThoughtORM.thought_id],
                set_={
                    key: values[key] for key in values if key not in ("thought_id", "created_at")
                },
            )
            .returning(ActiveThoughtORM)
        )

        async with self._session_factory() as session, session.begin():
            row = (await session.execute(statement)).scalar_one()
            return _to_domain(row)

    async def get_thought(self, thought_id: UUID) -> ActiveThought:
        async with self._session_factory() as session:
            row = await session.get(ActiveThoughtORM, thought_id)
            if row is None:
                raise ThoughtNotFoundError(f"no active thought with id {thought_id}")
            return _to_domain(row)

    async def list_thoughts(
        self, *, user_id: UUID, layer: AttentionLayer | None = None
    ) -> list[ActiveThought]:
        """Newest-updated first, with `thought_id` as an explicit tiebreaker.

        The tiebreaker is not decoration: two thoughts updated in the same
        transaction share a timestamp to microsecond precision, and without a
        second sort key their relative order is whatever the planner chose that
        run. Phase 4E's real-Postgres tier proved this class of property is not
        provable against a fake, which is why the `real_infra` test asserts it
        against a genuine tie.
        """
        statement = select(ActiveThoughtORM).where(ActiveThoughtORM.user_id == user_id)
        if layer is not None:
            statement = statement.where(ActiveThoughtORM.attention_layer == layer.value)
        statement = statement.order_by(
            ActiveThoughtORM.updated_at.desc(), ActiveThoughtORM.thought_id.desc()
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).scalars().all()
            return [_to_domain(row) for row in rows]

    async def move_layer(self, thought_id: UUID, layer: AttentionLayer) -> ActiveThought:
        """Record a layer change the domain already validated.

        `domain/attention.py::next_layer` decides *whether* a move is legal;
        this method only persists the outcome. Re-implementing the ladder here
        would give it two definitions, and the one in the database would be the
        one nobody reads.
        """
        async with self._session_factory() as session, session.begin():
            row = await session.get(ActiveThoughtORM, thought_id)
            if row is None:
                raise ThoughtNotFoundError(f"no active thought with id {thought_id}")
            row.attention_layer = layer.value
            await session.flush()
            await session.refresh(row)
            return _to_domain(row)
