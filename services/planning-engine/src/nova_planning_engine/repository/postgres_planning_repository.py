"""`PostgresPlanningRepository` -- implements `domain.ports.PlanningRepository`
against SQLAlchemy async, per the schema in
docs/design/phase-3/05-tdd-3b-planning-engine.md §4.

Every write (`insert`, `append_nodes`, `apply_transitions`,
`set_approved_at`) writes its accompanying `outbox_event` row in the same
transaction (TDD 3B §4's transactional-outbox requirement) -- mirrors
`memory-engine`'s own `create_long_term`/`OutboxEvent` pattern exactly,
applied to a multi-row (`task_graph` + N `task_node`) write instead of a
single row.

Every write that enqueues `planning.task_graph.created` additionally
performs the ready-to-running hand-off, in the exact order
`domain/ports.py::HAND_OFF_ORDERING` specifies: build the payload from the
pre-hand-off state, write the outbox row, *then* flip. `_hand_off` below is
the single implementation of step 4, called from both such paths so the
ordering cannot drift between them.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from nova_planning_engine.domain.models import (
    Estimate,
    RiskLevel,
    TaskGraph,
    TaskNode,
    TaskNodeStatus,
)
from nova_planning_engine.domain.ports import (
    OutboxEvent,
    OutboxRow,
    TaskGraphNotFoundError,
    TaskNodeNotFoundError,
)
from nova_planning_engine.domain.task_graph import admit, compute_critical_path
from nova_planning_engine.repository.models import OutboxEventORM, TaskGraphORM, TaskNodeORM

__all__ = ["PostgresPlanningRepository"]


def _hand_off(node_rows: list[TaskNodeORM]) -> set[UUID]:
    """`HAND_OFF_ORDERING` step 4: flip every still-`"ready"` row to
    `"running"` and report which ids moved. Mutates the ORM rows in the
    caller's open transaction (no `flush`/`commit` here) so the flip lands
    atomically with the outbox row the caller already added -- the whole
    point of the ordering. Must only ever be called *after* the payload has
    been built."""
    handed_off: set[UUID] = set()
    for node_row in node_rows:
        if node_row.status == "ready":
            node_row.status = "running"
            handed_off.add(node_row.id)
    return handed_off


def _domain_nodes(graph_row: TaskGraphORM) -> list[TaskNode]:
    return [_node_to_domain(node_row) for node_row in graph_row.nodes]


def _node_to_domain(row: TaskNodeORM) -> TaskNode:
    return TaskNode(
        id=row.id,
        objective=row.objective,
        depends_on=[UUID(dep_id) for dep_id in row.depends_on],
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
        depends_on=[str(dep_id) for dep_id in node.depends_on],
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

    async def insert(
        self, graph: TaskGraph, *, outbox_event_builder: Callable[[TaskGraph], OutboxEvent]
    ) -> TaskGraph:
        async with self._session_factory() as session, session.begin():
            session.add(
                TaskGraphORM(
                    id=graph.id,
                    root_objective=graph.root_objective,
                    critical_path=[str(node_id) for node_id in graph.critical_path],
                    approved_at=graph.approved_at,
                )
            )
            node_rows = [_node_orm(node, graph.id) for node in graph.nodes]
            for node_row in node_rows:
                session.add(node_row)

            # `HAND_OFF_ORDERING` steps 2-4: payload from the pre-hand-off
            # state, then flip. `graph` is already that state.
            session.add(_outbox_orm(outbox_event_builder(graph)))
            handed_off = _hand_off(node_rows)

        return graph.model_copy(
            update={
                "nodes": [
                    node.model_copy(update={"status": "running"})
                    if node.id in handed_off
                    else node
                    for node in graph.nodes
                ]
            }
        )

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

            # `HAND_OFF_ORDERING` step 1: admit the nodes just appended.
            # Without this a `planning.decompose.request` mutation would
            # re-create the exact defect graph creation had -- new nodes
            # stuck `"pending"` forever. `admit` only ever touches
            # `"pending"` nodes, so nothing already in flight is disturbed.
            admitted = {node.id: node.status for node in admit(_domain_nodes(row))}
            for node_row in row.nodes:
                node_row.status = admitted[node_row.id]

            published_graph = _graph_to_domain(row)
            session.add(_outbox_orm(outbox_event_builder(published_graph)))
            handed_off = _hand_off(list(row.nodes))

        return published_graph.model_copy(
            update={
                "nodes": [
                    node.model_copy(update={"status": "running"})
                    if node.id in handed_off
                    else node
                    for node in published_graph.nodes
                ]
            }
        )

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

    async def apply_transitions(
        self,
        task_graph_id: UUID,
        transitions: list[tuple[UUID, TaskNodeStatus]],
        *,
        outbox_event_builder: Callable[[TaskGraph], OutboxEvent],
    ) -> TaskGraph:
        async with self._session_factory() as session, session.begin():
            graph_result = await session.execute(
                select(TaskGraphORM)
                .where(TaskGraphORM.id == task_graph_id)
                .options(selectinload(TaskGraphORM.nodes))
            )
            graph_row = graph_result.scalar_one_or_none()
            if graph_row is None:
                raise TaskGraphNotFoundError(f"task_graph {task_graph_id} does not exist")

            rows_by_id = {node_row.id: node_row for node_row in graph_row.nodes}
            for node_id, status in transitions:
                node_row = rows_by_id.get(node_id)
                if node_row is None:
                    raise TaskNodeNotFoundError(
                        f"task_node {node_id} is not part of task_graph {task_graph_id}"
                    )
                node_row.status = status

            await session.flush()
            await session.refresh(graph_row, attribute_names=["nodes"])

            # `HAND_OFF_ORDERING` steps 2-4: the payload is built from the
            # post-transition, pre-hand-off state (so newly promoted nodes
            # appear as `"ready"` for the Scheduler), and only then are
            # those same nodes flipped to `"running"`.
            published_graph = _graph_to_domain(graph_row)
            session.add(_outbox_orm(outbox_event_builder(published_graph)))
            handed_off = _hand_off(list(graph_row.nodes))

        return published_graph.model_copy(
            update={
                "nodes": [
                    node.model_copy(update={"status": "running"})
                    if node.id in handed_off
                    else node
                    for node in published_graph.nodes
                ]
            }
        )

    async def list_all(self, *, limit: int = 1000) -> list[TaskGraph]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(TaskGraphORM).options(selectinload(TaskGraphORM.nodes)).limit(limit)
            )
            return [_graph_to_domain(row) for row in result.scalars().all()]

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
