"""Protocols this package depends on -- implements nothing itself
(docs/design/phase-3/08-tdd-3e-agent-os.md §7). `domain/` may only import
this module, `nova_contracts`, `nova_agent_sdk`, and other `domain/`
modules -- never FastAPI or `nova_eventbus_sdk` directly
(docs/architecture/03-backend-architecture.md §1).

**`AgentInstancePort`, disclosed.** Doc 12 §10's Agent Mailbox is a real
Event Bus subject family (`agent_os.instance.<id>.inbox`), but nothing in
this project can currently receive on it: `agent-os/kernel`'s own
Milestone 2 shipped health-only, with an empty `SUBSCRIBABLE_SUBJECTS`
(no Scheduler, no `inprocess` execution backend, confirmed by direct read
of `agent-os/kernel/src/nova_agent_os_kernel/events/subscribed.py` this
milestone) -- there is, today, no live agent instance anywhere for a
message to reach. `clients/instance_client.py` implements this Protocol
against the real wire subject regardless (the same "real code, no real
caller/callee yet" idiom this project already uses for
`agent_os.task.completed`'s own consumer gap, `GoalsPort`, and
`DigitalTwinPort`), but it cannot be exercised end-to-end until Kernel's
own Scheduler/`inprocess` backend exist -- a disclosed, out-of-scope-this-
milestone gap, not a silently invented one.

**Correction to the paragraph above, 2026-08-29 (Phase 3E Gate Review
closure pass).** Its *conclusion* still holds; its *stated reason* is now
false and is corrected here rather than left to mislead. The Kernel is no
longer health-only: `domain/scheduler.py` and
`domain/execution_backend.py` both exist, and `events/subscribed.py`'s
`SUBSCRIBABLE_SUBJECTS` is `{"planning.task_graph.created"}`, not empty
(both re-verified by direct read this pass). Live agent instances **do**
exist. What remains true is the narrower fact that matters here: **no
component anywhere subscribes to `agent_os.instance.*.inbox`.** Verified
against the two real allow-lists, not their docstrings --
`agent-os/kernel`'s set is `{"planning.task_graph.created"}` and
`agent-os/supervisors`' is `{"agent_os.supervisor.restart_plan.request",
"agent_os.supervisor.peer_review.request"}`. The Phase 3 peer-review round
delivers its `AgentMessage` **in-process**, through
`InprocessExecutionBackend.spawn_and_review()` calling the reviewer
Handler's `on_message()` directly -- correct for the only enabled backend,
per TDD 3E §6 and `01-tdd-preparation-and-fork-resolutions.md` §5.5 Fact 4,
which establish that `inprocess` passes these objects live rather than
serialized. So the Protocol is still "real code, no real callee yet", but
because the mailbox subject has no subscriber, not because the Kernel is
unbuilt. Recorded as a ratified Phase 3E narrowing in
`docs/design/phase-3/08-tdd-3e-agent-os.md` §10.

Every domain module that
depends on this Protocol is fully tested today against `FakeAgentInstancePort`.

**`DecisionMemoryPort`, disclosed.** `memory-engine`'s own Decision Memory
(`services/memory-engine/src/nova_memory_engine/domain/decision.py`)
exposes no create/record endpoint reachable by another engine -- confirmed
by reading its `api/decisions.py` (search/get only) and
`events/subscribed.py` (no decision-record RPC) this milestone. Doc 12 §9's
"Recorded to Decision Memory either way" is implemented as a real call
through this Protocol, but its default implementation
(`clients/decision_memory_client.py`) is a local, structured-log best-
effort -- not a live cross-engine RPC, since none exists to call. TDD 3E
§10's own event-contract list names no subject for this either. Disclosed,
matching the same "declared, not yet wired" treatment already given to
`Registry`'s `CommunicationPort`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from nova_contracts import AgentMessage, EventEnvelope
from pydantic import BaseModel

__all__ = [
    "AgentInstancePort",
    "DecisionMemoryPort",
    "EventPublisher",
    "ReasoningOutcome",
    "ReasoningPort",
]


@runtime_checkable
class EventPublisher(Protocol):
    """The subset of `BoundEventBus` `clients/` need -- declared here, not
    imported from `nova_eventbus_sdk`, so `domain/` never depends on the
    event-bus package directly. Matches `BoundEventBus.request()`'s
    signature exactly (same pattern as every other engine's own
    `domain/ports.py`)."""

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
class AgentInstancePort(Protocol):
    """Doc 12 §10's Agent Mailbox, from the Supervisor's own point of
    view: deliver one `AgentMessage` to an instance's inbox and await its
    `on_message()` reply (doc 12 §4: `on_message(...) -> AgentMessage |
    None`) within `timeout_ms`, modeled as a single request/reply call --
    the same transport primitive (`BoundEventBus.request()`) every other
    cross-engine RPC in this project already uses, applied here to a
    per-instance subject instead of a fixed one."""

    async def deliver(
        self, message: AgentMessage, *, timeout_ms: int = 30000
    ) -> AgentMessage | None: ...


class ReasoningOutcome(BaseModel):
    """The subset of reasoning-engine's `ReasoningReplyPayload` a conflict
    escalation needs -- deliberately not `communication-engine`'s own
    identically-shaped internal type (ADR-004: no engine imports another
    engine's internals, confirmed as this workspace's very first
    import-linter contract)."""

    outcome: str
    chosen_description: str | None
    confidence_score: float | None


@runtime_checkable
class ReasoningPort(Protocol):
    """TDD 3E §7's "existing RPC" -- `reasoning.reason.request`, the one
    live, already-shipped RPC `reasoning-engine` serves (confirmed:
    `services/reasoning-engine/src/nova_reasoning_engine/events/
    subscribed.py`'s only entry). Mirrors `communication-engine`'s own
    `ReasoningPort`/`ReasoningClient` precedent field-for-field."""

    async def reason(
        self, *, objective_text: str, user_id: UUID, correlation_id: UUID | None = None
    ) -> ReasoningOutcome: ...


@runtime_checkable
class DecisionMemoryPort(Protocol):
    """Doc 12 §9's "Recorded to Decision Memory either way" -- see this
    module's own docstring for why the default implementation is a local,
    best-effort record, not a live cross-engine RPC."""

    async def record(
        self,
        *,
        objective: str,
        alternatives: list[str],
        chosen_alternative: str,
        reasoning: str,
        correlation_id: UUID,
    ) -> None: ...
