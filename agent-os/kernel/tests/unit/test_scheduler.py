"""Unit tests for the Kernel Scheduler (`domain/scheduler.py`, TDD 3E §4,
disclosed implementation -- see that module's own docstring). Fake-backed:
`RegistryPort`/`SupervisorPort`/`AgentExecutionBackend`/`KernelRepository`/
`EventPublisher` are all fakes, the same discipline every other Phase 3
component's own domain-layer unit tests already establish."""

from __future__ import annotations

from uuid import uuid4

from nova_agent_os_kernel.domain.models import AgentInstanceHandle
from nova_agent_os_kernel.domain.scheduler import dispatch_ready_nodes, dispatch_task_node
from nova_contracts import (
    AgentMessage,
    AgentMessageType,
    AgentOsTaskCompletedPayload,
    AgentPackageSnapshot,
    AgentResult,
    TaskGraphSnapshot,
    TaskNodeSnapshot,
    ValidationOutcome,
)

from tests.fakes.event_publisher import FakeEventPublisher
from tests.fakes.ports import FakeAgentExecutionBackend, FakeRegistryPort, FakeSupervisorPort
from tests.fakes.repository import FakeKernelRepository


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


def _package() -> AgentPackageSnapshot:
    return AgentPackageSnapshot(
        id=uuid4(),
        category="research",
        version="0.1.0",
        manifest_json={"id": "research-agent", "version": "0.1.0"},
        health_status="healthy",
    )


def _success_handle(*, task_node_id, correlation_id) -> AgentInstanceHandle:  # type: ignore[no-untyped-def]
    result = AgentResult(
        agent_instance_id=uuid4(),
        task_node_id=task_node_id,
        status="success",
        output={"finding": "token-bucket rate limiting"},
        confidence=0.9,
        self_validation_passed=True,
        correlation_id=correlation_id,
    )
    return AgentInstanceHandle(
        instance_id=result.agent_instance_id,
        result=result,
        validation=ValidationOutcome(passed=True, requires_peer_review=False),
    )


def _coding_package() -> AgentPackageSnapshot:
    return AgentPackageSnapshot(
        id=uuid4(),
        category="coding",
        version="0.1.0",
        manifest_json={
            "id": "coding-agent",
            "version": "0.1.0",
            "peer_reviewer_category": "architect",
        },
        health_status="healthy",
    )


def _success_handle_requiring_review(*, task_node_id, correlation_id) -> AgentInstanceHandle:  # type: ignore[no-untyped-def]
    result = AgentResult(
        agent_instance_id=uuid4(),
        task_node_id=task_node_id,
        status="success",
        output={"diff": "applied a scripted code change"},
        confidence=0.9,
        self_validation_passed=True,
        correlation_id=correlation_id,
    )
    return AgentInstanceHandle(
        instance_id=result.agent_instance_id,
        result=result,
        validation=ValidationOutcome(passed=True, requires_peer_review=True),
    )


def _review_reply(*, status: str, correlation_id) -> AgentMessage:  # type: ignore[no-untyped-def]
    reviewer_result = AgentResult(
        agent_instance_id=uuid4(),
        task_node_id=uuid4(),
        status=status,
        output={"verdict": status},
        confidence=0.8,
        self_validation_passed=status == "success",
        correlation_id=correlation_id,
    )
    return AgentMessage(
        message_type=AgentMessageType.PEER_REVIEW_RESULT,
        from_instance_id=uuid4(),
        to_instance_id=uuid4(),
        payload=reviewer_result.model_dump(mode="json"),
        correlation_id=correlation_id,
    )


def _qa_package() -> AgentPackageSnapshot:
    return AgentPackageSnapshot(
        id=uuid4(),
        category="qa",
        version="0.1.0",
        manifest_json={"id": "qa-agent", "version": "0.1.0"},
        health_status="healthy",
    )


def _qa_success_handle(*, task_node_id, correlation_id) -> AgentInstanceHandle:  # type: ignore[no-untyped-def]
    result = AgentResult(
        agent_instance_id=uuid4(),
        task_node_id=task_node_id,
        status="success",
        output={"exit_code": 0, "stdout": "5 passed", "stderr": ""},
        confidence=1.0,
        self_validation_passed=True,
        correlation_id=correlation_id,
    )
    return AgentInstanceHandle(
        instance_id=result.agent_instance_id,
        result=result,
        validation=ValidationOutcome(passed=True, requires_peer_review=False),
    )


def _failure_handle(*, task_node_id, correlation_id) -> AgentInstanceHandle:  # type: ignore[no-untyped-def]
    result = AgentResult(
        agent_instance_id=uuid4(),
        task_node_id=task_node_id,
        status="failure",
        output={"error": "model gateway timed out"},
        confidence=None,
        self_validation_passed=False,
        correlation_id=correlation_id,
    )
    return AgentInstanceHandle(
        instance_id=result.agent_instance_id,
        result=result,
        validation=ValidationOutcome(passed=False, requires_peer_review=False),
    )


async def test_dispatch_task_node_with_no_assigned_category_is_a_noop() -> None:
    node = _node(assigned_agent_category=None)
    registry_port = FakeRegistryPort(package=_package())
    result = await dispatch_task_node(
        node,
        repository=FakeKernelRepository(),
        registry_port=registry_port,
        supervisor_port=FakeSupervisorPort(),
        execution_backend=FakeAgentExecutionBackend(handles=[]),
        event_publisher=FakeEventPublisher(),
        primary_user_id=uuid4(),
        correlation_id=uuid4(),
    )
    assert result is None
    assert registry_port.requested_categories == []


async def test_dispatch_task_node_with_no_healthy_candidate_is_a_noop() -> None:
    node = _node()
    result = await dispatch_task_node(
        node,
        repository=FakeKernelRepository(),
        registry_port=FakeRegistryPort(package=None),
        supervisor_port=FakeSupervisorPort(),
        execution_backend=FakeAgentExecutionBackend(handles=[]),
        event_publisher=FakeEventPublisher(),
        primary_user_id=uuid4(),
        correlation_id=uuid4(),
    )
    assert result is None


async def test_dispatch_task_node_success_persists_instance_and_publishes_completion() -> None:
    node = _node()
    correlation_id = uuid4()
    handle = _success_handle(task_node_id=node.id, correlation_id=correlation_id)
    repository = FakeKernelRepository()
    event_publisher = FakeEventPublisher()

    instance_id = await dispatch_task_node(
        node,
        repository=repository,
        registry_port=FakeRegistryPort(package=_package()),
        supervisor_port=FakeSupervisorPort(),
        execution_backend=FakeAgentExecutionBackend(handles=[handle]),
        event_publisher=event_publisher,
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    assert instance_id == handle.instance_id
    persisted = await repository.find_by_id(handle.instance_id)
    assert persisted is not None
    assert persisted.status == "completed"
    assert persisted.category == "research"
    assert persisted.assigned_task_node_id == node.id

    assert len(event_publisher.published) == 1
    envelope = event_publisher.published[0]
    assert envelope.subject == "agent_os.task.completed"
    payload = AgentOsTaskCompletedPayload.model_validate(envelope.payload)
    assert payload.outcome == "success"
    assert payload.agent_instance_id == handle.instance_id
    assert payload.task_node_id == node.id


async def test_dispatch_task_node_failure_triggers_restart_plan_and_retries_once() -> None:
    node = _node()
    correlation_id = uuid4()
    first_failure = _failure_handle(task_node_id=node.id, correlation_id=correlation_id)
    retry_success = _success_handle(task_node_id=node.id, correlation_id=correlation_id)
    repository = FakeKernelRepository()
    event_publisher = FakeEventPublisher()
    supervisor_port = FakeSupervisorPort(restart_instance_ids=[first_failure.instance_id])
    backend = FakeAgentExecutionBackend(handles=[first_failure, retry_success])

    instance_id = await dispatch_task_node(
        node,
        repository=repository,
        registry_port=FakeRegistryPort(package=_package()),
        supervisor_port=supervisor_port,
        execution_backend=backend,
        event_publisher=event_publisher,
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    assert len(backend.spawn_calls) == 2
    assert len(supervisor_port.calls) == 1
    assert supervisor_port.calls[0]["failed_instance_id"] == first_failure.instance_id

    assert instance_id == retry_success.instance_id
    failed_row = await repository.find_by_id(first_failure.instance_id)
    assert failed_row is not None
    assert failed_row.status == "failed"
    retried_row = await repository.find_by_id(retry_success.instance_id)
    assert retried_row is not None
    assert retried_row.status == "completed"

    assert len(event_publisher.published) == 1
    payload = AgentOsTaskCompletedPayload.model_validate(event_publisher.published[0].payload)
    assert payload.outcome == "success"
    assert payload.agent_instance_id == retry_success.instance_id


async def test_dispatch_when_supervisor_declines_restart_reports_failure_once() -> None:
    node = _node()
    correlation_id = uuid4()
    failure = _failure_handle(task_node_id=node.id, correlation_id=correlation_id)
    repository = FakeKernelRepository()
    event_publisher = FakeEventPublisher()
    backend = FakeAgentExecutionBackend(handles=[failure])

    instance_id = await dispatch_task_node(
        node,
        repository=repository,
        registry_port=FakeRegistryPort(package=_package()),
        supervisor_port=FakeSupervisorPort(restart_instance_ids=[]),
        execution_backend=backend,
        event_publisher=event_publisher,
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    assert len(backend.spawn_calls) == 1
    assert instance_id == failure.instance_id
    row = await repository.find_by_id(failure.instance_id)
    assert row is not None
    assert row.status == "failed"

    payload = AgentOsTaskCompletedPayload.model_validate(event_publisher.published[0].payload)
    assert payload.outcome == "failure"


async def test_dispatch_task_node_failure_when_retry_also_fails_reports_failure() -> None:
    node = _node()
    correlation_id = uuid4()
    first_failure = _failure_handle(task_node_id=node.id, correlation_id=correlation_id)
    second_failure = _failure_handle(task_node_id=node.id, correlation_id=correlation_id)
    repository = FakeKernelRepository()
    event_publisher = FakeEventPublisher()
    backend = FakeAgentExecutionBackend(handles=[first_failure, second_failure])
    supervisor_port = FakeSupervisorPort(restart_instance_ids=[first_failure.instance_id])

    instance_id = await dispatch_task_node(
        node,
        repository=repository,
        registry_port=FakeRegistryPort(package=_package()),
        supervisor_port=supervisor_port,
        execution_backend=backend,
        event_publisher=event_publisher,
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    assert len(backend.spawn_calls) == 2
    assert len(supervisor_port.calls) == 1, "must never re-consult the Supervisor a second time"
    assert instance_id == second_failure.instance_id
    payload = AgentOsTaskCompletedPayload.model_validate(event_publisher.published[0].payload)
    assert payload.outcome == "failure"


async def test_dispatch_ready_nodes_dispatches_only_ready_nodes() -> None:
    ready_node = _node()
    blocked_node = _node(status="blocked", assigned_agent_category="research")
    graph = TaskGraphSnapshot(
        id=uuid4(),
        root_objective="Investigate rate limiting",
        nodes=[ready_node, blocked_node],
        critical_path=[ready_node.id],
    )
    correlation_id = uuid4()
    handle = _success_handle(task_node_id=ready_node.id, correlation_id=correlation_id)

    dispatched = await dispatch_ready_nodes(
        graph,
        repository=FakeKernelRepository(),
        registry_port=FakeRegistryPort(package=_package()),
        supervisor_port=FakeSupervisorPort(),
        execution_backend=FakeAgentExecutionBackend(handles=[handle]),
        event_publisher=FakeEventPublisher(),
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    assert dispatched == [handle.instance_id]


async def test_dispatch_task_node_requiring_review_runs_peer_review_and_reports_success() -> None:
    node = _node(assigned_agent_category="coding")
    correlation_id = uuid4()
    handle = _success_handle_requiring_review(task_node_id=node.id, correlation_id=correlation_id)
    reply = _review_reply(status="success", correlation_id=correlation_id)
    repository = FakeKernelRepository()
    event_publisher = FakeEventPublisher()
    registry_port = FakeRegistryPort(package=_coding_package())
    supervisor_port = FakeSupervisorPort(peer_validation="approved")
    backend = FakeAgentExecutionBackend(handles=[handle], review_replies=[reply])

    instance_id = await dispatch_task_node(
        node,
        repository=repository,
        registry_port=registry_port,
        supervisor_port=supervisor_port,
        execution_backend=backend,
        event_publisher=event_publisher,
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    assert instance_id == handle.instance_id
    assert registry_port.requested_categories == ["coding", "architect"]
    assert len(backend.spawn_and_review_calls) == 1
    _, request_message = backend.spawn_and_review_calls[0]
    assert request_message.message_type is AgentMessageType.PEER_REVIEW_REQUEST

    assert len(supervisor_port.peer_review_calls) == 1
    call = supervisor_port.peer_review_calls[0]
    assert call["reviewer_category"] == "architect"
    assert call["reviewer_available"] is True

    payload = AgentOsTaskCompletedPayload.model_validate(event_publisher.published[0].payload)
    assert payload.outcome == "success"
    assert payload.result is not None
    assert payload.result["peer_validation"] == "approved"


async def test_dispatch_task_node_rejected_by_reviewer_reports_needs_revision() -> None:
    node = _node(assigned_agent_category="coding")
    correlation_id = uuid4()
    handle = _success_handle_requiring_review(task_node_id=node.id, correlation_id=correlation_id)
    reply = _review_reply(status="needs_revision", correlation_id=correlation_id)
    event_publisher = FakeEventPublisher()
    supervisor_port = FakeSupervisorPort(peer_validation="rejected")
    backend = FakeAgentExecutionBackend(handles=[handle], review_replies=[reply])

    instance_id = await dispatch_task_node(
        node,
        repository=FakeKernelRepository(),
        registry_port=FakeRegistryPort(package=_coding_package()),
        supervisor_port=supervisor_port,
        execution_backend=backend,
        event_publisher=event_publisher,
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    assert instance_id == handle.instance_id
    payload = AgentOsTaskCompletedPayload.model_validate(event_publisher.published[0].payload)
    assert payload.outcome == "needs_revision"


async def test_dispatch_task_node_no_reviewer_installed_still_reports_success() -> None:
    """A `coding-agent`-shaped package dispatched before `architect-agent`
    exists (this project's own roadmap sequencing) -- Registry finds no
    healthy `architect` candidate, `reviewer_available=False` is reported
    to the Supervisor, and the primary result is still accepted (TDD 3E
    §12's own non-fatal treatment of a missing/unresponsive reviewer)."""
    node = _node(assigned_agent_category="coding")
    correlation_id = uuid4()
    handle = _success_handle_requiring_review(task_node_id=node.id, correlation_id=correlation_id)
    event_publisher = FakeEventPublisher()
    supervisor_port = FakeSupervisorPort(peer_validation="timed_out")

    class _RegistryFindsPrimaryOnly:
        def __init__(self) -> None:
            self.requested_categories: list[str] = []

        async def find_healthy_package(self, *, category, correlation_id=None):  # type: ignore[no-untyped-def]
            self.requested_categories.append(category)
            return _coding_package() if category == "coding" else None

    registry_port = _RegistryFindsPrimaryOnly()
    backend = FakeAgentExecutionBackend(handles=[handle])

    instance_id = await dispatch_task_node(
        node,
        repository=FakeKernelRepository(),
        registry_port=registry_port,
        supervisor_port=supervisor_port,
        execution_backend=backend,
        event_publisher=event_publisher,
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    assert instance_id == handle.instance_id
    assert len(backend.spawn_and_review_calls) == 0
    assert supervisor_port.peer_review_calls[0]["reviewer_available"] is False
    payload = AgentOsTaskCompletedPayload.model_validate(event_publisher.published[0].payload)
    assert payload.outcome == "success"


async def test_dispatch_task_node_without_peer_reviewer_category_skips_review() -> None:
    """research-agent's own package (no `peer_reviewer_category`) must
    never trigger a peer-review round -- confirms the addition is fully
    additive."""
    node = _node()
    correlation_id = uuid4()
    handle = _success_handle(task_node_id=node.id, correlation_id=correlation_id)
    event_publisher = FakeEventPublisher()
    supervisor_port = FakeSupervisorPort()
    backend = FakeAgentExecutionBackend(handles=[handle])

    await dispatch_task_node(
        node,
        repository=FakeKernelRepository(),
        registry_port=FakeRegistryPort(package=_package()),
        supervisor_port=supervisor_port,
        execution_backend=backend,
        event_publisher=event_publisher,
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    assert len(backend.spawn_and_review_calls) == 0
    assert len(supervisor_port.peer_review_calls) == 0


async def test_dispatch_task_node_for_qa_agent_reports_success_with_no_peer_review() -> None:
    """qa-agent's own real package shape (`category="qa"`, no
    `peer_reviewer_category`) -- the third Agent Package, and the first
    since `coding-agent`'s own slice to prove, specifically for its own
    category, that the peer-review addition stays fully inert (TDD 3E §9's
    own agent table gives `qa-agent` no reviewer/reviewee role)."""
    node = _node(objective="Run the test suite", assigned_agent_category="qa")
    correlation_id = uuid4()
    handle = _qa_success_handle(task_node_id=node.id, correlation_id=correlation_id)
    event_publisher = FakeEventPublisher()
    supervisor_port = FakeSupervisorPort()
    backend = FakeAgentExecutionBackend(handles=[handle])

    await dispatch_task_node(
        node,
        repository=FakeKernelRepository(),
        registry_port=FakeRegistryPort(package=_qa_package()),
        supervisor_port=supervisor_port,
        execution_backend=backend,
        event_publisher=event_publisher,
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    assert len(backend.spawn_and_review_calls) == 0
    assert len(supervisor_port.peer_review_calls) == 0
    assert len(event_publisher.published) == 1
    published_payload = AgentOsTaskCompletedPayload.model_validate(
        event_publisher.published[0].payload
    )
    assert published_payload.outcome == "success"
    assert published_payload.result is not None
    assert published_payload.result["output"]["exit_code"] == 0
    assert "peer_validation" not in published_payload.result
