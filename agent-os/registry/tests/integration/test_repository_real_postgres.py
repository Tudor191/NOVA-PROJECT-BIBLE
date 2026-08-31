"""Real-Postgres verification of `PostgresRegistryRepository` -- real
schema (via this component's own Alembic migration chain,
`0001_initial_schema.py`), real INSERT/SELECT/UPDATE round trips against
the `agent_os.agent_package` table, including the `(category, version)`
unique-constraint violation -> `AgentPackageAlreadyExistsError`
translation. Matches the approved Fork 3E-2 concrete ORM shape (UUID
surrogate PK, `UniqueConstraint("category", "version")`) -- see
`docs/design/phase-3/15-3e-supervisor-reconciliation.md` §A for the
correction record. Mirrors `agent-os/kernel`'s own
`test_repository_real_postgres.py` convention.

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run
test` invocation (ADR-033) -- requires Docker.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from nova_agent_os_registry.domain.models import AgentPackage
from nova_agent_os_registry.domain.ports import AgentPackageAlreadyExistsError
from nova_agent_os_registry.domain.selection import select_dispatch_version
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
        "id": uuid4(),
        "category": "coding",
        "version": "1.2.0",
        "manifest_json": {"id": "coding-agent", "version": "1.2.0"},
        "installed_at": datetime.now(UTC),
        "health_status": "unknown",
        "checksum": "a" * 64,
    }
    defaults.update(overrides)
    return AgentPackage(**defaults)


async def test_insert_then_find_by_category_version_round_trips(
    repository: PostgresRegistryRepository,
) -> None:
    package = _package()
    assert await repository.find_by_category_version(package.category, package.version) is None

    inserted = await repository.insert(package)
    assert inserted == package

    fetched = await repository.find_by_category_version(package.category, package.version)
    assert fetched == package


async def test_the_surrogate_id_is_a_real_uuid_used_consistently(
    repository: PostgresRegistryRepository,
) -> None:
    """Point 9(c): the UUID surrogate key round-trips through ORM,
    repository, and the migration's own `UUID` column type -- proving
    consistency, not just that the domain model happens to type-hint
    `UUID`."""
    package = _package()
    inserted = await repository.insert(package)

    assert inserted.id == package.id
    fetched = await repository.find_by_category_version(package.category, package.version)
    assert fetched is not None
    assert fetched.id == package.id

    await repository.update_health_status(package.id, health_status="healthy")
    updated = await repository.find_by_category_version(package.category, package.version)
    assert updated is not None
    assert updated.id == package.id
    assert updated.health_status == "healthy"


async def test_inserting_a_duplicate_category_version_raises_already_exists(
    repository: PostgresRegistryRepository,
) -> None:
    package = _package()
    await repository.insert(package)

    duplicate = _package(id=uuid4(), checksum="b" * 64)
    with pytest.raises(AgentPackageAlreadyExistsError):
        await repository.insert(duplicate)


async def test_two_different_categories_coexist_at_the_same_version(
    repository: PostgresRegistryRepository,
) -> None:
    """Point 9(a) at the real-Postgres level: `(category, version)`
    uniqueness must not forbid two *different* categories from sharing a
    version number."""
    qa_package = await repository.insert(_package(category="qa", version="1.0.0"))
    coding_package = await repository.insert(_package(category="coding", version="1.0.0"))

    assert qa_package.id != coding_package.id
    assert await repository.find_by_category_version("qa", "1.0.0") is not None
    assert await repository.find_by_category_version("coding", "1.0.0") is not None


async def test_two_versions_of_the_same_category_coexist(
    repository: PostgresRegistryRepository,
) -> None:
    v1 = await repository.insert(_package(category="coding", version="1.2.0"))
    v2 = await repository.insert(_package(category="coding", version="1.3.0"))

    assert await repository.find_by_category_version("coding", "1.2.0") == v1
    assert await repository.find_by_category_version("coding", "1.3.0") == v2


async def test_hot_load_coexistence_selects_the_newest_healthy_version(
    repository: PostgresRegistryRepository,
) -> None:
    """TDD 3E §14 acceptance criterion #3 against real Postgres: `1.1.0`
    and `1.2.0` coexist as real rows under one category, and the real
    selection policy (`domain/selection.py`, the same function the served
    RPC uses) picks `1.2.0`. Full design record: `docs/design/phase-3/
    16-3e-hot-load-design-decision.md`."""
    v110 = await repository.insert(
        _package(category="hotload-coexist", version="1.1.0", health_status="healthy")
    )
    v120 = await repository.insert(
        _package(category="hotload-coexist", version="1.2.0", health_status="healthy")
    )

    rows = await repository.list_by_category("hotload-coexist")
    assert {row.id for row in rows} == {v110.id, v120.id}

    selected = select_dispatch_version(rows)
    assert selected is not None
    assert selected.version == "1.2.0"
    assert selected.id == v120.id


async def test_hot_load_falls_back_to_the_older_healthy_version_in_real_postgres(
    repository: PostgresRegistryRepository,
) -> None:
    """The newest row installed but never promoted past `"unknown"` (a
    failed `on_load`) must not make the category undispatchable while an
    older healthy row exists."""
    v110 = await repository.insert(
        _package(category="hotload-fallback", version="1.1.0", health_status="healthy")
    )
    await repository.insert(
        _package(category="hotload-fallback", version="1.2.0", health_status="unknown")
    )

    selected = select_dispatch_version(await repository.list_by_category("hotload-fallback"))
    assert selected is not None
    assert selected.version == "1.1.0"
    assert selected.id == v110.id


async def test_installing_a_newer_version_leaves_the_older_row_unmutated_in_real_postgres(
    repository: PostgresRegistryRepository,
) -> None:
    """The persistence-level guarantee every already-dispatched
    `agent_instance.agent_package_id` pin depends on: inserting `1.2.0`
    never touches `1.1.0`'s row."""
    v110 = await repository.insert(
        _package(category="hotload-immutable", version="1.1.0", health_status="healthy")
    )
    before = await repository.find_by_category_version("hotload-immutable", "1.1.0")

    await repository.insert(
        _package(category="hotload-immutable", version="1.2.0", health_status="healthy")
    )

    after = await repository.find_by_category_version("hotload-immutable", "1.1.0")
    assert after == before
    assert after is not None
    assert after.id == v110.id


async def test_find_latest_by_category_returns_the_most_recently_installed_version(
    repository: PostgresRegistryRepository,
) -> None:
    older = datetime(2026, 1, 1, tzinfo=UTC)
    newer = datetime(2026, 6, 1, tzinfo=UTC)
    await repository.insert(_package(category="coding", version="1.2.0", installed_at=older))
    latest = await repository.insert(
        _package(category="coding", version="1.3.0", installed_at=newer)
    )

    found = await repository.find_latest_by_category("coding")
    assert found is not None
    assert found.version == latest.version


async def test_find_latest_by_category_returns_none_for_an_unknown_category(
    repository: PostgresRegistryRepository,
) -> None:
    assert await repository.find_latest_by_category("unknown-category") is None


async def test_list_by_category_returns_only_matching_rows(
    repository: PostgresRegistryRepository,
) -> None:
    coding = await repository.insert(_package(category="coding"))
    await repository.insert(_package(category="research", version="0.1.0"))

    coding_rows = await repository.list_by_category("coding")
    assert [row.id for row in coding_rows] == [coding.id]


async def test_update_health_status_persists(repository: PostgresRegistryRepository) -> None:
    package = await repository.insert(_package())

    await repository.update_health_status(package.id, health_status="healthy")

    fetched = await repository.find_by_category_version(package.category, package.version)
    assert fetched is not None
    assert fetched.health_status == "healthy"


async def test_update_health_status_on_unknown_id_is_a_no_op(
    repository: PostgresRegistryRepository,
) -> None:
    # must not raise
    await repository.update_health_status(uuid4(), health_status="healthy")
