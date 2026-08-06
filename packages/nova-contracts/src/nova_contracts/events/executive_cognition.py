"""Executive Cognition Engine event payloads (Bible Part 19), per
docs/design/phase-2c/00-executive-cognition-engine.md Sec5 (interactions),
Sec6 (the Cognitive Priority Matrix), Sec7 (arbitration), Sec13 (human
override), Sec18 (the Executive Decision Trace), and Sec19 (data model).

`CognitivePriorityScore` carries eight factors: Bible Part 6's own seven
(urgency, importance, complexity, risk, learning_value, resource_cost,
user_impact), plus `long_term_alignment`, added per ADR-029 -- this engine's
own computation, never caller-supplied (design doc Sec6.1). Every payload
carries `schema_version: int = 1` from its first commit (ADR-024), the same
discipline every Phase 2A/2B payload already follows.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from nova_contracts.registry import register_payload

GoalTier = Literal["ad_hoc", "established"]
"""Design doc Sec8, ADR-029 -- the same two-value tier `Goal.goal_tier`
carries in every engine's own domain layer, redefined here as a wire-level
type alias per ADR-004 (no cross-engine imports of domain types)."""


class ArbitrationOutcome(StrEnum):
    """Design doc Sec4 -- the four outcomes every arbitration produces."""

    PROCEED = "proceed"
    PROCEED_REDUCED = "proceed_reduced"
    WAIT = "wait"
    ESCALATED = "escalated"


class ExecutiveDecisionType(StrEnum):
    """Design doc Sec18 -- what kind of decision an Executive Decision Trace records."""

    RESOURCE_ARBITRATION = "resource_arbitration"
    CONFLICT_RESOLUTION = "conflict_resolution"
    HUMAN_OVERRIDE = "human_override"


class ExecutiveOverrideAction(StrEnum):
    """Design doc Sec13's human-override action set -- identical shape to
    Reasoning Engine's own `OverrideAction` (design doc Sec18 of that
    engine), redefined here rather than imported so each engine's contracts
    module stays self-contained, the same convention every engine's own
    enums already follow even where two engines' vocabularies coincide."""

    CONFIRM = "confirm"
    REDIRECT = "redirect"
    REJECT = "reject"


class OutcomeReportResult(StrEnum):
    """Design doc Sec7.3 -- what a caller reports happened after acting on
    an arbitration decision."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABANDONED = "abandoned"


class CognitivePriorityScore(BaseModel):
    """Design doc Sec6, Sec6.1 -- the eight-factor Cognitive Priority Matrix
    breakdown for one contending request. The first seven factors are
    caller-supplied on `ExecutiveRequestPayload`; `long_term_alignment` and
    `composite` are computed by this engine itself, never invented by a
    caller (ADR-028's epistemic-deference boundary applies to the seven
    caller-supplied factors -- this engine trusts what it's told about a
    request's own urgency/importance/etc., but the alignment and composite
    scores are its own structural arithmetic, not another engine's
    assertion)."""

    urgency: float = Field(ge=0.0, le=1.0)
    importance: float = Field(ge=0.0, le=1.0)
    complexity: float = Field(ge=0.0, le=1.0)
    risk: float = Field(ge=0.0, le=1.0)
    learning_value: float = Field(ge=0.0, le=1.0)
    resource_cost: float = Field(ge=0.0, le=1.0)
    user_impact: float = Field(ge=0.0, le=1.0)
    long_term_alignment: float = Field(ge=0.0, le=1.0)
    composite: float


class ContenderSummary(BaseModel):
    """Design doc Sec18 -- identifies one request that participated in an
    arbitration, without carrying any of its domain content."""

    requesting_engine: str
    request_kind: str
    correlation_id: UUID


class ConflictSignals(BaseModel):
    """Design doc Sec10, Sec18 -- which of the five conflict-resolution
    signals were consulted and what each one indicated, never the domain
    content those signals were drawn from (ADR-028)."""

    evidence_comparison: str | None = None
    confidence_comparison: str | None = None
    policy_applied: str | None = None
    user_objective_signal: str | None = None
    historical_outcome_signal: str | None = None


@register_payload("executive.arbitrate.request")
class ExecutiveRequestPayload(BaseModel):
    """Event Bus RPC counterpart to `POST /v1/executive/arbitrate` (design
    doc Sec5.1-Sec5.2) -- submitted by a coordinated engine (AI Model
    Orchestration Engine, Reasoning Engine, and in future phases Planning
    Engine/NAOS, design doc Sec5.9-Sec5.10) before starting cognitive work
    that would compete for a shared resource budget."""

    requesting_engine: str
    request_kind: str
    """e.g. `"model_generate"`, `"reasoning_process"` -- design doc Sec5.1."""
    user_id: UUID
    """Design doc Sec5.3, Sec5.5-Sec5.7 -- every port this engine calls
    (`GoalsPort`, `WorldModelPort`, `MemoryPort`, `PersonalContextPort`) is
    scoped per-user; the identical required field Reasoning Engine's own
    `ReasoningRequestPayload.user_id` already carries."""
    correlation_id: UUID = Field(default_factory=uuid4)
    urgency: float = Field(ge=0.0, le=1.0)
    importance: float = Field(ge=0.0, le=1.0)
    complexity: float = Field(ge=0.0, le=1.0)
    risk: float = Field(ge=0.0, le=1.0)
    learning_value: float = Field(ge=0.0, le=1.0)
    resource_cost: float = Field(ge=0.0, le=1.0)
    user_impact: float = Field(ge=0.0, le=1.0)
    deadline: datetime | None = None
    goal_id: UUID | None = None
    """Design doc Sec5.7, Sec8 -- a caller-supplied placeholder until
    Planning Engine exists, the identical pattern ADR-026 established for
    Reasoning Engine's own `GoalsPort`."""
    goal_tier: GoalTier | None = None
    """Design doc Sec8, ADR-029 -- caller-supplied alongside `goal_id` since
    `GoalsPort` is itself a placeholder returning `[]` until Planning Engine
    exists (Sec5.7): without this field, `long_term_alignment` (Sec6.1)
    would have no real signal to compute from in Phase 2C at all. Takes
    precedence over any future `GoalsPort`-sourced tier the same way
    Reasoning Engine's own caller-supplied goals already take precedence
    over its `GoalsPort` result (that design's Sec7.1)."""
    schema_version: int = 1


@register_payload("executive.arbitrate.reply")
class ExecutiveArbitrateReplyPayload(BaseModel):
    correlation_id: UUID
    executive_decision_id: UUID
    outcome: ArbitrationOutcome
    retry_after_ms: float | None = None
    """Set only when `outcome == "wait"` -- design doc Sec7 step 5."""
    reduced_budget_hint: float | None = None
    """Set only when `outcome == "proceed_reduced"` -- design doc Sec7 step 5."""
    priority_score: CognitivePriorityScore
    error: str | None = None
    """Set only when arbitration itself failed (design doc Sec14) -- an
    informative reply, not a bus timeout with no diagnostic, the same
    additive pattern ADR-024 established for `GenerateReplyPayload.error`
    in Phase 2A and `ReasoningReplyPayload.error` in Phase 2B."""
    schema_version: int = 1


@register_payload("executive.outcome.report")
class ExecutiveOutcomeReportPayload(BaseModel):
    """Design doc Sec7.3 -- the optional, genuinely-opt-in outcome-report
    RPC. No caller is required to send this, and arbitration correctness
    never depends on one arriving."""

    correlation_id: UUID
    outcome: OutcomeReportResult
    actual_duration_ms: float | None = None
    note: str | None = None
    schema_version: int = 1


@register_payload("executive.outcome.report.reply")
class ExecutiveOutcomeReportReplyPayload(BaseModel):
    acknowledged: bool = True
    schema_version: int = 1


@register_payload("executive.decision.completed")
class ExecutiveDecisionCompletedPayload(BaseModel):
    """Published for every arbitration that produced an outcome --
    `proceed`, `proceed_reduced`, `wait`, or `escalated` alike (design doc
    Sec4, Sec7) -- the event-bus mirror of the `executive_decision` row
    `ExecutiveRepository` persists. Distinct from `.failed` below the same
    way Reasoning Engine's own `.completed`/`.failed` split works: this
    event means arbitration itself succeeded at producing *some* outcome,
    not that the outcome was necessarily `proceed`."""

    executive_decision_id: UUID
    correlation_id: UUID
    decision_type: ExecutiveDecisionType
    contending_requests: list[ContenderSummary]
    winner_correlation_id: UUID | None = None
    outcome: ArbitrationOutcome
    execution_duration_ms: float
    schema_version: int = 1


@register_payload("executive.decision.failed")
class ExecutiveDecisionFailedPayload(BaseModel):
    """Published when arbitration itself cannot produce any outcome (design
    doc Sec14) -- a malformed request, an unrecoverable internal failure --
    distinct from a genuine `escalated` outcome, which is still a
    successfully-produced decision (design doc Sec4, Sec13)."""

    correlation_id: UUID
    reason: str
    schema_version: int = 1


@register_payload("executive.human_override.applied")
class ExecutiveHumanOverrideAppliedPayload(BaseModel):
    """Design doc Sec13 -- published whenever a human confirms, redirects,
    or rejects an executive decision, the direct analog of Reasoning
    Engine's own `HumanOverrideAppliedPayload`."""

    executive_decision_id: UUID
    action: ExecutiveOverrideAction
    redirect_outcome: ArbitrationOutcome | None = None
    note: str | None = None
    schema_version: int = 1
