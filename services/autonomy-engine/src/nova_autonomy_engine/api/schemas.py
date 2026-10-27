"""Wire models for `/v1/autonomy/*` -- TDD 4D §8.1.

Separate from `domain/models.py` on purpose: the domain types are what the
engine reasons with, these are what the browser parses. The panel's Zod schemas
mirror *these*, and TDD §12 requires them to be strict -- an unknown field must
fail the parse rather than being silently dropped -- so every response model
here is closed and explicit.

Three shapes carry a distinction the panel must be able to render and that a
naive model would flatten:

* `TrustScoreResponse.score` is `float | None` with a separate `status`. A
  `None` score renders as **"insufficient evidence"**, never as `0`, and an
  unreachable upstream renders differently from "no data yet" -- TDD §13 row 1
  and §16 control 12.
* `LevelOption.selectable` is separate from the level existing at all, so the
  selector can show Level 2 **present and disabled** (D-1) rather than omitting
  it and leaving the user unable to see that it is coming.
* `SuggestionResponse.gates` reports which gates a stored suggestion passes
  *now*, per §12's *"which gates passed"*, rather than a status frozen at
  proposal time.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from nova_autonomy_engine.domain.models import (
    DecisionOutcome,
    PermissionCategory,
    PolicyEffect,
    RiskLevel,
    SuggestionStatus,
    TrustInputStatus,
)

__all__ = [
    "AutonomyOverviewResponse",
    "DecideSuggestionRequest",
    "LevelOption",
    "LevelResponse",
    "PermissionGrantResponse",
    "PermissionMatrixResponse",
    "PolicyCheckResponse",
    "PolicyCreateRequest",
    "PolicyResponse",
    "PolicyUpdateRequest",
    "SetLevelRequest",
    "SetPermissionsRequest",
    "SuggestionListResponse",
    "SuggestionResponse",
    "TrustScoreResponse",
]


class _Strict(BaseModel):
    """Unknown fields are an error, in both directions. A request carrying a
    field this service does not understand is a client that believes something
    untrue about the contract, and accepting it silently is how that belief
    survives."""

    model_config = ConfigDict(extra="forbid")


class LevelOption(_Strict):
    level: int
    name: str
    """Bible Part 14's own wording, so the UI and the Bible cannot drift."""
    selectable: bool
    note: str | None = None
    """Why a present-but-unselectable level is unselectable, shown next to the
    disabled control rather than left for the user to guess."""


class LevelResponse(_Strict):
    level: int
    name: str
    updated_at: datetime | None = None
    configured: bool
    """`False` when the user has never set a level, so "never configured" stays
    distinguishable from "deliberately set to Observation Only"."""
    options: list[LevelOption]


class SetLevelRequest(_Strict):
    level: int


class TrustScoreResponse(_Strict):
    category: PermissionCategory
    score: float | None
    """`None` renders as "insufficient evidence". **Never `0`** -- 2D-D's
    discipline carried into the UI (TDD §12)."""
    status: TrustInputStatus
    evidence_count: int
    detail: str | None = None


class PermissionGrantResponse(_Strict):
    category: PermissionCategory
    max_risk: RiskLevel | None
    """`None` means no autonomous authority in this category -- the
    fail-closed default, rendered as such."""
    requires_approval_above: RiskLevel | None
    granted: bool
    """`False` for a category with no row at all, so the panel can show all ten
    categories and distinguish "never configured" from "configured to nothing"."""
    updated_at: datetime | None = None


class PermissionMatrixResponse(_Strict):
    categories: list[PermissionGrantResponse]
    """All ten, always, in Bible Part 14's order."""


class SetPermissionsRequest(_Strict):
    grants: list[PermissionGrantResponse] = Field(default_factory=list)


class PolicyCheckResponse(_Strict):
    policy_id: UUID
    name: str
    effect: PolicyEffect
    matched: bool


class PolicyResponse(_Strict):
    id: UUID
    name: str
    effect: PolicyEffect
    match_category: PermissionCategory | None = None
    match_min_risk: RiskLevel | None = None
    match_capability_class: str | None = None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class PolicyCreateRequest(_Strict):
    name: str = Field(min_length=1, max_length=200)
    effect: PolicyEffect
    match_category: PermissionCategory | None = None
    match_min_risk: RiskLevel | None = None
    match_capability_class: str | None = None
    enabled: bool = True


class PolicyUpdateRequest(_Strict):
    """Every field optional -- `PATCH` merges. `None` means *"leave this
    alone"*, so clearing a match axis is not expressible here; that is a
    deliberate omission rather than an oversight, and re-creating the policy is
    the unambiguous way to do it."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    effect: PolicyEffect | None = None
    match_category: PermissionCategory | None = None
    match_min_risk: RiskLevel | None = None
    match_capability_class: str | None = None
    enabled: bool | None = None


class GateReportResponse(_Strict):
    denied: bool
    gate: str | None = None
    reason: str | None = None
    requires_approval: bool
    policy_checks: list[PolicyCheckResponse]


class SuggestionResponse(_Strict):
    id: UUID
    category: PermissionCategory
    risk: RiskLevel
    title: str
    detail: str
    status: SuggestionStatus
    created_at: datetime
    decided_at: datetime | None = None
    gates: GateReportResponse
    """*"each suggestion shows what is proposed, its risk, **which gates
    passed**"* (TDD §12), evaluated against the policies and grants in force
    now -- so a suggestion a newly-authored policy denies is visibly denied
    before the user can approve it."""


class SuggestionListResponse(_Strict):
    items: list[SuggestionResponse]
    next_cursor: str | None = None
    """Opaque. There is no `offset`, `page` or `total` -- TDD §8.1/§9."""


class DecideSuggestionRequest(_Strict):
    decision: str = Field(pattern="^(approve|reject)$")
    """The AC-5 control. **No default** -- an approval must be stated, never
    inferred from an empty body."""


class DecisionResultResponse(_Strict):
    suggestion: SuggestionResponse
    outcome: DecisionOutcome
    """What was recorded. **Never `execute`** -- approving a suggestion records
    the user's decision and executes nothing (TDD §18)."""
    executed: bool = False
    """Always `False` in this release, stated explicitly rather than left to be
    inferred from an absence. AC-5 measures exactly this."""


class AutonomyOverviewResponse(_Strict):
    """One call for the panel's first paint, matching 4C's `/v1/agents`
    shape."""

    level: LevelResponse
    trust: list[TrustScoreResponse]
    permissions: PermissionMatrixResponse
    proposed_count: int
    policy_count: int
    degraded: list[str] = Field(default_factory=list)
    """Named degradations -- currently the conversational trust input when its
    source cannot be consulted. A degraded upstream must never be reported as a
    clean empty result (TDD §16 control 12), so it is listed here as well as
    reflected in each `TrustScoreResponse.status`."""
