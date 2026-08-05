"""SQLAlchemy ORM models -- the `reasoning` Postgres schema, exactly as
specified in docs/design/phase-2b/00-reasoning-engine.md §20. `Base.metadata`
is what Alembic's `env.py` autogenerates migrations against;
`alembic/versions/0001_initial_schema.py` is hand-written to match this file
precisely, the same convention as every prior engine.

Per §0's one narrow exception to "never owns data": every row here describes
a reasoning process this engine itself ran, never a copy of a memory, a
knowledge node, or a World Model object. No `graph_write`/`graph_applied_at`
columns on `outbox_event` -- this engine owns no graph, the identical outbox
shape the AI Model Orchestration Engine's own schema already established.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, MetaData, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="reasoning")


class ReasoningProcessORM(Base):
    __tablename__ = "reasoning_process"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    correlation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    requesting_engine: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    parent_process_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("reasoning.reasoning_process.id"), nullable=True
    )
    objective_text: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning_mode: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning_level: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="received")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class HypothesisORM(Base):
    __tablename__ = "hypothesis"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    reasoning_process_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("reasoning.reasoning_process.id"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="investigating")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceORM(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("reasoning.hypothesis.id"), nullable=False
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[float] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlternativeORM(Base):
    __tablename__ = "alternative"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    reasoning_process_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("reasoning.reasoning_process.id"), nullable=False
    )
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("reasoning.hypothesis.id"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    constraint_status: Mapped[str] = mapped_column(Text, nullable=False)
    matrix_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DecisionORM(Base):
    __tablename__ = "decision"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    reasoning_process_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("reasoning.reasoning_process.id"), nullable=False
    )
    selected_alternative_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("reasoning.alternative.id"), nullable=True
    )
    explanation: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence_score: Mapped[float] = mapped_column(nullable=False)
    human_override: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReasoningTraceORM(Base):
    __tablename__ = "reasoning_trace"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    reasoning_process_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("reasoning.reasoning_process.id"), nullable=False
    )
    trace_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutboxEventORM(Base):
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
