"""Protocols this package depends on -- implements nothing itself
(docs/design/phase-3/06-tdd-3c-capability-engine.md §5). `domain/` may only
import this module, `nova_contracts`, and other `domain/` modules -- never
FastAPI, SQLAlchemy, or `nova_eventbus_sdk` directly (docs/architecture/
03-backend-architecture.md §1), and (per ADR-020) no LLM/AI provider SDK --
capability-engine has zero model dependency, confirmed in the TDD's own §H.

`CommunicationPort` mirrors `digital-twin-engine`'s own `domain/ports.py`
exactly -- the same Fork-D-precedent structural shape TDD 3C §5 cites for
the Permission Review pipeline stage's disclosure call.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from nova_contracts import Capability, EventEnvelope
from pydantic import BaseModel

__all__ = [
    "AdapterPort",
    "CapabilityAlreadyExistsError",
    "CapabilityRepository",
    "CommunicationPort",
    "EventPublisher",
]


class CapabilityAlreadyExistsError(Exception):
    """Raised by a `CapabilityRepository.insert()` implementation when a
    `(name, version)` uniqueness violation occurs -- Fork 3C-4's
    concurrent-installation-race safety net (TDD 3C §4). The caller
    (`domain/pipeline.py`) treats this identically to a pre-existing-row
    check found via `find_by_name_version`, never a hard failure."""


@runtime_checkable
class AdapterPort(Protocol):
    """One of the four built-in execution adapters (`git`/`filesystem`/
    `terminal`/`http`, TDD 3C §3) -- `capability-engine`'s own process is
    the real executor (Fork 3C-1/3D-1's resolution), never `action-engine`
    or any other caller. Concrete implementations (real subprocess/
    filesystem/httpx I/O) live in `adapters/`, never in `domain/` itself
    (docs/architecture/03-backend-architecture.md §1's framework-free
    boundary) -- `domain/pipeline.py`'s Sandbox Testing stage and the
    `capability.invoke.*` RPC handler both depend only on this Protocol.

    Takes `required_resources` directly (not a full `Capability`) --
    install-time Sandbox Testing runs before a capability is registered, so
    no `Capability.id` exists yet; the adapter only ever needs its own
    declared scope, never the full entity.

    Raises `domain.sandbox.SandboxViolation` for any scope-escape attempt --
    never returns a value pretending the operation partially succeeded."""

    name: str

    async def invoke(
        self, operation: str, parameters: dict, *, required_resources: list[str]
    ) -> dict: ...


@runtime_checkable
class EventPublisher(Protocol):
    """The subset of `BoundEventBus` `clients/communication_client.py`
    needs -- declared here, not imported from `nova_eventbus_sdk`, so
    `domain/` never depends on the event-bus package directly. Matches
    `BoundEventBus.request()`'s signature exactly (same pattern as
    `planning-engine`'s own `domain/ports.py`)."""

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
    """TDD 3C §5: the installation pipeline's "Permission Review" stage
    surfaces to a human via the existing `communication.intent.deliver.request`
    gate (same precedent as Fork D/TDD 3D) -- not a new mechanism.
    Implemented by `clients/communication_client.py`.

    `TimeoutError` propagates uncaught from both methods, mirroring every
    other client's documented convention in this project -- the Permission
    Review pipeline stage is the one place that catches it and treats a
    timeout the same as "disclosure not delivered right now," never a
    pipeline failure (the disclosure is best-effort, not a blocking
    approval gate -- unlike `action-engine`'s Critical-risk approval loop,
    nothing in TDD 3C says installation blocks pending a reply)."""

    async def get_connected_session(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> UUID | None: ...

    async def deliver_intent(
        self, *, session_id: UUID, content: str, correlation_id: UUID | None = None
    ) -> bool: ...


@runtime_checkable
class CapabilityRepository(Protocol):
    """Persistence port for the `capability` Postgres schema (TDD 3C §6).
    `find_by_name_version` is the natural-key lookup Fork 3C-4's idempotent
    install behavior is built on."""

    async def find_by_name_version(self, *, name: str, version: str) -> Capability | None: ...

    async def find_by_id(self, capability_id: UUID) -> Capability | None: ...

    async def find_by_name(self, name: str) -> Capability | None:
        """Resolve a capability by its stable `name` alone, without a
        specific `version` -- added for `capability.resolve.request`'s
        additive `name` field (Phase 3D research pass, approved:
        `docs/design/phase-3/13-3d-action-engine-research.md` §5.1).

        Phase 3's four built-in capabilities each install exactly one
        version, so `name` alone is unambiguous today. If more than one
        version of the same `name` is ever registered, the most recently
        installed one wins -- a small, defensible default consistent with
        ordinary "latest version" conventions, not a competing
        architecture requiring the user's judgment (there is exactly one
        reasonable reading of "resolve by name" when multiple versions
        exist, and Phase 3's own capability set never exercises it)."""
        ...

    async def list_all(self) -> list[Capability]: ...

    async def insert(self, capability: Capability) -> Capability:
        """Inserts a new row. A `(name, version)` uniqueness violation (a
        concurrent-install race, Fork 3C-4) must be caught by the caller and
        treated as the same idempotent no-op as a pre-existing-row check,
        never surfaced as a hard failure."""
        ...

    async def delete(self, capability_id: UUID) -> bool:
        """Returns `True` if a row was deleted, `False` if `capability_id`
        did not exist."""
        ...

    async def record_installation_event(
        self,
        *,
        capability_id: UUID | None,
        name: str,
        version: str,
        stage: str,
        outcome: str,
        detail: str | None = None,
    ) -> None:
        """Append-only log of pipeline-stage transitions (TDD 3C §6,
        `ConversationDecisionTraceORM`'s precedent). `capability_id` is
        `None` until the `Registration` stage actually mints one."""
        ...
