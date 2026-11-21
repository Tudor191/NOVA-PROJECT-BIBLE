"""Add cognitive_state.sensor_state

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-26

**Phase 4F.7, ratified decision A-4F7-1** --
docs/design/phase-4/11-tdd-4f7-cognitive-state-panel.md §8.4 and §28.1.

**Current-state storage, and nothing else.** One record per `sensor_id`, holding
the latest *known* lifecycle state `perception-engine` reported over
`perception.sensor.health_changed`. It is a projection of those reports, owned
by this engine; `perception-engine` remains the source of truth for a sensor's
lifecycle (TDD 4F §10).

**Deliberately absent**, each by ratified decision rather than by omission:
no history table, no row per event, no heartbeat history, no audit columns, no
expiry and no deletion path. `last_event_id` identifies the report the *current*
row came from -- an idempotency key for one row, not a log.

**Additive only.** One new table in the existing schema. `active_thought` is
untouched, and no other schema is affected.

**`state` is `TEXT` with no CHECK**, following this schema's own
`attention_layer` convention (`repository/models.py`): the domain type
`domain/sensor_state.py` is the authority on the six `SensorState` values, and
widening the vocabulary later should be a migration, not a schema rewrite.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE cognitive_state.sensor_state (
            sensor_id      TEXT PRIMARY KEY,
            sensor_type    TEXT NOT NULL,
            state          TEXT NOT NULL,
            reported_at    TIMESTAMPTZ NOT NULL,
            last_event_id  UUID NOT NULL
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS cognitive_state.sensor_state")
