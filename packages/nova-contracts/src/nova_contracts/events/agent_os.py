"""`agent-os` (NAOS) event payloads (Bible Part 4, docs/architecture/
12-agent-architecture.md), per docs/design/phase-3/08-tdd-3e-agent-os.md.

`AgentMessageType` is doc 12 §10's own closed, versioned enum -- used
verbatim, no proposed changes. `AgentMessage` is TDD 3E §6, Fork 3E-1
(RESOLVED, approved as proposed) -- the Agent Mailbox envelope. Per the
Extraction-E placement rule (`14-3e-agent-os-research.md` §3): `AgentMessage`
routes over a real Event Bus subject
(`agent_os.instance.<instance_id>.inbox`, doc 12 §10), so it lives here, in
`events/`, not in `entities.py` alongside the in-process-only
`AgentContext`/`AgentHealth`/`AgentMetrics`/`AgentResult`.

**Registration note, disclosed:** `agent_os.instance.<instance_id>.inbox` is
a per-instance, templated subject family -- no fixed literal subject exists
to register `AgentMessage` under, unlike every other payload in this
package. `nova_contracts.registry` has no precedent for a templated subject
(confirmed by a full-package search before writing this module) and its own
`_REGISTRY` is a plain exact-string dict. Registering under the canonical,
non-routable representative subject `"agent_os.instance.inbox"` below is the
smallest, most consistent extension of the existing design: it satisfies
`@register_payload`'s schema-documentation/contract-test/TypeScript-codegen
purpose (this project's own CI convention) without inventing a new
glob-aware registry mechanism. The real runtime subject
(`f"agent_os.instance.{instance_id}.inbox"`) is never registered
individually -- `nova_eventbus_sdk.BoundEventBus`'s existing glob-pattern
allow-list support (`fnmatch` semantics, already used for families like
`"memory.*.created"`) is what `agent-os/kernel`'s own `events/subscribed.py`
declares (`"agent_os.instance.*.inbox"`) to permit the real, per-instance
subscribe calls; `validate_payload()` on the real subject falls through
unvalidated, exactly as the registry's own docstring already tolerates for
any subject used before/without a literal-string registration.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from nova_contracts.registry import register_payload

__all__ = ["AgentMessage", "AgentMessageType", "AgentOsTaskCompletedPayload"]


class AgentMessageType(StrEnum):
    """Doc 12 §10, verbatim."""

    ASSIGN = "assign"
    PAUSE = "pause"
    RESUME = "resume"
    PEER_REVIEW_REQUEST = "peer_review_request"
    PEER_REVIEW_RESULT = "peer_review_result"
    CONFLICT_ESCALATION = "conflict_escalation"
    DELEGATION = "delegation"
    HEALTH_PING = "health_ping"


@register_payload("agent_os.instance.inbox")
class AgentMessage(BaseModel):
    """TDD 3E §6 -- the Agent Mailbox envelope. `from_instance_id=None` for
    Kernel/Supervisor-originated messages (doc 12 §10: "kernel-to-agent,
    supervisor-to-agent, and (never direct) agent-to-agent" -- agent-to-agent
    traffic is still routed through this envelope, just always carrying a
    non-`None` `from_instance_id` set by the mediating Supervisor, never a
    direct bus subscription between two instances)."""

    message_type: AgentMessageType
    from_instance_id: UUID | None = None
    to_instance_id: UUID
    payload: dict
    correlation_id: UUID
    schema_version: int = 1


@register_payload("agent_os.task.completed")
class AgentOsTaskCompletedPayload(BaseModel):
    """TDD 3E §10 -- new subject, owned by `agent-os/kernel`; `TDD 3B` §6.1
    already names `planning-engine` as this subject's consumer ("mutate the
    corresponding `TaskNode.status`"), field-level shape not previously
    defined anywhere (confirmed: no payload existed under this subject
    before this module, `agent_os.task.completed` was absent from every
    engine's `events/published.py`/`subscribed.py`, including
    `planning-engine`'s own -- `05-tdd-3b-planning-engine.md` §6.1's claim
    that a handler "is defined and tested now" does not match the merged
    `phase-3b-planning-persistence` code, a real, disclosed staleness in
    that document, not a design ambiguity: the intended behavior was never
    in question, only the field shape and the fact of non-implementation).

    `outcome` extends `AgentResult.status`'s vocabulary (`entities.py`)
    with `"interrupted"` -- the one outcome an `AgentResult` itself can
    never carry, since it is produced only by a live `execute()` call.
    `"interrupted"` is exclusively for Kernel-restart reconciliation (TDD
    3E §4/§12): a Kernel process restart finds `agent_instance` rows still
    `status="running"` whose actual `inprocess` asyncio task died with the
    old process -- there is no `AgentResult` to report, only the fact that
    the assignment was lost and the `TaskNode` must revert to `"ready"` for
    redispatch, never left `"running"` forever.

    `planning-engine`'s own consumption of this subject is intentionally
    not built by this change (`agent-os/kernel`'s milestone 2 slice) --
    "real code, no real caller yet" is this project's own established
    idiom (`GoalsPort`/`DigitalTwinPort`/Fork D precedent, TDD 3B §6.1's
    own words), and wiring the consumer side is `planning-engine`'s
    separate, disclosed follow-up.
    """

    task_node_id: UUID
    agent_instance_id: UUID
    outcome: Literal["success", "failure", "needs_revision", "interrupted"]
    result: dict | None = None
    correlation_id: UUID
    schema_version: int = 1
