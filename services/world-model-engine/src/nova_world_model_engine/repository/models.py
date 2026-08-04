"""SQLAlchemy ORM models -- the `world_model` Postgres schema, matching
docs/design/phase-1/03-world-model-engine.md §4 exactly. No `pgvector` import
here -- §10: World Model Engine does not embed, so unlike Memory/Knowledge
Engine's `repository/models.py`, there is no `VECTOR` column anywhere in this
schema. `Base.metadata` is what Alembic's `env.py` targets;
`alembic/versions/0001_initial_schema.py` is hand-written to match this file
(and the design doc) precisely.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, MetaData, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="world_model")


class ObjectStateHistoryORM(Base):
    __tablename__ = "object_state_history"
    __table_args__ = (
        Index("osh_object_idx", "object_id", "changed_at"),
        Index("osh_user_idx", "user_id", "changed_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[str] = mapped_column(Text, nullable=False)
    object_label: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    previous_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_state: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class SnapshotORM(Base):
    __tablename__ = "snapshot"
    __table_args__ = (Index("snapshot_user_idx", "user_id", "taken_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    taken_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    snapshot_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)


class PredictionORM(Base):
    __tablename__ = "prediction"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    prediction: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    predicted_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ConflictLogORM(Base):
    __tablename__ = "conflict_log"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    object_id: Mapped[str] = mapped_column(Text, nullable=False)
    observation_a: Mapped[dict] = mapped_column(JSONB, nullable=False)
    observation_b: Mapped[dict] = mapped_column(JSONB, nullable=False)
    resolution_strategy: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class OutboxEventORM(Base):
    """Present, with this exact shape (plus `graph_write`/`graph_applied_at`,
    per docs/design/phase-1/03-world-model-engine.md §4's own outbox table),
    matching docs/design/phase-1/00-shared-foundations.md's transactional
    outbox pattern, and the same two-phase saga shape as Knowledge Engine
    (§02 §4/§17)."""

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
