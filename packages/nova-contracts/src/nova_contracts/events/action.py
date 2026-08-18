"""Action Engine event payloads and shared entities (Bible Part 12), per
docs/design/phase-3/07-tdd-3d-action-engine.md.

`Action`, `RetryPolicy`, `RollbackStrategy` are entities -- never
independently published (no `@register_payload`), the same treatment
`Capability`/`CapabilityHandle` get in `events/capability.py`. `PendingApproval`
and `IdentityConfidencePolicy` (TDD 3D §4, §7) are repository-internal
concerns and stay in `action-engine`'s own `domain/models.py`, not here --
the same boundary `capability-engine`'s `permissions_reviewed_at`/
`sandbox_test_passed_at` bookkeeping already established (never promoted
to `nova_contracts`).

`action.execute` is the request/reply RPC `action-engine` serves now (no
real caller until Phase 3E's Kernel Scheduler, TDD 3D §5) -- structurally
identical to `capability.resolve.request`/`capability.invoke.request`
(ADR-004's request/reply pattern). Its reply is `action.result`, named
distinctly per TDD 3D's own text (not `action.execute.reply`) since it
also serves as the Action Principle lifecycle's stage 11 ("Report
Outcome") event.

`action.approval.requested`/`action.approval.decided` are fire-and-forget
published events (TDD 3D §4: "publishes... publishes...", never described
as a reply) -- a new, Phase-3-owned namespace. **Never
`autonomy.approval.requested`/`.decision.made`, which stay reserved,
undefined, for `autonomy-engine` to claim in Phase 4** (Fork E2's
resolution) -- this namespace boundary is a tested property, not just a
documented one (see `tests/contract/test_action_payloads.py`).

Every payload carries `schema_version: int = 1` from its first commit
(ADR-024).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from nova_contracts.registry import register_payload

__all__ = [
    "Action",
    "ActionApprovalDecidedPayload",
    "ActionApprovalRequestedPayload",
    "ActionExecuteRequestPayload",
    "ActionPriority",
    "ActionResultPayload",
    "ActionStatus",
    "ActionType",
    "ApprovalDecision",
    "RetryPolicy",
    "RollbackStrategy",
    "RollbackStrategyKind",
]

ActionType = Literal["terminal", "filesystem"]
"""Bible Part 12 names 13 Action Types; Phase 3 implements exactly these
two (TDD 3D §3.2). "Git" is not a Bible-named Action Type -- it is a
roadmap-level adapter layered on top of Terminal/Filesystem Actions,
represented here as `action_type="terminal"`/`"filesystem"` plus an
adapter selection (`execution_target`), never a third type value."""


class ActionPriority(StrEnum):
    """Bible Part 12's own 6-tier scheduling-priority scale
    (`part-12-action-engine.md:473-489`) -- architecturally independent of
    `RiskLevel` (risk = how dangerous an action is; priority = how urgently
    it should be scheduled). A Background-priority action can still be
    Critical-risk, and vice versa (TDD 3D §3.3)."""

    EMERGENCY = "emergency"
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BACKGROUND = "background"


ActionStatus = Literal[
    "pending",
    "approval_required",
    "approved",
    "denied",
    "executing",
    "completed",
    "failed",
    "rolled_back",
]
"""TDD 3D §3.1's exact 8-value status set. `denied` (user/policy rejection
via the approval loop) and `failed` (execution error) are deliberately
distinct values -- TDD 3D §4 point 5 requires a calling agent instance be
able to tell these apart, not receive one opaque failure outcome."""

RollbackStrategyKind = Literal["restore_file", "undo_configuration", "restart_service", "manual"]

ApprovalDecision = Literal["approved", "denied"]


class RetryPolicy(BaseModel):
    """TDD 3D §3.1 -- Bible names the field, not a schema; proposed here,
    ratified by the Phase 3D research/approval pass."""

    max_retries: int = 0
    backoff_seconds: float = 1.0


class RollbackStrategy(BaseModel):
    """TDD 3D §3.1 -- Bible gives six examples (`part-12-action-engine.md:275-285`),
    no enum; proposed here, ratified by the Phase 3D research/approval pass.
    The *mechanism* behind `"restore_file"` (read-before-write via
    `action-engine`'s own `CapabilityPort`, Fork 3C-3's resolution) is
    concrete; this model itself is unaffected by that resolution."""

    kind: RollbackStrategyKind
    detail: str | None = None


class Action(BaseModel):
    """TDD 3D §3.1's 18-field mapping of Bible Part 12's Action Object
    Model (`part-12-action-engine.md:127-169`). `execution_target` holds
    the target `Capability`'s stable `name` (e.g. `"git"`), resolved via
    `capability.resolve.request`'s additive `name` field -- approved,
    `docs/design/phase-3/13-3d-action-engine-research.md` §5.1."""

    id: UUID
    action_type: ActionType
    priority: ActionPriority
    source: str
    requested_by: UUID
    execution_target: str
    depends_on: list[UUID] = Field(default_factory=list)
    parameters: dict = Field(default_factory=dict)
    expected_result: str | None = None
    risk: str
    """`nova_contracts.events.planning.RiskLevel` value -- kept as `str`
    here (not the enum type) to avoid a hard dependency from `events/action.py`
    on `events/planning.py`; the enum itself is what every reader/writer of
    this field actually uses (`RiskLevel(action.risk)`)."""
    timeout_seconds: int
    retry_policy: RetryPolicy
    rollback_strategy: RollbackStrategy | None = None
    required_permissions: list[str] = Field(default_factory=list)
    status: ActionStatus
    verification_method: str
    confidence: float | None = None


@register_payload("action.execute")
class ActionExecuteRequestPayload(BaseModel):
    """Doc 10 row 7: *"an agent instance (via its Supervisor) ->
    `action.execute`"* -- served now, no real caller until Phase 3E (TDD
    3D §5). `action_id` is caller-supplied (not server-generated) -- this
    is what natural-key idempotency on `Action.id` (approved,
    `13-3d-action-engine-research.md` §5.3) is built on: a genuine retry
    supplies the same `action_id` as the original attempt.

    `risk`/`status`/`confidence` are deliberately absent -- these are
    server-computed by the Action Principle lifecycle's own stages
    (Estimate Risk, stage 4; ongoing status transitions), never
    caller-supplied."""

    action_id: UUID
    action_type: ActionType
    priority: ActionPriority
    source: str
    requested_by: UUID
    execution_target: str
    depends_on: list[UUID] = Field(default_factory=list)
    parameters: dict = Field(default_factory=dict)
    expected_result: str | None = None
    timeout_seconds: int = 30
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    rollback_strategy: RollbackStrategy | None = None
    required_permissions: list[str] = Field(default_factory=list)
    verification_method: str
    requesting_engine: str
    correlation_id: UUID
    schema_version: int = 1


@register_payload("action.result")
class ActionResultPayload(BaseModel):
    """TDD 3D §6 stage 11, "Report Outcome" -- also this RPC's reply
    payload (§5). A repeat `action.execute` for an already-terminal
    `action_id` (§5.3's idempotency guard) returns this same payload from
    the original attempt, unmodified -- never a second, possibly-different
    result."""

    action_id: UUID
    status: ActionStatus
    result: dict | None = None
    error: str | None = None
    schema_version: int = 1


@register_payload("action.approval.requested")
class ActionApprovalRequestedPayload(BaseModel):
    """TDD 3D §4 point 2 -- published, new Phase-3-owned namespace. **Never
    `autonomy.approval.requested`**, which stays reserved, undefined, for
    `autonomy-engine` to claim in Phase 4 (Fork E2's resolution)."""

    action_id: UUID
    risk: str
    """`RiskLevel` value, see `Action.risk`'s own docstring."""
    requested_at: datetime
    schema_version: int = 1


@register_payload("action.approval.decided")
class ActionApprovalDecidedPayload(BaseModel):
    """TDD 3D §4 point 5 -- published, new Phase-3-owned namespace. **Never
    `autonomy.decision.made`**, which stays reserved for Phase 4."""

    action_id: UUID
    decision: ApprovalDecision
    decided_at: datetime
    reason: str | None = None
    schema_version: int = 1
