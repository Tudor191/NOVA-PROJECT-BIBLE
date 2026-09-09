"""In-memory `KernelRepository` fake -- mirrors `capability-engine`'s own
`tests/fakes/repository.py` convention: lets `create_app()` be exercised in
`test_health.py` without a real Postgres connection, and lets domain-layer
tests exercise `reconcile_running_instances` without SQLAlchemy at all.

**The activity half holds the same contract the real repository does** (Phase
4C 4C.2b), because a fake that were laxer would let a test pass here and fail
against Postgres:

* the same `(occurred_at DESC, id DESC)` order, keyset-paged the same way --
  and, as there, **`correlation_id` is not part of it**: the sort key below
  names `occurred_at` and `id` only, so a change that started ordering by
  provenance would diverge from Postgres here rather than silently agreeing;
* the same foreign-key rule -- an activity for an unknown instance is refused
  rather than accepted into a dictionary that has no constraint;
* the same append-only surface: no update, no delete;
* the same "unknown instance id writes neither" rule in `update_status`.

`correlation_id` itself needs no handling here: this fake stores the domain
`AgentActivity` whole, so the field round-trips by construction rather than
through a mapping that could drop it. The real repository's mapping is where
that can go wrong, and `test_repository_real_postgres.py` is where it is
checked.

`FakeIntegrityError` stands in for the driver error the real repository
translates. It is deliberately not `sqlalchemy.exc.IntegrityError`: this fake
exists so tests can run without SQLAlchemy, and importing it here to raise a
more realistic type would undo that.
"""

from __future__ import annotations

from uuid import UUID

from nova_agent_os_kernel.domain.activity import (
    ActivityPage,
    AgentActivity,
    decode_cursor,
    encode_cursor,
)
from nova_agent_os_kernel.domain.models import AgentInstance
from nova_agent_os_kernel.domain.ports import AgentInstanceAlreadyExistsError

__all__ = ["FakeForeignKeyViolation", "FakeKernelRepository"]


class FakeForeignKeyViolation(Exception):
    """Raised where real Postgres would reject an activity whose
    `agent_instance_id` matches no row."""


class FakeKernelRepository:
    def __init__(self) -> None:
        self._rows: dict[UUID, AgentInstance] = {}
        self._activity: dict[UUID, AgentActivity] = {}

    # --- agent_instance ---------------------------------------------------

    async def find_by_id(self, instance_id: UUID) -> AgentInstance | None:
        return self._rows.get(instance_id)

    async def insert(
        self, instance: AgentInstance, *, activity: AgentActivity | None = None
    ) -> AgentInstance:
        if instance.id in self._rows:
            raise AgentInstanceAlreadyExistsError(f"agent_instance {instance.id} already exists")
        self._rows[instance.id] = instance
        if activity is not None:
            # After the instance exists, so the FK check below can see it --
            # the same order the real single transaction produces.
            self._append(activity)
        return instance

    async def list_by_status(self, status: str) -> list[AgentInstance]:
        return [row for row in self._rows.values() if row.status == status]

    async def list_instances(self, *, limit: int = 50) -> list[AgentInstance]:
        """Sorted the way `PostgresKernelRepository.list_instances` sorts, so
        an ordering test cannot pass here and fail against real Postgres."""
        ordered = sorted(
            self._rows.values(), key=lambda row: (row.started_at, row.id), reverse=True
        )
        return ordered[:limit]

    async def update_status(
        self,
        instance_id: UUID,
        *,
        status: str,
        health_status: str | None = None,
        activity: AgentActivity | None = None,
    ) -> None:
        row = self._rows.get(instance_id)
        if row is None:
            # No transition, therefore no record of one.
            return
        update: dict[str, str] = {"status": status}
        if health_status is not None:
            update["health_status"] = health_status
        self._rows[instance_id] = row.model_copy(update=update)
        if activity is not None:
            self._append(activity)

    # --- agent_activity (append-only) -------------------------------------

    def _append(self, activity: AgentActivity) -> None:
        if activity.agent_instance_id not in self._rows:
            raise FakeForeignKeyViolation(
                f"no agent_instance {activity.agent_instance_id} for activity {activity.id}"
            )
        self._activity[activity.id] = activity

    async def append_activity(self, activity: AgentActivity) -> None:
        self._append(activity)

    async def list_activity(
        self,
        agent_instance_id: UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> ActivityPage:
        rows = sorted(
            (a for a in self._activity.values() if a.agent_instance_id == agent_instance_id),
            key=lambda a: (a.occurred_at, a.id),
            reverse=True,
        )
        if cursor is not None:
            occurred_at, activity_id = decode_cursor(cursor)
            rows = [a for a in rows if (a.occurred_at, a.id) < (occurred_at, activity_id)]

        page = rows[:limit]
        has_more = len(rows) > limit
        next_cursor = (
            encode_cursor(page[-1].occurred_at, page[-1].id) if has_more and page else None
        )
        return ActivityPage(items=page, next_cursor=next_cursor)
