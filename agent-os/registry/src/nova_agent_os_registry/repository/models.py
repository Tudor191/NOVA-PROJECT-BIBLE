"""SQLAlchemy ORM models -- the `agent_os` Postgres schema's
`agent_package` table, matching the approved Fork 3E-2 resolution's own
concrete ORM (`docs/design/phase-3/14-3e-agent-os-research.md` §4) exactly
-- see `docs/design/phase-3/15-3e-supervisor-reconciliation.md` §A for the
full reconciliation record correcting Milestone 3's own, since-superseded
`(id: str, version)` composite-key interpretation. `Base.metadata` is what
Alembic's `env.py` autogenerates migrations against;
`alembic/versions/0001_initial_schema.py` is hand-written to match this
file precisely, the same convention as every prior engine.

`agent_instance` (TDD 3E §4) is deliberately not defined here -- it is
`agent-os/kernel`'s own table, a separate, already-built component
(Phase 3E Milestone 2); this migration only creates the shared `agent_os`
schema (`CREATE SCHEMA IF NOT EXISTS`, idempotent regardless of which
component's migration runs first) and the one table this component owns.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="agent_os")


class AgentPackageORM(Base):
    """The `AgentPackage` model (TDD 3E §5), field-for-field, plus
    `checksum`/`supervisor_notified_new_permissions` -- repository-internal
    bookkeeping beyond TDD 3E §5's own named field list, the same
    treatment `capability-engine`'s `permissions_reviewed_at`/
    `sandbox_test_passed_at` columns already established.

    UUID surrogate primary key (`id`), `UniqueConstraint("category",
    "version")` for natural-key idempotency -- the approved Fork 3E-2
    concrete ORM's exact shape, mirroring `capability-engine`'s own
    `CapabilityORM` structure (UUID PK + `UniqueConstraint("name",
    "version")`).
    """

    __tablename__ = "agent_package"
    __table_args__ = (
        UniqueConstraint("category", "version", name="uq_agent_package_category_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    health_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="unknown")
    checksum: Mapped[str] = mapped_column(Text, nullable=False)
    supervisor_notified_new_permissions: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
