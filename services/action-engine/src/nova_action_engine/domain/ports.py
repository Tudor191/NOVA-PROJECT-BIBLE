"""Protocols this package depends on -- implements nothing itself
(docs/design/phase-3/07-tdd-3d-action-engine.md §2, §4, §7). `domain/` may
only import this module, `nova_contracts`, and other `domain/` modules --
never FastAPI, SQLAlchemy, or `nova_eventbus_sdk` directly
(docs/architecture/03-backend-architecture.md §1), and (per ADR-020) no
LLM/AI provider SDK.

`CapabilityPort`, `CommunicationPort`, `IdentityPort` are each defined
here, independently, per the `GoalsPort`/`DigitalTwinPort` per-consumer
convention already confirmed real in shipped code (`reasoning-engine`,
`executive-cognition-engine`, `communication-engine` each define their own
copy of an analogous Protocol rather than importing a shared one) --
Fork 3C-1/3D-1's resolution names this exact pattern for `CapabilityPort`.
`CommunicationPort` mirrors `capability-engine`'s own `domain/ports.py`
(Fork D's precedent) field-for-field.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from nova_contracts import Action, Capability, EventEnvelope
from pydantic import BaseModel

from nova_action_engine.domain.models import IdentityConfidencePolicy, PendingApproval

__all__ = [
    "ActionAlreadyExistsError",
    "ActionRepository",
    "CapabilityInvokeOutcome",
    "CapabilityPort",
    "CommunicationPort",
    "EventPublisher",
    "IdentityPort",
]

CapabilityInvokeOutcome = Literal["success", "failure", "sandbox_violation"]


class ActionAlreadyExistsError(Exception):
    """Raised by an `ActionRepository.insert()` implementation when
    `action_id` already exists -- the natural-key idempotency guard
    approved for `action.execute` (§5.3,
    `docs/design/phase-3/13-3d-action-engine-research.md`), mirroring
    `capability-engine`'s own `CapabilityAlreadyExistsError`/Fork 3C-4
    precedent exactly. The caller (`domain/pipeline.py`) treats this
    identically to finding an existing terminal-state row via
    `find_by_id`, never a hard failure."""


@runtime_checkable
class EventPublisher(Protocol):
    """The subset of `BoundEventBus` the clients in `clients/` need --
    declared here, not imported from `nova_eventbus_sdk`, so `domain/`
    never depends on the event-bus package directly. Matches
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

    async def publish(self, envelope: EventEnvelope) -> None: ...


@runtime_checkable
class CapabilityPort(Protocol):
    """TDD 3D §2 (Fork 3C-1/3D-1's resolution, RESOLVED: Option A) --
    `action-engine` defines this Protocol; `capability-engine`'s own
    process is the sole executor of every adapter operation.
    `resolve()` targets the already-shipped `capability.resolve.request`
    RPC's additive by-name path (approved, §5.1,
    `13-3d-action-engine-research.md`). `invoke()` targets the unmodified
    `capability.invoke.request` RPC -- also reused for Fork 3C-3's
    rollback mechanism (a read-before-write `invoke()` call against a
    non-destructive operation, before a destructive one)."""

    async def resolve(
        self, *, name: str, correlation_id: UUID | None = None
    ) -> Capability | None: ...

    async def invoke(
        self,
        *,
        capability_id: UUID,
        operation: str,
        parameters: dict,
        correlation_id: UUID | None = None,
    ) -> tuple[CapabilityInvokeOutcome, dict | None, str | None]:
        """Returns `(outcome, result, error)` -- mirrors
        `CapabilityInvokeReplyPayload`'s own three fields directly rather
        than returning the payload class itself, so `domain/pipeline.py`
        never needs to import a `nova_contracts` payload type by name."""
        ...


@runtime_checkable
class CommunicationPort(Protocol):
    """TDD 3D §4 point 3: the approval loop's human-notification step
    calls the existing, unmodified `communication.intent.deliver.request`
    gate via this port -- `action-engine` never publishes
    `communication.intent.*` directly (ADR-005). Mirrors
    `capability-engine`'s own `CommunicationPort`/Fork D precedent
    field-for-field. `TimeoutError` propagates uncaught -- the approval
    loop (`domain/pipeline.py`) is the one place that catches it and
    treats a timeout the same as a denial (TDD 3D §4's timeout policy,
    §10)."""

    async def get_connected_session(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> UUID | None: ...

    async def deliver_intent(
        self, *, session_id: UUID, content: str, correlation_id: UUID | None = None
    ) -> bool: ...


@runtime_checkable
class IdentityPort(Protocol):
    """TDD 3D §7, ADR-032 -- consumes `world-model-engine`'s existing
    `present_identities` field via `world_model.context.request`. Per
    ADR-032 point 3, `action-engine` never performs identity recognition
    itself -- this only reads `perception-engine`'s (via World Model's)
    already-scored signal. Returns `None` on timeout or when no matching
    identity is present -- `domain/pipeline.py`'s ADR-032 gate treats a
    `None` confidence as zero (fail-closed, TDD 3D §10), never as "no
    check performed"."""

    async def get_confidence(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> float | None: ...


@runtime_checkable
class ActionRepository(Protocol):
    """Persistence port for the `action` Postgres schema (TDD 3D §8):
    `action`, `pending_approval`, `action_execution_history`,
    `identity_confidence_policy`."""

    async def find_by_id(self, action_id: UUID) -> Action | None: ...

    async def insert(self, action: Action) -> Action:
        """Inserts a new row. An `action_id` collision (a concurrent-retry
        race, §5.3's idempotency guard) must be caught by the caller and
        treated as the same idempotent short-circuit as a pre-existing-row
        check, never surfaced as a hard failure -- raises
        `ActionAlreadyExistsError`."""
        ...

    async def update_status(
        self, action_id: UUID, *, status: str, confidence: float | None = None
    ) -> None: ...

    async def record_result(
        self, action_id: UUID, *, result: dict | None, error: str | None
    ) -> None:
        """Persists the terminal `result`/`error` -- repository-internal
        columns beyond `Action`'s own shared-entity fields, the same
        pattern `capability-engine`'s `permissions_reviewed_at`/
        `sandbox_test_passed_at` bookkeeping already established. What
        `get_result()` reads back for an idempotent replay (§5.3)."""
        ...

    async def get_result(self, action_id: UUID) -> tuple[dict | None, str | None] | None:
        """Returns `(result, error)` for an already-terminal `action_id`,
        or `None` if no result has been recorded yet -- the idempotency
        guard's read path (§5.3): a repeat `action.execute` for a
        terminal-state `action_id` returns this stored `(result, error)`
        unmodified, never re-executing."""
        ...

    async def insert_pending_approval(self, approval: PendingApproval) -> None: ...

    async def find_pending_approval(self, action_id: UUID) -> PendingApproval | None: ...

    async def decide_pending_approval(
        self, action_id: UUID, *, decision: Literal["approved", "denied"], decided_at: datetime
    ) -> None: ...

    async def record_execution_history(
        self,
        *,
        action_id: UUID,
        stage: str,
        outcome: str,
        detail: str | None = None,
    ) -> None:
        """Append-only log of Action Principle lifecycle stage transitions
        (TDD 3D §6.12 "Store Experience") -- mirrors
        `capability_installation_event`'s append-only precedent."""
        ...

    async def find_identity_confidence_policy(
        self, user_id: UUID
    ) -> IdentityConfidencePolicy | None: ...
