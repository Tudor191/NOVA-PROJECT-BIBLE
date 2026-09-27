"""SQLAlchemy ORM models -- the `cognitive_state` Postgres schema, per TDD 4F
§13 (*"a new `cognitive_state` schema; additive tables only; zero existing
tables altered"*).

**One table, and the reason it is only one.** Active Thoughts are stored;
**Focus is not.** The focus set is a pure function of the stored thoughts plus
the caller's signals (`domain/focus.py`), so persisting it would create a second
source of truth for something already derivable -- and TDD 4F's scope rule for
4F.1 forbids speculative tables for later slices. Attention Layers are a column
on the thought, not a table, for the same reason: a layer is a property of a
thought, not an entity.

**The three relation lists are `JSONB` columns**, matching
`digital-twin-engine`'s own `unavailable_fields`/`corrections` convention rather
than introducing three child tables. They are opaque id lists that nothing joins
against in 4F; a child table would buy referential integrity against rows that
live in *other engines' databases*, which is not integrity this schema can
enforce and would be misleading to imply.

`Base.metadata` is what Alembic's `env.py` autogenerates against;
`alembic/versions/0001_initial_schema.py` is hand-written to match this file
precisely, the convention every prior engine follows.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

__all__ = ["ActiveThoughtORM", "Base", "SensorStateORM"]


class Base(DeclarativeBase):
    metadata = MetaData(schema="cognitive_state")


class ActiveThoughtORM(Base):
    """Bible Part 6's Active Thought. Every column maps one-to-one onto
    `domain.models.ActiveThought`, whose validators are the authority -- the
    CHECK constraints below duplicate only the two bounds that are cheap to
    state in SQL and expensive to discover in production.

    The domain model enforces strictly more than the table does (self-dependency,
    duplicate relations, archived-with-partial-progress, `updated_at` ordering).
    That asymmetry is deliberate: a constraint belongs in SQL when the database
    is the last line of defence, and in the type when the rule needs a message a
    human can act on.
    """

    __tablename__ = "active_thought"

    thought_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    current_progress: Mapped[float] = mapped_column(Float, nullable=False)

    dependencies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    related_memories: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    related_projects: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    estimated_completion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """Nullable because *"not estimated"* is a real answer. A sentinel date
    would be a fabricated timestamp, which TDD 4F §2.2 forbids outright."""

    proposed_action: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    """**Phase 4F.6**, migration `0002`. Nullable JSONB, following this table's
    existing JSONB columns. `NULL` is *"proposes no action"*; a present value is
    a complete `ProposedAction`, whose validators -- not a CHECK -- are the
    authority, per this class's docstring.

    **`none_as_null=True` is load-bearing.** SQLAlchemy's JSON types default to
    writing Python `None` as the JSON value `null`, which is *not* SQL `NULL`:
    `proposed_action IS NULL` would be false for a thought that proposes
    nothing. The real-Postgres tier caught exactly that before merge
    (`test_no_proposal_is_sql_null_not_a_json_value`)."""

    attention_layer: Mapped[str] = mapped_column(Text, nullable=False)
    """`TEXT` holding an `AttentionLayer` value. No CHECK pins the set: Part 6
    names five layers and widening that set later should be a migration, not a
    schema rewrite -- `autonomy-engine`'s `policy.effect` convention."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    """Both are written from the domain object on every insert and update, never
    left to the column default -- Phase 4E's ratified Option A, applied here from
    the start so this engine never ships the defect `memory-engine` had."""

    __table_args__ = (
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_active_thought_confidence_range",
        ),
        CheckConstraint(
            "current_progress >= 0.0 AND current_progress <= 1.0",
            name="ck_active_thought_progress_range",
        ),
        CheckConstraint("priority >= 0", name="ck_active_thought_priority_non_negative"),
        Index("ix_active_thought_user_layer", "user_id", "attention_layer"),
        Index("ix_active_thought_user_updated", "user_id", "updated_at"),
    )


class SensorStateORM(Base):
    """**Phase 4F.7, A-4F7-1** -- `cognitive_state.sensor_state`, matching
    migration `0003` column for column (TDD 4F.7 §28.1).

    **One current record per `sensor_id`.** This is current-state storage: a
    superseded state is overwritten, not kept, and there is no history, heartbeat
    or audit table beside it. `perception-engine` owns the fact; this table holds
    the latest copy this engine received.

    `state` is `TEXT` without a CHECK, the same convention as
    `ActiveThoughtORM.attention_layer`: `domain/sensor_state.py`'s six
    `SensorState` values are the authority, enforced before any write.
    """

    __tablename__ = "sensor_state"

    sensor_id: Mapped[str] = mapped_column(Text, primary_key=True)
    sensor_type: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    """The envelope's `occurred_at`: dispatch time, not transition time."""

    last_event_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    """The `event_id` of the report the current row came from -- an idempotency
    key for this row, not a log."""
