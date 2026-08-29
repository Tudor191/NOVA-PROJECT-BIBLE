"""`PostgresKernelRepository` -- implements `domain.ports.KernelRepository`
against SQLAlchemy async, per the schema in
docs/design/phase-3/08-tdd-3e-agent-os.md §4.

`insert()` translates an `id` primary-key violation
(`sqlalchemy.exc.IntegrityError`) into `AgentInstanceAlreadyExistsError` --
the natural-key idempotency guard convention every other Phase 3 repository
already establishes (`action-engine`'s `ActionAlreadyExistsError`,
`capability-engine`'s `CapabilityAlreadyExistsError`).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_agent_os_kernel.domain.models import AgentInstance
from nova_agent_os_kernel.domain.ports import AgentInstanceAlreadyExistsError
from nova_agent_os_kernel.repository.models import AgentInstanceORM

__all__ = ["PostgresKernelRepository"]


def _to_domain(row: AgentInstanceORM) -> AgentInstance:
    return AgentInstance(
        id=row.id,
        agent_package_id=row.agent_package_id,
        category=row.category,
        execution_backend=row.execution_backend,
        status=row.status,
        assigned_task_node_id=row.assigned_task_node_id,
        supervisor_id=row.supervisor_id,
        started_at=row.started_at,
        health_status=row.health_status,
    )


class PostgresKernelRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def find_by_id(self, instance_id: UUID) -> AgentInstance | None:
        async with self._session_factory() as session:
            row = await session.get(AgentInstanceORM, instance_id)
            return _to_domain(row) if row is not None else None

    async def insert(self, instance: AgentInstance) -> AgentInstance:
        row = AgentInstanceORM(
            id=instance.id,
            agent_package_id=instance.agent_package_id,
            category=instance.category,
            execution_backend=instance.execution_backend,
            status=instance.status,
            assigned_task_node_id=instance.assigned_task_node_id,
            supervisor_id=instance.supervisor_id,
            started_at=instance.started_at,
            health_status=instance.health_status,
        )
        async with self._session_factory() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise AgentInstanceAlreadyExistsError(
                    f"agent_instance {instance.id} already exists"
                ) from exc
        return instance

    async def list_by_status(self, status: str) -> list[AgentInstance]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AgentInstanceORM).where(AgentInstanceORM.status == status)
            )
            return [_to_domain(row) for row in result.scalars().all()]

    async def update_status(
        self, instance_id: UUID, *, status: str, health_status: str | None = None
    ) -> None:
        async with self._session_factory() as session:
            row = await session.get(AgentInstanceORM, instance_id)
            if row is None:
                return
            row.status = status
            if health_status is not None:
                row.health_status = health_status
            await session.commit()
