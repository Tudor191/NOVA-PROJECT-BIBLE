"""Protocols this package depends on -- implements nothing itself
(docs/design/phase-3/08-tdd-3e-agent-os.md §5). `domain/` may only import
this module, `nova_contracts`, `nova_agent_sdk`, and other `domain/`
modules -- never FastAPI, SQLAlchemy, or `nova_eventbus_sdk` directly
(docs/architecture/03-backend-architecture.md §1).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from nova_contracts import EventEnvelope
from pydantic import BaseModel

from nova_agent_os_registry.domain.models import AgentPackage

__all__ = [
    "AgentPackageAlreadyExistsError",
    "CommunicationPort",
    "EventPublisher",
    "RegistryRepository",
]


class AgentPackageAlreadyExistsError(Exception):
    """Raised by a `RegistryRepository.insert()` implementation when
    `(category, version)` already exists -- the natural-key idempotency
    guard every other Phase 3 repository already establishes
    (`capability-engine`'s `CapabilityAlreadyExistsError`/Fork 3C-4,
    `action-engine`'s `ActionAlreadyExistsError`, `agent-os/kernel`'s own
    `AgentInstanceAlreadyExistsError`)."""


@runtime_checkable
class EventPublisher(Protocol):
    """The subset of `BoundEventBus` `clients/communication_client.py`
    needs -- declared here, not imported from `nova_eventbus_sdk`, so
    `domain/` never depends on the event-bus package directly. Matches
    `BoundEventBus.request()`'s signature exactly (same pattern as every
    other engine's own `domain/ports.py`)."""

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
class CommunicationPort(Protocol):
    """TDD 3E §5's resolved note: the local diff-and-display permission
    review "surfaces to the user" -- mirrors `capability-engine`'s own
    `CommunicationPort`/Fork D precedent field-for-field (TDD 3C §10, the
    precedent this TDD explicitly cites). Best-effort, non-blocking: a
    missing/unreachable session never halts the install pipeline."""

    async def get_connected_session(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> UUID | None: ...

    async def deliver_intent(
        self, *, session_id: UUID, content: str, correlation_id: UUID | None = None
    ) -> bool: ...


@runtime_checkable
class RegistryRepository(Protocol):
    """Persistence port for the `agent_os` Postgres schema's
    `agent_package` table (TDD 3E §5). Natural key: `(category, version)`
    -- the approved Fork 3E-2 resolution's own concrete ORM
    (`14-3e-agent-os-research.md` §4), correcting Milestone 3's own
    `(id, version)` interpretation; see
    `docs/design/phase-3/15-3e-supervisor-reconciliation.md` §A."""

    async def find_by_category_version(
        self, category: str, version: str
    ) -> AgentPackage | None: ...

    async def find_latest_by_category(self, category: str) -> AgentPackage | None:
        """The most recently `installed_at` row for `category`, across
        every installed version -- what the Permission Review stage diffs
        a new install's `required_permissions` against (TDD 3E §5)."""
        ...

    async def list_by_category(self, category: str) -> list[AgentPackage]: ...

    async def insert(self, package: AgentPackage) -> AgentPackage:
        """Inserts a new row. A `(category, version)` collision must be
        caught by the caller and raises `AgentPackageAlreadyExistsError`,
        mirroring every other Phase 3 repository's own idempotency-guard
        translation."""
        ...

    async def update_health_status(self, package_id: UUID, *, health_status: str) -> None:
        """Keyed on the surrogate `id` alone -- once a row exists, its
        UUID is a sufficient, unique lookup key (mirrors
        `agent-os/kernel`'s own `update_status(instance_id: UUID, ...)`)."""
        ...
