"""Real-Postgres test fixtures via `testcontainers` (ADR-033's real-infrastructure
tier; docs/design/nova-testkit/technical-implementation-plan.md §2.3, §3.1).

`postgres_container` starts one throwaway `postgres:16-alpine` container -- the
exact image `infra/docker/docker-compose.local.yml`'s `postgres` service already
pins, never chosen independently -- and yields it for the whole test session
(container startup is amortized; per-test isolation comes from `postgres_session`'s
transaction rollback, not from restarting the container).

`run_alembic_upgrade` is the generic migration runner. Every engine's own
`alembic/env.py` resolves its DSN from `Settings().postgres_dsn` (itself an
`<ENGINE>_POSTGRES_DSN` environment variable), never from the Alembic `Config`
object's `sqlalchemy.url` -- confirmed by reading `personality-engine/alembic/
env.py` directly, not assumed. `run_alembic_upgrade` therefore never needs an
engine's own DSN as a parameter: it just invokes `alembic upgrade head` against
whichever `alembic.ini` it is pointed at. The calling engine's own test file is
responsible for setting that engine's own `<ENGINE>_POSTGRES_DSN` environment
variable to the container's connection URL *before* calling this -- exactly the
"nova-testkit provides generic pieces, the engine's own test composes them"
division of labor ADR-033 requires (nova-testkit never imports an engine's own
`Settings`/models/`env.py`).

**Unverified in this environment**: written against `testcontainers==4.13.3`'s
real, installed API -- confirmed by direct introspection (`inspect.signature`
against the package this workspace's own `>=4.9` constraint actually resolves
and locks, not a stray newer version) -- but the container start/migrate/
query/teardown cycle has not been executed here: no Docker daemon is reachable
in this session (`docker info` fails to connect, confirmed). Every
real-Postgres test that uses these fixtures is marked `@pytest.mark.
real_infra` and will not run anywhere until a Docker-capable environment
executes it. Uses the top-level `testcontainers.postgres` import path, not
`testcontainers.community.postgres` -- the latter does not exist at the
version this workspace resolves (it was introduced later than `>=4.9`
requires); the top-level path is confirmed non-deprecated at 4.13.3.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

__all__ = [
    "postgres_container",
    "postgres_engine",
    "postgres_session",
    "run_alembic_upgrade",
]

_POSTGRES_IMAGE = "postgres:16-alpine"
"""Matches infra/docker/docker-compose.local.yml's `postgres` service exactly."""


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """One throwaway, session-scoped Postgres container. `driver="asyncpg"`
    makes `get_connection_url()` return a `postgresql+asyncpg://...` URL
    directly usable by `create_async_engine` -- this project's own driver for
    every real repository (never `psycopg2`, the container class's own
    default)."""
    with PostgresContainer(_POSTGRES_IMAGE, driver="asyncpg") as container:
        yield container


def run_alembic_upgrade(alembic_ini_path: str | Path) -> None:
    """Run `alembic upgrade head` against whatever DSN the target `env.py`
    resolves from its own `Settings()`. Generic by design -- takes only a path
    to an `alembic.ini`, never an engine's own models/Settings/config module.
    Call `os.environ["<ENGINE>_POSTGRES_DSN"] = postgres_container.
    get_connection_url()` first, from the engine's own test file, so that
    `Settings()` resolves to the container rather than to `docker-compose.
    local.yml`'s `postgres` service (or a bare local default)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(alembic_ini_path))
    command.upgrade(cfg, "head")


@pytest.fixture
async def postgres_engine(postgres_container: PostgresContainer) -> AsyncIterator[AsyncEngine]:
    """A real `AsyncEngine` connected to `postgres_container`. Does not run
    migrations itself -- an engine's own session-scoped fixture should call
    `run_alembic_upgrade` once (against this same container) before any test
    using this fixture runs its first query."""
    engine = create_async_engine(postgres_container.get_connection_url(), pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest.fixture
async def postgres_session(postgres_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """One test = one outer transaction, unconditionally rolled back at
    teardown -- real Postgres, zero cross-test state leakage, no need to
    restart the container or truncate tables between tests (implementation
    plan §2.4). `join_transaction_mode="create_savepoint"` is SQLAlchemy 2.0's
    documented mechanism for joining a `Session` to an already-open connection
    transaction: repository code that calls `session.begin()`/`commit()`
    internally (this project's own write-path convention,
    `repository/db.py`) transparently becomes a SAVEPOINT instead of a real
    commit, so production repository code runs completely unmodified against
    this fixture and still gets rolled back at teardown regardless of how many
    times it committed."""
    async with postgres_engine.connect() as connection:
        outer_transaction = await connection.begin()
        session_factory = async_sessionmaker(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        session = session_factory()
        try:
            yield session
        finally:
            await session.close()
            await outer_transaction.rollback()
