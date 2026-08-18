"""SQLAlchemy ORM models -- the `action` Postgres schema, exactly as
specified in docs/design/phase-3/07-tdd-3d-action-engine.md §8. `Base.metadata`
is what Alembic's `env.py` autogenerates migrations against;
`alembic/versions/0001_initial_schema.py` is hand-written to match this
file precisely, the same convention as every prior engine.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, MetaData, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="action")


class ActionORM(Base):
    """The `Action` model (TDD 3D §3.1), plus `result`/`error` --
    repository-internal columns beyond `nova_contracts.Action`'s own
    shared-entity fields, the same treatment `capability-engine`'s
    `permissions_reviewed_at`/`sandbox_test_passed_at` bookkeeping already
    established. `id` (`= Action.id = ActionExecuteRequestPayload.action_id`)
    is the natural-key idempotency guard approved for `action.execute`
    (§5.3, `docs/design/phase-3/13-3d-action-engine-research.md`) -- its
    primary-key uniqueness is the actual concurrent-retry safety net,
    mirroring Fork 3C-4's `UNIQUE (name, version)` mechanism."""

    __tablename__ = "action"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    execution_target: Mapped[str] = mapped_column(Text, nullable=False)
    depends_on: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    expected_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk: Mapped[str] = mapped_column(Text, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    retry_policy: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rollback_strategy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    required_permissions: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    verification_method: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PendingApprovalORM(Base):
    """The approval-loop state machine record (TDD 3D §4 point 1)."""

    __tablename__ = "pending_approval"

    action_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    risk: Mapped[str] = mapped_column(Text, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)


class ActionExecutionHistoryORM(Base):
    """Append-only log of Action Principle lifecycle stage transitions
    (TDD 3D §6.12 "Store Experience") -- mirrors
    `capability_installation_event`'s append-only precedent."""

    __tablename__ = "action_execution_history"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    action_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdentityConfidencePolicyORM(Base):
    """TDD 3D §7 -- per-user, per-risk-tier identity-confidence threshold
    configuration (ADR-032 point 2)."""

    __tablename__ = "identity_confidence_policy"

    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    minimum_confidence_by_risk: Mapped[dict] = mapped_column(JSONB, nullable=False)
