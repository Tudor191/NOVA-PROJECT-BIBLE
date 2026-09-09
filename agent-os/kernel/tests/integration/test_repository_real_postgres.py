"""Real-Postgres verification of `PostgresKernelRepository` -- real schema
(via this component's own Alembic migration chain,
`0001_initial_schema.py`), real INSERT/SELECT/UPDATE round trips against
the `agent_os.agent_instance` table, including the `id` primary-key
uniqueness -> `AgentInstanceAlreadyExistsError` translation. Mirrors
`action-engine`'s own `test_repository_real_postgres.py` convention.

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run
test` invocation (ADR-033) -- requires Docker.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from nova_agent_os_kernel.domain.activity import (
    AgentActivity,
    AgentActivityKind,
    InvalidCursorError,
    encode_cursor,
)
from nova_agent_os_kernel.domain.models import AgentInstance
from nova_agent_os_kernel.domain.ports import AgentInstanceAlreadyExistsError
from nova_agent_os_kernel.repository.postgres_kernel_repository import PostgresKernelRepository
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["AGENT_OS_KERNEL_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
def repository(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> PostgresKernelRepository:
    return PostgresKernelRepository(postgres_session_factory)


def _instance(**overrides: object) -> AgentInstance:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "agent_package_id": uuid4(),
        "category": "research",
        "execution_backend": "inprocess",
        "status": "running",
        "assigned_task_node_id": uuid4(),
        "started_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return AgentInstance(**defaults)


async def test_insert_then_find_by_id_round_trips(
    repository: PostgresKernelRepository,
) -> None:
    instance = _instance()
    assert await repository.find_by_id(instance.id) is None

    inserted = await repository.insert(instance)
    assert inserted == instance

    fetched = await repository.find_by_id(instance.id)
    assert fetched == instance


async def test_insert_round_trips_a_row_with_no_assigned_task_or_supervisor(
    repository: PostgresKernelRepository,
) -> None:
    instance = _instance(assigned_task_node_id=None, supervisor_id=None)
    await repository.insert(instance)

    fetched = await repository.find_by_id(instance.id)
    assert fetched is not None
    assert fetched.assigned_task_node_id is None
    assert fetched.supervisor_id is None


async def test_inserting_a_duplicate_id_raises_agent_instance_already_exists(
    repository: PostgresKernelRepository,
) -> None:
    instance = _instance()
    await repository.insert(instance)

    duplicate = _instance(id=instance.id)
    with pytest.raises(AgentInstanceAlreadyExistsError):
        await repository.insert(duplicate)


async def test_list_by_status_returns_only_matching_rows(
    repository: PostgresKernelRepository,
) -> None:
    running = await repository.insert(_instance(status="running"))
    await repository.insert(_instance(status="completed"))

    running_rows = await repository.list_by_status("running")
    assert [row.id for row in running_rows] == [running.id]


async def test_update_status_persists(repository: PostgresKernelRepository) -> None:
    instance = await repository.insert(_instance())

    await repository.update_status(instance.id, status="failed")

    fetched = await repository.find_by_id(instance.id)
    assert fetched is not None
    assert fetched.status == "failed"


async def test_update_status_on_unknown_id_is_a_no_op(
    repository: PostgresKernelRepository,
) -> None:
    await repository.update_status(uuid4(), status="failed")  # must not raise


# --- agent_activity, Phase 4C milestone 4C.2b -------------------------------
#
# These exist because the in-memory fake cannot prove any of it. The ordering
# is produced by a real `ORDER BY ... DESC` and paged by a real row-value
# comparison; the foreign key and the `kind` CHECK are enforced by Postgres,
# not by Python. A Python `sorted()` agreeing with a SQL collation, or a dict
# accepting a row a constraint would reject, is exactly the kind of agreement
# that holds until it does not.
#
# `0002_agent_activity.py` is applied by the same session-scoped
# `run_alembic_upgrade` above, so a table these tests can write to is itself
# the migration test: nothing here would run against an unmigrated schema.


def _activity(
    agent_instance_id: UUID,
    *,
    occurred_at: datetime | None = None,
    kind: AgentActivityKind = AgentActivityKind.DISPATCHED,
    activity_id: UUID | None = None,
    correlation_id: UUID | None = None,
    detail: dict | None = None,
) -> AgentActivity:
    return AgentActivity(
        id=activity_id or uuid4(),
        agent_instance_id=agent_instance_id,
        occurred_at=occurred_at or datetime.now(UTC),
        kind=kind,
        correlation_id=correlation_id,
        detail=detail if detail is not None else {},
    )


async def test_the_migration_created_the_activity_table_with_its_index(
    postgres_session: AsyncSession,
) -> None:
    """`0002` applied, and applied with the index the keyset query depends on.
    Without it every page is a sort of the whole instance's history."""
    tables = await postgres_session.execute(
        text(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'agent_os' ORDER BY tablename"
        )
    )
    assert "agent_activity" in [row[0] for row in tables]

    indexes = await postgres_session.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE schemaname = 'agent_os' AND tablename = 'agent_activity'"
        )
    )
    assert "agent_activity_instance_time_idx" in [row[0] for row in indexes]


async def test_activity_round_trips_through_real_postgres(
    repository: PostgresKernelRepository,
) -> None:
    instance = await repository.insert(_instance())
    occurred_at = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    correlation_id = uuid4()
    activity = _activity(
        instance.id,
        occurred_at=occurred_at,
        kind=AgentActivityKind.PEER_REVIEW,
        correlation_id=correlation_id,
        detail={"reviewer_category": "architect", "peer_validation": "approved"},
    )

    await repository.append_activity(activity)

    page = await repository.list_activity(instance.id)
    assert len(page.items) == 1
    stored = page.items[0]
    assert stored.id == activity.id
    assert stored.agent_instance_id == instance.id
    assert stored.occurred_at == occurred_at
    assert stored.kind is AgentActivityKind.PEER_REVIEW
    assert stored.correlation_id == correlation_id
    assert stored.detail == {"reviewer_category": "architect", "peer_validation": "approved"}


# --- correlation_id against real Postgres -----------------------------------


async def test_the_migration_created_correlation_id_as_a_nullable_uuid(
    postgres_session: AsyncSession,
) -> None:
    """The column exists, is a real `uuid`, is nullable, and carries no
    default -- read from the catalogue rather than trusted from the ORM."""
    result = await postgres_session.execute(
        text(
            "SELECT data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema = 'agent_os' AND table_name = 'agent_activity' "
            "AND column_name = 'correlation_id'"
        )
    )
    row = result.one()
    assert row.data_type == "uuid"
    assert row.is_nullable == "YES"
    assert row.column_default is None


async def test_a_null_correlation_id_is_accepted_and_read_back_as_none(
    repository: PostgresKernelRepository,
) -> None:
    """"No correlation is known" is a legitimate, persistable state. It must
    not be rejected, and must not come back as anything other than `None`."""
    instance = await repository.insert(_instance())

    await repository.append_activity(_activity(instance.id, correlation_id=None))

    page = await repository.list_activity(instance.id)
    assert [a.correlation_id for a in page.items] == [None]


async def test_correlation_id_is_not_part_of_the_ordering_index(
    postgres_session: AsyncSession,
) -> None:
    """A join key, not an ordering key. If it entered the index, it would
    almost certainly have entered the ORDER BY with it."""
    result = await postgres_session.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE schemaname = 'agent_os' AND tablename = 'agent_activity' "
            "AND indexname = 'agent_activity_instance_time_idx'"
        )
    )
    indexdef = result.scalar_one()
    assert "occurred_at DESC" in indexdef
    assert "id DESC" in indexdef
    assert "correlation_id" not in indexdef


async def test_real_ordering_ignores_correlation_id(
    repository: PostgresKernelRepository,
) -> None:
    """Written with correlation ids in the *opposite* order to their
    timestamps, so a real `ORDER BY` that included provenance -- or used it as
    a tie-break -- would return a visibly different sequence."""
    instance = await repository.insert(_instance())
    base = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    correlation_ids = sorted((uuid4() for _ in range(3)), reverse=True)
    for offset, correlation_id in enumerate(correlation_ids):
        await repository.append_activity(
            _activity(
                instance.id,
                occurred_at=base + timedelta(minutes=offset),
                correlation_id=correlation_id,
            )
        )

    page = await repository.list_activity(instance.id)

    assert [a.occurred_at for a in page.items] == [
        base + timedelta(minutes=2),
        base + timedelta(minutes=1),
        base,
    ]
    assert [a.correlation_id for a in page.items] == list(reversed(correlation_ids))


async def test_real_ordering_is_undisturbed_by_null_correlation_ids(
    repository: PostgresKernelRepository,
) -> None:
    """Postgres sorts NULLs first or last depending on direction. If
    `correlation_id` were in the ORDER BY, the unset row would jump to an end
    instead of holding its place in time."""
    instance = await repository.insert(_instance())
    base = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    for offset, correlation_id in ((0, uuid4()), (1, None), (2, uuid4())):
        await repository.append_activity(
            _activity(
                instance.id,
                occurred_at=base + timedelta(minutes=offset),
                correlation_id=correlation_id,
            )
        )

    page = await repository.list_activity(instance.id)

    assert [a.correlation_id is None for a in page.items] == [False, True, False]


async def test_real_paging_is_unaffected_by_correlation_id(
    repository: PostgresKernelRepository,
) -> None:
    """Every row shares a timestamp, so the `(occurred_at, id)` tie-break does
    all the work while each row carries distinct provenance. No row skipped,
    none repeated, and no cursor that depends on `correlation_id`."""
    instance = await repository.insert(_instance())
    shared = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    ids = {uuid4() for _ in range(6)}
    for activity_id in ids:
        await repository.append_activity(
            _activity(
                instance.id,
                occurred_at=shared,
                activity_id=activity_id,
                correlation_id=uuid4(),
            )
        )

    seen: list[UUID] = []
    cursor: str | None = None
    for _ in range(10):
        page = await repository.list_activity(instance.id, limit=2, cursor=cursor)
        seen.extend(a.id for a in page.items)
        cursor = page.next_cursor
        if cursor is None:
            break

    assert cursor is None, "paging did not terminate"
    assert set(seen) == ids
    assert len(set(seen)) == len(seen), "a row was returned on two pages"


async def test_activity_is_queryable_by_correlation_id(
    postgres_session: AsyncSession, repository: PostgresKernelRepository
) -> None:
    """The point of keeping provenance first-class rather than in `detail`:
    it can be joined and filtered on with ordinary SQL. Asserted so that a
    later move into JSON would break a test rather than quietly removing a
    capability."""
    instance = await repository.insert(_instance())
    wanted = uuid4()
    await repository.append_activity(_activity(instance.id, correlation_id=wanted))
    await repository.append_activity(_activity(instance.id, correlation_id=uuid4()))
    await repository.append_activity(_activity(instance.id, correlation_id=None))

    result = await postgres_session.execute(
        text(
            "SELECT count(*) FROM agent_os.agent_activity "
            "WHERE correlation_id = :correlation_id"
        ),
        {"correlation_id": wanted},
    )
    assert result.scalar_one() == 1


async def test_the_foreign_key_rejects_activity_for_an_unknown_instance(
    repository: PostgresKernelRepository,
) -> None:
    """Real referential integrity, not a Python guard. `agent_instance`'s own
    `agent_package_id` has no constraint because it points across a component
    boundary; this one points at a table the same component migrates, so it
    is enforced."""
    with pytest.raises(IntegrityError):
        await repository.append_activity(_activity(uuid4()))


async def test_the_check_constraint_rejects_a_kind_outside_the_vocabulary(
    postgres_session: AsyncSession, repository: PostgresKernelRepository
) -> None:
    """The negative control for the closed vocabulary at the *database*
    boundary. The domain enum stops a caller going through `AgentActivity`;
    this proves a caller bypassing it still cannot persist an invalid kind.
    """
    instance = await repository.insert(_instance())

    with pytest.raises(IntegrityError):
        await postgres_session.execute(
            text(
                "INSERT INTO agent_os.agent_activity "
                "(id, agent_instance_id, occurred_at, kind, detail) "
                "VALUES (:id, :instance_id, :occurred_at, 'not_a_real_kind', '{}')"
            ),
            {
                "id": uuid4(),
                "instance_id": instance.id,
                "occurred_at": datetime.now(UTC),
            },
        )
    await postgres_session.rollback()


@pytest.mark.parametrize("kind", list(AgentActivityKind), ids=lambda k: k.value)
async def test_every_allowed_kind_persists(
    repository: PostgresKernelRepository, kind: AgentActivityKind
) -> None:
    """The other half of the control above: the CHECK must admit all six.
    A constraint that rejected a legitimate kind would be found only when
    that transition first occurred in production."""
    instance = await repository.insert(_instance())

    await repository.append_activity(_activity(instance.id, kind=kind))

    page = await repository.list_activity(instance.id)
    assert [a.kind for a in page.items] == [kind]


async def test_real_ordering_is_newest_first(
    repository: PostgresKernelRepository,
) -> None:
    instance = await repository.insert(_instance())
    base = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    # Inserted oldest-last so insertion order cannot produce the expected
    # answer by accident.
    for minutes in (5, 0, 10):
        await repository.append_activity(
            _activity(instance.id, occurred_at=base + timedelta(minutes=minutes))
        )

    page = await repository.list_activity(instance.id)

    assert [a.occurred_at for a in page.items] == [
        base + timedelta(minutes=10),
        base + timedelta(minutes=5),
        base,
    ]


async def test_real_ordering_breaks_timestamp_ties_by_id_descending(
    repository: PostgresKernelRepository,
) -> None:
    """The case a `server_default now()` timestamp would produce for every row
    written in one transaction, and the reason `id` is in the ordering key."""
    instance = await repository.insert(_instance())
    shared = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    ids = sorted(uuid4() for _ in range(5))
    for activity_id in ids:
        await repository.append_activity(
            _activity(instance.id, occurred_at=shared, activity_id=activity_id)
        )

    page = await repository.list_activity(instance.id)

    assert [a.id for a in page.items] == list(reversed(ids))


async def test_real_paging_walks_every_row_exactly_once_across_a_tie(
    repository: PostgresKernelRepository,
) -> None:
    """The end-to-end property, against a real row-value comparison: no row
    skipped, none repeated, with every timestamp identical so the composite
    key is doing all of the work."""
    instance = await repository.insert(_instance())
    shared = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    ids = {uuid4() for _ in range(7)}
    for activity_id in ids:
        await repository.append_activity(
            _activity(instance.id, occurred_at=shared, activity_id=activity_id)
        )

    seen: list[UUID] = []
    cursor: str | None = None
    for _ in range(10):  # bounded: a broken cursor must fail, not hang
        page = await repository.list_activity(instance.id, limit=2, cursor=cursor)
        seen.extend(a.id for a in page.items)
        cursor = page.next_cursor
        if cursor is None:
            break

    assert cursor is None, "paging did not terminate"
    assert set(seen) == ids
    assert len(set(seen)) == len(seen), "a row was returned on two pages"


async def test_real_cursor_past_the_last_row_returns_an_empty_page(
    repository: PostgresKernelRepository,
) -> None:
    instance = await repository.insert(_instance())
    await repository.append_activity(
        _activity(instance.id, occurred_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC))
    )

    beyond = encode_cursor(datetime(2020, 1, 1, tzinfo=UTC), UUID(int=0))
    page = await repository.list_activity(instance.id, cursor=beyond)

    assert page.items == []
    assert page.next_cursor is None


async def test_real_invalid_cursor_raises_before_touching_the_database(
    repository: PostgresKernelRepository,
) -> None:
    instance = await repository.insert(_instance())

    with pytest.raises(InvalidCursorError):
        await repository.list_activity(instance.id, cursor="not-a-cursor!!")


async def test_real_activity_is_scoped_to_its_own_instance(
    repository: PostgresKernelRepository,
) -> None:
    first = await repository.insert(_instance())
    second = await repository.insert(_instance())
    await repository.append_activity(_activity(first.id))
    await repository.append_activity(_activity(second.id))
    await repository.append_activity(_activity(second.id))

    assert len((await repository.list_activity(first.id)).items) == 1
    assert len((await repository.list_activity(second.id)).items) == 2


# --- transactional participation, against real Postgres ---------------------


async def test_insert_commits_the_instance_and_its_activity_together(
    repository: PostgresKernelRepository,
) -> None:
    instance = _instance()

    await repository.insert(
        instance, activity=_activity(instance.id, kind=AgentActivityKind.DISPATCHED)
    )

    assert await repository.find_by_id(instance.id) is not None
    page = await repository.list_activity(instance.id)
    assert [a.kind for a in page.items] == [AgentActivityKind.DISPATCHED]


async def test_a_failed_insert_rolls_back_its_activity_too(
    repository: PostgresKernelRepository,
) -> None:
    """The point of the shared transaction, proven by the failure path: a
    duplicate instance id aborts the whole statement, so the activity row that
    was going to describe it must not survive on its own.
    """
    instance = await repository.insert(_instance())
    orphan = _activity(instance.id, kind=AgentActivityKind.DISPATCHED)

    with pytest.raises(AgentInstanceAlreadyExistsError):
        await repository.insert(instance, activity=orphan)

    page = await repository.list_activity(instance.id)
    assert [a.id for a in page.items] == [], "the activity outlived its rolled-back instance"


async def test_update_status_commits_the_transition_and_its_activity_together(
    repository: PostgresKernelRepository,
) -> None:
    instance = await repository.insert(_instance())

    await repository.update_status(
        instance.id,
        status="completed",
        health_status="healthy",
        activity=_activity(instance.id, kind=AgentActivityKind.COMPLETED),
    )

    fetched = await repository.find_by_id(instance.id)
    assert fetched is not None
    assert fetched.status == "completed"
    assert fetched.health_status == "healthy"
    assert [a.kind for a in (await repository.list_activity(instance.id)).items] == [
        AgentActivityKind.COMPLETED
    ]


async def test_update_status_on_an_unknown_instance_writes_no_activity(
    repository: PostgresKernelRepository,
) -> None:
    unknown = uuid4()

    await repository.update_status(
        unknown,
        status="completed",
        activity=_activity(unknown, kind=AgentActivityKind.COMPLETED),
    )

    assert (await repository.list_activity(unknown)).items == []


# --- regression: agent_instance persistence is untouched by 4C.2b -----------


async def test_insert_without_activity_still_persists_only_the_instance(
    repository: PostgresKernelRepository,
) -> None:
    instance = await repository.insert(_instance())

    fetched = await repository.find_by_id(instance.id)
    assert fetched is not None
    assert fetched.id == instance.id
    assert (await repository.list_activity(instance.id)).items == []


async def test_update_status_without_activity_still_persists_only_the_status(
    repository: PostgresKernelRepository,
) -> None:
    instance = await repository.insert(_instance())

    await repository.update_status(instance.id, status="failed", health_status="unhealthy")

    fetched = await repository.find_by_id(instance.id)
    assert fetched is not None
    assert fetched.status == "failed"
    assert fetched.health_status == "unhealthy"
    assert (await repository.list_activity(instance.id)).items == []
