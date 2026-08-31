"""SQLAlchemy ORM models -- the `capability` Postgres schema, exactly as
specified in docs/design/phase-3/06-tdd-3c-capability-engine.md §6 (this
document, not docs/architecture/07-database-architecture.md's older,
superseded sketch of the same table, is authoritative -- TDD 3C §11).
`Base.metadata` is what Alembic's `env.py` autogenerates migrations
against; `alembic/versions/0001_initial_schema.py` is hand-written to
match this file precisely, the same convention as every prior engine.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="capability")


class CapabilityORM(Base):
    """The `Capability` model (TDD 3C §2.1), plus `permissions_reviewed_at`/
    `sandbox_test_passed_at` (§6) -- repository-internal pipeline-stage
    bookkeeping, not part of `nova_contracts.Capability` itself. Populated
    at insert time: by the time `Registration` runs, both the Permission
    Review and Sandbox Testing stages have already completed
    (`domain/pipeline.py`)."""

    __tablename__ = "capability"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_capability_name_version"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    dependencies: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    required_permissions: Mapped[list] = mapped_column(JSONB, nullable=False)
    required_resources: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    input_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    execution_adapter: Mapped[str] = mapped_column(Text, nullable=False)
    health_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="unknown")
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    permissions_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sandbox_test_passed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CapabilityInstallationEventORM(Base):
    """Append-only log of pipeline-stage transitions per install (TDD 3C
    §6) -- mirrors `communication-engine`'s own `ConversationDecisionTraceORM`
    append-only precedent. `capability_id` is `None` until the
    `Registration` stage actually mints one."""

    __tablename__ = "capability_installation_event"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    capability_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
