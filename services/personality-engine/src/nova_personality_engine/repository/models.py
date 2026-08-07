"""SQLAlchemy ORM models -- the `personality` Postgres schema, exactly as
specified in docs/design/phase-2d/02-personality-engine.md Sec9.
`Base.metadata` is what Alembic's `env.py` autogenerates migrations against;
`alembic/versions/0001_initial_schema.py` is hand-written to match this file
precisely, the same convention as every prior engine.

`core_identity` and `memory_profile` are both singleton tables (`id` fixed to
`1`, `CHECK (id = 1)`) -- design doc Sec9's own justification: there is
exactly one NOVA (Doc 23 Sec1), and ADR-025's single-user default means "per
user" and "the one row" are the same thing today. Dropping the check
constraint is the only change a future per-user `memory_profile` needs.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, MetaData, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="personality")


class CoreIdentityORM(Base):
    __tablename__ = "core_identity"
    __table_args__ = (CheckConstraint("id = 1", name="core_identity_singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    schema_version: Mapped[int] = mapped_column(nullable=False, default=1)
    traits: Mapped[list] = mapped_column(JSONB, nullable=False)
    values: Mapped[list] = mapped_column(JSONB, nullable=False)
    forbidden_behaviors: Mapped[list] = mapped_column(JSONB, nullable=False)
    version_note: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MemoryProfileORM(Base):
    __tablename__ = "memory_profile"
    __table_args__ = (CheckConstraint("id = 1", name="memory_profile_singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    verbosity: Mapped[str] = mapped_column(Text, nullable=False, default="moderate")
    technical_depth: Mapped[str] = mapped_column(Text, nullable=False, default="moderate")
    terminology_preference: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="static_default")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ValidationAuditORM(Base):
    __tablename__ = "validation_audit"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    passed: Mapped[bool] = mapped_column(nullable=False)
    violations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    selected_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
