"""SQLAlchemy ORM models -- the `knowledge` Postgres schema, matching
docs/design/phase-1/02-knowledge-engine.md §4, plus one justified extension:
`NodeUsageORM` (see its docstring). `Base.metadata` is what Alembic's `env.py`
targets; `alembic/versions/0001_initial_schema.py` is hand-written to match this
file (and the design doc) precisely, since pgvector's `VECTOR` type and the
partial HNSW index need raw SQL either way.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, DateTime, Index, Integer, MetaData, Text, func
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIMENSIONS = 768  # ADR-010

_LAYER_VALUES = (
    "raw",
    "processed",
    "verified",
    "connected",
    "applied",
    "expert",
    "strategic",
)
_PRIVACY_LEVEL_VALUES = ("public", "internal", "confidential", "highly_sensitive")


class Base(DeclarativeBase):
    metadata = MetaData(schema="knowledge")


layer_enum = ENUM(*_LAYER_VALUES, name="layer", schema="knowledge")
privacy_level_enum = ENUM(*_PRIVACY_LEVEL_VALUES, name="privacy_level", schema="knowledge")


class NodeMetadataORM(Base):
    __tablename__ = "node_metadata"
    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        Index("node_metadata_label_idx", "label"),
        Index("node_metadata_scope_idx", "scope", "project_id", "user_id"),
        Index("node_metadata_layer_idx", "layer"),
    )

    node_id: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str] = mapped_column(Text, nullable=False, default="global")
    project_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS), nullable=True
    )
    embedding_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(default=0.5)
    privacy_level: Mapped[str] = mapped_column(
        privacy_level_enum, nullable=False, default="internal"
    )
    layer: Mapped[str] = mapped_column(layer_enum, nullable=False, default="raw")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SourceAttributionORM(Base):
    __tablename__ = "source_attribution"
    __table_args__ = (Index("source_attribution_node_idx", "node_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    node_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_contribution: Mapped[float | None] = mapped_column(nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class NodeVersionHistoryORM(Base):
    __tablename__ = "node_version_history"
    __table_args__ = (Index("node_version_history_node_idx", "node_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    node_id: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    change_type: Mapped[str] = mapped_column(Text, nullable=False)
    previous_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    changed_by: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ContradictionORM(Base):
    __tablename__ = "contradiction"
    __table_args__ = (Index("contradiction_status_idx", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    node_a_id: Mapped[str] = mapped_column(Text, nullable=False)
    node_b_id: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NodeUsageORM(Base):
    """Not in §4's literal table listing -- a minimal, explicitly justified
    extension. §6's evolution state machine requires "referenced by a completed
    task/decision" (Connected -> Applied) and "referenced across >=2 distinct
    projects" (Expert -> Strategic) to be computable, and §13 explicitly lists
    `memory.long_term.created` and `reasoning.result` as subscribed events feeding
    exactly this signal -- without a table to record it, those two transitions
    would be permanently unreachable rather than merely deferred. One row per
    (node, referencing event); `usage_summary()` aggregates count and distinct
    `project_id`."""

    __tablename__ = "node_usage"
    __table_args__ = (Index("node_usage_node_idx", "node_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    node_id: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class OutboxEventORM(Base):
    """Present, with this exact shape (plus `graph_write`/`graph_applied_at`, per
    docs/design/phase-1/02-knowledge-engine.md §4's own outbox table), matching
    docs/design/phase-1/00-shared-foundations.md's transactional outbox pattern."""

    __tablename__ = "outbox_event"
    __table_args__ = (
        Index(
            "outbox_undispatched_idx", "created_at", postgresql_where="dispatched_at IS NULL"
        ),
        Index(
            "outbox_graph_pending_idx",
            "created_at",
            postgresql_where="graph_write IS NOT NULL AND graph_applied_at IS NULL",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    causation_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    graph_write: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    graph_applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
