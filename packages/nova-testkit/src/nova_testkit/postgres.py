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
    "postgres_session_factory",
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
    local.yml`'s `postgres` service (or a bare local default).

    `script_location` (every engine's `alembic.ini` sets it to the relative
    path `alembic`) is explicitly re-anchored to `alembic_ini_path`'s own
    parent directory rather than left to Alembic's own default resolution --
    confirmed by reading `alembic.util.pyfiles.coerce_resource_to_filename`
    directly, a relative `script_location` resolves against the *process's
    current working directory* at upgrade time, not the ini file's location.
    That happens to match today's convention (`uv run --package <name>
    pytest` runs with cwd already at that engine's own root), but making it
    explicit here means this function is correct regardless of the caller's
    cwd, not merely correct by convention."""
    from alembic import command
    from alembic.config import Config

    ini_path = Path(alembic_ini_path).resolve()
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(ini_path.parent / "alembic"))
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
async def postgres_session_factory(
    postgres_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """A real `async_sessionmaker[AsyncSession]` bound to one rollback-safe
    connection -- this project's own repository constructor shape: every real
    `Postgres*Repository` (confirmed universal across personality-engine,
    communication-engine, perception-engine, and every earlier engine) takes
    `session_factory: async_sessionmaker[AsyncSession]` and creates its own
    sessions internally per call (`async with self._session_factory() as
    db_session, db_session.begin(): ...`), never a single pre-built session.
    Passing this fixture straight into a real repository's constructor is
    therefore the primary, intended way to exercise one -- unmodified
    production code included.

    One test = one outer transaction, unconditionally rolled back at teardown.
    `join_transaction_mode="create_savepoint"` is SQLAlchemy 2.0's documented
    mechanism for joining a `Session` to an already-open connection
    transaction: every session the repository creates from this factory
    becomes a SAVEPOINT instead of a real commit, so a repository method that
    calls `session.begin()`/commits internally still rolls back at teardown
    regardless of how many times, or how many separate sessions, it
    committed."""
    async with postgres_engine.connect() as connection:
        outer_transaction = await connection.begin()
        factory = async_sessionmaker(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield factory
        finally:
            await outer_transaction.rollback()


@pytest.fixture
async def postgres_session(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """One ready-to-use `AsyncSession` from `postgres_session_factory`, for
    tests that run direct queries rather than constructing a repository
    class (e.g. this package's own `test_postgres.py`)."""
    session = postgres_session_factory()
    try:
        yield session
    finally:
        await session.close()
