"""A real Event Bus round-trip through `main.py`'s served
`planning.decompose.request` RPC (TDD 3B §6.2, doc 12 §11,
`phase-3b-planning-persistence` precursor) -- mirrors `action-engine`'s own
`test_events_action_execute.py` convention exactly (the closest, most
recent precedent for a served request/reply RPC in this codebase).

`app.state.bus`'s own `publishable_subjects` (`events/published.py`)
deliberately do not include `planning.decompose.request` -- this engine
only ever *serves* that subject, never calls it on itself. A second
`BoundEventBus`, wrapping the exact same underlying in-memory bus instance,
stands in for the kind of external caller (Phase 3E's future Supervisor)
whose own `published.py` would legitimately list it."""

from __future__ import annotations

from uuid import uuid4

import pytest
from nova_contracts import (
    GenerateReplyPayload,
    PlanningDecomposeReplyPayload,
    PlanningDecomposeRequestPayload,
    ToolCallPayload,
)
from nova_eventbus_sdk import BoundEventBus
from nova_planning_engine.config import Settings
from nova_planning_engine.domain.models import Estimate, RiskLevel, TaskGraph, TaskNode
from nova_planning_engine.events.decompose_handler import TaskNodeNotFoundError
from nova_planning_engine.main import create_app

from tests.fakes.ports import FakeModelOrchestrationPort
from tests.fakes.repository import FakePlanningRepository


def _seed_graph(repository: FakePlanningRepository, *, node: TaskNode) -> TaskGraph:
    graph = TaskGraph(root_objective="Ship the release", nodes=[node], critical_path=[node.id])
    repository.graphs[graph.id] = graph
    return graph


def _target_node() -> TaskNode:
    return TaskNode(
        objective="Implement the feature",
        depends_on=[],
        estimated_effort=Estimate(effort_hours=5.0, confidence=0.6),
        risk=RiskLevel.MODERATE,
    )


def _caller_bus(app):  # type: ignore[no-untyped-def]
    return BoundEventBus(
        app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
        engine_name="test-caller-engine",
        publishable_subjects=frozenset({"planning.decompose.request"}),
        subscribable_subjects=frozenset(),
    )


async def test_decompose_request_round_trips_a_genuine_breakdown(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    node = _target_node()
    port = FakeModelOrchestrationPort(
        reply=GenerateReplyPayload(
            text="",
            tool_calls=[
                ToolCallPayload(
                    id="call_0",
                    tool_name="propose_task_graph",
                    arguments={
                        "tasks": [
                            {
                                "local_id": "a",
                                "objective": "Design the schema",
                                "depends_on": [],
                                "effort_hours": 1.0,
                                "confidence": 0.7,
                                "risk": "low",
                            },
                            {
                                "local_id": "b",
                                "objective": "Implement the migration",
                                "depends_on": ["a"],
                                "effort_hours": 2.0,
                                "confidence": 0.6,
                                "risk": "moderate",
                            },
                        ]
                    },
                )
            ],
            input_tokens=10,
            output_tokens=10,
            finish_reason="tool_calls",
            structural_confidence=0.9,
            model_id=uuid4(),
            provider="fake",
        )
    )
    repository = FakePlanningRepository()
    graph = _seed_graph(repository, node=node)
    settings = Settings()
    app = create_app(settings, model_orchestration_port=port, repository=repository)

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)
        request = PlanningDecomposeRequestPayload(
            task_node_id=node.id, requesting_engine="test-caller-engine", correlation_id=uuid4()
        )
        reply_envelope = await caller_bus.request(
            "planning.decompose.request", request, source_engine="test-caller-engine"
        )
        result = PlanningDecomposeReplyPayload.model_validate(reply_envelope.payload)

    assert result.already_minimal is False
    assert {n.objective for n in result.new_nodes} == {
        "Design the schema",
        "Implement the migration",
    }
    # Mutation, not regeneration (TDD 3B §4): the original node's graph now
    # holds three nodes -- the original plus the two new ones -- never
    # replaced or deleted.
    updated_graph = repository.graphs[graph.id]
    assert len(updated_graph.nodes) == 3
    assert any(n.id == node.id for n in updated_graph.nodes)
    assert len(repository.outbox) == 1
    (outbox_row,) = repository.outbox.values()
    assert outbox_row.subject == "planning.task_graph.created"


async def test_decompose_request_reports_already_minimal(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    node = _target_node()
    port = FakeModelOrchestrationPort(
        reply=GenerateReplyPayload(
            text="",
            tool_calls=[
                ToolCallPayload(
                    id="call_0",
                    tool_name="propose_task_graph",
                    arguments={
                        "tasks": [
                            {
                                "local_id": "a",
                                "objective": node.objective,
                                "depends_on": [],
                                "effort_hours": 5.0,
                                "confidence": 0.6,
                                "risk": "moderate",
                            }
                        ]
                    },
                )
            ],
            input_tokens=10,
            output_tokens=10,
            finish_reason="tool_calls",
            structural_confidence=0.9,
            model_id=uuid4(),
            provider="fake",
        )
    )
    repository = FakePlanningRepository()
    graph = _seed_graph(repository, node=node)
    app = create_app(Settings(), model_orchestration_port=port, repository=repository)

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)
        request = PlanningDecomposeRequestPayload(
            task_node_id=node.id, requesting_engine="test-caller-engine", correlation_id=uuid4()
        )
        reply_envelope = await caller_bus.request(
            "planning.decompose.request", request, source_engine="test-caller-engine"
        )
        result = PlanningDecomposeReplyPayload.model_validate(reply_envelope.payload)

    assert result.already_minimal is True
    assert result.new_nodes == []
    # No mutation, no outbox event -- the graph is untouched.
    assert len(repository.graphs[graph.id].nodes) == 1
    assert repository.outbox == {}


async def test_decompose_request_raises_for_an_unknown_task_node_id(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePlanningRepository()
    app = create_app(
        Settings(), model_orchestration_port=FakeModelOrchestrationPort(), repository=repository
    )

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)
        request = PlanningDecomposeRequestPayload(
            task_node_id=uuid4(), requesting_engine="test-caller-engine", correlation_id=uuid4()
        )
        with pytest.raises(TaskNodeNotFoundError):
            await caller_bus.request(
                "planning.decompose.request", request, source_engine="test-caller-engine"
            )
