"""Async SQLAlchemy engine/session factory for the `model_orchestration`
Postgres schema (docs/design/phase-2a/00-ai-model-orchestration-engine.md §4)."""

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
