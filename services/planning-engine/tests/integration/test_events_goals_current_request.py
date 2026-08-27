"""A real Event Bus round-trip through `main.py`'s served
`planning.goals.current.request` RPC (TDD 3E §8) -- mirrors
`test_events_decompose_request.py`'s own "second `BoundEventBus` as
external caller" convention exactly, the closest, most recent precedent
for a served request/reply RPC in this codebase.

Also proves the disclosed scope limitation (`events/goals_handler.py`'s own
docstring): the reply is identical regardless of which `user_id` is
requested, since `TaskGraph` carries no ownership field to filter by."""

from __future__ import annotations

from uuid import uuid4

from nova_contracts import PlanningGoalsCurrentReplyPayload, PlanningGoalsCurrentRequestPayload
from nova_eventbus_sdk import BoundEventBus
from nova_planning_engine.config import Settings
from nova_planning_engine.domain.models import Estimate, RiskLevel, TaskGraph, TaskNode
from nova_planning_engine.main import create_app

from tests.fakes.ports import FakeModelOrchestrationPort
from tests.fakes.repository import FakePlanningRepository


def _node(*, effort_hours: float, status: str = "ready") -> TaskNode:
    return TaskNode(
        objective="do the thing",
        depends_on=[],
        estimated_effort=Estimate(effort_hours=effort_hours, confidence=0.7),
        risk=RiskLevel.LOW,
        status=status,  # type: ignore[arg-type]
    )


def _caller_bus(app):  # type: ignore[no-untyped-def]
    return BoundEventBus(
        app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
        engine_name="test-caller-engine",
        publishable_subjects=frozenset({"planning.goals.current.request"}),
        subscribable_subjects=frozenset(),
    )


async def test_goals_current_request_returns_only_active_graphs_ranked_by_effort(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePlanningRepository()

    low_node = _node(effort_hours=1.0)
    low_graph = TaskGraph(
        root_objective="Small fix", nodes=[low_node], critical_path=[low_node.id]
    )
    repository.graphs[low_graph.id] = low_graph

    high_node = _node(effort_hours=5.0)
    high_graph = TaskGraph(
        root_objective="Ship rate limiting", nodes=[high_node], critical_path=[high_node.id]
    )
    repository.graphs[high_graph.id] = high_graph

    done_node = _node(effort_hours=99.0, status="completed")
    done_graph = TaskGraph(
        root_objective="Already shipped", nodes=[done_node], critical_path=[done_node.id]
    )
    repository.graphs[done_graph.id] = done_graph

    app = create_app(
        Settings(), model_orchestration_port=FakeModelOrchestrationPort(), repository=repository
    )

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)
        request = PlanningGoalsCurrentRequestPayload(
            user_id=uuid4(), requesting_engine="test-caller-engine", correlation_id=uuid4()
        )
        reply_envelope = await caller_bus.request(
            "planning.goals.current.request", request, source_engine="test-caller-engine"
        )
        result = PlanningGoalsCurrentReplyPayload.model_validate(reply_envelope.payload)

    assert {g.id for g in result.goals} == {low_graph.id, high_graph.id}
    assert done_graph.id not in {g.id for g in result.goals}

    by_id = {g.id: g for g in result.goals}
    assert by_id[high_graph.id].priority == 1.0
    assert by_id[low_graph.id].priority == 0.0
    assert by_id[high_graph.id].description == "Ship rate limiting"
    assert by_id[high_graph.id].goal_tier == "ad_hoc"


async def test_goals_current_request_is_not_filtered_by_the_requesting_user_id(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """Disclosed limitation (`events/goals_handler.py` docstring): two
    different `user_id`s in the request produce the identical reply, since
    `TaskGraph` carries no ownership field to filter by."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePlanningRepository()
    node = _node(effort_hours=1.0)
    graph = TaskGraph(root_objective="Ship it", nodes=[node], critical_path=[node.id])
    repository.graphs[graph.id] = graph

    app = create_app(
        Settings(), model_orchestration_port=FakeModelOrchestrationPort(), repository=repository
    )

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)

        reply_a = await caller_bus.request(
            "planning.goals.current.request",
            PlanningGoalsCurrentRequestPayload(
                user_id=uuid4(), requesting_engine="test-caller-engine", correlation_id=uuid4()
            ),
            source_engine="test-caller-engine",
        )
        reply_b = await caller_bus.request(
            "planning.goals.current.request",
            PlanningGoalsCurrentRequestPayload(
                user_id=uuid4(), requesting_engine="test-caller-engine", correlation_id=uuid4()
            ),
            source_engine="test-caller-engine",
        )

    result_a = PlanningGoalsCurrentReplyPayload.model_validate(reply_a.payload)
    result_b = PlanningGoalsCurrentReplyPayload.model_validate(reply_b.payload)
    assert result_a == result_b


async def test_goals_current_request_returns_empty_list_when_nothing_is_active(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePlanningRepository()
    app = create_app(
        Settings(), model_orchestration_port=FakeModelOrchestrationPort(), repository=repository
    )

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)
        reply_envelope = await caller_bus.request(
            "planning.goals.current.request",
            PlanningGoalsCurrentRequestPayload(
                user_id=uuid4(), requesting_engine="test-caller-engine", correlation_id=uuid4()
            ),
            source_engine="test-caller-engine",
        )
        result = PlanningGoalsCurrentReplyPayload.model_validate(reply_envelope.payload)

    assert result.goals == []
