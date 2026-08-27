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
from nova_planning_engine.domain.task_graph import compute_critical_path


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

    async def insert(self, graph: TaskGraph, *, outbox_event: OutboxEvent) -> TaskGraph:
        self.graphs[graph.id] = graph
        self._enqueue(outbox_event)
        return graph

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
                "nodes": all_nodes,
                "critical_path": compute_critical_path(all_nodes),
            }
        )
        self.graphs[task_graph_id] = updated
        self._enqueue(outbox_event_builder(updated))
        return updated

    async def set_approved_at(self, task_graph_id: UUID, *, approved_at: datetime) -> TaskGraph:
        graph = self.graphs.get(task_graph_id)
        if graph is None:
            raise TaskGraphNotFoundError(f"task_graph {task_graph_id} does not exist")
        updated = graph.model_copy(update={"approved_at": approved_at})
        self.graphs[task_graph_id] = updated
        return updated

    async def reset_node_status(
        self,
        task_node_id: UUID,
        *,
        status: TaskNodeStatus,
        outbox_event_builder: Callable[[TaskGraph], OutboxEvent],
    ) -> TaskGraph:
        for graph in self.graphs.values():
            for index, node in enumerate(graph.nodes):
                if node.id != task_node_id:
                    continue
                updated_node = node.model_copy(update={"status": status})
                new_nodes = [*graph.nodes[:index], updated_node, *graph.nodes[index + 1 :]]
                updated_graph = graph.model_copy(update={"nodes": new_nodes})
                self.graphs[graph.id] = updated_graph
                self._enqueue(outbox_event_builder(updated_graph))
                return updated_graph
        raise TaskNodeNotFoundError(f"task_node {task_node_id} does not exist")

    async def list_all(self, *, limit: int = 1000) -> list[TaskGraph]:
        return list(self.graphs.values())[:limit]

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        return sorted(self.outbox.values(), key=lambda row: row.created_at)[:limit]

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        self.outbox.pop(outbox_id, None)
        self.dispatched.append(outbox_id)
