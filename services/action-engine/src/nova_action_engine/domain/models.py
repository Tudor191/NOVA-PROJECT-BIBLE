"""Repository-internal domain types -- `PendingApproval` and
`IdentityConfidencePolicy` (docs/design/phase-3/07-tdd-3d-action-engine.md
§4, §7) stay local to this engine, never promoted to `nova_contracts`, the
same boundary `capability-engine`'s `permissions_reviewed_at`/
`sandbox_test_passed_at` pipeline bookkeeping already established.

`Action`, `RetryPolicy`, `RollbackStrategy` are shared entities and live in
`nova_contracts.events.action` -- re-exported here for convenience so
`domain/` code only ever imports from this module, mirroring
`capability-engine`'s own `domain/models.py` convention (which re-exports
nothing itself, since `Capability`/`CapabilityHandle` needed no
engine-local companion types; `action-engine` does).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from nova_contracts import Action, RetryPolicy, RollbackStrategy
from pydantic import BaseModel

__all__ = [
    "Action",
    "IdentityConfidencePolicy",
    "PendingApproval",
    "RetryPolicy",
    "RollbackStrategy",
]


class PendingApproval(BaseModel):
    """TDD 3D §4 point 1 -- the approval-loop state machine record.
    `decided_at`/`decision` are `None` while `status="approval_required"`."""

    action_id: UUID
    risk: str
    """`RiskLevel` value, see `nova_contracts.events.action.Action.risk`'s
    own docstring for why this stays a plain `str` at the model boundary."""
    requested_at: datetime
    decided_at: datetime | None = None
    decision: Literal["approved", "denied"] | None = None


class IdentityConfidencePolicy(BaseModel):
    """TDD 3D §7, ADR-032 point 2 -- a configurable identity-confidence
    threshold *per risk tier*, never one global hardcoded value. Absent
    policy fails closed (§10) -- treated as requiring maximum confidence
    for every risk tier, the same idiom `ProactiveBoundaryPolicy`
    established for an absent policy elsewhere in this project."""

    user_id: UUID
    minimum_confidence_by_risk: dict[str, float]
    """Keyed by `RiskLevel` value (e.g. `"critical"`)."""
