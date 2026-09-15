"""Real-Postgres verification of `PostgresCognitiveStateRepository` -- real
schema via this engine's own Alembic chain, real round trips.

**Four things only real Postgres can prove**, and each is here because a fake
would pass while the real driver failed:

1. **The `created_at`/`updated_at` round trip.** Phase 4E's ratified finding:
   `memory-engine`'s `create_long_term` shipped omitting exactly these two
   columns, the `server_default=func.now()` fired, and every tier above the real
   driver saw a plausible timestamp while the caller's value was discarded. That
   defect is invisible to a fake repository by construction.
2. **The CHECK constraints** actually reject out-of-range values -- a Protocol
   has no constraints to violate.
3. **`JSONB` round-tripping** of the three relation lists, including the `UUID`
   → `str` → `UUID` conversion the driver performs.
4. **Ordering across a genuine timestamp tie**, where only the `thought_id`
   tiebreaker makes the order deterministic.

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run test`
invocation (ADR-033) -- requires Docker.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from nova_cognitive_state_engine.domain.models import ActiveThought, AttentionLayer
from nova_cognitive_state_engine.domain.ports import ThoughtNotFoundError
from nova_cognitive_state_engine.repository.postgres_cognitive_state_repository import (
    PostgresCognitiveStateRepository,
)
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
USER = uuid4()


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["COGNITIVE_STATE_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
def repository(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> PostgresCognitiveStateRepository:
    return PostgresCognitiveStateRepository(postgres_session_factory)


def _thought(
    *,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    layer: AttentionLayer = AttentionLayer.ACTIVE,
    thought_id: UUID | None = None,
    **overrides: object,
) -> ActiveThought:
    moment = created_at or datetime.now(UTC)
    defaults: dict[str, object] = {
        "thought_id": thought_id or uuid4(),
        "user_id": USER,
        "description": "Prepare tomorrow's meeting summary.",
        "priority": 3,
        "confidence": 0.8,
        "current_progress": 0.4,
        "attention_layer": layer,
        "created_at": moment,
        "updated_at": updated_at or moment,
    }
    defaults.update(overrides)
    return ActiveThought(**defaults)  # type: ignore[arg-type]


async def test_a_historical_created_at_is_persisted_not_overwritten_by_the_column_default(
    repository: PostgresCognitiveStateRepository,
) -> None:
    """**The Phase 4E defect, made impossible here.**

    A thought created weeks ago must read back with *that* timestamp, not with
    `now()`. The column carries `server_default now()`, so this passes only
    because the repository writes both timestamps explicitly.
    """
    long_ago = datetime.now(UTC) - timedelta(days=90)
    stored = await repository.upsert_thought(_thought(created_at=long_ago))

    assert stored.created_at == long_ago
    assert stored.updated_at == long_ago

    read_back = await repository.get_thought(stored.thought_id)
    assert read_back.created_at == long_ago


async def test_upsert_preserves_created_at_and_advances_updated_at(
    repository: PostgresCognitiveStateRepository,
) -> None:
    """An Active Thought is *ongoing*, so its age is meaningful: re-upserting
    must not reset when the reasoning process began."""
    born = datetime.now(UTC) - timedelta(days=10)
    first = await repository.upsert_thought(_thought(created_at=born))

    later = born + timedelta(days=1)
    second = await repository.upsert_thought(
        _thought(
            thought_id=first.thought_id,
            created_at=later,
            updated_at=later,
            current_progress=0.9,
        )
    )

    assert second.created_at == born, "created_at moved on re-upsert"
    assert second.updated_at == later
    assert second.current_progress == 0.9


async def test_the_three_relation_lists_round_trip_through_jsonb(
    repository: PostgresCognitiveStateRepository,
) -> None:
    memories = (uuid4(), uuid4())
    projects = (uuid4(),)
    dependencies = (uuid4(),)

    stored = await repository.upsert_thought(
        _thought(
            related_memories=memories,
            related_projects=projects,
            dependencies=dependencies,
        )
    )
    read_back = await repository.get_thought(stored.thought_id)

    assert read_back.related_memories == memories
    assert read_back.related_projects == projects
    assert read_back.dependencies == dependencies


async def test_an_absent_estimated_completion_stays_null(
    repository: PostgresCognitiveStateRepository,
) -> None:
    """*"Not estimated"* survives the round trip as `None`. A sentinel date
    would be a fabricated timestamp, which TDD 4F §2.2 forbids."""
    stored = await repository.upsert_thought(_thought(estimated_completion=None))
    assert (await repository.get_thought(stored.thought_id)).estimated_completion is None


@pytest.mark.parametrize(
    ("constraint", "priority", "confidence", "current_progress"),
    [
        ("ck_active_thought_confidence_range", 1, 1.5, 0.0),
        ("ck_active_thought_progress_range", 1, 0.5, 1.5),
        ("ck_active_thought_priority_non_negative", -1, 0.5, 0.0),
    ],
)
async def test_the_check_constraints_are_real(
    postgres_session_factory: async_sessionmaker[AsyncSession],
    constraint: str,
    priority: int,
    confidence: float,
    current_progress: float,
) -> None:
    """Bypassing the domain model on purpose: the table must refuse an
    out-of-range value on its own. A Protocol has no constraint to violate,
    which is exactly why this tier exists.

    **Each of the three constraints gets its own case, and each asserts the
    constraint *by name*.** Without the name this would only prove that *some*
    constraint fired -- a negative `priority` that tripped the confidence check
    would pass a bare `pytest.raises`, and the column the test claims to cover
    would be unprotected.

    **No `session.begin()` here, deliberately** -- the repository-wide pattern
    for an expected violation (`autonomy-engine`, `personality-engine`,
    `kernel`), and the reason is not stylistic. A constraint violation puts the
    Postgres transaction into the aborted state; `pytest.raises` then swallows
    the error, so an enclosing `session.begin()` block exits *normally* and
    SQLAlchemy issues its commit -- `RELEASE SAVEPOINT` against a transaction
    that can no longer accept commands. The assertion passes and the teardown
    fails. Closing the session instead rolls the savepoint back, which is what
    recovers the connection for the next statement.
    """
    async with postgres_session_factory() as session:
        with pytest.raises(IntegrityError) as raised:
            await session.execute(
                text(
                    """
                    INSERT INTO cognitive_state.active_thought
                        (thought_id, user_id, description, priority, confidence,
                         current_progress, attention_layer, created_at, updated_at)
                    VALUES
                        (:tid, :uid, 'out of range', :priority, :confidence,
                         :current_progress, 'active', now(), now())
                    """
                ),
                {
                    "tid": uuid4(),
                    "uid": USER,
                    "priority": priority,
                    "confidence": confidence,
                    "current_progress": current_progress,
                },
            )

    assert constraint in str(raised.value), (
        f"expected {constraint} to reject the row, got: {raised.value}"
    )


async def test_listing_is_deterministic_across_a_timestamp_tie(
    repository: PostgresCognitiveStateRepository,
) -> None:
    """Two thoughts updated at the same instant must still come back in a
    stable order, or the panel reorders itself on every read."""
    moment = datetime.now(UTC)
    low = UUID("00000000-0000-0000-0000-0000000000a1")
    high = UUID("00000000-0000-0000-0000-0000000000f9")
    user = uuid4()

    await repository.upsert_thought(_thought(thought_id=low, created_at=moment, user_id=user))
    await repository.upsert_thought(_thought(thought_id=high, created_at=moment, user_id=user))

    first = [t.thought_id for t in await repository.list_thoughts(user_id=user)]
    second = [t.thought_id for t in await repository.list_thoughts(user_id=user)]

    assert first == second
    assert first == [high, low], "the thought_id tiebreaker is not being applied"


async def test_listing_narrows_to_one_attention_layer(
    repository: PostgresCognitiveStateRepository,
) -> None:
    user = uuid4()
    await repository.upsert_thought(_thought(user_id=user, layer=AttentionLayer.ACTIVE))
    await repository.upsert_thought(_thought(user_id=user, layer=AttentionLayer.DORMANT))

    dormant = await repository.list_thoughts(user_id=user, layer=AttentionLayer.DORMANT)
    assert [t.attention_layer for t in dormant] == [AttentionLayer.DORMANT]
    assert len(await repository.list_thoughts(user_id=user)) == 2


async def test_move_layer_persists_the_transition(
    repository: PostgresCognitiveStateRepository,
) -> None:
    stored = await repository.upsert_thought(_thought(layer=AttentionLayer.ACTIVE))
    moved = await repository.move_layer(stored.thought_id, AttentionLayer.IMMEDIATE)

    assert moved.attention_layer is AttentionLayer.IMMEDIATE
    assert (
        await repository.get_thought(stored.thought_id)
    ).attention_layer is AttentionLayer.IMMEDIATE


async def test_a_missing_thought_raises_rather_than_returning_none(
    repository: PostgresCognitiveStateRepository,
) -> None:
    with pytest.raises(ThoughtNotFoundError):
        await repository.get_thought(uuid4())

    with pytest.raises(ThoughtNotFoundError):
        await repository.move_layer(uuid4(), AttentionLayer.ACTIVE)


async def test_the_migration_creates_exactly_one_table_in_its_own_schema(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """**Additive only.** 4F.1 creates one table in a new schema and no
    speculative table for a later slice."""
    async with postgres_session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'cognitive_state' ORDER BY table_name"
                )
            )
        ).scalars().all()
    assert list(rows) == ["active_thought"]
