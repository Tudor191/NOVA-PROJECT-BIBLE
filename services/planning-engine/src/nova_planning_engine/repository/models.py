"""SQLAlchemy ORM models -- the `planning` Postgres schema, exactly as
specified in docs/design/phase-3/05-tdd-3b-planning-engine.md §4.
`Base.metadata` is what Alembic's `env.py` autogenerates migrations
against; `alembic/versions/0001_initial_schema.py` is hand-written to
match this file precisely, the same convention as every prior engine
(e.g. `action-engine`'s `repository/models.py`).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, MetaData, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    metadata = MetaData(schema="planning")


class TaskGraphORM(Base):
    """TDD 3B §4: `id` (PK), `root_objective`, `critical_path` (JSONB array
    of UUIDs), `approved_at` (nullable, §5), `created_at`, `updated_at`."""

    __tablename__ = "task_graph"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    root_objective: Mapped[str] = mapped_column(Text, nullable=False)
    critical_path: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    nodes: Mapped[list[TaskNodeORM]] = relationship(
        back_populates="task_graph", order_by="TaskNodeORM.created_at"
    )


class TaskNodeORM(Base):
    """TDD 3B §4: `id` (PK), `task_graph_id` (FK), `objective`, `depends_on`
    (JSONB array of UUIDs), `assigned_agent_category` (nullable),
    `estimated_effort` (JSONB, embedding `Estimate`), `risk`, `status`,
    `created_at`, `updated_at`."""

    __tablename__ = "task_node"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    task_graph_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("planning.task_graph.id"), nullable=False, index=True
    )
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    depends_on: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    assigned_agent_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_effort: Mapped[dict] = mapped_column(JSONB, nullable=False)
    risk: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task_graph: Mapped[TaskGraphORM] = relationship(back_populates="nodes")


class OutboxEventORM(Base):
    """TDD 3B §4: "`outbox_event` table follows the standard
    transactional-outbox pattern every prior engine uses" -- field-for-field
    identical to `memory-engine`'s own `outbox_event` table."""

    __tablename__ = "outbox_event"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    causation_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
