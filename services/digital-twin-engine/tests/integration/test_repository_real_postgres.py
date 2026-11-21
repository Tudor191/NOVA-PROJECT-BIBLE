"""Real-Postgres verification of `PostgresDigitalTwinRepository` -- real
schema (via this engine's own Alembic migration chain,
`0001_initial_schema.py` + `0002_proactive_delivery.py`), real
INSERT/SELECT/UPDATE round trips, mirroring every prior engine's own
`test_repository_real_postgres.py` convention.

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run
test` invocation (ADR-033) -- requires Docker. **Not executed in the
environment this file was written in** (no reachable Docker daemon there);
see `nova_testkit.postgres`'s module docstring for exactly what was and
wasn't verifiable here.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from nova_digital_twin_engine.domain.models import (
    CommunicationProfile,
    CompletedSessionEvidence,
    HabitSignal,
    PreferenceEvolutionEntry,
    ProactiveBoundaryPolicy,
    ProactiveDeliveryRecord,
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


async def test_proactive_delivery_record_persists_and_lists_recent_by_window(
    repository: PostgresDigitalTwinRepository,
) -> None:
    user_id = uuid4()
    assert await repository.list_recent_proactive_deliveries(
        user_id, since=datetime(2026, 1, 1, tzinfo=UTC)
    ) == []

    stale = ProactiveDeliveryRecord(
        user_id=user_id, topic="deploy", delivered_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    recent = ProactiveDeliveryRecord(
        user_id=user_id, topic="deploy", delivered_at=datetime(2026, 8, 1, tzinfo=UTC)
    )
    await repository.record_proactive_delivery(stale)
    await repository.record_proactive_delivery(recent)

    within_window = await repository.list_recent_proactive_deliveries(
        user_id, since=datetime(2026, 6, 1, tzinfo=UTC)
    )
    assert len(within_window) == 1
    assert within_window[0].delivered_at == recent.delivered_at


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


# ---------------------------------------------------------------------------
# Phase 4E -- the three Part 16 domain tables (TDD 4E Sec9, Sec14.3, Sec19.4)
# ---------------------------------------------------------------------------
#
# Ratified Sec19.4: *"The test exercises real persisted rows and the real Digital
# Twin read path. The repository and database layers are not replaced with mocks;
# the fake repository used in Sec14.2's integration tier is explicitly not
# permitted here."* Everything below runs against real Postgres, real Alembic
# schema (migration 0003), and the real `PostgresDigitalTwinRepository`.


def _domain_model(user_id: UUID, domain: object, **overrides: object):  # type: ignore[no-untyped-def]
    """Construct through the real `DomainModel`, so its validators run here too --
    a test that reached past them could persist a state the API can never
    produce, and would then be asserting against a row production cannot create."""
    from nova_digital_twin_engine.domain.models import DomainModel

    return DomainModel(user_id=user_id, domain=domain, **overrides)  # type: ignore[arg-type]


async def test_a_domain_model_round_trips_with_its_reason_intact(
    repository: PostgresDigitalTwinRepository,
) -> None:
    """The reason is two columns (`reason_code`, `reason_detail`) and one object.
    A round trip that lost the code would turn Sec14.5 control 10 into prose."""
    from nova_digital_twin_engine.domain.models import (
        DomainReason,
        DomainReasonCode,
        DomainState,
        TwinDomain,
    )

    user_id = uuid4()
    model = _domain_model(
        user_id,
        TwinDomain.HARDWARE_ENVIRONMENT,
        state=DomainState.EMPTY,
        reason=DomainReason(
            code=DomainReasonCode.NO_SOURCE_ENGINE, detail="nova-companion is 4F's"
        ),
        unavailable_fields=["cpu", "gpu"],
    )

    await repository.record_domain_derivation(models=[model])
    fetched = await repository.get_domain_model(user_id, TwinDomain.HARDWARE_ENVIRONMENT)

    assert fetched is not None
    assert fetched.state is DomainState.EMPTY
    assert fetched.reason is not None
    assert fetched.reason.code is DomainReasonCode.NO_SOURCE_ENGINE
    assert fetched.reason.detail == "nova-companion is 4F's"
    assert fetched.unavailable_fields == ["cpu", "gpu"]


async def test_evidence_for_a_never_derived_domain_is_rejected_by_the_foreign_key(
    repository: PostgresDigitalTwinRepository,
) -> None:
    """**The structural half of Part 16 Sec69.** `domain_evidence` has a composite
    foreign key into `domain_model`, so provenance cannot exist for a domain that
    was never derived -- enforced by the database, not by a convention.

    This is the one property that only real Postgres can demonstrate: the fake
    repository has no referential integrity to violate.
    """
    from nova_digital_twin_engine.domain.models import (
        DomainEvidence,
        EvidenceKind,
        TwinDomain,
    )
    from sqlalchemy.exc import IntegrityError

    orphan = DomainEvidence(
        user_id=uuid4(),
        domain=TwinDomain.GOALS,
        kind=EvidenceKind.MEMORY_DECISION_RECORDED,
        source_record_id=uuid4(),
        source_created_at=datetime.now(UTC),
        observed_at=datetime.now(UTC),
    )

    with pytest.raises(IntegrityError):
        await repository.record_domain_derivation(models=[], evidence=[orphan])


async def test_a_redelivered_evidence_row_does_not_duplicate(
    repository: PostgresDigitalTwinRepository,
) -> None:
    """The primary key is `(user_id, domain, source_record_id)`. The bus is
    at-least-once, so this is what keeps a restart from inflating a count."""
    from nova_digital_twin_engine.domain.models import (
        DomainEvidence,
        DomainState,
        EvidenceKind,
        TwinDomain,
    )

    user_id = uuid4()
    model = _domain_model(
        user_id, TwinDomain.GOALS, state=DomainState.POPULATED, evidence_count=1
    )
    row = DomainEvidence(
        user_id=user_id,
        domain=TwinDomain.GOALS,
        kind=EvidenceKind.MEMORY_DECISION_RECORDED,
        source_record_id=uuid4(),
        source_created_at=datetime.now(UTC),
        observed_at=datetime.now(UTC),
    )

    await repository.record_domain_derivation(models=[model], evidence=[row])
    await repository.record_domain_derivation(models=[model], evidence=[row])

    assert len(await repository.list_domain_evidence(user_id, TwinDomain.GOALS)) == 1


async def test_evidence_is_returned_oldest_source_first_with_untimestamped_last(
    repository: PostgresDigitalTwinRepository,
) -> None:
    """A reconstruction reads as a history, and the ordering key is the *source's*
    timestamp -- not the row's `observed_at`, which for historical data is weeks
    later and in a different order."""
    from nova_digital_twin_engine.domain.models import (
        DomainEvidence,
        DomainState,
        EvidenceKind,
        TwinDomain,
    )

    user_id = uuid4()
    now = datetime.now(UTC)
    await repository.record_domain_derivation(
        models=[
            _domain_model(
                user_id,
                TwinDomain.PERSONAL_WORKFLOW,
                state=DomainState.POPULATED,
                evidence_count=3,
            )
        ],
        evidence=[
            DomainEvidence(
                user_id=user_id,
                domain=TwinDomain.PERSONAL_WORKFLOW,
                kind=EvidenceKind.MEMORY_LONG_TERM_CREATED,
                source_record_id=uuid4(),
                source_created_at=age,
                # Inserted in the opposite order to prove the query sorts.
                observed_at=now,
                attributes={"memory_type": "episodic"},
            )
            for age in (now - timedelta(days=5), None, now - timedelta(days=90))
        ],
    )

    rows = await repository.list_domain_evidence(user_id, TwinDomain.PERSONAL_WORKFLOW)

    assert [r.source_created_at for r in rows] == [
        now - timedelta(days=90),
        now - timedelta(days=5),
        None,
    ]


async def test_the_project_model_persists_a_multi_week_gap(
    repository: PostgresDigitalTwinRepository,
) -> None:
    """**AC-6 at the storage layer.** The gap is a stored column, not a read-time
    computation, so two reads of one derivation give the same answer."""
    from nova_digital_twin_engine.domain.models import ProjectModel

    user_id, project_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    await repository.record_domain_derivation(
        models=[],
        projects=[
            ProjectModel(
                user_id=user_id,
                project_id=project_id,
                memory_count=4,
                memory_type_counts={"project": 3, "episodic": 1},
                first_activity_at=now - timedelta(days=120),
                last_activity_at=now - timedelta(days=38),
                gap_days=38.0,
            )
        ],
    )

    fetched = await repository.get_project_model(user_id, project_id)

    assert fetched is not None
    assert fetched.memory_count == 4
    assert fetched.memory_type_counts == {"project": 3, "episodic": 1}
    assert fetched.last_activity_at == now - timedelta(days=38)
    assert fetched.gap_days == pytest.approx(38.0)
    assert fetched.gap_days > 21, "a multi-week gap must survive persistence"


async def test_a_null_gap_survives_persistence_as_null_not_zero(
    repository: PostgresDigitalTwinRepository,
) -> None:
    """`0.0` would render as "active today". A column default or a coercion
    anywhere in this path would turn "unknown" into exactly the wrong claim."""
    from nova_digital_twin_engine.domain.models import ProjectModel

    user_id, project_id = uuid4(), uuid4()
    await repository.record_domain_derivation(
        models=[],
        projects=[ProjectModel(user_id=user_id, project_id=project_id, memory_count=1)],
    )

    fetched = await repository.get_project_model(user_id, project_id)

    assert fetched is not None
    assert fetched.gap_days is None
    assert fetched.last_activity_at is None


async def test_projects_list_most_recently_active_first(
    repository: PostgresDigitalTwinRepository,
) -> None:
    from nova_digital_twin_engine.domain.models import ProjectModel

    user_id = uuid4()
    now = datetime.now(UTC)
    stale, fresh, unplaceable = uuid4(), uuid4(), uuid4()
    await repository.record_domain_derivation(
        models=[],
        projects=[
            ProjectModel(
                user_id=user_id,
                project_id=stale,
                memory_count=1,
                last_activity_at=now - timedelta(days=200),
                gap_days=200.0,
            ),
            ProjectModel(
                user_id=user_id,
                project_id=fresh,
                memory_count=1,
                last_activity_at=now - timedelta(days=1),
                gap_days=1.0,
            ),
            ProjectModel(user_id=user_id, project_id=unplaceable, memory_count=1),
        ],
    )

    order = [p.project_id for p in await repository.list_project_models(user_id)]

    assert order == [fresh, stale, unplaceable]


async def test_the_full_derivation_path_runs_against_real_postgres(
    repository: PostgresDigitalTwinRepository,
) -> None:
    """**Ratified Sec19.4, end to end.** The real derivation service, the real
    repository, the real schema -- the fake repository is not involved anywhere.

    This is the AC-6 chain minus the bus and the browser: a historically-dated
    memory event folded in, evidence persisted with its own `created_at`, and the
    project model read back through the real read path with a real multi-week gap.
    """
    from nova_contracts import PrivacyLevel
    from nova_digital_twin_engine import domain_derivation
    from nova_digital_twin_engine.domain.derivation import evidence_from_memory_created
    from nova_digital_twin_engine.domain.models import DomainState, TwinDomain

    user_id, project_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    for age_days in (90, 60, 33):
        await domain_derivation.record_evidence(
            repository,
            evidence_from_memory_created(
                user_id=user_id,
                memory_id=uuid4(),
                memory_type="project",
                privacy_level=PrivacyLevel.INTERNAL,
                project_id=project_id,
                knowledge_node_id=None,
                source_created_at=now - timedelta(days=age_days),
                observed_at=now,
            ),
            user_id=user_id,
        )

    model = await repository.get_domain_model(user_id, TwinDomain.PROJECTS)
    project = await repository.get_project_model(user_id, project_id)

    assert model is not None
    assert model.state is DomainState.POPULATED
    assert model.evidence_count == 3
    assert project is not None
    assert project.memory_count == 3
    assert project.first_activity_at == now - timedelta(days=90)
    assert project.last_activity_at == now - timedelta(days=33)
    assert project.gap_days is not None and project.gap_days > 21


async def test_a_restricted_memory_persists_nothing_against_real_postgres(
    repository: PostgresDigitalTwinRepository,
) -> None:
    """**Sec14.5 control 6 against the real database**, where "no row" is checkable
    rather than asserted about an in-memory dict."""
    from nova_contracts import PrivacyLevel
    from nova_digital_twin_engine import domain_derivation
    from nova_digital_twin_engine.domain.derivation import evidence_from_memory_created
    from nova_digital_twin_engine.domain.models import TwinDomain

    user_id, project_id = uuid4(), uuid4()
    await domain_derivation.record_evidence(
        repository,
        evidence_from_memory_created(
            user_id=user_id,
            memory_id=uuid4(),
            memory_type="procedural",
            privacy_level=PrivacyLevel.HIGHLY_SENSITIVE,
            project_id=project_id,
            knowledge_node_id="concept:credentials",
            source_created_at=datetime.now(UTC),
            observed_at=datetime.now(UTC),
        ),
        user_id=user_id,
    )

    assert await repository.list_domain_evidence(user_id) == []
    assert await repository.get_domain_model(user_id, TwinDomain.PROJECTS) is None
    assert await repository.get_project_model(user_id, project_id) is None
