"""SQLAlchemy ORM models -- the `autonomy` Postgres schema, per TDD 4D §9.

`autonomy.decision_log` is **doc 07's canonical table, implemented as
written** (`docs/architecture/07-data-architecture.md`): the column names,
types and nullability are doc 07's, not this engine's preferences. Where the
domain model's field name differs -- `DecisionLogEntry.subject_id` against the
column `action_id` -- the *column* keeps doc 07's name and the mapping is made
explicit here, because renaming a canonical column to suit one milestone's
vocabulary is how a schema stops being canonical.

`Base.metadata` is what Alembic's `env.py` autogenerates against;
`alembic/versions/0001_initial_schema.py` is hand-written to match this file
precisely, the convention every prior engine follows.

**`DecisionLogORM` carries a foreign key to `autonomy.suggestion`** and the
relationship is declared on the parent. That is deliberate and is the direct
lesson of 4C.2's `4eafa80` defect: SQLAlchemy orders unrelated mappers by name
within a flush, so a child INSERT can precede its parent's and violate the
constraint. TDD §9 requires designing that out rather than rediscovering it.

Because a denied or observe-only decision has no suggestion, `suggestion_id`
is the **nullable** side of that relationship while doc 07's `action_id` stays
`NOT NULL` -- the two columns answer different questions, and collapsing them
would either make denials unloggable or make the foreign key unenforceable.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    MetaData,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    metadata = MetaData(schema="autonomy")


class AutonomyLevelORM(Base):
    """One row per user (ADR-025: one trusted user per instance, so in
    practice one row). Keyed by `user_id` because the schema already is --
    **not** because 4D introduces multi-user (TDD §10 item 5)."""

    __tablename__ = "autonomy_level"

    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PolicyORM(Base):
    """A user-authored policy. `effect` is `TEXT` holding a `PolicyEffect`
    value; there is no `allow` effect in 4D, and no CHECK constraint pins the
    set because widening it later is a migration, not a schema rewrite."""

    __tablename__ = "policy"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    effect: Mapped[str] = mapped_column(Text, nullable=False)
    match_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_min_risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_capability_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_policy_user_id", "user_id"),)


class PermissionGrantORM(Base):
    """One row per (user, category). The composite primary key is what makes
    "grant this category" an upsert rather than an append -- and what keeps a
    category from acquiring two conflicting ceilings.

    **A category with no row is the fail-closed default** (TDD §7), so this
    table is expected to be sparse and must never be backfilled with
    permissive defaults."""

    __tablename__ = "permission_grant"

    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    category: Mapped[str] = mapped_column(Text, primary_key=True)
    max_risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_approval_above: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SuggestionORM(Base):
    """What Level 1 proposes and the panel renders.

    The `(user_id, created_at DESC, id DESC)` index is what makes TDD §9's
    keyset pagination an index scan rather than a sort -- and the `id`
    tiebreaker is what makes a page boundary deterministic when two
    suggestions share a timestamp, which the `real_infra` tier tests
    explicitly."""

    __tablename__ = "suggestion"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    risk: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="proposed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    decisions: Mapped[list[DecisionLogORM]] = relationship(
        back_populates="suggestion", cascade="save-update"
    )
    """Declared so SQLAlchemy orders this INSERT before its children's within a
    flush. Without it the flush order is by mapper name, and
    `decision_log` < `suggestion` alphabetically -- the exact shape of 4C.2's
    `4eafa80` defect. **No `delete` cascade**: the log is append-only."""

    __table_args__ = (
        Index("ix_suggestion_user_created_id", "user_id", "created_at", "id"),
        Index("ix_suggestion_user_status", "user_id", "status"),
    )


class DecisionLogORM(Base):
    """**Doc 07's canonical `autonomy.decision_log`, append-only.**

    Bible Part 14: *"Store every important autonomous decision."* There is no
    repository method that updates or deletes a row here, and
    `tests/unit/test_repository_contract.py` asserts the absence of those
    method names mechanically.

    `action_id` is doc 07's column name, kept. 4D writes the decision's own
    subject id into it -- the suggestion's id for a proposal, a freshly minted
    id for a denial -- because 4D creates no `Action` (the `action-engine`
    boundary, TDD §8.1). A later milestone that decides real Actions writes an
    Action id into the same column without a migration.

    `confidence` is doc 07's `REAL NOT NULL`, so a decision taken without a
    trust score records the fail-closed `0.0` here while `TrustScore.score`
    itself stays `None`.
    """

    __tablename__ = "decision_log"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    action_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    suggestion_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("autonomy.suggestion.id", ondelete="RESTRICT"),
        nullable=True,
    )
    """Nullable because a `deny` or `observe_only` decision has no suggestion.
    `ON DELETE RESTRICT` rather than `CASCADE`: deleting a suggestion must not
    be able to erase the record of the decision that produced it."""
    autonomy_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    risk: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    policy_checks: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    suggestion: Mapped[SuggestionORM | None] = relationship(back_populates="decisions")

    __table_args__ = (
        Index("ix_decision_log_action_id", "action_id"),
        Index("ix_decision_log_created_id", "created_at", "id"),
    )
