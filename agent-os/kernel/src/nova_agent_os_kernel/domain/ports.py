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

from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from nova_agent_sdk import AgentContext, AgentHealth, AgentMessage
from nova_contracts import AgentPackageSnapshot, AgentResult, EventEnvelope
from pydantic import BaseModel

from nova_agent_os_kernel.domain.activity import ActivityPage, AgentActivity
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
    """Persistence port for the `agent_os` schema's `agent_instance` (TDD 3E
    §4) and, since Phase 4C milestone 4C.2b, its append-only
    `agent_activity` table.

    **One port for both tables, deliberately.** `action-engine`'s own
    `ActionRepository` already owns four tables under one Protocol, and here
    it is load-bearing rather than stylistic: an activity row that records a
    state transition must commit in the *same transaction* as the transition
    itself, and that is only possible when one implementation owns the
    session for both. Splitting them would force a second transaction
    abstraction to coordinate the two -- which 4C.2b was explicitly scoped
    not to invent.

    The activity table is **append-only at this boundary**: `append_activity`
    and `list_activity` are the entire surface. There is no update, no
    delete, and no method that takes an existing activity id to modify. That
    is asserted by `tests/unit/test_activity.py`, so a mutation cannot be
    added without a test failing.
    """

    async def find_by_id(self, instance_id: UUID) -> AgentInstance | None: ...

    async def insert(
        self, instance: AgentInstance, *, activity: AgentActivity | None = None
    ) -> AgentInstance:
        """Inserts a new row. An `id` collision must be caught by the
        caller and raises `AgentInstanceAlreadyExistsError`, mirroring
        every other Phase 3 repository's own idempotency-guard
        translation.

        `activity`, when given, is written **in the same transaction** as the
        instance row. That is what makes "an instance was dispatched" and
        "the dispatch was recorded" one fact rather than two that can
        disagree: a crash between two separate commits would leave a running
        instance with no record of starting. Passing `None` (the default,
        and every existing caller's behaviour) writes the instance alone.

        The activity's `agent_instance_id` is not checked against
        `instance.id` here -- the foreign key does that, and a repository
        re-deriving what the database already enforces would be a second
        place for the rule to live."""
        ...

    async def list_by_status(self, status: str) -> list[AgentInstance]: ...

    async def list_instances(self, *, limit: int = 50) -> list[AgentInstance]:
        """Every agent instance, newest `started_at` first.

        Added in Phase 4C milestone 4C.2c to serve `GET /v1/agents`, which had
        no method returning more than one status. Deliberately **not** filtered
        to `"running"`: the response carries each instance's `status`, and a
        list that could only ever contain running rows would make that field
        constant while hiding every instance that had just finished -- which,
        with Phase 3's synchronous `inprocess` backend, is nearly all of them
        nearly all of the time.

        `limit` bounds an unbounded table, matching `/v1/plans`' and
        `/v1/action/approvals`' own `limit: int = 50` convention. Newest first
        for the same reason `/v1/plans` is: a panel opening on a long history
        should show current work, not the first instance the system ever ran.
        """
        ...

    async def update_status(
        self,
        instance_id: UUID,
        *,
        status: str,
        health_status: str | None = None,
        activity: AgentActivity | None = None,
    ) -> None:
        """Transitions an already-inserted `agent_instance` row. `Scheduler`
        uses it to move a row from `"running"` (written before `spawn()`, so
        restart reconciliation has a real orphan to recover -- TDD 3E §4) to
        its terminal `"completed"`/`"failed"`. `health_status` is left
        unchanged when `None`; an unknown `instance_id` is a no-op, never an
        error.

        `activity`, when given, is written in the same transaction as the
        status change, for the reason `insert` gives. **An unknown
        `instance_id` writes neither**: a no-op transition must not leave an
        activity row claiming a transition that did not happen."""
        ...

    async def append_activity(self, activity: AgentActivity) -> None:
        """Records an activity that is **not** part of an `agent_instance`
        mutation -- `restart_planned` and `peer_review` today, both of which
        happen between transitions rather than at one.

        Its own transaction, and correctly so: there is no other write to be
        atomic with. Activity that *does* accompany a transition goes through
        `insert`/`update_status` instead, which is why this method takes no
        status argument and cannot be used to fake one."""
        ...

    async def list_activity(
        self,
        agent_instance_id: UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> ActivityPage:
        """One page of an instance's activity, newest first, ordered by
        `(occurred_at DESC, id DESC)` -- the composite key `domain/activity.py`
        documents and the index matches.

        Keyset, never offset: `cursor` is an opaque `encode_cursor` value and
        an invalid one raises `InvalidCursorError` rather than silently
        restarting at the first page. The returned `next_cursor` is `None`
        exactly when no further row exists, so a caller never follows a
        cursor to an empty page."""
        ...


@runtime_checkable
class RegistryPort(Protocol):
    """Everything the Kernel needs from Registry -- not only what the
    Scheduler needs. `find_healthy_package` serves dispatch (TDD 3E §4 step
    1); `list_packages` serves the read-only `/v1` surface D-4 authorises.
    Both wrap disclosed RPC subjects in `nova_contracts.events.agent_os`."""

    async def find_healthy_package(
        self, *, category: str, correlation_id: UUID | None = None
    ) -> AgentPackageSnapshot | None:
        """TDD 3E §4 step 1: "query Registry for healthy candidates in the
        required category." Wraps
        `agent_os.registry.find_healthy_package.request`."""
        ...

    async def list_packages(
        self, *, correlation_id: UUID | None = None
    ) -> list[AgentPackageSnapshot]:
        """Every installed Agent Package. Wraps
        `agent_os.registry.list_packages.request` (Phase 4C milestone
        4C.2a, approved 2026-09-08).

        **An empty list means Registry is healthy and holds nothing.** An
        unreachable or failing Registry must **raise**, never return `[]` --
        that separation is what lets `GET /v1/agents` answer 503 for a
        degraded Registry and `200 []` for a healthy empty one (decision
        **D-1**). An implementation that swallowed the failure would collapse
        the two into one indistinguishable response, which is the exact
        shape `api-gateway`'s own `domain/envelope.py` forbids: "a degraded
        upstream must never look like an empty success."

        This slice (4C.2a) adds the port and its client; the endpoint that
        turns a raised error into 503 is 4C.2c's."""
        ...


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

    async def record_peer_review(
        self,
        *,
        primary_result: AgentResult,
        reviewer_category: str,
        reviewer_result: AgentResult | None,
        reviewer_available: bool,
        correlation_id: UUID | None = None,
    ) -> Literal["approved", "rejected", "timed_out", "not_required"]:
        """Disclosed addition, coding-agent slice: wraps
        `agent_os.supervisor.peer_review.request` -- see
        `nova_contracts.events.agent_os`'s own
        `AgentOsPeerReviewRequestPayload` docstring for the full
        ownership-split disclosure (Kernel spawns and delivers, the
        Supervisor classifies and records to Decision Memory)."""
        ...


@runtime_checkable
class AgentExecutionBackend(Protocol):
    """Doc 12 §8, verbatim four-method Protocol -- "one interface, four
    implementations... scaling from 10 agents to 10,000... is a scheduling
    and infrastructure decision, never a rewrite." Phase 3 implements only
    `inprocess` (`domain/execution_backend.py::InprocessExecutionBackend`);
    declaring the full Protocol shape now, not a redesign later, is the
    explicit point of doc 12 §8's own "already designed for" framing.

    `spawn_and_review`, disclosed addition (coding-agent slice): not one of
    doc 12 §8's own four methods -- see `domain/execution_backend.py`'s own
    module docstring for why the Agent Mailbox `send()` this Protocol
    already declares cannot reach a completed, synchronous `spawn()`'s
    instance, and why this is the smallest additional method that lets the
    Kernel Scheduler still deliver a `PEER_REVIEW_REQUEST` to a freshly
    spawned reviewer without redesigning `spawn()` itself."""

    def next_instance_id(self) -> UUID:
        """Mints the id the next `spawn()` should use. Disclosed addition
        (TaskNode-lifecycle slice) -- lets the Scheduler persist a
        `"running"` `agent_instance` row *before* awaiting `spawn()`, which
        is what makes TDD 3E §4's restart reconciliation reachable at all.
        The id stays the backend's to mint, since a future `subprocess`/
        `container`/`remote` backend may need it to carry backend-specific
        structure."""
        ...

    async def spawn(
        self,
        agent: AgentPackageSnapshot,
        context: AgentContext,
        *,
        instance_id: UUID | None = None,
    ) -> AgentInstanceHandle:
        """`instance_id` reuses an id already minted by
        `next_instance_id()`; `None` mints a fresh one, preserving every
        existing caller's behavior unchanged."""
        ...

    async def spawn_and_review(
        self, agent: AgentPackageSnapshot, message: AgentMessage
    ) -> AgentMessage | None: ...

    async def send(self, handle: AgentInstanceHandle, message: AgentMessage) -> None: ...

    async def health(self, handle: AgentInstanceHandle) -> AgentHealth: ...

    async def terminate(self, handle: AgentInstanceHandle) -> None: ...
