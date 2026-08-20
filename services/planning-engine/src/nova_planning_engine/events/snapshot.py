"""Translates a domain `TaskGraph`/`TaskNode` into the wire-shaped
`nova_contracts.events.planning` snapshot types -- the one place this
translation happens, shared by both call sites that publish
`planning.task_graph.created` (the `reasoning.process.completed` handler's
graph-creation path and the `planning.decompose.request` handler's
mutation path), per `nova_contracts.events.planning`'s own module
docstring (domain types stay engine-local; wire payloads are
independently defined and translated at the publish boundary)."""

from __future__ import annotations

from uuid import UUID

from nova_contracts import (
    PlanningTaskGraphCreatedPayload,
    TaskGraphSnapshot,
    TaskNodeSnapshot,
)

from nova_planning_engine.domain.models import TaskGraph, TaskNode

__all__ = ["node_snapshot", "task_graph_created_payload"]


def node_snapshot(node: TaskNode) -> TaskNodeSnapshot:
    return TaskNodeSnapshot(
        id=node.id,
        objective=node.objective,
        depends_on=list(node.depends_on),
        assigned_agent_category=node.assigned_agent_category,
        effort_hours=node.estimated_effort.effort_hours,
        confidence=node.estimated_effort.confidence,
        risk=node.risk,
        status=node.status,
    )


def task_graph_created_payload(
    graph: TaskGraph, *, correlation_id: UUID
) -> PlanningTaskGraphCreatedPayload:
    """TDD 3B §6.2: "published on graph creation *and* on major mutation" --
    the identical payload shape serves both callers."""
    return PlanningTaskGraphCreatedPayload(
        graph=TaskGraphSnapshot(
            id=graph.id,
            root_objective=graph.root_objective,
            nodes=[node_snapshot(node) for node in graph.nodes],
            critical_path=graph.critical_path,
            approved_at=graph.approved_at,
        ),
        correlation_id=correlation_id,
    )
