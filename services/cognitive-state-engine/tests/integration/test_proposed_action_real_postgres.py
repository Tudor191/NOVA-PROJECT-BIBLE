"""`proposed_action` against **real PostgreSQL** -- Phase 4F.6, A-4F6-2a (TDD
4F.6 §19: *"Schema changes permitted by this contract: exactly one -- the
nullable JSONB column on `cognitive_state.active_thought`"*).

Two claims only a real database can decide:

1. **Migration 0002 is exactly that one change.** One nullable `JSONB` column is
   added; every 0001 column and every 0001 CHECK constraint is still there,
   unaltered, and nothing else is added.
2. **The proposal survives the real driver**, read back with **independent SQL
   on its own connection** -- and "no proposal" is SQL `NULL`, not a JSON
   `null` or an empty object a later reader could mistake for one.

Writes use a real, **committing** engine rather than the shared rollback
fixture, whose writes are invisible to a second connection (4F.3/4F.4/4F.5's
recorded reasoning).

`@pytest.mark.real_infra`: requires Docker.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from nova_cognitive_state_engine.domain.models import (
    ActiveThought,
    AttentionLayer,
    ProposedAction,
)
from nova_cognitive_state_engine.repository.postgres_cognitive_state_repository import (
    PostgresCognitiveStateRepository,
)
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

PROPOSAL = {
    "category": "modify",
    "risk": "low",
    "action_type": "filesystem",
    "execution_target": "filesystem",
    "verification_method": "checksum",
    "title": "rotate the scratch directory",
    "detail": "keep the last seven",
}

_COLUMNS_0001 = [
    "thought_id",
    "user_id",
    "description",
    "priority",
    "confidence",
    "current_progress",
    "dependencies",
    "related_memories",
    "related_projects",
    "estimated_completion",
    "attention_layer",
    "created_at",
    "updated_at",
]
"""0001's columns, in 0001's order -- copied from the migration, not queried,
so a changed column fails here rather than being absorbed."""

_CHECKS_0001 = {
    "ck_active_thought_confidence_range",
    "ck_active_thought_progress_range",
    "ck_active_thought_priority_non_negative",
}


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["COGNITIVE_STATE_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
async def database(postgres_container: PostgresContainer) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(postgres_container.get_connection_url())
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM cognitive_state.active_thought"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM cognitive_state.active_thought"))
    await engine.dispose()


@pytest.fixture
def repository(database: AsyncEngine) -> PostgresCognitiveStateRepository:
    return PostgresCognitiveStateRepository(async_sessionmaker(database, expire_on_commit=False))


def _thought(
    *, proposal: dict | None, layer: AttentionLayer = AttentionLayer.ACTIVE
) -> ActiveThought:
    moment = datetime.now(UTC)
    return ActiveThought(
        thought_id=uuid4(),
        user_id=uuid4(),
        description="Keep the scratch directory bounded.",
        priority=2,
        confidence=0.6,
        current_progress=0.1,
        attention_layer=layer,
        created_at=moment,
        updated_at=moment,
        proposed_action=proposal,  # type: ignore[arg-type]
    )


async def _row(database: AsyncEngine, thought_id: UUID) -> dict:
    async with database.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT proposed_action, proposed_action IS NULL AS is_sql_null, "
                "jsonb_typeof(proposed_action) AS json_type, attention_layer "
                "FROM cognitive_state.active_thought WHERE thought_id = :id"
            ),
            {"id": thought_id},
        )
        return dict(result.mappings().one())


# --- the migration ---------------------------------------------------------------


async def test_0002_adds_exactly_one_nullable_jsonb_column(database: AsyncEngine) -> None:
    async with database.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(
                        "SELECT column_name, data_type, is_nullable, column_default "
                        "FROM information_schema.columns "
                        "WHERE table_schema = 'cognitive_state' AND table_name = 'active_thought' "
                        "ORDER BY ordinal_position"
                    )
                )
            )
            .mappings()
            .all()
        )

    assert [row["column_name"] for row in rows] == [*_COLUMNS_0001, "proposed_action"]
    added = rows[-1]
    assert added["data_type"] == "jsonb"
    assert added["is_nullable"] == "YES"
    assert added["column_default"] is None


async def test_0002_leaves_the_check_constraints_exactly_as_0001_defined_them(
    database: AsyncEngine,
) -> None:
    async with database.connect() as connection:
        names = (
            (
                await connection.execute(
                    text(
                        "SELECT conname FROM pg_constraint WHERE contype = 'c' "
                        "AND conrelid = 'cognitive_state.active_thought'::regclass"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert set(names) == _CHECKS_0001


async def test_0002_adds_no_table(database: AsyncEngine) -> None:
    async with database.connect() as connection:
        tables = (
            (
                await connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'cognitive_state' AND table_type = 'BASE TABLE'"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert list(tables) == ["active_thought"]


# --- the round trip ----------------------------------------------------------------


async def test_a_proposal_round_trips_and_is_stored_as_a_json_object(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    stored = await repository.upsert_thought(_thought(proposal=PROPOSAL))

    row = await _row(database, stored.thought_id)
    assert row["json_type"] == "object"
    assert row["proposed_action"] == PROPOSAL  # the enum values, exactly as authored

    read_back = await repository.get_thought(stored.thought_id)
    assert read_back.proposed_action == ProposedAction.model_validate(PROPOSAL)


async def test_no_proposal_is_sql_null_not_a_json_value(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    stored = await repository.upsert_thought(_thought(proposal=None))

    row = await _row(database, stored.thought_id)
    assert row["is_sql_null"] is True
    assert row["json_type"] is None

    assert (await repository.get_thought(stored.thought_id)).proposed_action is None


async def test_moving_a_layer_keeps_the_proposal(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    stored = await repository.upsert_thought(_thought(proposal=PROPOSAL))

    await repository.move_layer(stored.thought_id, AttentionLayer.IMMEDIATE)

    row = await _row(database, stored.thought_id)
    assert row["attention_layer"] == "immediate"
    assert row["proposed_action"] == PROPOSAL


async def test_a_proposal_can_be_withdrawn_back_to_null(
    repository: PostgresCognitiveStateRepository, database: AsyncEngine
) -> None:
    """Upserting the thought without its proposal clears the column -- the
    repository writes the field it is given rather than keeping a stale one."""
    stored = await repository.upsert_thought(_thought(proposal=PROPOSAL))
    await repository.upsert_thought(stored.model_copy(update={"proposed_action": None}))

    assert (await _row(database, stored.thought_id))["is_sql_null"] is True
