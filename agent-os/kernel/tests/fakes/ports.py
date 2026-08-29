"""In-memory `RegistryPort`/`SupervisorPort`/`AgentExecutionBackend` fakes --
lets `domain/scheduler.py` unit tests exercise the full dispatch loop
without any real Event Bus/Registry/Supervisors/filesystem-import
involved, the same "domain tested against a fake Port" discipline every
other Phase 3 component's own unit tests already establish."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from nova_agent_os_kernel.domain.models import AgentInstance, AgentInstanceHandle
from nova_agent_sdk import AgentContext, AgentHealth, AgentMessage
from nova_contracts import AgentPackageSnapshot, AgentResult

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
    def __init__(
        self,
        *,
        restart_instance_ids: list[UUID] | None = None,
        peer_validation: Literal["approved", "rejected", "timed_out", "not_required"] = (
            "not_required"
        ),
    ) -> None:
        self._restart_instance_ids = (
            restart_instance_ids if restart_instance_ids is not None else []
        )
        self._peer_validation = peer_validation
        self.calls: list[dict[str, object]] = []
        self.peer_review_calls: list[dict[str, object]] = []

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

    async def record_peer_review(
        self,
        *,
        primary_result: AgentResult,
        reviewer_category: str,
        reviewer_result: AgentResult | None,
        reviewer_available: bool,
        correlation_id: UUID | None = None,
    ) -> Literal["approved", "rejected", "timed_out", "not_required"]:
        self.peer_review_calls.append(
            {
                "primary_result": primary_result,
                "reviewer_category": reviewer_category,
                "reviewer_result": reviewer_result,
                "reviewer_available": reviewer_available,
            }
        )
        return self._peer_validation


class FakeAgentExecutionBackend:
    """`handles` is consumed in order -- each `spawn()` call pops the next
    queued handle, so a test can script "first attempt fails, retry
    succeeds" precisely. `review_replies` is consumed the same way by
    `spawn_and_review()`.

    `next_instance_id()` returns the id of the **next queued handle**,
    mirroring the real `InprocessExecutionBackend`'s own contract that the
    backend mints the id `spawn()` will then use. That is what lets the
    Scheduler persist a `"running"` `agent_instance` row before awaiting
    `spawn()` and still have the row, the handle, and the published
    `agent_os.task.completed` all carry one id."""

    def __init__(
        self,
        *,
        handles: list[AgentInstanceHandle],
        review_replies: list[AgentMessage | None] | None = None,
    ) -> None:
        self._handles = list(handles)
        self._review_replies = list(review_replies) if review_replies is not None else []
        self.spawn_calls: list[tuple[AgentPackageSnapshot, AgentContext]] = []
        self.spawn_and_review_calls: list[tuple[AgentPackageSnapshot, AgentMessage]] = []

    def next_instance_id(self) -> UUID:
        return self._handles[0].instance_id

    async def spawn(
        self,
        agent: AgentPackageSnapshot,
        context: AgentContext,
        *,
        instance_id: UUID | None = None,
    ) -> AgentInstanceHandle:
        self.spawn_calls.append((agent, context))
        handle = self._handles.pop(0)
        if instance_id is not None and instance_id != handle.instance_id:
            handle = handle.model_copy(update={"instance_id": instance_id})
        return handle

    async def spawn_and_review(
        self, agent: AgentPackageSnapshot, message: AgentMessage
    ) -> AgentMessage | None:
        self.spawn_and_review_calls.append((agent, message))
        return self._review_replies.pop(0)

    async def send(self, handle: AgentInstanceHandle, message: AgentMessage) -> None:
        raise NotImplementedError

    async def health(self, handle: AgentInstanceHandle) -> AgentHealth:
        raise NotImplementedError

    async def terminate(self, handle: AgentInstanceHandle) -> None:
        pass
