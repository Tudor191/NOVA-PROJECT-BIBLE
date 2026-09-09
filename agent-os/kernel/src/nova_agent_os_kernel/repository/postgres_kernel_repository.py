"""`PostgresKernelRepository` -- implements `domain.ports.KernelRepository`
against SQLAlchemy async, per the schema in
docs/design/phase-3/08-tdd-3e-agent-os.md §4 and, since Phase 4C milestone
4C.2b, the append-only `agent_activity` table.

`insert()` translates an `id` primary-key violation
(`sqlalchemy.exc.IntegrityError`) into `AgentInstanceAlreadyExistsError` --
the natural-key idempotency guard convention every other Phase 3 repository
already establishes (`action-engine`'s `ActionAlreadyExistsError`,
`capability-engine`'s `CapabilityAlreadyExistsError`).

**Transactional participation (4C.2b).** `insert` and `update_status` each
take an optional `activity`, added to the *same session* before the single
commit. One `async with self._session_factory()` block is the transaction;
adding a row to it needs no coordination mechanism, which is why the port
gained a parameter rather than the codebase gaining a unit-of-work
abstraction. `append_activity` is for activity that accompanies no
transition and correctly commits alone.

**No update or delete of an activity row exists in this file.** That is the
append-only guarantee, and `tests/unit/test_activity.py` asserts the
absence rather than trusting it.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_agent_os_kernel.domain.activity import (
    ActivityPage,
    AgentActivity,
    AgentActivityKind,
    decode_cursor,
    encode_cursor,
)
from nova_agent_os_kernel.domain.models import AgentInstance
from nova_agent_os_kernel.domain.ports import AgentInstanceAlreadyExistsError
from nova_agent_os_kernel.repository.models import AgentActivityORM, AgentInstanceORM

__all__ = ["PostgresKernelRepository"]


def _to_domain(row: AgentInstanceORM) -> AgentInstance:
    return AgentInstance(
        id=row.id,
        agent_package_id=row.agent_package_id,
        category=row.category,
        execution_backend=row.execution_backend,
        status=row.status,
        assigned_task_node_id=row.assigned_task_node_id,
        supervisor_id=row.supervisor_id,
        started_at=row.started_at,
        health_status=row.health_status,
    )


def _activity_to_domain(row: AgentActivityORM) -> AgentActivity:
    return AgentActivity(
        id=row.id,
        agent_instance_id=row.agent_instance_id,
        occurred_at=row.occurred_at,
        kind=AgentActivityKind(row.kind),
        correlation_id=row.correlation_id,
        detail=dict(row.detail),
    )


def _activity_orm(activity: AgentActivity) -> AgentActivityORM:
    return AgentActivityORM(
        id=activity.id,
        agent_instance_id=activity.agent_instance_id,
        occurred_at=activity.occurred_at,
        kind=activity.kind.value,
        correlation_id=activity.correlation_id,
        detail=activity.detail,
    )


class PostgresKernelRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def find_by_id(self, instance_id: UUID) -> AgentInstance | None:
        async with self._session_factory() as session:
            row = await session.get(AgentInstanceORM, instance_id)
            return _to_domain(row) if row is not None else None

    async def insert(
        self, instance: AgentInstance, *, activity: AgentActivity | None = None
    ) -> AgentInstance:
        row = AgentInstanceORM(
            id=instance.id,
            agent_package_id=instance.agent_package_id,
            category=instance.category,
            execution_backend=instance.execution_backend,
            status=instance.status,
            assigned_task_node_id=instance.assigned_task_node_id,
            supervisor_id=instance.supervisor_id,
            started_at=instance.started_at,
            health_status=instance.health_status,
        )
        async with self._session_factory() as session:
            session.add(row)
            if activity is not None:
                # Same session, therefore the same transaction and the same
                # commit below. The instance and the record of it appearing
                # are one fact.
                session.add(_activity_orm(activity))
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise AgentInstanceAlreadyExistsError(
                    f"agent_instance {instance.id} already exists"
                ) from exc
        return instance

    async def list_by_status(self, status: str) -> list[AgentInstance]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AgentInstanceORM).where(AgentInstanceORM.status == status)
            )
            return [_to_domain(row) for row in result.scalars().all()]

    async def update_status(
        self,
        instance_id: UUID,
        *,
        status: str,
        health_status: str | None = None,
        activity: AgentActivity | None = None,
    ) -> None:
        async with self._session_factory() as session:
            row = await session.get(AgentInstanceORM, instance_id)
            if row is None:
                # An unknown id is a no-op for the transition, so it must be a
                # no-op for the record of the transition too -- otherwise this
                # would write an activity row asserting a change that never
                # happened, on an instance that does not exist.
                return
            row.status = status
            if health_status is not None:
                row.health_status = health_status
            if activity is not None:
                session.add(_activity_orm(activity))
            await session.commit()

    async def append_activity(self, activity: AgentActivity) -> None:
        async with self._session_factory() as session:
            session.add(_activity_orm(activity))
            await session.commit()

    async def list_activity(
        self,
        agent_instance_id: UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> ActivityPage:
        """Keyset pagination over `(occurred_at DESC, id DESC)`.

        The predicate is a **row-value comparison** -- `(occurred_at, id) <
        (cursor_occurred_at, cursor_id)` -- not `occurred_at < ts OR
        (occurred_at = ts AND id < id)`. The two are equivalent, and the row
        form is the one Postgres can satisfy with a single index range scan
        on `agent_activity_instance_time_idx` rather than an OR that it may
        turn into a bitmap union.

        `limit + 1` rows are fetched so "is there a next page" is answered by
        a row that exists rather than by comparing counts, which is what lets
        `next_cursor` be `None` exactly when the page is last.
        """
        statement = (
            select(AgentActivityORM)
            .where(AgentActivityORM.agent_instance_id == agent_instance_id)
            .order_by(AgentActivityORM.occurred_at.desc(), AgentActivityORM.id.desc())
            .limit(limit + 1)
        )
        if cursor is not None:
            # Raises InvalidCursorError, which the caller surfaces rather than
            # silently restarting at page one.
            occurred_at, activity_id = decode_cursor(cursor)
            statement = statement.where(
                tuple_(AgentActivityORM.occurred_at, AgentActivityORM.id)
                < (occurred_at, activity_id)
            )

        async with self._session_factory() as session:
            result = await session.execute(statement)
            rows = list(result.scalars().all())

        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = (
            encode_cursor(page[-1].occurred_at, page[-1].id) if has_more and page else None
        )
        return ActivityPage(
            items=[_activity_to_domain(row) for row in page], next_cursor=next_cursor
        )
