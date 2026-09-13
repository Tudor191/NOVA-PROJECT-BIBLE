"""Real-Postgres verification of `PostgresAutonomyRepository` -- real schema
via this engine's own Alembic chain, real round trips across all five
`autonomy` tables.

**TDD §16 makes this tier mandatory for this engine, not optional.** 4C.2's
`4eafa80` defect is the reason: *"source inspection and a fake repository
cannot exercise a foreign key, and that is exactly how the defect reached
CI."* The four things only real Postgres can prove are all here --

1. the **transaction coupling** of a suggestion decision with its
   decision-log row, including the foreign key that orders the two INSERTs;
2. the **append-only** guarantee against the real `ON DELETE RESTRICT`
   constraint, not against a Protocol's missing method;
3. **keyset pagination across a tie**, where two suggestions share a
   `created_at` and only the `id` tiebreaker makes the page boundary
   deterministic;
4. the real **Alembic migration chain** producing the schema the ORM expects.

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run
test` invocation (ADR-033) -- requires Docker.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

from nova_autonomy_engine.domain.models import (
    AutonomyLevel,
    DecisionLogEntry,
    DecisionOutcome,
    PermissionCategory,
    PermissionGrant,
    Policy,
    PolicyCheck,
    PolicyEffect,
    PolicyMatch,
    RiskLevel,
    Suggestion,
    SuggestionStatus,
)
from nova_autonomy_engine.domain.ports import (
    SuggestionAlreadyDecidedError,
    SuggestionNotFoundError,
)
from nova_autonomy_engine.repository.postgres_autonomy_repository import (
    PostgresAutonomyRepository,
)
from nova_testkit.postgres import run_alembic_upgrade

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
USER = uuid4()


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["AUTONOMY_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
def repository(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> PostgresAutonomyRepository:
    return PostgresAutonomyRepository(postgres_session_factory)


def _suggestion(*, created_at: datetime | None = None, title: str = "tidy up") -> Suggestion:
    return Suggestion(
        user_id=USER,
        category=PermissionCategory.MODIFY,
        risk=RiskLevel.LOW,
        title=title,
        created_at=created_at or datetime.now(UTC),
    )


def _log(suggestion: Suggestion, outcome: DecisionOutcome) -> DecisionLogEntry:
    return DecisionLogEntry(
        subject_id=suggestion.id,
        autonomy_level=AutonomyLevel.SUGGESTIVE,
        risk=suggestion.risk,
        confidence=0.0,
        policy_checks=[],
        outcome=outcome,
        reason="test",
    )


# --- The migration chain -----------------------------------------------------
async def test_the_migration_creates_exactly_the_five_tables(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with postgres_session_factory() as session:
        result = await session.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'autonomy' ORDER BY tablename")
        )
        assert [row[0] for row in result] == [
            "autonomy_level",
            "decision_log",
            "permission_grant",
            "policy",
            "suggestion",
        ]


async def test_the_migration_does_not_touch_another_engines_schema(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """TDD §19: additive only. `action.identity_confidence_policy` is untouched
    in structure **and** in content -- this migration creates no `action`
    schema and seeds no row anywhere."""
    async with postgres_session_factory() as session:
        result = await session.execute(
            text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'action'")
        )
        assert result.first() is None


async def test_the_decision_log_matches_doc_07s_column_definition(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Doc 07's canonical table, as written: column names, types and
    nullability come from the architecture document, not from convenience."""
    async with postgres_session_factory() as session:
        result = await session.execute(
            text(
                "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                "WHERE table_schema = 'autonomy' AND table_name = 'decision_log' "
                "ORDER BY ordinal_position"
            )
        )
        columns = {row[0]: (row[1], row[2]) for row in result}

    assert columns["id"] == ("uuid", "NO")
    assert columns["action_id"] == ("uuid", "NO")
    assert columns["autonomy_level"] == ("smallint", "NO")
    assert columns["risk"] == ("text", "NO")
    assert columns["confidence"] == ("real", "NO")
    assert columns["policy_checks"] == ("jsonb", "NO")
    assert columns["outcome"][1] == "YES"
    assert columns["created_at"] == ("timestamp with time zone", "NO")


# --- The transaction coupling (TDD §16's stated reason for this tier) --------
async def test_a_proposal_and_its_log_row_are_written_in_one_transaction(
    repository: PostgresAutonomyRepository,
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """**The 4C.2 lesson, exercised against a real foreign key.** The log row
    references the suggestion, so the parent INSERT must reach the database
    first. A fake dictionary cannot fail this test; Postgres can."""
    suggestion = _suggestion()
    await repository.insert_suggestion(suggestion, _log(suggestion, DecisionOutcome.PROPOSE))

    async with postgres_session_factory() as session:
        result = await session.execute(
            text(
                "SELECT suggestion_id, action_id FROM autonomy.decision_log "
                "WHERE action_id = :subject"
            ),
            {"subject": suggestion.id},
        )
        rows = result.all()

    assert len(rows) == 1
    assert rows[0][0] == suggestion.id
    assert rows[0][1] == suggestion.id


async def test_a_decision_and_its_log_row_are_written_in_one_transaction(
    repository: PostgresAutonomyRepository,
) -> None:
    suggestion = _suggestion()
    await repository.insert_suggestion(suggestion, _log(suggestion, DecisionOutcome.PROPOSE))

    decided = await repository.decide_suggestion(
        USER,
        suggestion.id,
        status=SuggestionStatus.APPROVED,
        log_entry=_log(suggestion, DecisionOutcome.PROPOSE),
    )

    assert decided.status is SuggestionStatus.APPROVED
    assert decided.decided_at is not None
    entries = await repository.list_decision_log(subject_id=suggestion.id)
    assert len(entries) == 2


async def test_a_log_row_cannot_reference_a_suggestion_that_does_not_exist(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The constraint is real, not decorative -- which is what makes the
    ordering test above meaningful."""
    from sqlalchemy.exc import IntegrityError

    async with postgres_session_factory() as session, pytest.raises(IntegrityError):
        await session.execute(
            text(
                "INSERT INTO autonomy.decision_log "
                "(id, action_id, suggestion_id, autonomy_level, risk, confidence, policy_checks) "
                "VALUES (:id, :aid, :sid, 1, 'low', 0.0, '[]'::jsonb)"
            ),
            {"id": uuid4(), "aid": uuid4(), "sid": uuid4()},
        )


# --- Append-only, against the real constraint --------------------------------
async def test_deleting_a_suggestion_cannot_erase_its_decision_record(
    repository: PostgresAutonomyRepository,
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """`ON DELETE RESTRICT`, not `CASCADE`. Bible Part 14: *"Store every
    important autonomous decision."* A cascade would make the log erasable
    through a side door even with no delete method on the repository."""
    from sqlalchemy.exc import IntegrityError

    suggestion = _suggestion()
    await repository.insert_suggestion(suggestion, _log(suggestion, DecisionOutcome.PROPOSE))

    async with postgres_session_factory() as session, pytest.raises(IntegrityError):
        await session.execute(
            text("DELETE FROM autonomy.suggestion WHERE id = :id"), {"id": suggestion.id}
        )


# --- Keyset pagination across a tie ------------------------------------------
async def test_pagination_is_deterministic_when_two_suggestions_share_a_timestamp(
    repository: PostgresAutonomyRepository,
) -> None:
    """The `id` tiebreaker, exercised. Without it a tied page boundary can
    repeat or skip a row -- the failure mode that only shows up under a real
    index scan."""
    moment = datetime.now(UTC)
    made = [_suggestion(created_at=moment, title=f"tied-{index}") for index in range(4)]
    for suggestion in made:
        await repository.insert_suggestion(suggestion, _log(suggestion, DecisionOutcome.PROPOSE))

    seen: list[str] = []
    cursor: str | None = None
    for _ in range(4):
        page = await repository.list_suggestions(USER, limit=2, cursor=cursor)
        seen += [str(item.id) for item in page.items]
        cursor = page.next_cursor
        if cursor is None:
            break

    assert len(seen) == len(set(seen)) == 4
    assert set(seen) == {str(suggestion.id) for suggestion in made}


# --- The decision lifecycle --------------------------------------------------
async def test_a_second_decision_is_refused_by_the_conditional_update(
    repository: PostgresAutonomyRepository,
) -> None:
    """The transition is `WHERE status = 'proposed'` in the database, not a
    read followed by a write -- so two approvals cannot both succeed."""
    suggestion = _suggestion()
    await repository.insert_suggestion(suggestion, _log(suggestion, DecisionOutcome.PROPOSE))
    await repository.decide_suggestion(
        USER,
        suggestion.id,
        status=SuggestionStatus.APPROVED,
        log_entry=_log(suggestion, DecisionOutcome.PROPOSE),
    )

    with pytest.raises(SuggestionAlreadyDecidedError) as excinfo:
        await repository.decide_suggestion(
            USER,
            suggestion.id,
            status=SuggestionStatus.REJECTED,
            log_entry=_log(suggestion, DecisionOutcome.DENY),
        )
    assert excinfo.value.status is SuggestionStatus.APPROVED


async def test_deciding_an_unknown_suggestion_raises_not_found(
    repository: PostgresAutonomyRepository,
) -> None:
    with pytest.raises(SuggestionNotFoundError):
        await repository.decide_suggestion(
            USER,
            uuid4(),
            status=SuggestionStatus.APPROVED,
            log_entry=DecisionLogEntry(
                subject_id=uuid4(),
                autonomy_level=AutonomyLevel.SUGGESTIVE,
                risk=RiskLevel.LOW,
                confidence=0.0,
            ),
        )


# --- The other three tables --------------------------------------------------
async def test_the_autonomy_level_round_trips(repository: PostgresAutonomyRepository) -> None:
    assert await repository.get_level(USER) is None
    await repository.set_level(USER, AutonomyLevel.SUGGESTIVE)
    stored = await repository.get_level(USER)
    assert stored is not None
    assert stored.level is AutonomyLevel.SUGGESTIVE

    await repository.set_level(USER, AutonomyLevel.OBSERVATION_ONLY)
    stored = await repository.get_level(USER)
    assert stored is not None
    assert stored.level is AutonomyLevel.OBSERVATION_ONLY


async def test_policies_round_trip_including_the_match_columns(
    repository: PostgresAutonomyRepository,
) -> None:
    policy = Policy(
        user_id=USER,
        name="never deploy after midnight",
        effect=PolicyEffect.DENY,
        match=PolicyMatch(
            category=PermissionCategory.DEPLOY,
            min_risk=RiskLevel.MODERATE,
            capability_class="cloud",
        ),
    )
    await repository.create_policy(policy)

    stored = await repository.get_policy(USER, policy.id)
    assert stored is not None
    assert stored.effect is PolicyEffect.DENY
    assert stored.match.category is PermissionCategory.DEPLOY
    assert stored.match.min_risk is RiskLevel.MODERATE
    assert stored.match.capability_class == "cloud"

    replaced = await repository.replace_policy(stored.model_copy(update={"enabled": False}))
    assert replaced is not None
    assert replaced.enabled is False

    assert await repository.delete_policy(USER, policy.id) is True
    assert await repository.get_policy(USER, policy.id) is None


async def test_permission_grants_upsert_by_category_and_leave_others_alone(
    repository: PostgresAutonomyRepository,
) -> None:
    await repository.upsert_permission_grants(
        USER,
        [
            PermissionGrant(
                user_id=USER, category=PermissionCategory.READ, max_risk=RiskLevel.MODERATE
            ),
            PermissionGrant(
                user_id=USER, category=PermissionCategory.CREATE, max_risk=RiskLevel.LOW
            ),
        ],
    )
    await repository.upsert_permission_grants(
        USER,
        [
            PermissionGrant(
                user_id=USER, category=PermissionCategory.READ, max_risk=RiskLevel.CRITICAL
            )
        ],
    )

    by_category = {
        grant.category: grant for grant in await repository.list_permission_grants(USER)
    }
    assert by_category[PermissionCategory.READ].max_risk is RiskLevel.CRITICAL
    assert by_category[PermissionCategory.CREATE].max_risk is RiskLevel.LOW
    assert PermissionCategory.DELETE not in by_category


async def test_policy_checks_survive_the_jsonb_round_trip(
    repository: PostgresAutonomyRepository,
) -> None:
    """The decision log's explanation is only useful if it comes back intact --
    Part 14's *"What policies were applied?"*"""
    suggestion = _suggestion()
    entry = _log(suggestion, DecisionOutcome.PROPOSE)
    entry.policy_checks = [
        PolicyCheck(policy_id=uuid4(), name="ask first", effect=PolicyEffect.REQUIRE_APPROVAL,
                    matched=True),
        PolicyCheck(policy_id=uuid4(), name="unrelated", effect=PolicyEffect.DENY, matched=False),
    ]
    await repository.insert_suggestion(suggestion, entry)

    stored = await repository.list_decision_log(subject_id=suggestion.id)
    assert len(stored) == 1
    assert [(check.name, check.matched) for check in stored[0].policy_checks] == [
        ("ask first", True),
        ("unrelated", False),
    ]


async def test_counts_are_scoped_by_status(repository: PostgresAutonomyRepository) -> None:
    first = _suggestion(title="one")
    second = _suggestion(title="two")
    for suggestion in (first, second):
        await repository.insert_suggestion(suggestion, _log(suggestion, DecisionOutcome.PROPOSE))
    await repository.decide_suggestion(
        USER,
        second.id,
        status=SuggestionStatus.REJECTED,
        log_entry=_log(second, DecisionOutcome.DENY),
    )

    assert await repository.count_suggestions(USER) == 2
    assert await repository.count_suggestions(USER, status=SuggestionStatus.PROPOSED) == 1
    assert await repository.count_suggestions(USER, status=SuggestionStatus.REJECTED) == 1


async def test_ping_succeeds_against_a_reachable_database(
    repository: PostgresAutonomyRepository,
) -> None:
    await repository.ping()
