"""Phase 4C milestone 4C.2d against real Postgres: the lifecycle paths
themselves -- `dispatch_task_node` and `reconcile_running_instances` -- driven
end to end over a real `PostgresKernelRepository`.

`tests/unit/test_activity_wiring.py` proves the *call shape*: that each kind is
produced, and that the coupled ones ride their own state mutation rather than a
second `append_activity`. It cannot prove atomicity, because its repository is a
dictionary. `tests/integration/test_repository_real_postgres.py` proves the
repository's transaction honours the coupling. **This file joins the two**: a
real lifecycle operation, a real transaction, and -- in
`test_a_failed_dispatch_leaves_no_orphan_dispatched_row` -- a real abort that
must take the activity down with the instance.

It also verifies what only a real database can: that `detail` survives the
JSONB round trip with its exact shape, and that a missing correlation is stored
as SQL `NULL` rather than as a string.

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run test`
invocation (ADR-033) -- requires Docker.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from nova_agent_os_kernel.domain.activity import AgentActivityKind
from nova_agent_os_kernel.domain.models import AgentInstance, AgentInstanceHandle
from nova_agent_os_kernel.domain.ports import AgentInstanceAlreadyExistsError
from nova_agent_os_kernel.domain.reconciliation import reconcile_running_instances
from nova_agent_os_kernel.domain.scheduler import dispatch_task_node
from nova_agent_os_kernel.repository.postgres_kernel_repository import PostgresKernelRepository
from nova_contracts import (
    AgentPackageSnapshot,
    AgentResult,
    TaskNodeSnapshot,
    ValidationOutcome,
)
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

from tests.fakes.event_publisher import FakeEventPublisher
from tests.fakes.ports import FakeAgentExecutionBackend, FakeRegistryPort, FakeSupervisorPort

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    """Same chain `test_repository_real_postgres.py` runs. `alembic upgrade
    head` is idempotent, so both files reaching it on the shared session
    container is a no-op for whichever runs second."""
    os.environ["AGENT_OS_KERNEL_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
def repository(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> PostgresKernelRepository:
    return PostgresKernelRepository(postgres_session_factory)


def _node(**overrides: object) -> TaskNodeSnapshot:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "objective": "Research rate limiting approaches",
        "depends_on": [],
        "assigned_agent_category": "research",
        "effort_hours": 1.0,
        "confidence": 0.7,
        "risk": "low",
        "status": "ready",
    }
    defaults.update(overrides)
    return TaskNodeSnapshot(**defaults)


def _package(**overrides: object) -> AgentPackageSnapshot:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "category": "research",
        "version": "0.1.0",
        "manifest_json": {"id": "research-agent", "version": "0.1.0"},
        "health_status": "healthy",
    }
    defaults.update(overrides)
    return AgentPackageSnapshot(**defaults)


def _handle(
    *, task_node_id: UUID, correlation_id: UUID, status: str = "success", review: bool = False
) -> AgentInstanceHandle:
    result = AgentResult(
        agent_instance_id=uuid4(),
        task_node_id=task_node_id,
        status=status,
        output={"finding": "token-bucket rate limiting"},
        confidence=0.9 if status == "success" else None,
        self_validation_passed=status == "success",
        correlation_id=correlation_id,
    )
    return AgentInstanceHandle(
        instance_id=result.agent_instance_id,
        result=result,
        validation=ValidationOutcome(passed=status == "success", requires_peer_review=review),
    )


async def _dispatch(
    *,
    repository: PostgresKernelRepository,
    handles: list[AgentInstanceHandle],
    node: TaskNodeSnapshot,
    correlation_id: UUID,
    package: AgentPackageSnapshot | None = None,
    restart_instance_ids: list[UUID] | None = None,
    peer_validation: str = "not_required",
) -> UUID | None:
    return await dispatch_task_node(
        node,
        repository=repository,
        registry_port=FakeRegistryPort(package=package if package is not None else _package()),
        supervisor_port=FakeSupervisorPort(
            restart_instance_ids=restart_instance_ids,
            peer_validation=peer_validation,  # type: ignore[arg-type]
        ),
        execution_backend=FakeAgentExecutionBackend(
            handles=handles, review_replies=[None] * len(handles)
        ),
        event_publisher=FakeEventPublisher(),
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )


# --- the dispatch lifecycle, persisted --------------------------------------


async def test_a_real_successful_dispatch_persists_dispatched_then_completed(
    repository: PostgresKernelRepository,
) -> None:
    node = _node()
    correlation_id = uuid4()
    package = _package()

    instance_id = await _dispatch(
        repository=repository,
        handles=[_handle(task_node_id=node.id, correlation_id=correlation_id)],
        node=node,
        correlation_id=correlation_id,
        package=package,
    )

    assert instance_id is not None
    fetched = await repository.find_by_id(instance_id)
    assert fetched is not None
    assert fetched.status == "completed"

    # Newest first, so the terminal row leads.
    items = (await repository.list_activity(instance_id)).items
    assert [a.kind for a in items] == [
        AgentActivityKind.COMPLETED,
        AgentActivityKind.DISPATCHED,
    ]
    assert all(a.correlation_id == correlation_id for a in items)
    assert items[1].detail == {
        "task_node_id": str(node.id),
        "category": "research",
        "agent_package_id": str(package.id),
        "execution_backend": "inprocess",
    }
    assert items[0].detail == {"task_node_id": str(node.id), "outcome": "success"}


async def test_a_real_failed_dispatch_persists_dispatched_then_failed(
    repository: PostgresKernelRepository,
) -> None:
    node = _node()
    correlation_id = uuid4()

    instance_id = await _dispatch(
        repository=repository,
        handles=[
            _handle(task_node_id=node.id, correlation_id=correlation_id, status="failure")
        ],
        node=node,
        correlation_id=correlation_id,
        restart_instance_ids=[],
    )

    assert instance_id is not None
    fetched = await repository.find_by_id(instance_id)
    assert fetched is not None
    assert fetched.status == "failed"
    assert [a.kind for a in (await repository.list_activity(instance_id)).items] == [
        AgentActivityKind.FAILED,
        AgentActivityKind.DISPATCHED,
    ]


async def test_a_real_planned_restart_persists_restart_planned(
    repository: PostgresKernelRepository,
) -> None:
    node = _node()
    correlation_id = uuid4()
    first = _handle(task_node_id=node.id, correlation_id=correlation_id, status="failure")
    retry = _handle(task_node_id=node.id, correlation_id=correlation_id)

    retry_id = await _dispatch(
        repository=repository,
        handles=[first, retry],
        node=node,
        correlation_id=correlation_id,
        restart_instance_ids=[first.instance_id],
    )

    assert [a.kind for a in (await repository.list_activity(first.instance_id)).items] == [
        AgentActivityKind.RESTART_PLANNED,
        AgentActivityKind.FAILED,
        AgentActivityKind.DISPATCHED,
    ]
    assert retry_id == retry.instance_id
    assert [a.kind for a in (await repository.list_activity(retry.instance_id)).items] == [
        AgentActivityKind.COMPLETED,
        AgentActivityKind.DISPATCHED,
    ]


async def test_a_real_peer_review_round_persists_its_verdict(
    repository: PostgresKernelRepository,
) -> None:
    node = _node(assigned_agent_category="coding")
    correlation_id = uuid4()
    package = _package(
        category="coding",
        manifest_json={
            "id": "coding-agent",
            "version": "0.1.0",
            "peer_reviewer_category": "architect",
        },
    )

    instance_id = await _dispatch(
        repository=repository,
        handles=[
            _handle(task_node_id=node.id, correlation_id=correlation_id, review=True)
        ],
        node=node,
        correlation_id=correlation_id,
        package=package,
        peer_validation="approved",
    )

    assert instance_id is not None
    items = (await repository.list_activity(instance_id)).items
    review = next(a for a in items if a.kind is AgentActivityKind.PEER_REVIEW)
    assert review.detail == {
        "reviewer_category": "architect",
        "peer_validation": "approved",
        "reviewer_available": False,
    }
    assert review.correlation_id == correlation_id


# --- the transaction, proven through the lifecycle --------------------------


async def test_a_failed_dispatch_leaves_no_orphan_dispatched_row(
    repository: PostgresKernelRepository,
) -> None:
    """The atomicity guarantee, reached the way production reaches it.

    The backend mints the instance id up front, so seeding a row with that id
    makes the Scheduler's own `insert` abort on the primary key -- with the
    `dispatched` activity already in the same statement batch. If the two were
    not one transaction, the activity would survive and the panel would show a
    dispatch for an instance that never existed.
    """
    node = _node()
    correlation_id = uuid4()
    handle = _handle(task_node_id=node.id, correlation_id=correlation_id)

    # The row the Scheduler is about to collide with.
    await repository.insert(
        AgentInstance(
            id=handle.instance_id,
            agent_package_id=uuid4(),
            category="research",
            execution_backend="inprocess",
            status="running",
            assigned_task_node_id=uuid4(),
            started_at=datetime.now(UTC),
            health_status="unknown",
        )
    )

    with pytest.raises(AgentInstanceAlreadyExistsError):
        await _dispatch(
            repository=repository,
            handles=[handle],
            node=node,
            correlation_id=correlation_id,
        )

    assert (await repository.list_activity(handle.instance_id)).items == [], (
        "the dispatched activity outlived the instance insert it was written with"
    )


# --- reconciliation, persisted ----------------------------------------------


async def _seed_running(
    repository: PostgresKernelRepository, *, task_node_id: UUID | None
) -> AgentInstance:
    instance = AgentInstance(
        id=uuid4(),
        agent_package_id=uuid4(),
        category="research",
        execution_backend="inprocess",
        status="running",
        assigned_task_node_id=task_node_id,
        started_at=datetime.now(UTC),
        health_status="unknown",
    )
    return await repository.insert(instance)


async def test_real_reconciliation_persists_interrupted_with_the_events_id(
    repository: PostgresKernelRepository,
) -> None:
    orphan = await _seed_running(repository, task_node_id=uuid4())
    publisher = FakeEventPublisher()

    await reconcile_running_instances(repository, publisher)

    fetched = await repository.find_by_id(orphan.id)
    assert fetched is not None
    assert fetched.status == "failed"

    items = (await repository.list_activity(orphan.id)).items
    assert [a.kind for a in items] == [AgentActivityKind.INTERRUPTED]
    published = next(
        e for e in publisher.published if e.payload["agent_instance_id"] == str(orphan.id)
    )
    assert items[0].correlation_id == published.correlation_id
    assert items[0].detail == {
        "reason": "kernel_restart",
        "task_node_id": str(orphan.assigned_task_node_id),
    }


async def test_real_interrupted_without_a_task_node_stores_sql_null(
    repository: PostgresKernelRepository,
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Checked in SQL, not only through the mapper: `NULL` and the string
    `"None"` both round-trip as a falsy Python value through a careless
    mapping, and only one of them is correct."""
    orphan = await _seed_running(repository, task_node_id=None)

    await reconcile_running_instances(repository, FakeEventPublisher())

    items = (await repository.list_activity(orphan.id)).items
    assert [a.kind for a in items] == [AgentActivityKind.INTERRUPTED]
    assert items[0].correlation_id is None

    async with postgres_session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT correlation_id IS NULL, detail FROM agent_os.agent_activity "
                    "WHERE agent_instance_id = :iid"
                ),
                {"iid": str(orphan.id)},
            )
        ).all()
    assert [tuple(row) for row in rows] == [(True, {"reason": "kernel_restart"})]
