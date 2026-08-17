"""Real-Postgres verification of `PostgresCapabilityRepository` -- real
schema (via this engine's own Alembic migration chain,
`0001_initial_schema.py`), real INSERT/SELECT/DELETE round trips including
the `(name, version)` uniqueness violation -> `CapabilityAlreadyExistsError`
translation Fork 3C-4 depends on. Mirrors every prior engine's own
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
from nova_capability_engine.domain.ports import CapabilityAlreadyExistsError
from nova_capability_engine.repository.postgres_capability_repository import (
    PostgresCapabilityRepository,
)
from nova_contracts import Capability
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["CAPABILITY_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
def repository(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> PostgresCapabilityRepository:
    return PostgresCapabilityRepository(postgres_session_factory)


def _capability(**overrides: object) -> Capability:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "name": "filesystem",
        "description": "Read, write, and list files within a declared root.",
        "category": "filesystem",
        "version": "1.0.0",
        "required_permissions": ["filesystem:read", "filesystem:write"],
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "execution_adapter": "filesystem",
        "health_status": "healthy",
        "installed_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Capability(**defaults)  # type: ignore[arg-type]


async def test_insert_then_find_by_id_round_trips(
    repository: PostgresCapabilityRepository,
) -> None:
    capability = _capability()
    assert await repository.find_by_id(capability.id) is None

    inserted = await repository.insert(capability)
    assert inserted == capability

    fetched = await repository.find_by_id(capability.id)
    assert fetched == capability


async def test_find_by_name_version_round_trips(
    repository: PostgresCapabilityRepository,
) -> None:
    capability = _capability(name="git", version="1.0.0")
    await repository.insert(capability)

    fetched = await repository.find_by_name_version(name="git", version="1.0.0")
    assert fetched == capability
    assert await repository.find_by_name_version(name="git", version="2.0.0") is None


async def test_list_all_returns_every_inserted_capability(
    repository: PostgresCapabilityRepository,
) -> None:
    a = _capability(name="a-tool", version="1.0.0")
    b = _capability(name="b-tool", version="1.0.0")
    await repository.insert(a)
    await repository.insert(b)

    all_capabilities = await repository.list_all()
    assert {c.id for c in all_capabilities} >= {a.id, b.id}


async def test_inserting_a_duplicate_name_and_version_raises_capability_already_exists(
    repository: PostgresCapabilityRepository,
) -> None:
    capability = _capability(name="duplicate-tool", version="1.0.0")
    await repository.insert(capability)

    duplicate = _capability(name="duplicate-tool", version="1.0.0")
    with pytest.raises(CapabilityAlreadyExistsError):
        await repository.insert(duplicate)


async def test_delete_removes_a_row_and_returns_false_for_an_unknown_id(
    repository: PostgresCapabilityRepository,
) -> None:
    capability = _capability()
    await repository.insert(capability)

    assert await repository.delete(capability.id) is True
    assert await repository.find_by_id(capability.id) is None
    assert await repository.delete(capability.id) is False


async def test_record_installation_event_persists(
    repository: PostgresCapabilityRepository,
) -> None:
    await repository.record_installation_event(
        capability_id=None,
        name="pending-tool",
        version="1.0.0",
        stage="download",
        outcome="success",
    )
    # No read port is exposed for installation events (TDD 3C's own model
    # has no such API) -- this proves the insert itself does not raise,
    # the append-only log's own functional requirement.
