"""`FakePlanningRepository` -- an in-memory `domain.ports.PlanningRepository`,
mirroring `PostgresPlanningRepository`'s own behavior closely enough that
swapping one for the other in a test changes nothing observable, including
the `find_by_id`/`append_nodes`/`set_approved_at` -> `TaskGraphNotFoundError`
translation (mirrors `action-engine`'s own `FakeActionRepository`)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid4

from nova_planning_engine.domain.models import TaskGraph, TaskNode, TaskNodeStatus
from nova_planning_engine.domain.ports import (
    OutboxEvent,
    OutboxRow,
    TaskGraphNotFoundError,
    TaskNodeNotFoundError,
)
from nova_planning_engine.domain.task_graph import admit, compute_critical_path


class FakePlanningRepository:
    def __init__(self) -> None:
        self.graphs: dict[UUID, TaskGraph] = {}
        self.outbox: dict[UUID, OutboxRow] = {}
        self.dispatched: list[UUID] = []

    async def find_by_id(self, task_graph_id: UUID) -> TaskGraph | None:
        return self.graphs.get(task_graph_id)

    async def find_node(self, task_node_id: UUID) -> tuple[TaskGraph, TaskNode] | None:
        for graph in self.graphs.values():
            for node in graph.nodes:
                if node.id == task_node_id:
                    return graph, node
        return None

    def _enqueue(self, event: OutboxEvent) -> None:
        outbox_id = uuid4()
        self.outbox[outbox_id] = OutboxRow(
            id=outbox_id,
            subject=event.subject,
            payload=event.payload,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            created_at=datetime.now().astimezone(),
        )

    def _hand_off(self, graph: TaskGraph) -> TaskGraph:
        """`HAND_OFF_ORDERING` step 4, mirroring
        `PostgresPlanningRepository._hand_off` -- called only *after* the
        outbox payload has been built from the pre-hand-off state."""
        handed = graph.model_copy(
            update={
                "nodes": [
                    node.model_copy(update={"status": "running"})
                    if node.status == "ready"
                    else node
                    for node in graph.nodes
                ]
            }
        )
        self.graphs[graph.id] = handed
        return handed

    async def insert(
        self, graph: TaskGraph, *, outbox_event_builder: Callable[[TaskGraph], OutboxEvent]
    ) -> TaskGraph:
        self.graphs[graph.id] = graph
        self._enqueue(outbox_event_builder(graph))
        return self._hand_off(graph)

    async def append_nodes(
        self,
        task_graph_id: UUID,
        new_nodes: list[TaskNode],
        *,
        outbox_event_builder: Callable[[TaskGraph], OutboxEvent],
    ) -> TaskGraph:
        graph = self.graphs.get(task_graph_id)
        if graph is None:
            raise TaskGraphNotFoundError(f"task_graph {task_graph_id} does not exist")
        all_nodes = [*graph.nodes, *new_nodes]
        updated = graph.model_copy(
            update={
                "nodes": admit(all_nodes),
                "critical_path": compute_critical_path(all_nodes),
            }
        )
        self.graphs[task_graph_id] = updated
        self._enqueue(outbox_event_builder(updated))
        return self._hand_off(updated)

    async def set_approved_at(self, task_graph_id: UUID, *, approved_at: datetime) -> TaskGraph:
        graph = self.graphs.get(task_graph_id)
        if graph is None:
            raise TaskGraphNotFoundError(f"task_graph {task_graph_id} does not exist")
        updated = graph.model_copy(update={"approved_at": approved_at})
        self.graphs[task_graph_id] = updated
        return updated

    async def apply_transitions(
        self,
        task_graph_id: UUID,
        transitions: list[tuple[UUID, TaskNodeStatus]],
        *,
        outbox_event_builder: Callable[[TaskGraph], OutboxEvent],
    ) -> TaskGraph:
        graph = self.graphs.get(task_graph_id)
        if graph is None:
            raise TaskGraphNotFoundError(f"task_graph {task_graph_id} does not exist")

        by_id = {node.id: node for node in graph.nodes}
        new_status: dict[UUID, TaskNodeStatus] = {}
        for node_id, status in transitions:
            if node_id not in by_id:
                raise TaskNodeNotFoundError(
                    f"task_node {node_id} is not part of task_graph {task_graph_id}"
                )
            new_status[node_id] = status

        published_graph = graph.model_copy(
            update={
                "nodes": [
                    node.model_copy(update={"status": new_status[node.id]})
                    if node.id in new_status
                    else node
                    for node in graph.nodes
                ]
            }
        )
        self.graphs[task_graph_id] = published_graph
        self._enqueue(outbox_event_builder(published_graph))
        return self._hand_off(published_graph)

    async def list_all(self, *, limit: int = 1000) -> list[TaskGraph]:
        return list(self.graphs.values())[:limit]

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        return sorted(self.outbox.values(), key=lambda row: row.created_at)[:limit]

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        self.outbox.pop(outbox_id, None)
        self.dispatched.append(outbox_id)
