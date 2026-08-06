"""Alembic environment for Knowledge Engine's `knowledge` Postgres schema.

Async-aware per SQLAlchemy 2.0's documented pattern (`connection.run_sync`) --
Knowledge Engine's own runtime is fully async (docs/architecture/03-backend-
architecture.md §1), so migrations should be too, rather than pulling in a second,
sync-only driver just for this one tool.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from nova_knowledge_engine.config import Settings
from nova_knowledge_engine.repository.models import Base
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _dsn() -> str:
    return Settings().postgres_dsn


def run_migrations_offline() -> None:
    context.configure(
        url=_dsn(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table="alembic_version_knowledge",
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    # `alembic_version` deliberately stays in the connection's default schema
    # (not `knowledge`) -- the `knowledge` schema doesn't exist yet on a fresh
    # database until migration 0001's own `CREATE SCHEMA` statement runs, so
    # pointing Alembic's own bookkeeping table at it would be a chicken-and-egg
    # problem.
    # `version_table` is namespaced per engine (not the default
    # "alembic_version") because every engine's DSN points at the same
    # physical `nova` database (infra/docker/docker-compose.local.yml) --
    # without this, whichever engine's migration runs first would silently
    # claim the shared bookkeeping row and every other engine's migration
    # would believe it was already at head and create nothing. Discovered
    # and fixed during Phase 2C's own real-Postgres verification.
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table="alembic_version_knowledge",
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _dsn()
    connectable = async_engine_from_config(
        configuration, prefix="sqlalchemy.", poolclass=pool.NullPool
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
