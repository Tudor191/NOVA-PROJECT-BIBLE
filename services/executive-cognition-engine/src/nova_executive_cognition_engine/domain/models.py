"""Domain entities -- not ORM models (docs/design/phase-2c/
00-executive-cognition-engine.md §1, §19). `ArbitrationOutcome`,
`ExecutiveDecisionType`, `ExecutiveOverrideAction`, `CognitivePriorityScore`,
`ContenderSummary`, and `ConflictSignals` are re-exported from
`nova_contracts.events.executive_cognition` rather than redefined here, the
same shared-type convention every prior engine follows for cross-cutting
classification schemes and wire-identical structural types. `FailureAction`
is reused directly from `nova_contracts.events.reasoning` -- design doc §14
mirrors Reasoning Engine's own failure-recovery action set exactly rather
than reinventing one.

`MemoryReference`, `WorldModelSnapshot`, and `PersonalContext` are this
engine's own independent redefinitions of Reasoning Engine's identically-
shaped domain types (§5.3, §5.5, §5.6) -- structurally reused, never
imported across the engine boundary (ADR-004): each engine owns its own
lightweight representation of what it read from a shared upstream port.

**The boundary this file exists to enforce** (ADR-027/028/029, design doc
§0): every model here either describes *this engine's own arbitration
decisions* (an `ExecutiveDecisionTrace`, an `ExecutivePolicy` application)
or is a lightweight, caller-supplied *request* for coordination
(`ExecutiveRequest`, `Goal`). Nothing here caches another engine's domain
conclusion, fact, memory, or state -- if a future change to this file would
make it store a copy of Reasoning Engine's own `Decision` content, Knowledge
Engine's facts, or Memory Engine's experiences, it belongs in a different
engine instead.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from nova_contracts.events.executive_cognition import (
    ArbitrationOutcome,
    CognitivePriorityScore,
    ConflictSignals,
    ContenderSummary,
    ExecutiveDecisionType,
    ExecutiveOverrideAction,
)
from nova_contracts.events.reasoning import FailureAction
from pydantic import BaseModel, Field

__all__ = [
    "ArbitrationOutcome",
    "ArbitrationResult",
    "CognitivePriorityScore",
    "ConflictSignals",
    "ContenderSummary",
    "ContextSwitchEvaluation",
    "ExecutiveDecisionTrace",
    "ExecutiveDecisionType",
    "ExecutiveFailureRecovery",
    "ExecutiveOverrideAction",
    "ExecutivePolicy",
    "ExecutiveRequest",
    "FailureAction",
    "Goal",
    "HumanOverrideRequest",
    "MemoryReference",
    "PersonalContext",
    "WorldModelSnapshot",
]


class Goal(BaseModel):
    """§5.7, §8 -- reused from Reasoning Engine's own `GoalsPort` shape,
    extended with `goal_tier` per ADR-029 §8: a request grouped under an
    `established` goal scores higher `long_term_alignment` (§6.1) than an
    `ad_hoc` one. Additive and defaulted, so Reasoning Engine's own use of
    the equivalent shape needs no change."""

    id: UUID
    description: str
    priority: float = Field(ge=0.0, le=1.0)
    goal_tier: Literal["ad_hoc", "established"] = "ad_hoc"


class MemoryReference(BaseModel):
    """§5.3 -- carries Memory Engine's own ID and a summary only, never the
    memory's full content duplicated into this engine's own records. Used
    narrowly for historical-outcome lookups (§7.3), never general recall."""

    memory_id: UUID
    summary: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class WorldModelSnapshot(BaseModel):
    """§5.5 -- a read-only snapshot of World Model's Active Context, used for
    situational grounding during arbitration. `degraded` mirrors
    `ContextReplyPayload.degraded`: not an error, a signal to proceed without
    that grounding rather than failing."""

    user_id: UUID
    objective: str | None = None
    project_id: UUID | None = None
    device: str | None = None
    task: str | None = None
    activity: str | None = None
    confidence: float | None = None
    degraded: bool = False


class PersonalContext(BaseModel):
    """§5.6 -- a thin projection of `WorldModelSnapshot`, the identical
    placeholder pattern Reasoning Engine already established: Personal
    Context has no dedicated engine yet (Bible Part 16, future phase)."""

    user_id: UUID
    objective: str | None = None
    project_id: UUID | None = None
    device: str | None = None
    task: str | None = None


class ExecutiveRequest(BaseModel):
    """§5.1-§5.2 -- one request for cognitive resources from a coordinated
    engine, submitted before starting work that would compete for a shared
    resource budget. Domain equivalent of `ExecutiveRequestPayload`."""

    requesting_engine: str
    request_kind: str
    user_id: UUID
    """§5.3, §5.5-§5.7 -- every port this engine calls is scoped per-user."""
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
    goal_tier: Literal["ad_hoc", "established"] | None = None
    """§5.7, §8, ADR-029 -- caller-supplied alongside `goal_id` since
    `GoalsPort` is itself a placeholder returning `[]` until Planning Engine
    exists (§5.7): without this field, `long_term_alignment` (§6.1) would
    have no real signal to compute from in Phase 2C at all. Takes precedence
    over any future `GoalsPort`-sourced tier the same way Reasoning Engine's
    own caller-supplied goals already take precedence over its `GoalsPort`
    result (that design's §7.1)."""


class ArbitrationResult(BaseModel):
    """§4, §7 -- what arbitration produces for one contending request.
    Domain equivalent of `ExecutiveArbitrateReplyPayload`."""

    correlation_id: UUID
    outcome: ArbitrationOutcome
    priority_score: CognitivePriorityScore
    retry_after_ms: float | None = None
    reduced_budget_hint: float | None = None
    policies_applied: list[str] = Field(default_factory=list)
    """§12 -- names of any `ExecutivePolicy` that changed this result from
    what raw composite-score ranking alone would have produced."""


class ContextSwitchEvaluation(BaseModel):
    """§11 -- evaluated before recommending that an already-in-flight,
    lower-priority request be interrupted rather than merely queued. No real
    caller supplies `current_progress` yet (§11's own honest scope note) --
    specified in full now so it has real effect the moment one does."""

    current_progress: float = Field(ge=0.0, le=1.0)
    recovery_cost: float = Field(ge=0.0, le=1.0)
    interruption_impact: float = Field(ge=0.0, le=1.0)
    potential_benefit: float = Field(ge=0.0, le=1.0)
    switch_recommended: bool


class ExecutivePolicy(BaseModel):
    """§12 -- a fixed, named, structural rule, never learned or inferred.
    `absolute` exists because a policy *could*, in principle, be made
    non-absolute by the user -- unlike ADR-028's epistemic-deference
    invariant (§0.5), which is never modeled as a policy at all (§12's own
    closing note)."""

    name: str
    description: str
    absolute: bool = True
    applies_to: Literal["arbitration", "conflict_resolution", "both"]


class HumanOverrideRequest(BaseModel):
    """§13 -- override is available on any executive decision, not only
    low-confidence ones (ADR-025: the user is always the final authority).
    The request that produces an `ExecutiveHumanOverrideAppliedPayload` once
    applied."""

    executive_decision_id: UUID
    action: ExecutiveOverrideAction
    redirect_outcome: ArbitrationOutcome | None = None
    note: str | None = None


class ExecutiveFailureRecovery(BaseModel):
    """§14 -- reuses Reasoning Engine's own six-action failure-recovery
    vocabulary (`FailureAction`) rather than inventing an
    arbitration-specific one."""

    stage: str
    action: FailureAction
    reason: str
    retry_count: int = 0


class ExecutiveDecisionTrace(BaseModel):
    """§18 -- structured metadata *about* an arbitration decision, never the
    domain content of what was arbitrated. Built incrementally as
    arbitration runs, persisted on every outcome -- `proceed`,
    `proceed_reduced`, `wait`, `escalated`, or a failure alike."""

    id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID
    decision_type: ExecutiveDecisionType
    contending_requests: list[ContenderSummary] = Field(default_factory=list)
    priority_scores: dict[UUID, CognitivePriorityScore] = Field(default_factory=dict)
    policies_applied: list[str] = Field(default_factory=list)
    conflict_resolution_signals: ConflictSignals | None = None
    winner_correlation_id: UUID | None = None
    rejected_reasons: dict[UUID, str] = Field(default_factory=dict)
    outcome: ArbitrationOutcome
    human_override: HumanOverrideRequest | None = None
    execution_duration_ms: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    schema_version: int = 1
