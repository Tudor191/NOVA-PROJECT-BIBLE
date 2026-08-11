"""Real-Postgres verification of `PostgresDigitalTwinRepository` -- real
schema (via this engine's own Alembic migration `0001_initial_schema.py`),
real INSERT/SELECT/UPDATE round trips, mirroring every prior engine's own
`test_repository_real_postgres.py` convention.

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run
test` invocation (ADR-033) -- requires Docker. **Not executed in the
environment this file was written in** (no reachable Docker daemon there);
see `nova_testkit.postgres`'s module docstring for exactly what was and
wasn't verifiable here.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from nova_digital_twin_engine.domain.models import (
    CommunicationProfile,
    CompletedSessionEvidence,
    HabitSignal,
    PreferenceEvolutionEntry,
    ProactiveBoundaryPolicy,
    TrustMetric,
    TrustMetricHistoryEntry,
)
from nova_digital_twin_engine.domain.ports import OutboxEvent
from nova_digital_twin_engine.repository.postgres_digital_twin_repository import (
    PostgresDigitalTwinRepository,
)
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["DIGITAL_TWIN_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
def repository(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> PostgresDigitalTwinRepository:
    return PostgresDigitalTwinRepository(postgres_session_factory)


async def test_communication_profile_round_trips_and_upserts(
    repository: PostgresDigitalTwinRepository,
) -> None:
    user_id = uuid4()
    assert await repository.get_communication_profile(user_id) is None

    created = await repository.upsert_communication_profile(CommunicationProfile(user_id=user_id))
    assert created.verbosity == "moderate"

    updated = await repository.upsert_communication_profile(
        created.model_copy(update={"verbosity": "concise", "source": "learned"})
    )
    assert updated.verbosity == "concise"

    fetched = await repository.get_communication_profile(user_id)
    assert fetched is not None
    assert fetched.verbosity == "concise"
    assert fetched.source == "learned"


async def test_preference_evolution_entry_persists(
    repository: PostgresDigitalTwinRepository,
) -> None:
    entry = PreferenceEvolutionEntry(
        user_id=uuid4(),
        field="verbosity",
        previous_value="moderate",
        new_value="concise",
        confidence=0.9,
        source="test",
        reason="3 consecutive consistent observations",
    )
    created = await repository.create_preference_evolution_entry(entry)
    assert created.id == entry.id
    assert created.new_value == "concise"


async def test_habit_signal_persists(repository: PostgresDigitalTwinRepository) -> None:
    signal = HabitSignal(
        user_id=uuid4(), session_id=uuid4(), turn_count=5, observed_at=datetime.now(UTC)
    )
    created = await repository.record_habit_signal(signal)
    assert created.turn_count == 5


async def test_completed_session_evidence_round_trips_and_lists_recent(
    repository: PostgresDigitalTwinRepository,
) -> None:
    user_id = uuid4()
    older = CompletedSessionEvidence(
        session_id=uuid4(),
        user_id=user_id,
        turn_count=2,
        closed_at=datetime(2026, 1, 1, tzinfo=UTC),
        corrections=["a"],
    )
    newer = CompletedSessionEvidence(
        session_id=uuid4(),
        user_id=user_id,
        turn_count=3,
        closed_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    await repository.record_completed_session_evidence(older)
    await repository.record_completed_session_evidence(newer)

    recent = await repository.list_recent_completed_sessions(user_id, limit=1)
    assert len(recent) == 1
    assert recent[0].session_id == newer.session_id


async def test_trust_metric_round_trips_and_upserts(
    repository: PostgresDigitalTwinRepository,
) -> None:
    user_id = uuid4()
    assert await repository.get_trust_metric(user_id) is None

    metric = TrustMetric(user_id=user_id, correction_frequency=0.5, window_session_count=4)
    await repository.upsert_trust_metric(metric)

    fetched = await repository.get_trust_metric(user_id)
    assert fetched is not None
    assert fetched.correction_frequency == 0.5
    assert fetched.clarification_acceptance_rate is None


async def test_trust_metric_history_entry_persists(
    repository: PostgresDigitalTwinRepository,
) -> None:
    entry = TrustMetricHistoryEntry(
        user_id=uuid4(), correction_frequency=0.25, window_session_count=8
    )
    created = await repository.create_trust_metric_history_entry(entry)
    assert created.correction_frequency == 0.25


async def test_proactive_boundary_policy_round_trips_and_upserts(
    repository: PostgresDigitalTwinRepository,
) -> None:
    user_id = uuid4()
    assert await repository.get_proactive_boundary_policy(user_id) is None

    policy = ProactiveBoundaryPolicy(user_id=user_id, max_per_topic_per_window={"deploy": 2})
    await repository.upsert_proactive_boundary_policy(policy)

    fetched = await repository.get_proactive_boundary_policy(user_id)
    assert fetched is not None
    assert fetched.max_per_topic_per_window == {"deploy": 2}


async def test_outbox_enqueue_list_and_mark_dispatched_round_trip(
    repository: PostgresDigitalTwinRepository,
) -> None:
    outbox_id = await repository.enqueue_outbox(
        OutboxEvent(subject="personality.memory.update", payload={"x": 1}, correlation_id=uuid4())
    )

    ready = await repository.list_dispatch_ready()
    assert any(row.id == outbox_id for row in ready)

    await repository.mark_dispatched(outbox_id)

    ready_after = await repository.list_dispatch_ready()
    assert not any(row.id == outbox_id for row in ready_after)
