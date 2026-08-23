"""Real-Postgres verification of `PostgresRegistryRepository` -- real
schema (via this component's own Alembic migration chain,
`0001_initial_schema.py`), real INSERT/SELECT/UPDATE round trips against
the `agent_os.agent_package` table, including the `(id, version)`
composite primary-key uniqueness -> `AgentPackageAlreadyExistsError`
translation. Mirrors `agent-os/kernel`'s own
`test_repository_real_postgres.py` convention.

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run
test` invocation (ADR-033) -- requires Docker.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from nova_agent_os_registry.domain.models import AgentPackage
from nova_agent_os_registry.domain.ports import AgentPackageAlreadyExistsError
from nova_agent_os_registry.repository.postgres_registry_repository import (
    PostgresRegistryRepository,
)
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["AGENT_OS_REGISTRY_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
def repository(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> PostgresRegistryRepository:
    return PostgresRegistryRepository(postgres_session_factory)


def _package(**overrides: object) -> AgentPackage:
    defaults: dict[str, object] = {
        "id": "coding-agent",
        "category": "coding",
        "version": "1.2.0",
        "manifest_json": {"id": "coding-agent", "version": "1.2.0"},
        "installed_at": datetime.now(UTC),
        "health_status": "unknown",
        "checksum": "a" * 64,
    }
    defaults.update(overrides)
    return AgentPackage(**defaults)


async def test_insert_then_find_by_id_version_round_trips(
    repository: PostgresRegistryRepository,
) -> None:
    package = _package()
    assert await repository.find_by_id_version(package.id, package.version) is None

    inserted = await repository.insert(package)
    assert inserted == package

    fetched = await repository.find_by_id_version(package.id, package.version)
    assert fetched == package


async def test_inserting_a_duplicate_id_version_raises_already_exists(
    repository: PostgresRegistryRepository,
) -> None:
    package = _package()
    await repository.insert(package)

    duplicate = _package(checksum="b" * 64)
    with pytest.raises(AgentPackageAlreadyExistsError):
        await repository.insert(duplicate)


async def test_two_versions_of_the_same_id_coexist(
    repository: PostgresRegistryRepository,
) -> None:
    v1 = await repository.insert(_package(version="1.2.0"))
    v2 = await repository.insert(_package(version="1.3.0"))

    assert await repository.find_by_id_version("coding-agent", "1.2.0") == v1
    assert await repository.find_by_id_version("coding-agent", "1.3.0") == v2


async def test_find_latest_by_id_returns_the_most_recently_installed_version(
    repository: PostgresRegistryRepository,
) -> None:
    older = datetime(2026, 1, 1, tzinfo=UTC)
    newer = datetime(2026, 6, 1, tzinfo=UTC)
    await repository.insert(_package(version="1.2.0", installed_at=older))
    latest = await repository.insert(_package(version="1.3.0", installed_at=newer))

    found = await repository.find_latest_by_id("coding-agent")
    assert found is not None
    assert found.version == latest.version


async def test_find_latest_by_id_returns_none_for_an_unknown_id(
    repository: PostgresRegistryRepository,
) -> None:
    assert await repository.find_latest_by_id("unknown-agent") is None


async def test_list_by_category_returns_only_matching_rows(
    repository: PostgresRegistryRepository,
) -> None:
    coding = await repository.insert(_package(id="coding-agent", category="coding"))
    await repository.insert(_package(id="research-agent", category="research", version="0.1.0"))

    coding_rows = await repository.list_by_category("coding")
    assert [row.id for row in coding_rows] == [coding.id]


async def test_update_health_status_persists(repository: PostgresRegistryRepository) -> None:
    package = await repository.insert(_package())

    await repository.update_health_status(package.id, package.version, health_status="healthy")

    fetched = await repository.find_by_id_version(package.id, package.version)
    assert fetched is not None
    assert fetched.health_status == "healthy"


async def test_update_health_status_on_unknown_row_is_a_no_op(
    repository: PostgresRegistryRepository,
) -> None:
    # must not raise
    await repository.update_health_status("nonexistent", "0.0.0", health_status="healthy")
