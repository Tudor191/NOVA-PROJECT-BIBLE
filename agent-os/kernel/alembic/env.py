"""Alembic environment for agent-os/kernel's `agent_os` Postgres schema.

Async-aware per SQLAlchemy 2.0's documented pattern (`connection.run_sync`),
the same convention every prior engine's `env.py` follows.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from nova_agent_os_kernel.config import Settings
from nova_agent_os_kernel.repository.models import Base
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
        version_table="alembic_version_agent_os_kernel",
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    # `alembic_version` deliberately stays in the connection's default schema
    # (not `agent_os`) -- that schema doesn't exist until migration 0001's
    # own `CREATE SCHEMA` statement runs. `version_table` is namespaced per
    # component -- every engine's DSN points at the same physical `nova`
    # database, and a shared default table name would collide (the same
    # Phase 2C real-Postgres fix already applied to every engine's env.py).
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table="alembic_version_agent_os_kernel",
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
