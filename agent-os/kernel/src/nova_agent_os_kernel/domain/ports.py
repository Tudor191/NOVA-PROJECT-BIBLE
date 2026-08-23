"""Protocols this package depends on -- implements nothing itself
(docs/design/phase-3/08-tdd-3e-agent-os.md §4). `domain/` may only import
this module, `nova_contracts`, and other `domain/` modules -- never
FastAPI, SQLAlchemy, or `nova_eventbus_sdk` directly
(docs/architecture/03-backend-architecture.md §1).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from nova_contracts import EventEnvelope

from nova_agent_os_kernel.domain.models import AgentInstance

__all__ = ["AgentInstanceAlreadyExistsError", "EventPublisher", "KernelRepository"]


class AgentInstanceAlreadyExistsError(Exception):
    """Raised by a `KernelRepository.insert()` implementation when `id`
    already exists -- the natural-key idempotency guard every other Phase 3
    engine's repository already establishes (`action-engine`'s
    `ActionAlreadyExistsError`, `capability-engine`'s
    `CapabilityAlreadyExistsError`, Fork 3C-4's precedent)."""


@runtime_checkable
class EventPublisher(Protocol):
    """The subset of `BoundEventBus` this component needs to publish
    `agent_os.task.completed` -- declared here, not imported from
    `nova_eventbus_sdk`, so `domain/` never depends on the event-bus
    package directly. Matches `BoundEventBus.publish()`'s signature
    exactly (same pattern as every other engine's own `domain/ports.py`)."""

    async def publish(self, envelope: EventEnvelope) -> None: ...


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
