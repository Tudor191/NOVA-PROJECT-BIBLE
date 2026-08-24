"""Protocols this package depends on -- implements nothing itself
(docs/design/phase-3/08-tdd-3e-agent-os.md §4). `domain/` may only import
this module, `nova_contracts`, `nova_agent_sdk`, and other `domain/`
modules -- never FastAPI, SQLAlchemy, or `nova_eventbus_sdk` directly
(docs/architecture/03-backend-architecture.md §1).

`RegistryPort`/`SupervisorPort`/`AgentExecutionBackend` are disclosed
additions: TDD 3E §4 names the Kernel Scheduler's four dispatch steps
("query Registry for healthy candidates," restart via the owning
Supervisor's strategy, "select an execution backend," "dispatch") but
defines no Protocol for any of them -- this milestone's own
`SUBSCRIBABLE_SUBJECTS`/`events/subscribed.py` disclosure already flagged
the Scheduler itself as "not yet built." These three close that gap,
proposed here, not extracted, flagged for Gate Review -- the same
discipline already applied throughout Phase 3E.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from nova_agent_sdk import AgentContext, AgentHealth, AgentMessage
from nova_contracts import AgentPackageSnapshot, EventEnvelope
from pydantic import BaseModel

from nova_agent_os_kernel.domain.models import AgentInstance, AgentInstanceHandle

__all__ = [
    "AgentExecutionBackend",
    "AgentInstanceAlreadyExistsError",
    "EventPublisher",
    "KernelRepository",
    "RegistryPort",
    "SupervisorPort",
]


class AgentInstanceAlreadyExistsError(Exception):
    """Raised by a `KernelRepository.insert()` implementation when `id`
    already exists -- the natural-key idempotency guard every other Phase 3
    engine's repository already establishes (`action-engine`'s
    `ActionAlreadyExistsError`, `capability-engine`'s
    `CapabilityAlreadyExistsError`, Fork 3C-4's precedent)."""


@runtime_checkable
class EventPublisher(Protocol):
    """The subset of `BoundEventBus` this component needs -- `publish()`
    for `agent_os.task.completed`, `request()` for the two new outbound RPCs
    (`RegistryPort`/`SupervisorPort`'s own client adapters). Declared here,
    not imported from `nova_eventbus_sdk`, so `domain/` never depends on the
    event-bus package directly (same pattern as every other engine's own
    `domain/ports.py`)."""

    async def publish(self, envelope: EventEnvelope) -> None: ...

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope: ...


@runtime_checkable
class KernelRepository(Protocol):
    """Persistence port for the `agent_os` Postgres schema's
    `agent_instance` table (TDD 3E §4)."""

    async def find_by_id(self, instance_id: UUID) -> AgentInstance | None: ...

    async def insert(self, instance: AgentInstance) -> AgentInstance:
        """Inserts a new row. An `id` collision must be caught by the
        caller and raises `AgentInstanceAlreadyExistsError`, mirroring
        every other Phase 3 repository's own idempotency-guard
        translation."""
        ...

    async def list_by_status(self, status: str) -> list[AgentInstance]: ...

    async def update_status(self, instance_id: UUID, *, status: str) -> None: ...


@runtime_checkable
class RegistryPort(Protocol):
    """TDD 3E §4 step 1: "query Registry for healthy candidates in the
    required category." Wraps `agent_os.registry.find_healthy_package.request`
    (disclosed addition, `nova_contracts.events.agent_os`)."""

    async def find_healthy_package(
        self, *, category: str, correlation_id: UUID | None = None
    ) -> AgentPackageSnapshot | None: ...


@runtime_checkable
class SupervisorPort(Protocol):
    """TDD 3E §12's failure table: "owning Supervisor applies its
    configured restart strategy." Wraps
    `agent_os.supervisor.restart_plan.request` (disclosed addition,
    `nova_contracts.events.agent_os`)."""

    async def plan_restart(
        self,
        *,
        failed_instance_id: UUID,
        category: str,
        siblings: list[AgentInstance],
        correlation_id: UUID | None = None,
    ) -> list[UUID]: ...


@runtime_checkable
class AgentExecutionBackend(Protocol):
    """Doc 12 §8, verbatim four-method Protocol -- "one interface, four
    implementations... scaling from 10 agents to 10,000... is a scheduling
    and infrastructure decision, never a rewrite." Phase 3 implements only
    `inprocess` (`domain/execution_backend.py::InprocessExecutionBackend`);
    declaring the full Protocol shape now, not a redesign later, is the
    explicit point of doc 12 §8's own "already designed for" framing."""

    async def spawn(
        self, agent: AgentPackageSnapshot, context: AgentContext
    ) -> AgentInstanceHandle: ...

    async def send(self, handle: AgentInstanceHandle, message: AgentMessage) -> None: ...

    async def health(self, handle: AgentInstanceHandle) -> AgentHealth: ...

    async def terminate(self, handle: AgentInstanceHandle) -> None: ...
