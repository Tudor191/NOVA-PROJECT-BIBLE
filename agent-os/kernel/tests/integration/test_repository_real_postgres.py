"""Real-Postgres verification of `PostgresKernelRepository` -- real schema
(via this component's own Alembic migration chain,
`0001_initial_schema.py`), real INSERT/SELECT/UPDATE round trips against
the `agent_os.agent_instance` table, including the `id` primary-key
uniqueness -> `AgentInstanceAlreadyExistsError` translation. Mirrors
`action-engine`'s own `test_repository_real_postgres.py` convention.

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run
test` invocation (ADR-033) -- requires Docker.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from nova_agent_os_kernel.domain.models import AgentInstance
from nova_agent_os_kernel.domain.ports import AgentInstanceAlreadyExistsError
from nova_agent_os_kernel.repository.postgres_kernel_repository import PostgresKernelRepository
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["AGENT_OS_KERNEL_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
def repository(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> PostgresKernelRepository:
    return PostgresKernelRepository(postgres_session_factory)


def _instance(**overrides: object) -> AgentInstance:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "agent_package_id": uuid4(),
        "category": "research",
        "execution_backend": "inprocess",
        "status": "running",
        "assigned_task_node_id": uuid4(),
        "started_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return AgentInstance(**defaults)


async def test_insert_then_find_by_id_round_trips(
    repository: PostgresKernelRepository,
) -> None:
    instance = _instance()
    assert await repository.find_by_id(instance.id) is None

    inserted = await repository.insert(instance)
    assert inserted == instance

    fetched = await repository.find_by_id(instance.id)
    assert fetched == instance


async def test_insert_round_trips_a_row_with_no_assigned_task_or_supervisor(
    repository: PostgresKernelRepository,
) -> None:
    instance = _instance(assigned_task_node_id=None, supervisor_id=None)
    await repository.insert(instance)

    fetched = await repository.find_by_id(instance.id)
    assert fetched is not None
    assert fetched.assigned_task_node_id is None
    assert fetched.supervisor_id is None


async def test_inserting_a_duplicate_id_raises_agent_instance_already_exists(
    repository: PostgresKernelRepository,
) -> None:
    instance = _instance()
    await repository.insert(instance)

    duplicate = _instance(id=instance.id)
    with pytest.raises(AgentInstanceAlreadyExistsError):
        await repository.insert(duplicate)


async def test_list_by_status_returns_only_matching_rows(
    repository: PostgresKernelRepository,
) -> None:
    running = await repository.insert(_instance(status="running"))
    await repository.insert(_instance(status="completed"))

    running_rows = await repository.list_by_status("running")
    assert [row.id for row in running_rows] == [running.id]


async def test_update_status_persists(repository: PostgresKernelRepository) -> None:
    instance = await repository.insert(_instance())

    await repository.update_status(instance.id, status="failed")

    fetched = await repository.find_by_id(instance.id)
    assert fetched is not None
    assert fetched.status == "failed"


async def test_update_status_on_unknown_id_is_a_no_op(
    repository: PostgresKernelRepository,
) -> None:
    await repository.update_status(uuid4(), status="failed")  # must not raise
