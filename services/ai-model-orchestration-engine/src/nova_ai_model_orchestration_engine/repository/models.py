"""SQLAlchemy ORM models -- the `model_orchestration` Postgres schema, exactly
as specified in docs/design/phase-2a/00-ai-model-orchestration-engine.md §4.
`Base.metadata` is what Alembic's `env.py` autogenerates migrations against;
`alembic/versions/0001_initial_schema.py` is hand-written to match this file
precisely, the same convention as every Phase 1 engine.

No `graph_write`/`graph_applied_at` columns on `outbox_event` -- this engine
owns no graph (design doc §4), so its saga is the simpler Memory-Engine-shaped
version, not Knowledge/World Model's two-phase one.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, MetaData, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="model_orchestration")


class ModelRegistryORM(Base):
    __tablename__ = "model_registry"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    connector_type: Mapped[str] = mapped_column(Text, nullable=False)
    is_local: Mapped[bool] = mapped_column(nullable=False)
    modalities: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    capability_scores: Mapped[dict] = mapped_column(JSONB, nullable=False)
    context_window: Mapped[int] = mapped_column(Integer, nullable=False)
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_latency_ms: Mapped[float | None] = mapped_column(nullable=True)
    avg_quality_score: Mapped[float | None] = mapped_column(nullable=True)
    hardware_requirements: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    license: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_per_input_token: Mapped[float | None] = mapped_column(Numeric(12, 8), nullable=True)
    cost_per_output_token: Mapped[float | None] = mapped_column(Numeric(12, 8), nullable=True)
    max_privacy_tier: Mapped[str] = mapped_column(Text, nullable=False)
    health_status: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelHealthSnapshotORM(Base):
    __tablename__ = "model_health_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("model_orchestration.model_registry.id"), nullable=False
    )
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    available: Mapped[bool] = mapped_column(nullable=False)
    latency_ms: Mapped[float | None] = mapped_column(nullable=True)
    error_rate: Mapped[float | None] = mapped_column(nullable=True)


class UsageRecordORM(Base):
    __tablename__ = "usage_record"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    correlation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    requesting_engine: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("model_orchestration.model_registry.id"), nullable=False
    )
    routing_decision: Mapped[dict] = mapped_column(JSONB, nullable=False)
    estimated_complexity: Mapped[float] = mapped_column(nullable=False)
    latency_ms: Mapped[float] = mapped_column(nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fallback_used: Mapped[bool] = mapped_column(nullable=False, default=False)
    privacy_classification: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BudgetORM(Base):
    __tablename__ = "budget"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    scope_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    period: Mapped[str] = mapped_column(Text, nullable=False, default="monthly")
    limit_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="USD")
    alert_threshold_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=80)


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
