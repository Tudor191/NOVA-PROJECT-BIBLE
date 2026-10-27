"""Real-Postgres verification of `PostgresMemoryRepository`'s timestamp handling.

**Why this file exists, and why it is the only tier that can prove the point.**
Phase 4E's AC-6 turns on a memory carrying a `created_at` weeks in the past, and
`create_long_term()` used to build its `MemoryRecordORM` without `created_at` or
`updated_at` at all -- so PostgreSQL's `server_default=func.now()` supplied both
and the caller's values were discarded. A fake repository cannot find that: it
stores whatever object it is handed, so the bug is invisible anywhere above the
real driver. The column defaults are the defect, and the real column is the only
place to assert against them (TDD 4E §20.1).

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run test`
invocation (ADR-033) -- requires Docker. **Not executed in the environment this
file was written in** (no reachable Docker daemon); see `nova_testkit.postgres`'s
own module docstring for the same caveat.

**This file defines its own container rather than using `nova_testkit`'s
`postgres_container`, and the reason is a real finding, not a preference.**
`nova_testkit.postgres` pins `postgres:16-alpine` and its docstring says that
image *"Matches infra/docker/docker-compose.local.yml's `postgres` service
exactly"*. It no longer does: the compose file was corrected to
`pgvector/pgvector:pg16` precisely because this engine's migration `0001` opens
with `CREATE EXTENSION IF NOT EXISTS vector`, which fails on the alpine image with
*"extension \"vector\" is not available"*. Against the shared fixture this
engine's schema cannot be created at all.

That drift is **reported, not fixed here** (protocol §13.1): changing the shared
fixture's image would change every other engine's real-infra runs, which is
outside Phase 4E's scope. What this file does instead is exactly the division of
labour `nova_testkit.postgres` documents -- *"nova-testkit provides generic
pieces, the engine's own test composes them"* -- it composes its own container
from the image its own architecture requires, and reuses `run_alembic_upgrade`
unchanged.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from nova_memory_engine.domain.models import MemoryRecord, MemoryType, PrivacyLevel
from nova_memory_engine.repository.postgres_memory_repository import PostgresMemoryRepository
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"

_PGVECTOR_IMAGE = "pgvector/pgvector:pg16"
"""Matches `infra/docker/docker-compose.local.yml`'s `postgres` service, which is
what `nova_testkit`'s own fixture claims and no longer does -- see the module
docstring. Still PostgreSQL 16, so nothing else about the tier changes."""


@pytest.fixture(scope="module")
def pgvector_container() -> Iterator[PostgresContainer]:
    with PostgresContainer(_PGVECTOR_IMAGE, driver="asyncpg") as container:
        os.environ["MEMORY_ENGINE_POSTGRES_DSN"] = container.get_connection_url()
        run_alembic_upgrade(_ALEMBIC_INI)
        yield container


@pytest.fixture
async def session_factory(
    pgvector_container: PostgresContainer,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(pgvector_container.get_connection_url())
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.fixture
def repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> PostgresMemoryRepository:
    return PostgresMemoryRepository(session_factory)


def _record(**overrides: object) -> MemoryRecord:
    defaults: dict[str, object] = {
        "memory_type": MemoryType.EPISODIC,
        "content": "Refactored the ingest pipeline's retry loop.",
        "user_id": uuid4(),
        "privacy_level": PrivacyLevel.INTERNAL,
    }
    return MemoryRecord(**{**defaults, **overrides})  # type: ignore[arg-type]


async def test_a_historical_created_at_is_persisted_not_overwritten_by_the_column_default(
    repository: PostgresMemoryRepository,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """**The AC-6 property.** A memory dated weeks in the past stays dated weeks
    in the past, in the column, after the round trip.

    Asserted against the raw column as well as the returned object: `create_long_term`
    ends with `session.refresh(orm)`, so a returned value that looked right would
    still have proved the write, but re-reading in a *separate* session proves it
    is committed rather than merely present in the identity map.
    """
    written_at = datetime.now(UTC) - timedelta(days=45)
    record = _record(created_at=written_at, updated_at=written_at)

    returned = await repository.create_long_term(record)

    assert returned.created_at == written_at, (
        "create_long_term returned a different created_at than it was given -- the "
        "column default overwrote it, which is the defect TDD 4E §20.1 fixes"
    )
    assert returned.updated_at == written_at

    async with session_factory() as session:
        row = (
            await session.execute(
                text("SELECT created_at, updated_at FROM memory.memory_record WHERE id = :id"),
                {"id": record.id},
            )
        ).one()
    assert row.created_at == written_at, "the persisted column is not the value written"
    assert row.updated_at == written_at


async def test_the_round_trip_is_lossless_for_both_timestamps(
    repository: PostgresMemoryRepository,
) -> None:
    """`get()` returns what `create_long_term()` was handed. Before the fix this
    failed silently: `_memory_to_domain` reads both columns back, so the caller
    got a *different* record than it wrote, with nothing raised."""
    created = datetime.now(UTC) - timedelta(days=200)
    updated = datetime.now(UTC) - timedelta(days=190)
    record = _record(created_at=created, updated_at=updated)

    await repository.create_long_term(record)
    fetched = await repository.get(record.id, user_id=record.user_id)

    assert fetched is not None
    assert fetched.created_at == created
    assert fetched.updated_at == updated


async def test_an_ordinary_write_still_lands_at_roughly_now(
    repository: PostgresMemoryRepository,
) -> None:
    """The anti-regression control for everything that is *not* AC-6.

    Nearly every caller goes through `long_term.write()`, which supplies
    `MemoryRecord`'s own `_utcnow()` default rather than a historical value. This
    asserts the fix did not change what those callers observe -- the authority
    moved from Postgres's `func.now()` to the application's `datetime.now(UTC)`,
    and both are timezone-aware UTC taken within the same transaction.
    """
    before = datetime.now(UTC)
    record = _record()
    returned = await repository.create_long_term(record)
    after = datetime.now(UTC)

    assert before <= returned.created_at <= after
    assert returned.created_at.tzinfo is not None, "the column must stay timezone-aware"


async def test_the_timeline_query_orders_by_the_persisted_created_at(
    repository: PostgresMemoryRepository,
) -> None:
    """The half AC-6's reconstruction depends on: historical rows must sort by
    when they *happened*, not by when they were inserted.

    All three rows below are inserted within milliseconds of each other, so a
    `created_at` supplied by the column default would order them arbitrarily by
    insertion. Their supplied timestamps are deliberately inserted out of order.
    """
    user_id = uuid4()
    project_id = uuid4()
    now = datetime.now(UTC)
    ages = [timedelta(days=30), timedelta(days=90), timedelta(days=2)]
    for age in ages:
        await repository.create_long_term(
            _record(user_id=user_id, project_id=project_id, created_at=now - age)
        )

    rows = await repository.list_by_timeline(user_id=user_id, project_id=project_id, limit=10)

    assert [r.created_at for r in rows] == sorted(
        (now - age for age in ages), reverse=True
    ), "list_by_timeline did not order by the persisted created_at"
    assert (rows[0].created_at - rows[-1].created_at) > timedelta(days=80), (
        "the spread between the oldest and newest row was not preserved"
    )
