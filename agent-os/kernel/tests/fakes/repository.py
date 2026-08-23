"""In-memory `KernelRepository` fake -- mirrors `capability-engine`'s own
`tests/fakes/repository.py` convention: lets `create_app()` be exercised in
`test_health.py` without a real Postgres connection, and lets domain-layer
tests exercise `reconcile_running_instances` without SQLAlchemy at all."""

from __future__ import annotations

from uuid import UUID

from nova_agent_os_kernel.domain.models import AgentInstance
from nova_agent_os_kernel.domain.ports import AgentInstanceAlreadyExistsError

__all__ = ["FakeKernelRepository"]


class FakeKernelRepository:
    def __init__(self) -> None:
        self._rows: dict[UUID, AgentInstance] = {}

    async def find_by_id(self, instance_id: UUID) -> AgentInstance | None:
        return self._rows.get(instance_id)

    async def insert(self, instance: AgentInstance) -> AgentInstance:
        if instance.id in self._rows:
            raise AgentInstanceAlreadyExistsError(f"agent_instance {instance.id} already exists")
        self._rows[instance.id] = instance
        return instance

    async def list_by_status(self, status: str) -> list[AgentInstance]:
        return [row for row in self._rows.values() if row.status == status]

    async def update_status(self, instance_id: UUID, *, status: str) -> None:
        row = self._rows.get(instance_id)
        if row is None:
            return
        self._rows[instance_id] = row.model_copy(update={"status": status})
