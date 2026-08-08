"""Verifies `nova_testkit.postgres`'s fixtures against a real Postgres container
-- real schema creation, a real INSERT/SELECT round trip, a real constraint
violation, and real transaction-rollback isolation between tests (implementation
plan §13's verification bar: "the container started" is not sufficient).

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run test`
invocation (ADR-033) -- requires Docker. **Not executed in the environment this
file was written in** (no reachable Docker daemon there); correctness rests on
direct API introspection against the installed `testcontainers`/`sqlalchemy`
packages (see `postgres.py`'s own module docstring) and manual review, not a
passing test run. The first Docker-capable environment to run
`pytest -m real_infra` here is this file's real verification.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.real_infra

_CREATE_TABLE = text(
    """
    CREATE TABLE IF NOT EXISTS testkit_widget (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    )
    """
)


async def test_real_insert_and_select_round_trip(postgres_session: AsyncSession) -> None:
    await postgres_session.execute(_CREATE_TABLE)
    await postgres_session.execute(text("INSERT INTO testkit_widget (name) VALUES ('gizmo')"))

    row = (
        await postgres_session.execute(text("SELECT name FROM testkit_widget WHERE name = 'gizmo'"))
    ).one()

    assert row.name == "gizmo"


async def test_real_unique_constraint_is_enforced(postgres_session: AsyncSession) -> None:
    await postgres_session.execute(_CREATE_TABLE)
    await postgres_session.execute(text("INSERT INTO testkit_widget (name) VALUES ('dupe')"))

    with pytest.raises(IntegrityError):
        await postgres_session.execute(text("INSERT INTO testkit_widget (name) VALUES ('dupe')"))
        await postgres_session.flush()


async def test_transaction_rollback_isolates_each_test(postgres_session: AsyncSession) -> None:
    """Runs after the two tests above in file order; if rollback isolation were
    broken, the table created by `test_real_insert_and_select_round_trip` would
    still contain `'gizmo'` here."""
    await postgres_session.execute(_CREATE_TABLE)

    count = (
        await postgres_session.execute(text("SELECT count(*) AS n FROM testkit_widget"))
    ).scalar_one()

    assert count == 0
