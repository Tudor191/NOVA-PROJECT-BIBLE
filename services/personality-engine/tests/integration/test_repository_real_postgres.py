"""Real-Postgres verification of `PostgresPersonalityRepository` -- closes
task #93's personality-engine leg (docs/design/nova-testkit/
technical-implementation-plan.md §4, §6). Real schema (via this engine's own
Alembic migration `0001_initial_schema.py`), including its data-seeding INSERT
statements (Doc 23's core identity traits/values/forbidden behaviors), a real
UPDATE with `onupdate` timestamp advancement, and a real singleton `CHECK
(id = 1)` constraint the fake repository (`tests/fakes/repository.py`) cannot
represent at all.

Deliberately narrow: exercises the repository/infrastructure boundary only,
per direct instruction not to rewrite this engine's existing (fake-backed)
unit/integration tests merely to increase coverage.

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run test`
invocation (ADR-033) -- requires Docker. **Not executed in the environment
this file was written in** (no reachable Docker daemon there); see
`nova_testkit.postgres`'s module docstring for exactly what was and wasn't
verifiable here.
"""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from nova_personality_engine.domain.models import (
    MemoryProfile,
    ValidationResult,
    ViolationCheckFamily,
    ViolationRecord,
)
from nova_personality_engine.repository.postgres_personality_repository import (
    PostgresPersonalityRepository,
)
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    """Runs this engine's real Alembic migration once per session against
    `postgres_container`, before any test below runs -- including the
    migration's own data-seeding INSERTs for `core_identity`/`memory_profile`."""
    os.environ["PERSONALITY_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
def repository(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> PostgresPersonalityRepository:
    return PostgresPersonalityRepository(postgres_session_factory)


async def test_get_core_identity_returns_the_real_migration_seeded_row(
    repository: PostgresPersonalityRepository,
) -> None:
    """Verifies the migration's own data-seeding INSERT (Doc 23's twelve
    traits) landed correctly -- not just that the table exists."""
    identity = await repository.get_core_identity()

    assert identity is not None
    assert "calm" in identity.traits
    assert "Trust Before Intelligence" in identity.values
    assert "manipulation" in identity.forbidden_behaviors
    assert len(identity.traits) == 12


async def test_get_memory_profile_returns_the_real_migration_seeded_default(
    repository: PostgresPersonalityRepository,
) -> None:
    profile = await repository.get_memory_profile()

    assert profile.verbosity == "moderate"
    assert profile.source == "static_default"


async def test_update_memory_profile_persists_and_advances_updated_at(
    repository: PostgresPersonalityRepository,
) -> None:
    before = await repository.get_memory_profile()

    updated = await repository.update_memory_profile(
        MemoryProfile(
            verbosity="concise",
            technical_depth="expert",
            terminology_preference={"prefers": "code-first"},
            source="learned",
        )
    )

    assert updated.verbosity == "concise"
    assert updated.source == "learned"
    assert updated.updated_at >= before.updated_at

    refetched = await repository.get_memory_profile()
    assert refetched.verbosity == "concise"


async def test_record_validation_audit_persists_a_real_row(
    repository: PostgresPersonalityRepository, postgres_session: AsyncSession
) -> None:
    """`record_validation_audit` has no read-back method on the repository
    itself (write-only per its own domain port) -- verified here via a direct
    query against the real table, not by trusting the repository's return
    value alone."""
    session_id = uuid4()

    await repository.record_validation_audit(
        session_id=session_id,
        result=ValidationResult(
            passed=False,
            violations=[
                ViolationRecord(
                    check_family=ViolationCheckFamily.FORBIDDEN_PATTERN, detail="test violation"
                )
            ],
        ),
        selected_style="professional",
    )

    row = (
        await postgres_session.execute(
            text(
                "SELECT passed, selected_style FROM personality.validation_audit "
                "WHERE session_id = :session_id"
            ),
            {"session_id": session_id},
        )
    ).one()

    assert row.passed is False
    assert row.selected_style == "professional"


async def test_core_identity_singleton_check_constraint_is_enforced(
    postgres_session: AsyncSession,
) -> None:
    """A behavior the fake repository cannot represent at all: the real
    schema's `CHECK (id = 1)` constraint rejects a second `core_identity` row,
    matching the design doc's "there is exactly one NOVA" invariant."""
    with pytest.raises(IntegrityError):
        await postgres_session.execute(
            text(
                "INSERT INTO personality.core_identity "
                "(id, schema_version, traits, values, forbidden_behaviors, version_note) "
                "VALUES (2, 1, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, 'bogus')"
            )
        )
        await postgres_session.flush()
