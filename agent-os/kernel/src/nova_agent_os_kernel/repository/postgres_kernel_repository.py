"""`PostgresKernelRepository` -- implements `domain.ports.KernelRepository`
against SQLAlchemy async, per the schema in
docs/design/phase-3/08-tdd-3e-agent-os.md §4 and, since Phase 4C milestone
4C.2b, the append-only `agent_activity` table.

`insert()` translates an `id` primary-key violation
(`sqlalchemy.exc.IntegrityError`) into `AgentInstanceAlreadyExistsError` --
the natural-key idempotency guard convention every other Phase 3 repository
already establishes (`action-engine`'s `ActionAlreadyExistsError`,
`capability-engine`'s `CapabilityAlreadyExistsError`). **Only that
violation.** The translation happens around the instance's own flush, where
nothing else is pending; a constraint the *activity* row violates propagates
as the `IntegrityError` it is.

**Transactional participation (4C.2b).** `insert` and `update_status` each
take an optional `activity`, added to the *same session* before the single
commit. One `async with self._session_factory()` block is the transaction;
adding a row to it needs no coordination mechanism, which is why the port
gained a parameter rather than the codebase gaining a unit-of-work
abstraction. `append_activity` is for activity that accompanies no
transition and correctly commits alone.

**Ordering inside that transaction (fixed 2026-09-10).** `insert` flushes the
`agent_instance` row before adding the activity, because SQLAlchemy orders an
unrelated pair of mappers by name rather than by foreign key -- see the
comment at the call site. The flush changes *when the INSERT is emitted*, not
how many transactions there are: still one block, still one `commit()`.

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
            # **Flushed before the activity is added, and that ordering is
            # load-bearing.** `AgentActivityORM` declares a real foreign key to
            # `agent_instance.id` but no ORM `relationship()`, so SQLAlchemy's
            # unit of work has no dependency edge between the two mappers and
            # falls back to sorting them by mapper name. `AgentActivityORM`
            # sorts before `AgentInstanceORM`, so adding both and committing
            # once emitted the child INSERT first and the foreign key had no
            # parent row yet -- a deterministic `ForeignKeyViolationError`,
            # found by the first CI run that had a real database (4C.2, PR #26).
            #
            # `flush()` emits the INSERT inside the *still-open* transaction.
            # It is not a commit: the single `commit()` below is still the only
            # one, so the instance and its activity remain one atomic fact
            # (decision D-3). If the activity write fails, this flushed row
            # rolls back with it.
            try:
                await session.flush()
            except IntegrityError as exc:
                # The instance row is the only thing pending here, so an
                # integrity error at this point can only be its own id
                # colliding -- which is what makes translating it correct.
                # The blanket `except` this replaces sat around the commit,
                # where it also caught the activity's constraint violations and
                # reported a foreign-key failure as "already exists": the
                # opposite of the truth, and what hid the defect above.
                await session.rollback()
                raise AgentInstanceAlreadyExistsError(
                    f"agent_instance {instance.id} already exists"
                ) from exc

            if activity is not None:
                # Same session, therefore the same transaction and the same
                # commit below. The instance and the record of it appearing
                # are one fact.
                session.add(_activity_orm(activity))
            # Any `IntegrityError` from here propagates untranslated. A
            # constraint the activity violates is not an instance conflict, and
            # mislabelling it would send the next reader after the wrong bug.
            await session.commit()
        return instance

    async def list_by_status(self, status: str) -> list[AgentInstance]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AgentInstanceORM).where(AgentInstanceORM.status == status)
            )
            return [_to_domain(row) for row in result.scalars().all()]

    async def list_instances(self, *, limit: int = 50) -> list[AgentInstance]:
        """Ordered in SQL. `id` breaks a `started_at` tie so the sequence is
        total and repeated reads agree -- the same reason the activity cursor
        carries `id`, and the same failure mode if it did not: two instances
        dispatched in one batch share a `started_at` to the microsecond more
        often than is comfortable."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(AgentInstanceORM)
                .order_by(AgentInstanceORM.started_at.desc(), AgentInstanceORM.id.desc())
                .limit(limit)
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
