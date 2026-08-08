"""Phase 2D-C: Conversation Intelligence additive schema

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-08

Matches docs/design/phase-2d/04-conversation-intelligence.md Sec3/Sec14
exactly: three additive columns on `conversation_session` (`conversation_memory`,
`interrupted_content`, `dnd_override`) and one new, append-only
`conversation_decision_trace` table. No column on any existing table is
altered or dropped -- every existing row remains valid with the new
columns' defaults.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE communication.conversation_session
            ADD COLUMN conversation_memory JSONB NOT NULL DEFAULT '{}',
            ADD COLUMN interrupted_content TEXT,
            ADD COLUMN dnd_override BOOLEAN NOT NULL DEFAULT false
        """
    )

    op.execute(
        """
        CREATE TABLE communication.conversation_decision_trace (
            id                UUID PRIMARY KEY,
            session_id        UUID,
            decision_type     TEXT NOT NULL,
            inputs            JSONB NOT NULL,
            confidence        DOUBLE PRECISION,
            confidence_tier   TEXT,
            outcome           TEXT NOT NULL,
            reason            TEXT NOT NULL,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX conversation_decision_trace_session_idx "
        "ON communication.conversation_decision_trace (session_id)"
    )
    op.execute(
        "CREATE INDEX conversation_decision_trace_created_at_idx "
        "ON communication.conversation_decision_trace (created_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS communication.conversation_decision_trace")
    op.execute(
        """
        ALTER TABLE communication.conversation_session
            DROP COLUMN IF EXISTS conversation_memory,
            DROP COLUMN IF EXISTS interrupted_content,
            DROP COLUMN IF EXISTS dnd_override
        """
    )
