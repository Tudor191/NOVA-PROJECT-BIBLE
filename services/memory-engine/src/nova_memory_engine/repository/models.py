"""SQLAlchemy ORM models -- the `memory` Postgres schema, exactly as specified in
docs/design/phase-1/01-memory-engine.md §4. `Base.metadata` is what Alembic's
`env.py` autogenerates migrations against; `alembic/versions/0001_initial_schema.py`
is hand-written to match this file (and the design doc) precisely, since pgvector's
`VECTOR` type and the partial HNSW index need raw SQL either way.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIMENSIONS = 768  # ADR-010

_MEMORY_TYPE_VALUES = (
    "semantic",
    "procedural",
    "episodic",
    "project",
    "preference",
    "decision",
)
_LIFECYCLE_STATE_VALUES = ("active", "weak", "archived", "scheduled_for_deletion", "deleted")
_PRIVACY_LEVEL_VALUES = ("public", "internal", "confidential", "highly_sensitive")


class Base(DeclarativeBase):
    metadata = MetaData(schema="memory")


memory_type_enum = ENUM(*_MEMORY_TYPE_VALUES, name="memory_type", schema="memory")
lifecycle_state_enum = ENUM(*_LIFECYCLE_STATE_VALUES, name="lifecycle_state", schema="memory")
privacy_level_enum = ENUM(*_PRIVACY_LEVEL_VALUES, name="privacy_level", schema="memory")


class MemoryRecordORM(Base):
    __tablename__ = "memory_record"
    __table_args__ = (
        CheckConstraint("importance_score BETWEEN 0 AND 1", name="importance_score_range"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        Index("memory_record_type_idx", "memory_type"),
        Index(
            "memory_record_project_idx", "project_id", postgresql_where="project_id IS NOT NULL"
        ),
        Index("memory_record_lifecycle_idx", "lifecycle_state"),
        Index("memory_record_user_idx", "user_id"),
        Index("memory_record_type_data_gin", "type_data", postgresql_using="gin"),
        Index("memory_record_created_at_idx", "created_at", postgresql_using="btree"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    memory_type: Mapped[str] = mapped_column(memory_type_enum, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS), nullable=True
    )
    embedding_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    importance_score: Mapped[float] = mapped_column(default=0.5)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    privacy_level: Mapped[str] = mapped_column(
        privacy_level_enum, nullable=False, default="internal"
    )
    lifecycle_state: Mapped[str] = mapped_column(
        lifecycle_state_enum, nullable=False, default="active"
    )
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_ref: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    knowledge_node_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, default=1)


class ShortTermRecordORM(Base):
    __tablename__ = "short_term_record"
    __table_args__ = (
        Index("short_term_expires_idx", "expires_at"),
        Index("short_term_user_idx", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_ref: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DecisionRecordORM(Base):
    __tablename__ = "decision_record"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    memory_record_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("memory.memory_record.id", ondelete="CASCADE"),
        nullable=False,
    )
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    alternatives: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    chosen_alternative: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    tradeoffs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    risks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confidence_at_decision: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ConsolidationRunORM(Base):
    __tablename__ = "consolidation_run"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    records_scanned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    records_merged: Mapped[int | None] = mapped_column(Integer, nullable=True)
    records_advanced: Mapped[int | None] = mapped_column(Integer, nullable=True)
    records_deleted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")


class AuditLogORM(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    memory_record_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class OutboxEventORM(Base):
    """Present, with this exact shape, per docs/design/phase-1/
    00-shared-foundations.md's transactional outbox pattern."""

    __tablename__ = "outbox_event"
    __table_args__ = (
        Index(
            "outbox_undispatched_idx", "created_at", postgresql_where="dispatched_at IS NULL"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    causation_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
