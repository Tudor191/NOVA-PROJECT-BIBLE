"""Real-Postgres verification of `PostgresPerceptionRepository` -- closes
task #93's perception-engine leg (docs/design/nova-testkit/
technical-implementation-plan.md §4, §6). Real schema (via this engine's own
Alembic migration `0001_initial_schema.py`), real identity/consent round
trips, and -- the highest-value test in this file -- a real exercise of the
`identity_observation.identity_id` foreign key to `enrolled_identity` that the
Project Health Review (August 2026) found missing from the ORM model and the
Step 1 cleanup pass fixed (`repository/models.py`'s own comment cites that
fix directly): this is the first time that fix has ever run against an actual
Postgres foreign key, not just been re-declared in the ORM.

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
from nova_perception_engine.domain.models import ConsentGrant, EnrolledIdentity, IdentityObservation
from nova_perception_engine.domain.ports import OutboxEvent
from nova_perception_engine.repository.postgres_perception_repository import (
    PostgresPerceptionRepository,
)
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    """Runs this engine's real Alembic migration once per session against
    `postgres_container`, before any test below runs."""
    os.environ["PERCEPTION_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
def repository(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> PostgresPerceptionRepository:
    return PostgresPerceptionRepository(postgres_session_factory)


async def test_enroll_and_list_identities_round_trips_through_real_postgres(
    repository: PostgresPerceptionRepository,
) -> None:
    user_id = uuid4()
    enrolled = await repository.enroll_identity(
        EnrolledIdentity(user_id=user_id, modality="voice", template_ciphertext=b"opaque-bytes")
    )

    identities = await repository.list_identities(user_id=user_id)

    assert len(identities) == 1
    assert identities[0].identity_id == enrolled.identity_id
    assert identities[0].template_ciphertext == b"opaque-bytes"


async def test_get_identity_templates_filters_by_modality(
    repository: PostgresPerceptionRepository,
) -> None:
    user_id = uuid4()
    await repository.enroll_identity(
        EnrolledIdentity(user_id=user_id, modality="voice", template_ciphertext=b"voice-template")
    )
    await repository.enroll_identity(
        EnrolledIdentity(user_id=user_id, modality="face", template_ciphertext=b"face-template")
    )

    voice_only = await repository.get_identity_templates(user_id=user_id, modality="voice")

    assert len(voice_only) == 1
    assert voice_only[0].template_ciphertext == b"voice-template"


async def test_revoke_identity_hard_deletes(repository: PostgresPerceptionRepository) -> None:
    enrolled = await repository.enroll_identity(
        EnrolledIdentity(user_id=uuid4(), modality="voice", template_ciphertext=b"x")
    )

    revoked = await repository.revoke_identity(enrolled.identity_id)
    still_present = await repository.list_identities(user_id=enrolled.user_id)

    assert revoked is True
    assert still_present == []


async def test_consent_grant_status_and_revoke_round_trip(
    repository: PostgresPerceptionRepository,
) -> None:
    user_id = uuid4()
    await repository.grant_consent(
        ConsentGrant(user_id=user_id, source="microphone", scope="voice_identification")
    )

    assert await repository.has_active_consent(user_id=user_id, source="microphone") is True

    revoked = await repository.revoke_consent(user_id=user_id, source="microphone")

    assert revoked is not None
    assert revoked.revoked_at is not None
    assert await repository.has_active_consent(user_id=user_id, source="microphone") is False


async def test_record_identity_observation_enforces_the_real_foreign_key(
    repository: PostgresPerceptionRepository,
) -> None:
    """The Project Health Review / Step 1 fix under direct verification: a
    non-existent `identity_id` is rejected by the real foreign key to
    `enrolled_identity`, exactly matching what the migration always declared
    but the ORM model didn't, until Step 1 corrected it -- this is the first
    time that correction has run against a real Postgres constraint."""
    with pytest.raises(IntegrityError):
        await repository.record_identity_observation(
            IdentityObservation(
                user_id=uuid4(),
                identity_id=uuid4(),  # no matching enrolled_identity row
                fused_confidence=0.9,
                confidence_tier="high",
            )
        )


async def test_record_identity_observation_with_a_real_enrolled_identity(
    repository: PostgresPerceptionRepository,
) -> None:
    """The success path of the same foreign key: a real, previously-enrolled
    `identity_id` is accepted."""
    enrolled = await repository.enroll_identity(
        EnrolledIdentity(user_id=uuid4(), modality="face", template_ciphertext=b"y")
    )

    observation = await repository.record_identity_observation(
        IdentityObservation(
            user_id=enrolled.user_id,
            identity_id=enrolled.identity_id,
            fused_confidence=0.95,
            confidence_tier="high",
        )
    )

    assert observation.identity_id == enrolled.identity_id


async def test_outbox_enqueue_list_and_mark_dispatched_round_trip(
    repository: PostgresPerceptionRepository,
) -> None:
    outbox_id = await repository.enqueue_outbox(
        OutboxEvent(
            subject="perception.identity.observed", payload={"x": 1}, correlation_id=uuid4()
        )
    )

    ready = await repository.list_dispatch_ready()
    assert any(row.id == outbox_id for row in ready)

    await repository.mark_dispatched(outbox_id)

    ready_after = await repository.list_dispatch_ready()
    assert not any(row.id == outbox_id for row in ready_after)
