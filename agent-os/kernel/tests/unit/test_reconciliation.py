"""Unit tests for `domain.reconciliation.reconcile_running_instances`
(TDD 3E §4/§12) -- framework-free, exercised entirely against the
in-memory `FakeKernelRepository`/`FakeEventPublisher` fakes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from nova_agent_os_kernel.domain.models import AgentInstance
from nova_agent_os_kernel.domain.reconciliation import reconcile_running_instances

from tests.fakes.event_publisher import FakeEventPublisher
from tests.fakes.repository import FakeKernelRepository


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


async def test_reconcile_marks_every_running_instance_failed() -> None:
    repository = FakeKernelRepository()
    running = await repository.insert(_instance())
    await repository.insert(_instance(status="completed"))

    await reconcile_running_instances(repository, FakeEventPublisher())

    reconciled = await repository.find_by_id(running.id)
    assert reconciled is not None
    assert reconciled.status == "failed"
    still_completed = await repository.list_by_status("completed")
    assert len(still_completed) == 1


async def test_reconcile_publishes_agent_os_task_completed_with_interrupted_outcome() -> None:
    repository = FakeKernelRepository()
    instance = await repository.insert(_instance())
    publisher = FakeEventPublisher()

    await reconcile_running_instances(repository, publisher)

    assert len(publisher.published) == 1
    envelope = publisher.published[0]
    assert envelope.subject == "agent_os.task.completed"
    assert envelope.source_engine == "kernel"
    assert envelope.payload["task_node_id"] == str(instance.assigned_task_node_id)
    assert envelope.payload["agent_instance_id"] == str(instance.id)
    assert envelope.payload["outcome"] == "interrupted"
    assert str(envelope.correlation_id) == envelope.payload["correlation_id"]


async def test_reconcile_does_not_publish_for_an_instance_with_no_assigned_task() -> None:
    repository = FakeKernelRepository()
    await repository.insert(_instance(assigned_task_node_id=None))
    publisher = FakeEventPublisher()

    reconciled_ids = await reconcile_running_instances(repository, publisher)

    assert len(reconciled_ids) == 1
    assert publisher.published == []


async def test_reconcile_is_a_no_op_when_nothing_is_running() -> None:
    repository = FakeKernelRepository()
    await repository.insert(_instance(status="completed"))
    publisher = FakeEventPublisher()

    reconciled_ids = await reconcile_running_instances(repository, publisher)

    assert reconciled_ids == []
    assert publisher.published == []
