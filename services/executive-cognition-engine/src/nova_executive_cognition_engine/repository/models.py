"""SQLAlchemy ORM models -- the `executive` Postgres schema, exactly as
specified in docs/design/phase-2c/00-executive-cognition-engine.md §19.
`Base.metadata` is what Alembic's `env.py` autogenerates migrations against;
`alembic/versions/0001_initial_schema.py` is hand-written to match this file
precisely, the same convention as every prior engine.

Per §0's one narrow exception to "never owns data": every row here describes
an arbitration decision this engine itself made, never a copy of a memory, a
knowledge node, a World Model object, or another engine's request payload
beyond the priority factors it itself declared.

`ExecutiveDecisionORM.trace_payload` stores the entire `ExecutiveDecisionTrace`
as one JSONB blob rather than decomposing it into relational columns --
mirroring `ReasoningTraceORM`'s own trade-off (Phase 2B): a handful of
columns are duplicated outside the blob purely for querying/ordering
(`correlation_id`, `requesting_engine`, `decision_type`, `outcome`,
`created_at`), the JSONB blob itself remains the single source of truth for
domain reconstruction. There is no separate `hypothesis`/`evidence`-style
row breakout here because design doc §19's own table list names exactly one
table for decisions (`executive_decision`), not several.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, MetaData, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="executive")


class ExecutiveRequestORM(Base):
    __tablename__ = "executive_request"

    correlation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    """§5.1-§5.2 -- `ExecutiveRequest` carries no `id` field of its own;
    `correlation_id` (`Field(default_factory=uuid4)`) is the domain object's
    own identifier, reused here as the primary key rather than adding a
    second, redundant one."""
    requesting_engine: Mapped[str] = mapped_column(Text, nullable=False)
    request_kind: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    urgency: Mapped[float] = mapped_column(nullable=False)
    importance: Mapped[float] = mapped_column(nullable=False)
    complexity: Mapped[float] = mapped_column(nullable=False)
    risk: Mapped[float] = mapped_column(nullable=False)
    learning_value: Mapped[float] = mapped_column(nullable=False)
    resource_cost: Mapped[float] = mapped_column(nullable=False)
    user_impact: Mapped[float] = mapped_column(nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    goal_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    goal_tier: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExecutiveDecisionORM(Base):
    __tablename__ = "executive_decision"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    correlation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    requesting_engine: Mapped[str] = mapped_column(Text, nullable=False)
    """Derived from `trace.contending_requests` at write time (the entry
    whose `correlation_id == trace.correlation_id`) -- duplicated outside
    the JSONB blob solely so `list_decisions(requesting_engine=...)` can
    filter without a JSONB containment query."""
    decision_type: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    trace_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExecutiveOutcomeReportORM(Base):
    __tablename__ = "executive_outcome_report"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    """§19 -- `ExecutiveOutcomeReportPayload` carries no `id` field of its
    own, the same exception §19 already states for `outbox_event.id`."""
    correlation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("executive.executive_request.correlation_id"),
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    actual_duration_ms: Mapped[float | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HumanOverrideORM(Base):
    __tablename__ = "human_override"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    """§13, §19 -- `HumanOverrideRequest` carries no `id` field of its own,
    the identical exception applied to `ExecutiveOutcomeReportORM.id` and
    `outbox_event.id` above."""
    executive_decision_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("executive.executive_decision.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    redirect_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
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
