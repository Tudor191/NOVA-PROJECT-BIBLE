"""End-to-end tests through `api/plans.py` -- `GET /v1/plans/{id}` and
`POST /v1/plans/{id}/approve` (TDD 3B §5, `phase-3b-planning-persistence`
precursor), against `create_app()` and a real `TestClient`. Mirrors
`action-engine`'s own `test_approvals_api.py` convention."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from nova_contracts import RiskLevel
from nova_planning_engine.config import Settings
from nova_planning_engine.domain.models import Estimate, TaskGraph, TaskNode
from nova_planning_engine.domain.ports import OutboxEvent
from nova_planning_engine.main import create_app

from tests.fakes.ports import FakeModelOrchestrationPort
from tests.fakes.repository import FakePlanningRepository


def _graph() -> TaskGraph:
    node = TaskNode(
        objective="Ship the feature",
        depends_on=[],
        estimated_effort=Estimate(effort_hours=3.0, confidence=0.7),
        risk=RiskLevel.LOW,
    )
    return TaskGraph(root_objective="Ship the feature", nodes=[node], critical_path=[node.id])


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePlanningRepository()
    app = create_app(
        Settings(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        repository=repository,
    )
    with TestClient(app) as client:
        yield client, repository


def test_get_plan_returns_a_persisted_task_graph(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness
    graph = _graph()
    asyncio.run(
        repository.insert(
            graph,
            outbox_event=OutboxEvent(
                subject="planning.task_graph.created",
                payload={},
                correlation_id=uuid4(),
            ),
        )
    )

    response = client.get(f"/v1/plans/{graph.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(graph.id)
    assert body["root_objective"] == "Ship the feature"
    assert body["approved_at"] is None


def test_get_plan_returns_404_for_an_unknown_task_graph_id(harness) -> None:  # type: ignore[no-untyped-def]
    client, _repository = harness

    response = client.get(f"/v1/plans/{uuid4()}")

    assert response.status_code == 404


def test_approve_plan_records_an_approval_decision(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness
    graph = _graph()
    asyncio.run(
        repository.insert(
            graph,
            outbox_event=OutboxEvent(
                subject="planning.task_graph.created", payload={}, correlation_id=uuid4()
            ),
        )
    )

    response = client.post(f"/v1/plans/{graph.id}/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(graph.id)
    assert body["approved_at"] is not None
    # §5's own "scoped honestly" disclosure: approval records the decision
    # but does not gate anything else -- no agent-os/kernel exists yet to
    # consume it. This test only proves the timestamp is persisted.
    persisted = asyncio.run(repository.find_by_id(graph.id))
    assert persisted is not None
    assert persisted.approved_at is not None


def test_approve_plan_returns_404_for_an_unknown_task_graph_id(harness) -> None:  # type: ignore[no-untyped-def]
    client, _repository = harness

    response = client.post(f"/v1/plans/{uuid4()}/approve")

    assert response.status_code == 404
