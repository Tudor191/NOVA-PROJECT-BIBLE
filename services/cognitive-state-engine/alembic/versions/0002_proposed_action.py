"""Add cognitive_state.active_thought.proposed_action

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-22

**Phase 4F.6, A-4F6-2a** -- docs/design/phase-4/10-tdd-4f6-initiative-trigger.md
§4.7 and §19. **The one schema change the ratified 4F.6 contract permits.**

**Additive only.** One nullable `JSONB` column, following this table's existing
JSONB columns (`dependencies`, `related_memories`, `related_projects`). No
existing column is altered, no existing CHECK constraint is touched or added,
no backfill runs, and no other schema is affected -- `autonomy` in particular is
untouched.

`NULL` is *"this thought proposes no action"*, which is what every existing row
means, so no default is needed. A present value is a complete `ProposedAction`;
its domain validators are the authority, per `repository/models.py`'s
convention that the type -- not a CHECK -- enforces rules that need a message a
human can act on.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE cognitive_state.active_thought ADD COLUMN proposed_action JSONB NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE cognitive_state.active_thought DROP COLUMN IF EXISTS proposed_action")
