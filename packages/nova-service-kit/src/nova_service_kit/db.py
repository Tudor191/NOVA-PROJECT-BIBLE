"""Async SQLAlchemy engine/session factory construction -- identical across
every engine with a Postgres schema (Project Health Review, August 2026;
`docs/design/nova-service-kit/boilerplate-extraction-proposal.md` Extraction B).
Zero engine-specific knowledge: takes a DSN, returns a plain SQLAlchemy engine
and session factory, nothing more.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(dsn: str) -> AsyncEngine:
    return create_async_engine(dsn, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
