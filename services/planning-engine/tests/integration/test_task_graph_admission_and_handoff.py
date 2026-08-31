"""Graph admission and the ready-to-running hand-off, end to end through
`main.py`'s real subscribed `reasoning.process.completed` handler and the
real `decompose()` -- the path whose missing admission step meant the real
Reasoning -> Planning -> Kernel chain dispatched **zero** agent instances no
matter how good the Task Graph was.

Two properties are proven here that no other test covers:

1. **Admission.** A real decomposition produces at least one `"ready"` node
   in the published `planning.task_graph.created` snapshot, so
   `agent-os/kernel`'s Scheduler (which dispatches only `"ready"` nodes) has
   something to dispatch at all.
2. **Hand-off ordering** (`domain/ports.py::HAND_OFF_ORDERING`). The
   published snapshot says `"ready"`; the committed rows already say
   `"running"`. That difference is what stops a later republish -- and every
   completion triggers one -- from re-dispatching work already in flight.

The model is the only stand-in: `FakeModelOrchestrationPort` returns a
fixed `propose_task_graph` tool call, exactly as `test_events_reasoning_
completed.py` already does. Everything below the model boundary --
`decompose()`, admission, the repository, the outbox -- is real.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_contracts import (
    EventEnvelope,
    GenerateReplyPayload,
    PlanningTaskGraphCreatedPayload,
    ReasoningProcessCompletedPayload,
    ToolCallPayload,
)
from nova_eventbus_sdk import BoundEventBus
from nova_planning_engine.config import Settings
from nova_planning_engine.main import create_app

from tests.fakes.ports import FakeModelOrchestrationPort
from tests.fakes.repository import FakePlanningRepository

_DIAMOND_TASKS = {
    "tasks": [
        {
            "local_id": "endpoint",
            "objective": "Add the /health endpoint",
            "depends_on": [],
            "assigned_agent_category": "coding",
            "effort_hours": 2.0,
            "confidence": 0.8,
            "risk": "moderate",
        },
        {
            "local_id": "docs",
            "objective": "Document the /health endpoint",
            "depends_on": [],
            "assigned_agent_category": "documentation",
            "effort_hours": 1.0,
            "confidence": 0.9,
            "risk": "low",
        },
        {
            "local_id": "qa",
            "objective": "Run the test suite",
            "depends_on": ["endpoint", "docs"],
            "assigned_agent_category": "qa",
            "effort_hours": 1.0,
            "confidence": 0.9,
            "risk": "low",
        },
    ]
}


def _model_port(tasks: dict) -> FakeModelOrchestrationPort:
    return FakeModelOrchestrationPort(
        reply=GenerateReplyPayload(
            text="",
            input_tokens=10,
            output_tokens=10,
            finish_reason="tool_calls",
            structural_confidence=0.9,
            model_id=uuid4(),
            provider="fake",
            tool_calls=[
                ToolCallPayload(id="call-1", tool_name="propose_task_graph", arguments=tasks)
            ],
        )
    )


async def _decompose_through_the_real_handler(
    monkeypatch,  # type: ignore[no-untyped-def]
    tasks: dict,
) -> tuple[FakePlanningRepository, PlanningTaskGraphCreatedPayload]:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePlanningRepository()
    app = create_app(
        Settings(), model_orchestration_port=_model_port(tasks), repository=repository
    )

    async with app.router.lifespan_context(app):
        caller_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
            engine_name="reasoning-engine",
            publishable_subjects=frozenset({"reasoning.process.completed"}),
            subscribable_subjects=frozenset(),
        )
        correlation_id = uuid4()
        payload = ReasoningProcessCompletedPayload(
            reasoning_process_id=uuid4(),
            correlation_id=correlation_id,
            requesting_engine="reasoning-engine",
            user_id=uuid4(),
            reasoning_mode="analytical",
            reasoning_level=1,
            confidence_score=0.9,
            execution_duration_ms=120.0,
            outcome="decided",
            objective_text="Add a health-check endpoint to a sample repo",
            chosen_description="Add a /health route, document it, and run the tests",
        )
        await caller_bus.publish(
            EventEnvelope(
                subject="reasoning.process.completed",
                source_engine="reasoning-engine",
                correlation_id=correlation_id,
                payload=payload.model_dump(mode="json"),
            )
        )

    rows = [
        row
        for row in repository.outbox.values()
        if row.subject == "planning.task_graph.created"
    ]
    assert len(rows) == 1
    return repository, PlanningTaskGraphCreatedPayload.model_validate(rows[0].payload)


def _published_statuses(published: PlanningTaskGraphCreatedPayload) -> dict[str, str]:
    return {node.objective: node.status for node in published.graph.nodes}


def _persisted_statuses(repository: FakePlanningRepository, graph_id: UUID) -> dict[str, str]:
    return {node.objective: node.status for node in repository.graphs[graph_id].nodes}


async def test_a_real_decomposition_publishes_dispatchable_ready_nodes(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """The regression this slice exists to prevent. Before admission, every
    node `decompose()` produced carried `TaskNode`'s default `"pending"`,
    and `agent-os/kernel`'s Scheduler dispatches only `"ready"` nodes -- so
    a structurally perfect Task Graph yielded zero agent instances."""
    _repository, published = await _decompose_through_the_real_handler(
        monkeypatch, _DIAMOND_TASKS
    )

    ready = [node for node in published.graph.nodes if node.status == "ready"]
    assert ready, "a real decomposition must publish at least one dispatchable node"


async def test_admission_marks_both_independent_nodes_ready_and_the_dependent_pending(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """TDD 3E §14 criterion #1's parallelism clause depends on BOTH
    independent nodes being admitted -- one `"ready"` node can never produce
    two concurrent agent instances."""
    _repository, published = await _decompose_through_the_real_handler(
        monkeypatch, _DIAMOND_TASKS
    )

    assert _published_statuses(published) == {
        "Add the /health endpoint": "ready",
        "Document the /health endpoint": "ready",
        "Run the test suite": "pending",
    }


async def test_the_published_snapshot_says_ready_while_the_persisted_rows_say_running(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """`HAND_OFF_ORDERING` in one assertion pair: the snapshot is the
    hand-off document, the rows record that the hand-off already happened."""
    repository, published = await _decompose_through_the_real_handler(
        monkeypatch, _DIAMOND_TASKS
    )

    assert _published_statuses(published) == {
        "Add the /health endpoint": "ready",
        "Document the /health endpoint": "ready",
        "Run the test suite": "pending",
    }
    assert _persisted_statuses(repository, published.graph.id) == {
        "Add the /health endpoint": "running",
        "Document the /health endpoint": "running",
        "Run the test suite": "pending",
    }


async def test_no_handed_off_node_is_ever_re_offered_by_a_later_republish(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """The double-dispatch hazard the hand-off exists to close: when the
    first of two in-flight siblings completes, the resulting republish must
    NOT re-offer the sibling that is still running."""
    from nova_contracts import AgentOsTaskCompletedPayload

    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePlanningRepository()
    app = create_app(
        Settings(), model_orchestration_port=_model_port(_DIAMOND_TASKS), repository=repository
    )

    async with app.router.lifespan_context(app):
        reasoning_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001
            engine_name="reasoning-engine",
            publishable_subjects=frozenset({"reasoning.process.completed"}),
            subscribable_subjects=frozenset(),
        )
        await reasoning_bus.publish(
            EventEnvelope(
                subject="reasoning.process.completed",
                source_engine="reasoning-engine",
                correlation_id=uuid4(),
                payload=ReasoningProcessCompletedPayload(
                    reasoning_process_id=uuid4(),
                    correlation_id=uuid4(),
                    requesting_engine="reasoning-engine",
                    user_id=uuid4(),
                    reasoning_mode="analytical",
                    reasoning_level=1,
                    confidence_score=0.9,
                    execution_duration_ms=120.0,
                    outcome="decided",
                    objective_text="Add a health-check endpoint to a sample repo",
                    chosen_description="Add a /health route, document it, and run the tests",
                ).model_dump(mode="json"),
            )
        )

        graph = next(iter(repository.graphs.values()))
        endpoint = next(n for n in graph.nodes if n.objective == "Add the /health endpoint")
        docs = next(n for n in graph.nodes if n.objective == "Document the /health endpoint")

        kernel_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001
            engine_name="kernel",
            publishable_subjects=frozenset({"agent_os.task.completed"}),
            subscribable_subjects=frozenset(),
        )
        await kernel_bus.publish(
            EventEnvelope(
                subject="agent_os.task.completed",
                source_engine="kernel",
                correlation_id=uuid4(),
                payload=AgentOsTaskCompletedPayload(
                    task_node_id=endpoint.id,
                    agent_instance_id=uuid4(),
                    outcome="success",
                    result={"output": {}},
                    correlation_id=uuid4(),
                ).model_dump(mode="json"),
            )
        )

    republished = [
        PlanningTaskGraphCreatedPayload.model_validate(row.payload)
        for row in repository.outbox.values()
        if row.subject == "planning.task_graph.created"
    ]
    assert len(republished) == 2

    latest = {node.id: node.status for node in republished[-1].graph.nodes}
    assert latest[endpoint.id] == "completed"
    # The still-in-flight sibling is NOT re-offered as "ready" -- it was
    # already handed off on the first publish.
    assert latest[docs.id] == "running"
    # ...and the qa node stays "pending": one of its two dependencies is
    # still running.
    qa = next(n for n in republished[-1].graph.nodes if n.objective == "Run the test suite")
    assert qa.status == "pending"
