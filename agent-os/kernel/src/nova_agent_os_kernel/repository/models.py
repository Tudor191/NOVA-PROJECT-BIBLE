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

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, MetaData, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from nova_agent_os_kernel.domain.activity import AgentActivityKind


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


class AgentActivityORM(Base):
    """The append-only `agent_activity` table (Phase 4C milestone 4C.2b).

    Three things here are load-bearing rather than incidental:

    **`occurred_at` has no `server_default`.** Every other timestamp default in
    this repository would resolve to Postgres `now()`, which is transaction-
    *start* time and therefore identical for every row written in one
    transaction -- the exact tie `(occurred_at DESC, id DESC)` exists to break.
    The value is stamped in Python by `domain/activity.py::new_activity`.

    **The foreign key is real.** `agent_instance.agent_package_id` deliberately
    carries no constraint because it points at `agent-os/registry`'s table
    across a component boundary; this points at a table this same component
    owns and migrates, so integrity is enforceable here without that problem.

    **`kind` is constrained in the database, not only in Pydantic.** The domain
    enum rejects an unknown kind at the model boundary, but a caller
    constructing the ORM row directly would bypass it. The `CHECK` makes the
    closed vocabulary true of the table itself, and is generated from
    `AgentActivityKind` so the two cannot drift.

    There is no `updated_at` and no soft-delete column: rows are written once
    and never change, and the repository exposes no update or delete at all.
    """

    __tablename__ = "agent_activity"
    __table_args__ = (
        CheckConstraint(
            "kind IN ("
            + ", ".join(f"'{kind.value}'" for kind in AgentActivityKind)
            + ")",
            name="ck_agent_activity_kind",
        ),
        Index(
            "agent_activity_instance_time_idx",
            "agent_instance_id",
            "occurred_at",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    agent_instance_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_os.agent_instance.id"),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    """Nullable and with no default. `NULL` means "no correlation is known",
    which is true; a generated default would manufacture provenance linking
    nothing. Deliberately **not** in `agent_activity_instance_time_idx`: it is
    a join key, not an ordering key, and the ordering stays
    `(occurred_at DESC, id DESC)`."""
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
