"""Phase 4E: Bible Part 16's domain model, evidence provenance, and project model

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-14

Matches `repository/models.py`'s `DomainModelORM`, `DomainEvidenceORM` and
`ProjectModelORM` exactly (TDD 4E Sec9) -- three additive tables. **No existing
table is altered**, and the two Phase 2D-D domains (`communication_profile`,
`preference_evolution_history`) are untouched: 4E reports their state from the
rows they already hold rather than restating them here.

`domain_evidence`'s composite foreign key into `domain_model` is the structural
half of Part 16 Sec69 (*"Never create assumptions without evidence"*): evidence
cannot exist for a domain that was never derived, and a domain with no evidence
rows cannot be reported as populated (`DomainModel`'s own validator). `ON DELETE
CASCADE` so `POST /domains/{domain}/refresh` can re-derive from a clean slate
without leaving orphaned provenance.

Hand-written to match the ORM, the same convention as `0001` and `0002`.
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
        CREATE TABLE digital_twin.domain_model (
            user_id             UUID        NOT NULL,
            domain              TEXT        NOT NULL,
            state               TEXT        NOT NULL,
            reason_code         TEXT        NULL,
            reason_detail       TEXT        NULL,
            evidence_count      INTEGER     NOT NULL DEFAULT 0,
            facts               JSONB       NOT NULL DEFAULT '{}'::jsonb,
            unavailable_fields  JSONB       NOT NULL DEFAULT '[]'::jsonb,
            derived_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, domain)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE digital_twin.domain_evidence (
            user_id            UUID        NOT NULL,
            domain             TEXT        NOT NULL,
            source_record_id   UUID        NOT NULL,
            id                 UUID        NOT NULL,
            kind               TEXT        NOT NULL,
            source_created_at  TIMESTAMPTZ NULL,
            observed_at        TIMESTAMPTZ NOT NULL,
            attributes         JSONB       NOT NULL DEFAULT '{}'::jsonb,
            PRIMARY KEY (user_id, domain, source_record_id),
            CONSTRAINT domain_evidence_domain_model_fk
                FOREIGN KEY (user_id, domain)
                REFERENCES digital_twin.domain_model (user_id, domain)
                ON DELETE CASCADE
        )
        """
    )
    op.execute(
        "CREATE INDEX domain_evidence_source_created_at_idx "
        "ON digital_twin.domain_evidence (user_id, domain, source_created_at)"
    )
    op.execute(
        """
        CREATE TABLE digital_twin.project_model (
            user_id             UUID        NOT NULL,
            project_id          UUID        NOT NULL,
            memory_count        INTEGER     NOT NULL DEFAULT 0,
            memory_type_counts  JSONB       NOT NULL DEFAULT '{}'::jsonb,
            first_activity_at   TIMESTAMPTZ NULL,
            last_activity_at    TIMESTAMPTZ NULL,
            gap_days            DOUBLE PRECISION NULL,
            derived_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, project_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX project_model_last_activity_idx "
        "ON digital_twin.project_model (user_id, last_activity_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS digital_twin.project_model")
    # `domain_evidence` first: it is the child of `domain_model`.
    op.execute("DROP TABLE IF EXISTS digital_twin.domain_evidence")
    op.execute("DROP TABLE IF EXISTS digital_twin.domain_model")
