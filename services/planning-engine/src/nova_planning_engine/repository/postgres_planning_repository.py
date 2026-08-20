"""`PostgresPlanningRepository` -- implements `domain.ports.PlanningRepository`
against SQLAlchemy async, per the schema in
docs/design/phase-3/05-tdd-3b-planning-engine.md §4.

Every write (`insert`, `append_nodes`, `set_approved_at`) writes its
accompanying `outbox_event` row in the same transaction (TDD 3B §4's
transactional-outbox requirement) -- mirrors `memory-engine`'s own
`create_long_term`/`OutboxEvent` pattern exactly, applied to a
multi-row (`task_graph` + N `task_node`) write instead of a single row.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from nova_planning_engine.domain.models import Estimate, RiskLevel, TaskGraph, TaskNode
from nova_planning_engine.domain.ports import (
    OutboxEvent,
    OutboxRow,
    TaskGraphNotFoundError,
)
from nova_planning_engine.domain.task_graph import compute_critical_path
from nova_planning_engine.repository.models import OutboxEventORM, TaskGraphORM, TaskNodeORM

__all__ = ["PostgresPlanningRepository"]


def _node_to_domain(row: TaskNodeORM) -> TaskNode:
    return TaskNode(
        id=row.id,
        objective=row.objective,
        depends_on=list(row.depends_on),
        assigned_agent_category=row.assigned_agent_category,
        estimated_effort=Estimate.model_validate(row.estimated_effort),
        risk=RiskLevel(row.risk),
        status=row.status,
    )


def _graph_to_domain(row: TaskGraphORM) -> TaskGraph:
    return TaskGraph(
        id=row.id,
        root_objective=row.root_objective,
        nodes=[_node_to_domain(node) for node in row.nodes],
        critical_path=list(row.critical_path),
        approved_at=row.approved_at,
    )


def _node_orm(node: TaskNode, task_graph_id: UUID) -> TaskNodeORM:
    return TaskNodeORM(
        id=node.id,
        task_graph_id=task_graph_id,
        objective=node.objective,
        depends_on=list(node.depends_on),
        assigned_agent_category=node.assigned_agent_category,
        estimated_effort=node.estimated_effort.model_dump(mode="json"),
        risk=node.risk.value,
        status=node.status,
    )


def _outbox_orm(event: OutboxEvent) -> OutboxEventORM:
    return OutboxEventORM(
        subject=event.subject,
        payload=event.payload,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
    )


class PostgresPlanningRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def find_by_id(self, task_graph_id: UUID) -> TaskGraph | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(TaskGraphORM)
                .where(TaskGraphORM.id == task_graph_id)
                .options(selectinload(TaskGraphORM.nodes))
            )
            row = result.scalar_one_or_none()
            return _graph_to_domain(row) if row is not None else None

    async def find_node(self, task_node_id: UUID) -> tuple[TaskGraph, TaskNode] | None:
        async with self._session_factory() as session:
            node_result = await session.execute(
                select(TaskNodeORM).where(TaskNodeORM.id == task_node_id)
            )
            node_row = node_result.scalar_one_or_none()
            if node_row is None:
                return None
            graph_result = await session.execute(
                select(TaskGraphORM)
                .where(TaskGraphORM.id == node_row.task_graph_id)
                .options(selectinload(TaskGraphORM.nodes))
            )
            graph_row = graph_result.scalar_one()
            return _graph_to_domain(graph_row), _node_to_domain(node_row)

    async def insert(self, graph: TaskGraph, *, outbox_event: OutboxEvent) -> TaskGraph:
        async with self._session_factory() as session, session.begin():
            session.add(
                TaskGraphORM(
                    id=graph.id,
                    root_objective=graph.root_objective,
                    critical_path=[str(node_id) for node_id in graph.critical_path],
                    approved_at=graph.approved_at,
                )
            )
            for node in graph.nodes:
                session.add(_node_orm(node, graph.id))
            session.add(_outbox_orm(outbox_event))
        return graph

    async def append_nodes(
        self,
        task_graph_id: UUID,
        new_nodes: list[TaskNode],
        *,
        outbox_event_builder: Callable[[TaskGraph], OutboxEvent],
    ) -> TaskGraph:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                select(TaskGraphORM)
                .where(TaskGraphORM.id == task_graph_id)
                .options(selectinload(TaskGraphORM.nodes))
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise TaskGraphNotFoundError(f"task_graph {task_graph_id} does not exist")

            for node in new_nodes:
                session.add(_node_orm(node, task_graph_id))

            all_nodes = [_node_to_domain(existing) for existing in row.nodes] + new_nodes
            row.critical_path = [str(node_id) for node_id in compute_critical_path(all_nodes)]

            await session.flush()
            await session.refresh(row, attribute_names=["nodes"])
            updated_graph = _graph_to_domain(row)

            session.add(_outbox_orm(outbox_event_builder(updated_graph)))
            return updated_graph

    async def set_approved_at(self, task_graph_id: UUID, *, approved_at: datetime) -> TaskGraph:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                select(TaskGraphORM)
                .where(TaskGraphORM.id == task_graph_id)
                .options(selectinload(TaskGraphORM.nodes))
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise TaskGraphNotFoundError(f"task_graph {task_graph_id} does not exist")
            row.approved_at = approved_at
            await session.flush()
            return _graph_to_domain(row)

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(OutboxEventORM)
                .where(OutboxEventORM.dispatched_at.is_(None))
                .order_by(OutboxEventORM.created_at)
                .limit(limit)
            )
            return [
                OutboxRow(
                    id=row.id,
                    subject=row.subject,
                    payload=dict(row.payload),
                    correlation_id=row.correlation_id,
                    causation_id=row.causation_id,
                    created_at=row.created_at,
                )
                for row in result.scalars().all()
            ]

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(OutboxEventORM)
                .where(OutboxEventORM.id == outbox_id)
                .values(dispatched_at=datetime.now().astimezone())
            )
