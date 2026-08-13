"""Phase 2D-D Step 9: proactive delivery history

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-13

Matches `repository/models.py`'s `ProactiveDeliveryRecordORM` exactly --
one additive, append-only table (`domain/ports.py`'s own module docstring
explains why it exists beyond docs/design/phase-2d/06-personal-companion.md
Sec11.1's originally-named list: `domain/proactive_boundary.py::
evaluate_proactive_suggestion`'s frequency-limit check needs genuine,
per-user delivery history to compute against). No existing table is
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
        CREATE TABLE digital_twin.proactive_delivery_record (
            id             UUID PRIMARY KEY,
            user_id        UUID NOT NULL,
            topic          TEXT NOT NULL,
            delivered_at   TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX proactive_delivery_record_user_idx "
        "ON digital_twin.proactive_delivery_record (user_id, topic, delivered_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS digital_twin.proactive_delivery_record")
