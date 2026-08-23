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
from uuid import UUID

from pydantic import BaseModel

from nova_contracts.registry import register_payload

__all__ = ["AgentMessage", "AgentMessageType"]


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
