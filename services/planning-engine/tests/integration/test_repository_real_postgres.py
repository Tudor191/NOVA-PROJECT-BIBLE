"""Real-Postgres verification of `PostgresPlanningRepository` -- real schema
(via this engine's own Alembic migration chain, `0001_initial_schema.py`),
real INSERT/SELECT/UPDATE round trips across all three tables (`task_graph`,
`task_node`, `outbox_event`), including the "mutation, not regeneration"
critical-path recomputation `append_nodes` depends on (TDD 3B §4). Mirrors
`action-engine`'s own `test_repository_real_postgres.py` convention.

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run
test` invocation (ADR-033) -- requires Docker. **Not executed in the
environment this file was written in** (no reachable Docker daemon there);
see `nova_testkit.postgres`'s module docstring for exactly what was and
wasn't verifiable here.
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from nova_contracts import RiskLevel
from nova_planning_engine.domain.models import Estimate, TaskGraph, TaskNode
from nova_planning_engine.domain.ports import (
    OutboxEvent,
    TaskGraphNotFoundError,
    TaskNodeNotFoundError,
)
from nova_planning_engine.repository.postgres_planning_repository import (
    PostgresPlanningRepository,
)
from nova_testkit.postgres import run_alembic_upgrade
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.real_infra

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(postgres_container: PostgresContainer) -> None:
    os.environ["PLANNING_ENGINE_POSTGRES_DSN"] = postgres_container.get_connection_url()
    run_alembic_upgrade(_ALEMBIC_INI)


@pytest.fixture
def repository(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> PostgresPlanningRepository:
    return PostgresPlanningRepository(postgres_session_factory)


def _node(**overrides: object) -> TaskNode:
    defaults: dict[str, object] = {
        "objective": "Set up the project skeleton",
        "depends_on": [],
        "assigned_agent_category": "coding-agent",
        "estimated_effort": Estimate(effort_hours=2.0, confidence=0.8),
        "risk": RiskLevel.LOW,
    }
    defaults.update(overrides)
    return TaskNode(**defaults)  # type: ignore[arg-type]


def _graph(**overrides: object) -> TaskGraph:
    node = _node()
    defaults: dict[str, object] = {
        "root_objective": "Ship the feature",
        "nodes": [node],
        "critical_path": [node.id],
    }
    defaults.update(overrides)
    return TaskGraph(**defaults)  # type: ignore[arg-type]


def _outbox_event(**overrides: object) -> OutboxEvent:
    defaults: dict[str, object] = {
        "subject": "planning.task_graph.created",
        "payload": {"foo": "bar"},
        "correlation_id": uuid4(),
    }
    defaults.update(overrides)
    return OutboxEvent(**defaults)  # type: ignore[arg-type]


def _builder(**overrides: object):  # type: ignore[no-untyped-def]
    """Builder-style counterpart to `_outbox_event`, for the repository
    methods that derive their payload from the pre-hand-off graph
    (`domain/ports.py::HAND_OFF_ORDERING`)."""
    event = _outbox_event(**overrides)
    return lambda _graph: event


def _statuses(graph: TaskGraph) -> dict[UUID, str]:
    return {node.id: node.status for node in graph.nodes}


async def test_insert_then_find_by_id_round_trips(
    repository: PostgresPlanningRepository,
) -> None:
    graph = _graph()
    assert await repository.find_by_id(graph.id) is None

    await repository.insert(graph, outbox_event_builder=_builder(correlation_id=uuid4()))

    fetched = await repository.find_by_id(graph.id)
    assert fetched == graph


async def test_insert_persists_multiple_nodes_in_order(
    repository: PostgresPlanningRepository,
) -> None:
    node_a = _node(objective="a")
    node_b = _node(objective="b", depends_on=[node_a.id])
    graph = _graph(nodes=[node_a, node_b], critical_path=[node_a.id, node_b.id])
    await repository.insert(graph, outbox_event_builder=_builder())

    fetched = await repository.find_by_id(graph.id)
    assert fetched is not None
    assert {n.objective for n in fetched.nodes} == {"a", "b"}
    fetched_b = next(n for n in fetched.nodes if n.objective == "b")
    assert fetched_b.depends_on == [node_a.id]


async def test_find_node_locates_the_graph_containing_it(
    repository: PostgresPlanningRepository,
) -> None:
    node = _node()
    graph = _graph(nodes=[node], critical_path=[node.id])
    await repository.insert(graph, outbox_event_builder=_builder())

    found = await repository.find_node(node.id)
    assert found is not None
    found_graph, found_node = found
    assert found_graph.id == graph.id
    assert found_node.id == node.id


async def test_find_node_returns_none_for_an_unknown_id(
    repository: PostgresPlanningRepository,
) -> None:
    assert await repository.find_node(uuid4()) is None


async def test_append_nodes_mutates_in_place_and_recomputes_critical_path(
    repository: PostgresPlanningRepository,
) -> None:
    """TDD 3B §4's "mutation, not regeneration": the original node's own row
    is never deleted or replaced -- new nodes are appended, and
    `critical_path` reflects the post-mutation graph."""
    original = _node(
        objective="original", estimated_effort=Estimate(effort_hours=1.0, confidence=0.9)
    )
    graph = _graph(nodes=[original], critical_path=[original.id])
    await repository.insert(graph, outbox_event_builder=_builder())

    new_node = _node(
        objective="appended", estimated_effort=Estimate(effort_hours=3.0, confidence=0.7)
    )

    captured_builder_arg: list[TaskGraph] = []

    def _capturing_builder(updated_graph: TaskGraph) -> OutboxEvent:
        captured_builder_arg.append(updated_graph)
        return _outbox_event(correlation_id=uuid4())

    updated = await repository.append_nodes(
        graph.id, [new_node], outbox_event_builder=_capturing_builder
    )

    assert {n.id for n in updated.nodes} == {original.id, new_node.id}
    assert new_node.id in updated.critical_path

    # The builder is called with the fully-updated, post-mutation graph
    # (recomputed critical_path included) -- not the pre-mutation state.
    assert len(captured_builder_arg) == 1
    published = captured_builder_arg[0]
    assert {n.id for n in published.nodes} == {original.id, new_node.id}
    assert new_node.id in published.critical_path

    # `HAND_OFF_ORDERING`: `append_nodes` admits the newly appended,
    # dependency-free node, so the published snapshot offers it as "ready"
    # while the returned/committed state already says "running".
    assert _statuses(published) == {original.id: "ready", new_node.id: "ready"}
    assert _statuses(updated) == {original.id: "running", new_node.id: "running"}

    fetched = await repository.find_by_id(graph.id)
    assert fetched is not None
    assert {n.id for n in fetched.nodes} == {original.id, new_node.id}
    assert _statuses(fetched) == {original.id: "running", new_node.id: "running"}


async def test_append_nodes_raises_for_an_unknown_task_graph_id(
    repository: PostgresPlanningRepository,
) -> None:
    with pytest.raises(TaskGraphNotFoundError):
        await repository.append_nodes(
            uuid4(), [_node()], outbox_event_builder=lambda _graph: _outbox_event()
        )


async def test_set_approved_at_persists_the_decision(
    repository: PostgresPlanningRepository,
) -> None:
    from datetime import UTC, datetime

    graph = _graph()
    await repository.insert(graph, outbox_event_builder=_builder())
    assert graph.approved_at is None

    approved_at = datetime.now(UTC)
    updated = await repository.set_approved_at(graph.id, approved_at=approved_at)
    assert updated.approved_at == approved_at

    fetched = await repository.find_by_id(graph.id)
    assert fetched is not None
    assert fetched.approved_at == approved_at


async def test_set_approved_at_raises_for_an_unknown_task_graph_id(
    repository: PostgresPlanningRepository,
) -> None:
    from datetime import UTC, datetime

    with pytest.raises(TaskGraphNotFoundError):
        await repository.set_approved_at(uuid4(), approved_at=datetime.now(UTC))


async def test_apply_transitions_mutates_status_and_republishes(
    repository: PostgresPlanningRepository,
) -> None:
    """TDD 3E §4/§12's own restart-resume write -- mirrors
    `test_append_nodes_mutates_in_place_and_recomputes_critical_path`'s own
    "mutation, not regeneration" verification shape, applied to a status
    change instead of a node-set change."""
    node = _node(status="running")
    graph = _graph(nodes=[node], critical_path=[node.id])
    await repository.insert(graph, outbox_event_builder=_builder())

    captured: list[TaskGraph] = []

    def _capturing_builder(updated_graph: TaskGraph) -> OutboxEvent:
        captured.append(updated_graph)
        return _outbox_event(subject="planning.task_graph.created", correlation_id=uuid4())

    returned = await repository.apply_transitions(
        graph.id, [(node.id, "ready")], outbox_event_builder=_capturing_builder
    )

    # `HAND_OFF_ORDERING`: the published payload says "ready" (it is a
    # hand-off document for the Scheduler), the committed row says
    # "running" (it has already been handed over).
    assert len(captured) == 1
    assert _statuses(captured[0]) == {node.id: "ready"}
    assert _statuses(returned) == {node.id: "running"}

    fetched = await repository.find_by_id(graph.id)
    assert fetched is not None
    assert _statuses(fetched) == {node.id: "running"}

    # Second row in the outbox now (the original insert's own row, plus
    # this mutation's own republish).
    ready_rows = await repository.list_dispatch_ready()
    assert len(ready_rows) == 2


async def test_apply_transitions_advances_a_completion_and_its_dependent_atomically(
    repository: PostgresPlanningRepository,
) -> None:
    """The completion and every promotion it unblocks land in one
    transaction and one republish -- a half-advanced graph is never
    observable, and the Scheduler is never handed two snapshots for one
    advancement."""
    first = _node(objective="write the endpoint", status="running")
    second = _node(objective="test the endpoint", depends_on=[first.id])
    graph = _graph(nodes=[first, second], critical_path=[first.id, second.id])
    await repository.insert(graph, outbox_event_builder=_builder())

    captured: list[TaskGraph] = []

    def _capturing_builder(updated_graph: TaskGraph) -> OutboxEvent:
        captured.append(updated_graph)
        return _outbox_event(correlation_id=uuid4())

    await repository.apply_transitions(
        graph.id,
        [(first.id, "completed"), (second.id, "ready")],
        outbox_event_builder=_capturing_builder,
    )

    assert len(captured) == 1
    assert _statuses(captured[0]) == {first.id: "completed", second.id: "ready"}

    fetched = await repository.find_by_id(graph.id)
    assert fetched is not None
    assert _statuses(fetched) == {first.id: "completed", second.id: "running"}


async def test_apply_transitions_raises_for_an_unknown_task_node_id(
    repository: PostgresPlanningRepository,
) -> None:
    graph = _graph()
    await repository.insert(graph, outbox_event_builder=_builder())
    with pytest.raises(TaskNodeNotFoundError):
        await repository.apply_transitions(
            graph.id, [(uuid4(), "ready")], outbox_event_builder=lambda _graph: _outbox_event()
        )


async def test_apply_transitions_raises_for_an_unknown_task_graph_id(
    repository: PostgresPlanningRepository,
) -> None:
    with pytest.raises(TaskGraphNotFoundError):
        await repository.apply_transitions(
            uuid4(), [(uuid4(), "ready")], outbox_event_builder=lambda _graph: _outbox_event()
        )


async def test_insert_hands_off_admitted_nodes_while_publishing_them_as_ready(
    repository: PostgresPlanningRepository,
) -> None:
    """`HAND_OFF_ORDERING` at graph creation, against real Postgres: the
    enqueued snapshot names the admitted node `"ready"`; the committed row
    already says `"running"`, so a later republish cannot re-offer it."""
    ready_node = _node(objective="dispatch me", status="ready")
    pending_node = _node(objective="wait for me", depends_on=[ready_node.id])
    graph = _graph(
        nodes=[ready_node, pending_node], critical_path=[ready_node.id, pending_node.id]
    )

    captured: list[TaskGraph] = []

    def _capturing_builder(persisted_graph: TaskGraph) -> OutboxEvent:
        captured.append(persisted_graph)
        return _outbox_event()

    returned = await repository.insert(graph, outbox_event_builder=_capturing_builder)

    assert len(captured) == 1
    assert _statuses(captured[0]) == {ready_node.id: "ready", pending_node.id: "pending"}
    assert _statuses(returned) == {ready_node.id: "running", pending_node.id: "pending"}

    fetched = await repository.find_by_id(graph.id)
    assert fetched is not None
    assert _statuses(fetched) == {ready_node.id: "running", pending_node.id: "pending"}


async def test_outbox_list_dispatch_ready_and_mark_dispatched_round_trip(
    repository: PostgresPlanningRepository,
) -> None:
    graph = _graph()
    correlation_id = uuid4()
    await repository.insert(graph, outbox_event_builder=_builder(correlation_id=correlation_id))

    ready = await repository.list_dispatch_ready()
    assert len(ready) == 1
    row = ready[0]
    assert row.subject == "planning.task_graph.created"
    assert row.correlation_id == correlation_id

    await repository.mark_dispatched(row.id)

    assert await repository.list_dispatch_ready() == []


async def test_a_fresh_repository_instance_reads_back_a_graph_written_earlier(
    postgres_session_factory: async_sessionmaker[AsyncSession],
    repository: PostgresPlanningRepository,
) -> None:
    """TDD 3B §12/§13 acceptance criterion 4: "`TaskGraph`/`TaskNode` state
    survives a real-Postgres restart simulation unchanged" -- the TDD's own
    wording scopes this as "simulated via a fresh repository instance
    against the same real Postgres," exactly what this test does: a
    *second*, independently constructed `PostgresPlanningRepository`
    (standing in for a restarted process's own freshly constructed
    repository) reads back what the first instance wrote, proving
    persistence does not depend on any in-process instance state (e.g. a
    Python dict cache)."""
    graph = _graph()
    await repository.insert(graph, outbox_event_builder=_builder())

    second_repository = PostgresPlanningRepository(postgres_session_factory)
    fetched = await second_repository.find_by_id(graph.id)
    assert fetched == graph
