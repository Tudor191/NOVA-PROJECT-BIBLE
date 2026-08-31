"""Unit tests for the Kernel Scheduler (`domain/scheduler.py`, TDD 3E §4,
disclosed implementation -- see that module's own docstring). Fake-backed:
`RegistryPort`/`SupervisorPort`/`AgentExecutionBackend`/`KernelRepository`/
`EventPublisher` are all fakes, the same discipline every other Phase 3
component's own domain-layer unit tests already establish."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

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


# --- `agent_instance` running-state correctness (TDD 3E §4, D2) -------------


async def test_a_running_instance_row_exists_while_the_agent_is_executing() -> None:
    """TDD 3E §4's restart reconciliation re-queues "every `agent_instance`
    row still marked `status="running"`" -- but until this slice no row was
    ever written in that state. `spawn()` is synchronous, so rows were
    inserted already terminal, and a Kernel killed mid-dispatch left nothing
    to recover. The row is now persisted *before* `spawn()` is awaited; this
    observes it from inside the backend, the only point at which the
    in-flight state is visible."""
    node = _node()
    correlation_id = uuid4()
    handle = _success_handle(task_node_id=node.id, correlation_id=correlation_id)
    repository = FakeKernelRepository()
    observed: list[tuple[str, str, UUID | None]] = []

    class _ObservingBackend(FakeAgentExecutionBackend):
        async def spawn(self, agent, context, *, instance_id=None):  # type: ignore[no-untyped-def]
            row = await repository.find_by_id(instance_id or handle.instance_id)
            if row is not None:
                observed.append((row.status, row.health_status, row.assigned_task_node_id))
            return await super().spawn(agent, context, instance_id=instance_id)

    await dispatch_task_node(
        node,
        repository=repository,
        registry_port=FakeRegistryPort(package=_package()),
        supervisor_port=FakeSupervisorPort(),
        execution_backend=_ObservingBackend(handles=[handle]),
        event_publisher=FakeEventPublisher(),
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    # Mid-execution: a real, recoverable orphan row.
    assert observed == [("running", "unknown", node.id)]

    # After execution: transitioned to terminal, not left "running" forever.
    final = await repository.find_by_id(handle.instance_id)
    assert final is not None
    assert final.status == "completed"
    assert final.health_status == "healthy"


async def test_a_failed_instance_row_ends_failed_and_unhealthy() -> None:
    node = _node()
    correlation_id = uuid4()
    failed = _failure_handle(task_node_id=node.id, correlation_id=correlation_id)
    retry = _failure_handle(task_node_id=node.id, correlation_id=correlation_id)
    repository = FakeKernelRepository()

    await dispatch_task_node(
        node,
        repository=repository,
        registry_port=FakeRegistryPort(package=_package()),
        # Restart the failed instance, so the bounded single retry really
        # runs and a second row is written -- the default FakeSupervisorPort
        # declines every restart.
        supervisor_port=FakeSupervisorPort(restart_instance_ids=[failed.instance_id]),
        execution_backend=FakeAgentExecutionBackend(handles=[failed, retry]),
        event_publisher=FakeEventPublisher(),
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    for handle in (failed, retry):
        row = await repository.find_by_id(handle.instance_id)
        assert row is not None
        assert row.status == "failed"
        assert row.health_status == "unhealthy"
        # No row is left "running": reconciliation must not re-queue work
        # that already reached a terminal outcome.
    assert await repository.list_by_status("running") == []


# --- Parallel dispatch (doc 12 §7, TDD 3E §14 criterion #1) ------------------


class _BarrierBackend(FakeAgentExecutionBackend):
    """Every `spawn()` blocks on a shared `asyncio.Barrier` sized to the
    number of nodes expected to run together. If dispatch were sequential
    the first `spawn()` would wait for participants that can never arrive,
    and the test would time out -- so passing is itself proof of real
    overlap, not merely of two completed executions.

    Handles are keyed by `task_node_id` rather than popped from the base
    class's shared in-order queue, so concurrent spawns cannot steal each
    other's results."""

    def __init__(
        self,
        *,
        handles_by_node: dict[UUID, AgentInstanceHandle],
        parties: int,
        timeout: float = 5.0,
    ) -> None:
        super().__init__(handles=list(handles_by_node.values()))
        self._by_node = dict(handles_by_node)
        self._pending = list(handles_by_node.values())
        self._barrier = asyncio.Barrier(parties)
        self._timeout = timeout
        self.concurrent_peak = 0
        self._in_flight = 0

    def next_instance_id(self) -> UUID:
        return self._pending[0].instance_id

    async def spawn(self, agent, context, *, instance_id=None):  # type: ignore[no-untyped-def]
        handle = self._by_node[context.task.id]
        self._pending = [h for h in self._pending if h.instance_id != handle.instance_id]
        self.spawn_calls.append((agent, context))

        self._in_flight += 1
        self.concurrent_peak = max(self.concurrent_peak, self._in_flight)
        try:
            async with asyncio.timeout(self._timeout):
                await self._barrier.wait()
        finally:
            self._in_flight -= 1
        return handle


async def test_independent_ready_nodes_execute_concurrently_not_sequentially() -> None:
    """The barrier releases only once BOTH spawns are simultaneously in
    flight, so a sequential `for` loop over the ready set cannot pass this
    test -- it would block on the first node until the timeout fires."""
    first = _node(objective="left branch")
    second = _node(objective="right branch")
    graph = TaskGraphSnapshot(
        id=uuid4(),
        root_objective="Two independent branches",
        nodes=[first, second],
        critical_path=[first.id],
    )
    correlation_id = uuid4()
    handles = {
        first.id: _success_handle(task_node_id=first.id, correlation_id=correlation_id),
        second.id: _success_handle(task_node_id=second.id, correlation_id=correlation_id),
    }
    backend = _BarrierBackend(handles_by_node=handles, parties=2)
    repository = FakeKernelRepository()
    event_publisher = FakeEventPublisher()

    dispatched = await dispatch_ready_nodes(
        graph,
        repository=repository,
        registry_port=FakeRegistryPort(package=_package()),
        supervisor_port=FakeSupervisorPort(),
        execution_backend=backend,
        event_publisher=event_publisher,
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    assert backend.concurrent_peak == 2

    # Deterministic ordering: results follow `graph.nodes` order, never
    # completion order.
    assert dispatched == [handles[first.id].instance_id, handles[second.id].instance_id]

    # Per-node lifecycle isolation: one row and one completion event each.
    for node in (first, second):
        row = await repository.find_by_id(handles[node.id].instance_id)
        assert row is not None
        assert row.assigned_task_node_id == node.id
        assert row.status == "completed"

    assert len(event_publisher.published) == 2
    completed = [
        AgentOsTaskCompletedPayload.model_validate(envelope.payload)
        for envelope in event_publisher.published
    ]
    assert {payload.task_node_id for payload in completed} == {first.id, second.id}
    assert all(payload.outcome == "success" for payload in completed)


async def test_three_independent_nodes_all_overlap() -> None:
    """Not special-cased to two: a three-node ready set rendezvouses with
    all three in flight."""
    nodes = [_node(objective=f"branch {index}") for index in range(3)]
    graph = TaskGraphSnapshot(
        id=uuid4(), root_objective="Three branches", nodes=nodes, critical_path=[nodes[0].id]
    )
    correlation_id = uuid4()
    handles = {
        node.id: _success_handle(task_node_id=node.id, correlation_id=correlation_id)
        for node in nodes
    }
    backend = _BarrierBackend(handles_by_node=handles, parties=3)

    dispatched = await dispatch_ready_nodes(
        graph,
        repository=FakeKernelRepository(),
        registry_port=FakeRegistryPort(package=_package()),
        supervisor_port=FakeSupervisorPort(),
        execution_backend=backend,
        event_publisher=FakeEventPublisher(),
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    assert backend.concurrent_peak == 3
    assert dispatched == [handles[node.id].instance_id for node in nodes]


async def test_a_non_ready_node_is_never_part_of_the_concurrent_batch() -> None:
    """Only `"ready"` nodes are dispatched, so only they participate -- a
    `"blocked"` sibling must not be spawned at all, which a mismatched
    barrier party count would otherwise expose as a timeout."""
    ready = _node(objective="dispatch me")
    blocked = _node(objective="not yet", status="blocked")
    graph = TaskGraphSnapshot(
        id=uuid4(), root_objective="One ready", nodes=[ready, blocked], critical_path=[ready.id]
    )
    correlation_id = uuid4()
    handles = {ready.id: _success_handle(task_node_id=ready.id, correlation_id=correlation_id)}
    backend = _BarrierBackend(handles_by_node=handles, parties=1)

    dispatched = await dispatch_ready_nodes(
        graph,
        repository=FakeKernelRepository(),
        registry_port=FakeRegistryPort(package=_package()),
        supervisor_port=FakeSupervisorPort(),
        execution_backend=backend,
        event_publisher=FakeEventPublisher(),
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    assert dispatched == [handles[ready.id].instance_id]
    assert len(backend.spawn_calls) == 1


async def test_dispatch_ready_nodes_with_no_ready_nodes_returns_empty() -> None:
    graph = TaskGraphSnapshot(
        id=uuid4(),
        root_objective="Nothing runnable",
        nodes=[_node(status="pending"), _node(status="completed")],
        critical_path=[],
    )
    dispatched = await dispatch_ready_nodes(
        graph,
        repository=FakeKernelRepository(),
        registry_port=FakeRegistryPort(package=_package()),
        supervisor_port=FakeSupervisorPort(),
        execution_backend=FakeAgentExecutionBackend(handles=[]),
        event_publisher=FakeEventPublisher(),
        primary_user_id=uuid4(),
        correlation_id=uuid4(),
    )
    assert dispatched == []


# --- Failure isolation under concurrent dispatch -----------------------------


class _PerNodeBackend(FakeAgentExecutionBackend):
    """Handles keyed by `task_node_id`, with an optional per-node exception
    raised from `spawn()` -- the shape needed to script "one node blows up,
    its sibling must still finish"."""

    def __init__(
        self,
        *,
        handles_by_node: dict[UUID, AgentInstanceHandle],
        raise_for_node: dict[UUID, Exception] | None = None,
    ) -> None:
        super().__init__(handles=list(handles_by_node.values()))
        self._by_node = dict(handles_by_node)
        self._pending = list(handles_by_node.values())
        self._raise_for_node = dict(raise_for_node or {})

    def next_instance_id(self) -> UUID:
        return self._pending[0].instance_id

    async def spawn(self, agent, context, *, instance_id=None):  # type: ignore[no-untyped-def]
        handle = self._by_node[context.task.id]
        self._pending = [h for h in self._pending if h.instance_id != handle.instance_id]
        self.spawn_calls.append((agent, context))
        # Yield, so a raising sibling really is interleaved with the other
        # coroutine rather than failing before it ever starts.
        await asyncio.sleep(0)
        boom = self._raise_for_node.get(context.task.id)
        if boom is not None:
            raise boom
        return handle


class _FailingRegistryPort:
    """Raises for one named category, answers normally for every other --
    models a Registry RPC timeout affecting a single node's dispatch."""

    def __init__(self, *, package: AgentPackageSnapshot, failing_category: str) -> None:
        self._package = package
        self._failing_category = failing_category
        self.requested_categories: list[str] = []

    async def find_healthy_package(self, *, category, correlation_id=None):  # type: ignore[no-untyped-def]
        self.requested_categories.append(category)
        if category == self._failing_category:
            raise TimeoutError("registry RPC timed out")
        return self._package


async def test_one_node_raising_does_not_cancel_an_independent_sibling() -> None:
    """`return_exceptions=True`, proven: the backend raises for one node
    while the other is mid-flight. The sibling must still reach a terminal
    `agent_instance` row and still publish its own completion event."""
    doomed = _node(objective="this one explodes")
    healthy = _node(objective="this one must still finish")
    graph = TaskGraphSnapshot(
        id=uuid4(),
        root_objective="One of each",
        nodes=[doomed, healthy],
        critical_path=[doomed.id],
    )
    correlation_id = uuid4()
    handles = {
        doomed.id: _success_handle(task_node_id=doomed.id, correlation_id=correlation_id),
        healthy.id: _success_handle(task_node_id=healthy.id, correlation_id=correlation_id),
    }
    repository = FakeKernelRepository()
    event_publisher = FakeEventPublisher()

    dispatched = await dispatch_ready_nodes(
        graph,
        repository=repository,
        registry_port=FakeRegistryPort(package=_package()),
        supervisor_port=FakeSupervisorPort(),
        execution_backend=_PerNodeBackend(
            handles_by_node=handles,
            raise_for_node={doomed.id: RuntimeError("backend exploded")},
        ),
        event_publisher=event_publisher,
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    # The raising node contributes no id; the sibling is unaffected.
    assert dispatched == [handles[healthy.id].instance_id]

    healthy_row = await repository.find_by_id(handles[healthy.id].instance_id)
    assert healthy_row is not None
    assert healthy_row.status == "completed"

    assert len(event_publisher.published) == 1
    payload = AgentOsTaskCompletedPayload.model_validate(event_publisher.published[0].payload)
    assert payload.task_node_id == healthy.id
    assert payload.outcome == "success"


async def test_a_registry_rpc_failure_on_one_node_does_not_stop_its_sibling() -> None:
    """A different failure surface, same guarantee: the failure happens
    before any `agent_instance` row exists for that node, and the sibling
    still completes."""
    doomed = _node(objective="registry times out for me", assigned_agent_category="qa")
    healthy = _node(objective="I still run", assigned_agent_category="research")
    graph = TaskGraphSnapshot(
        id=uuid4(), root_objective="Mixed", nodes=[doomed, healthy], critical_path=[healthy.id]
    )
    correlation_id = uuid4()
    handles = {
        healthy.id: _success_handle(task_node_id=healthy.id, correlation_id=correlation_id)
    }
    repository = FakeKernelRepository()

    dispatched = await dispatch_ready_nodes(
        graph,
        repository=repository,
        registry_port=_FailingRegistryPort(package=_package(), failing_category="qa"),
        supervisor_port=FakeSupervisorPort(),
        execution_backend=_PerNodeBackend(handles_by_node=handles),
        event_publisher=FakeEventPublisher(),
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    assert dispatched == [handles[healthy.id].instance_id]
    # No orphan row for the node whose dispatch never got past Registry.
    assert await repository.list_by_status("running") == []


async def test_every_node_raising_yields_an_empty_result_without_propagating() -> None:
    """A whole batch failing is still not an exception out of
    `dispatch_ready_nodes` -- the caller (`events/scheduler_handler.py`) is
    fire-and-forget and must never see a raise."""
    first = _node(objective="boom one")
    second = _node(objective="boom two")
    graph = TaskGraphSnapshot(
        id=uuid4(), root_objective="All broken", nodes=[first, second], critical_path=[first.id]
    )
    correlation_id = uuid4()
    handles = {
        first.id: _success_handle(task_node_id=first.id, correlation_id=correlation_id),
        second.id: _success_handle(task_node_id=second.id, correlation_id=correlation_id),
    }

    dispatched = await dispatch_ready_nodes(
        graph,
        repository=FakeKernelRepository(),
        registry_port=FakeRegistryPort(package=_package()),
        supervisor_port=FakeSupervisorPort(),
        execution_backend=_PerNodeBackend(
            handles_by_node=handles,
            raise_for_node={
                first.id: RuntimeError("one"),
                second.id: RuntimeError("two"),
            },
        ),
        event_publisher=FakeEventPublisher(),
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    assert dispatched == []


# --- Supervisor restart-plan RPC failure (requirement 12) --------------------


class _RaisingSupervisorPort(FakeSupervisorPort):
    """`plan_restart` raises, as the real `SupervisorClient` does on an
    Event Bus timeout -- it catches nothing."""

    async def plan_restart(self, **kwargs):  # type: ignore[no-untyped-def]
        raise TimeoutError("agent_os.supervisor.restart_plan.request timed out")


async def test_a_supervisor_restart_plan_timeout_still_reports_the_original_outcome() -> None:
    """Requirement 12. Before this slice the timeout propagated out of
    `dispatch_task_node`, leaving the worst possible state: the
    `agent_instance` row already stamped `"failed"` but NO
    `agent_os.task.completed` published -- so `planning-engine` never
    learned the outcome and left its `TaskNode` `"running"` forever, and
    Kernel reconciliation (which re-queues only `"running"` instance rows)
    had nothing to recover either."""
    node = _node()
    correlation_id = uuid4()
    handle = _failure_handle(task_node_id=node.id, correlation_id=correlation_id)
    repository = FakeKernelRepository()
    event_publisher = FakeEventPublisher()

    instance_id = await dispatch_task_node(
        node,
        repository=repository,
        registry_port=FakeRegistryPort(package=_package()),
        supervisor_port=_RaisingSupervisorPort(),
        execution_backend=FakeAgentExecutionBackend(handles=[handle]),
        event_publisher=event_publisher,
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    # Does not raise, and the node is not stranded.
    assert instance_id == handle.instance_id

    assert len(event_publisher.published) == 1
    payload = AgentOsTaskCompletedPayload.model_validate(event_publisher.published[0].payload)
    assert payload.task_node_id == node.id
    assert payload.outcome == "failure"

    # agent_instance state stays correct and terminal -- never left "running".
    row = await repository.find_by_id(handle.instance_id)
    assert row is not None
    assert row.status == "failed"
    assert row.health_status == "unhealthy"
    assert await repository.list_by_status("running") == []


async def test_a_supervisor_timeout_skips_the_retry_rather_than_retrying_blind() -> None:
    """Declining is the fail-closed reading: the retry is an optimisation
    the Supervisor authorises, and an unreachable Supervisor authorises
    nothing. Exactly one spawn, never two."""
    node = _node()
    correlation_id = uuid4()
    first = _failure_handle(task_node_id=node.id, correlation_id=correlation_id)
    unused_retry = _success_handle(task_node_id=node.id, correlation_id=correlation_id)
    backend = FakeAgentExecutionBackend(handles=[first, unused_retry])

    await dispatch_task_node(
        node,
        repository=FakeKernelRepository(),
        registry_port=FakeRegistryPort(package=_package()),
        supervisor_port=_RaisingSupervisorPort(),
        execution_backend=backend,
        event_publisher=FakeEventPublisher(),
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    assert len(backend.spawn_calls) == 1


async def test_a_supervisor_timeout_on_one_node_does_not_affect_its_sibling() -> None:
    """The two mechanisms composed: a Supervisor RPC failure is absorbed at
    the node level, so the concurrent batch is not disturbed at all."""
    failing = _node(objective="fails, supervisor unreachable")
    healthy = _node(objective="succeeds")
    graph = TaskGraphSnapshot(
        id=uuid4(),
        root_objective="Mixed outcomes",
        nodes=[failing, healthy],
        critical_path=[failing.id],
    )
    correlation_id = uuid4()
    handles = {
        failing.id: _failure_handle(task_node_id=failing.id, correlation_id=correlation_id),
        healthy.id: _success_handle(task_node_id=healthy.id, correlation_id=correlation_id),
    }
    repository = FakeKernelRepository()
    event_publisher = FakeEventPublisher()

    dispatched = await dispatch_ready_nodes(
        graph,
        repository=repository,
        registry_port=FakeRegistryPort(package=_package()),
        supervisor_port=_RaisingSupervisorPort(),
        execution_backend=_PerNodeBackend(handles_by_node=handles),
        event_publisher=event_publisher,
        primary_user_id=uuid4(),
        correlation_id=correlation_id,
    )

    # Both nodes report: the failing one as "failure", the healthy one as
    # "success". Neither is stranded, neither cancelled the other.
    assert dispatched == [handles[failing.id].instance_id, handles[healthy.id].instance_id]

    outcomes = {
        AgentOsTaskCompletedPayload.model_validate(envelope.payload).task_node_id:
        AgentOsTaskCompletedPayload.model_validate(envelope.payload).outcome
        for envelope in event_publisher.published
    }
    assert outcomes == {failing.id: "failure", healthy.id: "success"}
    assert await repository.list_by_status("running") == []
