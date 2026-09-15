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

from sqlalchemy import DateTime, Float, ForeignKeyConstraint, Index, Integer, MetaData, Text, func
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


# ---------------------------------------------------------------------------
# Phase 4E -- Bible Part 16's nine remaining domains (TDD 4E Sec9)
# ---------------------------------------------------------------------------


class DomainModelORM(Base):
    """One row per Part 16 domain per user -- name, state, machine-readable
    reason, derived-at (TDD 4E Sec9).

    `state`/`reason_code` are `TEXT`, not a Postgres `ENUM`. Every prior table in
    this schema stores its enums the same way, and the reason holds here too: the
    vocabulary is Part 16's, a later milestone will extend it (4F's real
    Software/Hardware sources change which states those domains may reach), and a
    native enum turns that into a migration with a table rewrite. The values are
    validated by `DomainState`/`DomainReasonCode` on the way in and out.
    """

    __tablename__ = "domain_model"

    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    domain: Mapped[str] = mapped_column(Text, primary_key=True)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    facts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    unavailable_fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    derived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DomainEvidenceORM(Base):
    """Provenance: which source record produced which derivation.

    **This table is what makes Part 16 Sec69 enforceable** (TDD 4E Sec9). A domain
    with no rows here is empty *by construction* -- `DomainModel`'s own validator
    refuses to call it populated -- rather than by anyone remembering to check.

    Two structural properties, both deliberate:

    * **The primary key is `(user_id, domain, source_record_id)`**, so the same
      source record contributes at most one row per domain. The Event Bus is
      at-least-once, and a redelivered `memory.long_term.created` must not inflate
      a count. Idempotency belongs in the key, not in a handler's memory.
    * **The foreign key to `domain_model`** means evidence cannot exist for a
      domain that was never derived. `record_domain_derivation` writes the parent
      and its children in one transaction for exactly that reason.

    `attributes` holds bounded metadata already on the wire -- a memory type, a
    knowledge node id, an attention state. **Never memory content**: none of the
    three subscribed payloads carries any, and `domain/derivation.py` adds none.
    """

    __tablename__ = "domain_evidence"

    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    domain: Mapped[str] = mapped_column(Text, primary_key=True)
    source_record_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    source_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "domain"],
            ["digital_twin.domain_model.user_id", "digital_twin.domain_model.domain"],
            ondelete="CASCADE",
            name="domain_evidence_domain_model_fk",
        ),
        Index("domain_evidence_source_created_at_idx", "user_id", "domain", "source_created_at"),
    )


class ProjectModelORM(Base):
    """Bible Part 16's Project Model, keyed by `memory-engine`'s own `project_id`
    -- **AC-6's reconstruction** (TDD 4E Sec9, Sec16).

    `gap_days` is stored rather than computed at read time so a reconstruction is
    reproducible: two reads of the same derivation return the same answer, and the
    number the panel shows is the number the derivation actually produced. It is
    nullable, never `0.0`, when no evidence row carried a timestamp -- zero would
    read as "active today".

    No foreign key to `domain_model`: a project row is keyed by `project_id`, not
    by domain, and `memory-engine` owns project identity (TDD 4E Sec6.1) so there
    is nothing local to reference. The `projects` domain's own `domain_model` row
    is what carries its state.
    """

    __tablename__ = "project_model"

    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    memory_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    memory_type_counts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    first_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    gap_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    derived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("project_model_last_activity_idx", "user_id", "last_activity_at"),
    )
