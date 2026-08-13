"""SQLAlchemy ORM models -- the `communication` Postgres schema, exactly as
specified in docs/design/phase-2d/01-communication-engine.md Sec10.
`Base.metadata` is what Alembic's `env.py` autogenerates migrations against;
`alembic/versions/0001_initial_schema.py` is hand-written to match this file
precisely, the same convention as every prior engine.

No graph store, no vector store (design doc Sec10's own closing note) --
`ConversationSessionORM.turns` is the only relationship, loaded eagerly
(`postgres_communication_repository.py`) since every domain `ConversationSession`
always carries its full `turns` list.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, MetaData, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    metadata = MetaData(schema="communication")


class ConversationSessionORM(Base):
    __tablename__ = "conversation_session"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    device_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    pending_questions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    conversation_memory: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    """Phase 2D-C addition (04-conversation-intelligence.md Sec3.1/Sec9) --
    the `ConversationMemory` domain model's `questions`/`decisions`/
    `preferences`/`corrections`/`feedback` lists, serialized whole."""
    interrupted_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Phase 2D-C addition (Sec3.1/Sec5.1)."""
    dnd_override: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    """Phase 2D-C addition (Sec3.1/Sec5.2)."""

    turns: Mapped[list[ConversationTurnORM]] = relationship(
        back_populates="session", order_by="ConversationTurnORM.created_at"
    )


class ConversationTurnORM(Base):
    __tablename__ = "conversation_turn"

    turn_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("communication.conversation_session.session_id")
    )
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    personality_validated: Mapped[bool | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    """Phase 2D-D Step 10 fix -- a real GitHub Actions real-infra run caught
    `get_last_outbound_turn()` (Sec5.2) returning the wrong turn when two
    `append_turn` calls land within the same Postgres transaction-start-time
    tick: `server_default=func.now()` resolves to the *transaction's* start
    time, not the statement's, so rapid sequential inserts (each its own
    transaction, but issued back-to-back with no intervening real-world
    delay) can tie. A Python-side `default`, evaluated at ORM-object
    construction time -- after the real network round trip of the *previous*
    `append_turn` call's own commit has already returned -- cannot tie the
    same way. `server_default` is kept as a DB-level fallback for any
    non-ORM insert path; this also fixes the same latent tie risk in
    `ConversationSessionORM.turns`'s own `order_by="ConversationTurnORM.
    created_at"` relationship ordering, pre-existing since Phase 2D-A and
    never previously real-infra-tested under back-to-back inserts."""

    session: Mapped[ConversationSessionORM] = relationship(back_populates="turns")


class NotificationORM(Base):
    __tablename__ = "notification"

    notification_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(Text, nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConversationDecisionTraceORM(Base):
    """Phase 2D-C addition (04-conversation-intelligence.md Sec3.2/Sec14) --
    append-only, never mutated once inserted; no `session_id` foreign key
    (unlike `ConversationTurnORM`) since a pre-session addressee check has
    no session yet to reference."""

    __tablename__ = "conversation_decision_trace"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    decision_type: Mapped[str] = mapped_column(Text, nullable=False)
    inputs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    confidence_tier: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
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
