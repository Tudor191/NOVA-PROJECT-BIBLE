"""In-memory `RegistryPort`/`SupervisorPort`/`AgentExecutionBackend` fakes --
lets `domain/scheduler.py` unit tests exercise the full dispatch loop
without any real Event Bus/Registry/Supervisors/filesystem-import
involved, the same "domain tested against a fake Port" discipline every
other Phase 3 component's own unit tests already establish."""

from __future__ import annotations

from uuid import UUID

from nova_agent_os_kernel.domain.models import AgentInstance, AgentInstanceHandle
from nova_agent_sdk import AgentContext, AgentHealth, AgentMessage
from nova_contracts import AgentPackageSnapshot

__all__ = ["FakeAgentExecutionBackend", "FakeRegistryPort", "FakeSupervisorPort"]


class FakeRegistryPort:
    def __init__(self, *, package: AgentPackageSnapshot | None) -> None:
        self._package = package
        self.requested_categories: list[str] = []

    async def find_healthy_package(
        self, *, category: str, correlation_id: UUID | None = None
    ) -> AgentPackageSnapshot | None:
        self.requested_categories.append(category)
        return self._package


class FakeSupervisorPort:
    def __init__(self, *, restart_instance_ids: list[UUID] | None = None) -> None:
        self._restart_instance_ids = (
            restart_instance_ids if restart_instance_ids is not None else []
        )
        self.calls: list[dict[str, object]] = []

    async def plan_restart(
        self,
        *,
        failed_instance_id: UUID,
        category: str,
        siblings: list[AgentInstance],
        correlation_id: UUID | None = None,
    ) -> list[UUID]:
        self.calls.append(
            {"failed_instance_id": failed_instance_id, "category": category, "siblings": siblings}
        )
        return self._restart_instance_ids


class FakeAgentExecutionBackend:
    """`handles` is consumed in order -- each `spawn()` call pops the next
    queued handle, so a test can script "first attempt fails, retry
    succeeds" precisely."""

    def __init__(self, *, handles: list[AgentInstanceHandle]) -> None:
        self._handles = list(handles)
        self.spawn_calls: list[tuple[AgentPackageSnapshot, AgentContext]] = []

    async def spawn(
        self, agent: AgentPackageSnapshot, context: AgentContext
    ) -> AgentInstanceHandle:
        self.spawn_calls.append((agent, context))
        return self._handles.pop(0)

    async def send(self, handle: AgentInstanceHandle, message: AgentMessage) -> None:
        raise NotImplementedError

    async def health(self, handle: AgentInstanceHandle) -> AgentHealth:
        raise NotImplementedError

    async def terminate(self, handle: AgentInstanceHandle) -> None:
        pass
