"""SQLAlchemy ORM models -- the `agent_os` Postgres schema's `agent_instance`
table, exactly as specified in docs/design/phase-3/08-tdd-3e-agent-os.md §4.
`Base.metadata` is what Alembic's `env.py` autogenerates migrations against;
`alembic/versions/0001_initial_schema.py` is hand-written to match this file
precisely, the same convention as every prior engine.

`agent_package` (TDD 3E §5) is deliberately not defined here -- it is
`agent-os/registry`'s own table, a separate, not-yet-built component; this
migration only creates the shared `agent_os` schema (`CREATE SCHEMA IF NOT
EXISTS`) and the one table this component owns.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="agent_os")


class AgentInstanceORM(Base):
    """The `AgentInstance` model (TDD 3E §4), field-for-field."""

    __tablename__ = "agent_instance"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    agent_package_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    execution_backend: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_task_node_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    supervisor_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    health_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="unknown")
