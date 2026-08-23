"""Purely in-memory domain types for `agent-os/supervisors` -- doc 12 §9's
Supervision Tree concepts
(`RestartStrategy`, a tracked `SupervisedInstance`, one `PeerReviewOutcome`,
one `ConflictRecord`), TDD 3E §7. None of these are persisted: TDD 3E §7
names no Supervisor-owned schema, and Kernel already owns the one
persisted fact that survives a process restart (`agent_instance`, TDD 3E
§4/§12, Milestone 2) -- a Supervisor's own bookkeeping (which instances it
is currently tracking, an in-flight peer-review round) is meaningless once
the process holding it has died, the same reasoning
`14-3e-agent-os-research.md` §4 gives for why `agent_instance` itself is
not colocated with `planning-engine`'s own schema. See `main.py`'s module
docstring for the full disclosure.

`AgentResult` (`nova_contracts.entities`, Fork 3E-1, approved) is used
verbatim, never modified -- `PeerReviewOutcome.peer_validation` is
Supervisor-local bookkeeping *around* an `AgentResult`, not a new field
grafted onto the shared, approved contract (TDD 3E §12's failure-table
prose names a `peer_validation` value the approved `AgentResult` shape
never carried; see this milestone's own reconciliation note for why this
is resolved as a wrapper type here rather than as a change to
`nova_contracts`)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from nova_contracts import AgentResult
from pydantic import BaseModel

__all__ = [
    "ConflictRecord",
    "PeerReviewOutcome",
    "RestartStrategy",
    "SupervisedInstance",
]


class RestartStrategy(StrEnum):
    """Doc 12 §9, verbatim three-member set. `engineering` Supervisor uses
    `ONE_FOR_ONE` by default for its four agent categories (TDD 3E §7)."""

    ONE_FOR_ONE = "one_for_one"
    ONE_FOR_ALL = "one_for_all"
    REST_FOR_ONE = "rest_for_one"


class SupervisedInstance(BaseModel):
    """One agent instance this Supervisor is currently tracking --
    Supervisor-local mirror of the subset of Kernel's own `AgentInstance`
    (TDD 3E §4) `restart.py`'s pure planning functions need. `started_order`
    is a monotonic per-supervisor sequence number (not a timestamp).
    """

    id: UUID
    category: str
    restart_strategy: RestartStrategy
    started_order: int
    status: Literal["running", "completed", "failed"]


class PeerReviewOutcome(BaseModel):
    """One completed (or timed-out) peer-review round (doc 12 §9, TDD 3E
    §12). `peer_validation="timed_out"` is TDD 3E §12's own required,
    non-fatal outcome -- the Supervisor proceeds with `primary_result`
    exactly as self-validated, never silently treating a timeout as an
    approving review."""

    primary_result: AgentResult
    reviewer_instance_id: UUID | None
    peer_validation: Literal["approved", "rejected", "timed_out", "not_required"]
    reviewer_result: AgentResult | None = None


class ConflictRecord(BaseModel):
    """One conflict-resolution attempt (doc 12 §9: "escalates first to the
    owning Supervisor... only escalates further to `reasoning-engine`...
    Recorded to Decision Memory either way"). `resolution` names which of
    the two levels actually resolved it."""

    description: str
    resolution: Literal["supervisor_resolved", "escalated_to_reasoning"]
    outcome: str
    correlation_id: UUID
