"""Add perception.known_project

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11

**Phase 4F.8, ratified decision A-4F8-2 (a1)** --
docs/design/phase-4/12-tdd-4f8-acceptance-verification.md §29.1.

**The project identities NOVA holds, as this engine has learned them.** One row
per `project_id` seen on `memory.long_term.created`, the existing subject that
carries `MemoryRecord.project_id` -- *"the only project identity in the
system"*, read via events and never from another engine's store (TDD 4F §4.1;
ADR-004). An operator-declared folder binding for a project becomes active only
once that project has a row here.

**Current state only**, following A-4F7-1's precedent: no history, no row per
event, no audit and no expiry. `first_observed_at` and `source_event_id` say
which event first made the project known -- provenance for one row, not a log.
A later sighting of the same project writes nothing.

**Persisted rather than held in memory** (A-4F8-2 (a1)), so a restart of this
engine does not silently make every project unknown.

**Additive only.** One new table in the existing schema; no other table is
altered.
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
        CREATE TABLE perception.known_project (
            project_id         UUID PRIMARY KEY,
            first_observed_at  TIMESTAMPTZ NOT NULL,
            source_event_id    UUID NOT NULL
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS perception.known_project")
