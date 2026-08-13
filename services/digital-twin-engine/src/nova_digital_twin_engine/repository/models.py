"""SQLAlchemy ORM models -- the `digital_twin` Postgres schema, exactly as
specified in docs/design/phase-2d/06-personal-companion.md Sec11.1 (plus
`completed_session_evidence` and `proactive_delivery_record`, both
implementation-time additions -- `domain/ports.py`'s own module docstring
explains why -- and the transactional outbox table every prior publishing
engine's own initial migration adds). `Base.metadata` is what Alembic's
`env.py` autogenerates migrations against; `alembic/versions/
0001_initial_schema.py` and `0002_proactive_delivery.py` are hand-written
to match this file precisely, the same convention as every prior engine.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, MetaData, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="digital_twin")


class CommunicationProfileORM(Base):
    __tablename__ = "communication_profile"

    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    verbosity: Mapped[str] = mapped_column(Text, nullable=False, default="moderate")
    technical_depth: Mapped[str] = mapped_column(Text, nullable=False, default="moderate")
    terminology_preference: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    conversation_pacing: Mapped[str | None] = mapped_column(Text, nullable=True)
    habit_timing_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="static_default")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class PreferenceEvolutionHistoryORM(Base):
    __tablename__ = "preference_evolution_history"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    field: Mapped[str] = mapped_column(Text, nullable=False)
    previous_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class HabitSignalORM(Base):
    __tablename__ = "habit_signal"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False)
    session_duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CompletedSessionEvidenceORM(Base):
    __tablename__ = "completed_session_evidence"

    session_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False)
    corrections: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    preferences: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    feedback: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    decisions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TrustMetricORM(Base):
    __tablename__ = "trust_metric"

    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    correction_frequency: Mapped[float | None] = mapped_column(nullable=True)
    window_session_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clarification_acceptance_rate: Mapped[float | None] = mapped_column(nullable=True)
    proactive_suggestion_acceptance_rate: Mapped[float | None] = mapped_column(nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class TrustMetricHistoryORM(Base):
    __tablename__ = "trust_metric_history"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correction_frequency: Mapped[float | None] = mapped_column(nullable=True)
    window_session_count: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProactiveBoundaryPolicyORM(Base):
    __tablename__ = "proactive_boundary_policy"

    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    max_per_topic_per_window: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    window_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)


class ProactiveDeliveryRecordORM(Base):
    """Phase 2D-D Step 9 (Sec10.2, Fork D) -- `domain/ports.py`'s own module
    docstring explains why this table exists beyond Sec11.1's named list:
    `domain/proactive_boundary.py::evaluate_proactive_suggestion`'s
    frequency-limit check needs genuine, per-user delivery history."""

    __tablename__ = "proactive_delivery_record"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OutboxEventORM(Base):
    __tablename__ = "outbox_event"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    causation_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
