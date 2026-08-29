"""A real Event Bus round-trip through `main.py`'s subscribed
`agent_os.task.completed` handler (TDD 3E §4/§12) -- mirrors
`test_events_decompose_request.py`'s own "second `BoundEventBus` as
external caller" convention exactly, standing in for `agent-os/kernel`'s
own real publisher (`domain/reconciliation.py::reconcile_running_instances`
and `domain/scheduler.py::dispatch_task_node`'s own `_publish_task_completed`
call, both of which construct `AgentOsTaskCompletedPayload` with this exact
field shape).

Like `test_events_decompose_request.py`, the republished `planning.
task_graph.created` is verified via `repository.outbox` directly, not by
listening on the live Event Bus -- TDD 3B §4's transactional-outbox
pattern means the actual Event Bus publish is `workers/outbox_worker.py`'s
own, separate responsibility, decoupled from this handler's own write.

**Published snapshot vs. persisted state.** Every assertion below checks
both, because they deliberately differ: the enqueued
`planning.task_graph.created` payload names newly-runnable nodes `"ready"`
(it is the hand-off document `agent-os/kernel`'s Scheduler dispatches
from), while the committed rows already say `"running"` -- they have been
handed over, so a later republish cannot re-offer them. See
`domain/ports.py::HAND_OFF_ORDERING` for the full record.

`test_kernel_restart_then_planning_resume_round_trip` is the strongest
"restart followed by resume" proof achievable from planning-engine's own
side of the ADR-004 engine boundary: it constructs the *exact* payload
`reconcile_running_instances` produces on a real Kernel restart
(`task_node_id`, `agent_instance_id`, `outcome="interrupted"`, `result=None`)
against a `TaskNode` seeded at `status="running"` (the real state a node
left mid-dispatch would be in), and confirms planning-engine's own real
`create_app()` resets it to `"ready"` and enqueues a fresh `planning.
task_graph.created` outbox row with every other node's status untouched --
the exact `TaskGraphSnapshot` shape Kernel's own `dispatch_ready_nodes`
already consumes (once the outbox worker dispatches it) to redispatch
every `status == "ready"` node it finds (see `agent-os/kernel/domain/
scheduler.py`'s own module docstring). The Kernel side of this same
restart (a real `create_app()` actually publishing this payload on
restart) is proven independently in `agent-os/kernel/tests/integration/
test_restart_reconciliation.py` -- the two together, sharing the same
`nova_contracts.AgentOsTaskCompletedPayload` contract type, prove the full
restart-resume chain without either engine importing the other's
production code (ADR-004)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from nova_contracts import (
    AgentOsTaskCompletedPayload,
    EventEnvelope,
    PlanningTaskGraphCreatedPayload,
    RiskLevel,
)
from nova_eventbus_sdk import BoundEventBus
from nova_planning_engine.config import Settings
from nova_planning_engine.domain.models import Estimate, TaskGraph, TaskNode
from nova_planning_engine.main import create_app

from tests.fakes.ports import FakeModelOrchestrationPort
from tests.fakes.repository import FakePlanningRepository


def _node(**overrides: object) -> TaskNode:
    defaults: dict[str, object] = {
        "objective": "Implement the feature",
        "depends_on": [],
        "assigned_agent_category": "coding-agent",
        "estimated_effort": Estimate(effort_hours=2.0, confidence=0.7),
        "risk": RiskLevel.LOW,
    }
    defaults.update(overrides)
    return TaskNode(**defaults)  # type: ignore[arg-type]


def _seed_graph(repository: FakePlanningRepository, *, nodes: list[TaskNode]) -> TaskGraph:
    graph = TaskGraph(
        root_objective="Ship the release", nodes=nodes, critical_path=[n.id for n in nodes]
    )
    repository.graphs[graph.id] = graph
    return graph


def _caller_bus(app):  # type: ignore[no-untyped-def]
    return BoundEventBus(
        app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
        engine_name="kernel",
        publishable_subjects=frozenset({"agent_os.task.completed"}),
        subscribable_subjects=frozenset(),
    )


async def _publish(app, payload: AgentOsTaskCompletedPayload) -> None:  # type: ignore[no-untyped-def]
    caller_bus = _caller_bus(app)
    await caller_bus.publish(
        EventEnvelope(
            subject="agent_os.task.completed",
            source_engine="kernel",
            correlation_id=payload.correlation_id,
            payload=payload.model_dump(mode="json"),
        )
    )


def _enqueued_graphs(repository: FakePlanningRepository) -> list[PlanningTaskGraphCreatedPayload]:
    return [
        PlanningTaskGraphCreatedPayload.model_validate(row.payload)
        for row in repository.outbox.values()
        if row.subject == "planning.task_graph.created"
    ]


async def test_kernel_restart_then_planning_resume_round_trip(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    interrupted_node = _node(status="running")
    sibling_node = _node(objective="Write the tests", status="completed")
    repository = FakePlanningRepository()
    graph = _seed_graph(repository, nodes=[interrupted_node, sibling_node])

    app = create_app(
        Settings(), model_orchestration_port=FakeModelOrchestrationPort(), repository=repository
    )

    async with app.router.lifespan_context(app):
        # The exact payload agent-os/kernel's own reconcile_running_instances
        # constructs on a real Kernel restart (see that module's own
        # AgentOsTaskCompletedPayload(... outcome="interrupted", ...) call).
        payload = AgentOsTaskCompletedPayload(
            task_node_id=interrupted_node.id,
            agent_instance_id=uuid4(),
            outcome="interrupted",
            result=None,
            correlation_id=uuid4(),
        )
        await _publish(app, payload)

    enqueued = _enqueued_graphs(repository)
    assert len(enqueued) == 1
    updated_snapshot = enqueued[0].graph
    assert updated_snapshot.id == graph.id
    by_id = {n.id: n for n in updated_snapshot.nodes}

    # The interrupted node is resumed -- reset to "ready" so that once
    # workers/outbox_worker.py dispatches this enqueued row, Kernel's own
    # dispatch_ready_nodes picks it up on the resulting planning.task_graph.
    # created (that redispatch itself is Kernel's own, unmodified
    # responsibility -- proven by the existing dispatch_ready_nodes tests).
    assert by_id[interrupted_node.id].status == "ready"

    # Preserve completed work: the sibling node, already "completed" before
    # this event arrived, is never touched or regressed by this handler.
    assert by_id[sibling_node.id].status == "completed"

    persisted = repository.graphs[graph.id]
    persisted_by_id = {n.id: n for n in persisted.nodes}
    # Hand-off: the published snapshot said "ready" (asserted above); the
    # committed row says "running", so a later republish cannot re-offer
    # work already handed to the Kernel.
    assert persisted_by_id[interrupted_node.id].status == "running"
    assert persisted_by_id[sibling_node.id].status == "completed"


@pytest.mark.parametrize("outcome", ["interrupted", "needs_revision"])
async def test_redispatch_outcomes_reset_a_running_node_to_ready(
    monkeypatch,  # type: ignore[no-untyped-def]
    outcome: str,
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    node = _node(status="running")
    repository = FakePlanningRepository()
    graph = _seed_graph(repository, nodes=[node])
    app = create_app(
        Settings(), model_orchestration_port=FakeModelOrchestrationPort(), repository=repository
    )

    async with app.router.lifespan_context(app):
        payload = AgentOsTaskCompletedPayload(
            task_node_id=node.id,
            agent_instance_id=uuid4(),
            outcome=outcome,  # type: ignore[arg-type]
            result=None,
            correlation_id=uuid4(),
        )
        await _publish(app, payload)

    enqueued = _enqueued_graphs(repository)
    assert len(enqueued) == 1
    assert enqueued[0].graph.nodes[0].status == "ready"
    assert repository.graphs[graph.id].nodes[0].status == "running"


async def test_success_completes_the_node_and_promotes_its_dependent(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """The transition that makes a multi-step Task Graph advance past its
    first layer at all -- and the one this handler previously did not make."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    first = _node(objective="Write the endpoint", status="running")
    second = _node(objective="Test the endpoint", depends_on=[first.id], status="pending")
    repository = FakePlanningRepository()
    graph = _seed_graph(repository, nodes=[first, second])
    app = create_app(
        Settings(), model_orchestration_port=FakeModelOrchestrationPort(), repository=repository
    )

    async with app.router.lifespan_context(app):
        await _publish(
            app,
            AgentOsTaskCompletedPayload(
                task_node_id=first.id,
                agent_instance_id=uuid4(),
                outcome="success",
                result={"output": {}},
                correlation_id=uuid4(),
            ),
        )

    enqueued = _enqueued_graphs(repository)
    assert len(enqueued) == 1
    published = {n.id: n.status for n in enqueued[0].graph.nodes}
    assert published == {first.id: "completed", second.id: "ready"}

    persisted = {n.id: n.status for n in repository.graphs[graph.id].nodes}
    assert persisted == {first.id: "completed", second.id: "running"}


async def test_failure_marks_the_node_terminally_failed_without_redispatch(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """Approved Phase 3 decision (Option B): by the time `outcome="failure"`
    reaches this engine the Kernel has already run the Supervisor restart
    path and its bounded retry, so the node is terminal. TDD 3E §12 does not
    define post-retry failure semantics -- see
    `domain/task_completion.py`'s own docstring for the full record."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    node = _node(status="running")
    repository = FakePlanningRepository()
    graph = _seed_graph(repository, nodes=[node])
    app = create_app(
        Settings(), model_orchestration_port=FakeModelOrchestrationPort(), repository=repository
    )

    async with app.router.lifespan_context(app):
        await _publish(
            app,
            AgentOsTaskCompletedPayload(
                task_node_id=node.id,
                agent_instance_id=uuid4(),
                outcome="failure",
                result=None,
                correlation_id=uuid4(),
            ),
        )

    enqueued = _enqueued_graphs(repository)
    assert len(enqueued) == 1
    assert enqueued[0].graph.nodes[0].status == "failed"
    # Never "ready" and never handed off: the Scheduler is not offered this
    # node again.
    assert repository.graphs[graph.id].nodes[0].status == "failed"


async def test_a_deterministic_failure_never_enters_an_unbounded_redispatch_loop(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """The concrete hazard Option B prevents, through the real handler:
    replaying the same failure produces exactly one state change and one
    republish, then nothing -- so the graph cannot cycle forever."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    node = _node(status="running")
    repository = FakePlanningRepository()
    graph = _seed_graph(repository, nodes=[node])
    app = create_app(
        Settings(), model_orchestration_port=FakeModelOrchestrationPort(), repository=repository
    )

    async with app.router.lifespan_context(app):
        for _ in range(4):
            await _publish(
                app,
                AgentOsTaskCompletedPayload(
                    task_node_id=node.id,
                    agent_instance_id=uuid4(),
                    outcome="failure",
                    result=None,
                    correlation_id=uuid4(),
                ),
            )

    # One republish for the first event; the three redeliveries change
    # nothing and enqueue nothing.
    assert len(_enqueued_graphs(repository)) == 1
    assert repository.graphs[graph.id].nodes[0].status == "failed"


async def test_an_already_completed_node_is_never_regressed(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """Preserve completed work, do not duplicate completed agent
    instances -- a late/duplicate interrupted event for an already-
    completed node is a defined no-op, never a regression. NATS JetStream
    is at-least-once, so this is a real delivery mode, not a hypothetical."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    node = _node(status="completed")
    repository = FakePlanningRepository()
    graph = _seed_graph(repository, nodes=[node])
    app = create_app(
        Settings(), model_orchestration_port=FakeModelOrchestrationPort(), repository=repository
    )

    async with app.router.lifespan_context(app):
        payload = AgentOsTaskCompletedPayload(
            task_node_id=node.id,
            agent_instance_id=uuid4(),
            outcome="interrupted",
            result=None,
            correlation_id=uuid4(),
        )
        await _publish(app, payload)

    assert _enqueued_graphs(repository) == []
    assert repository.graphs[graph.id].nodes[0].status == "completed"
    assert repository.outbox == {}


async def test_an_unknown_task_node_id_is_a_defined_no_op(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePlanningRepository()
    app = create_app(
        Settings(), model_orchestration_port=FakeModelOrchestrationPort(), repository=repository
    )

    async with app.router.lifespan_context(app):
        payload = AgentOsTaskCompletedPayload(
            task_node_id=uuid4(),
            agent_instance_id=uuid4(),
            outcome="interrupted",
            result=None,
            correlation_id=uuid4(),
        )
        await _publish(app, payload)

    assert repository.outbox == {}
