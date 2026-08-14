"""Reasoning Engine event payloads (Bible Part 8), per
docs/design/phase-2b/00-reasoning-engine.md §19 (the structured reasoning
trace), §20 (data model), and §23 (APIs/events).

`ReasoningMode` mirrors design doc §6's ten-mode taxonomy exactly -- the
canonical, structural set this engine's domain layer dispatches on, distinct
from Bible Part 8's own "Levels of Reasoning" (a cost/depth dial, carried here
as a plain `int` field, not an enum) and "Thinking Modes" (a domain-flavor
hint, carried as free-text `thinking_mode_hint`) -- see design doc §6 for the
full reconciliation of all three.

Every payload here carries `schema_version: int = 1` from its first commit
(ADR-024), the same discipline every Phase 2A payload already follows.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from nova_contracts.registry import register_payload


class ReasoningMode(StrEnum):
    """Design doc §6's ten reasoning-mode taxonomy."""

    REACTIVE = "reactive"
    ANALYTICAL = "analytical"
    STRATEGIC = "strategic"
    LONG_TERM_PLANNING = "long_term_planning"
    GOAL_DRIVEN = "goal_driven"
    CONSTRAINT_BASED = "constraint_based"
    MULTI_STEP = "multi_step"
    REFLECTIVE = "reflective"
    SELF_EVALUATION = "self_evaluation"
    COLLABORATIVE = "collaborative"


class ReasoningOutcome(StrEnum):
    """Design doc §5's four terminal lifecycle states."""

    DECIDED = "decided"
    DEGRADED = "degraded"
    FAILED = "failed"
    ABANDONED = "abandoned"


class FailureAction(StrEnum):
    """Design doc §17's Bible Part 8 failure-recovery action set."""

    RESTART = "restart"
    REDUCE_COMPLEXITY = "reduce_complexity"
    REQUEST_CLARIFICATION = "request_clarification"
    DELEGATE = "delegate"
    RETRIEVE_MORE_KNOWLEDGE = "retrieve_more_knowledge"
    ESCALATE_DEEPER = "escalate_deeper"


class OverrideAction(StrEnum):
    """Design doc §18's human-override action set."""

    CONFIRM = "confirm"
    REDIRECT = "redirect"
    REJECT = "reject"


class ConstraintKind(StrEnum):
    """Design doc §9's constraint sources."""

    BUDGET = "budget"
    PRIVACY = "privacy"
    TIME = "time"
    RESOURCE = "resource"
    POLICY = "policy"


class GoalPayload(BaseModel):
    """Design doc §8 -- one Current Goal, as read from `GoalsPort`
    (a caller-supplied placeholder until Planning Engine exists, §7.1)."""

    id: UUID
    description: str
    priority: float = Field(ge=0.0, le=1.0)


class ConstraintPayload(BaseModel):
    """Design doc §9 -- a hard gate applied before scoring, never blended into
    the Decision Matrix. `hard=False` constraints instead contribute a scoring
    penalty (not implemented as a gate) -- see design doc §9."""

    kind: ConstraintKind
    description: str
    hard: bool = True


@register_payload("reasoning.reason.request")
class ReasoningRequestPayload(BaseModel):
    """Event Bus RPC counterpart to `POST /v1/reasoning/reason` (design doc
    §23) -- for callers (e.g. a future Planning Engine, §7.1) that prefer
    request/reply over HTTP."""

    objective_text: str
    user_id: UUID
    requesting_engine: str
    correlation_id: UUID = Field(default_factory=uuid4)
    reasoning_mode_hint: ReasoningMode | None = None
    reasoning_level_hint: int | None = Field(default=None, ge=1, le=4)
    thinking_mode_hint: str | None = None
    goals: list[GoalPayload] = Field(default_factory=list)
    constraints: list[ConstraintPayload] = Field(default_factory=list)
    parent_process_id: UUID | None = None
    """Design doc §11 -- set when this request is one step of a Multi-step
    reasoning chain."""
    prior_nova_utterance: str | None = None
    """Phase 2D-D (docs/design/phase-2d/06-personal-companion.md §5.2) --
    the requesting session's most recent outbound turn, when the caller is
    `communication-engine` mid-conversation. Optional and additive
    (ADR-024): a future Planning Engine caller (§7.1's own docstring) never
    populates this, since it has no conversation session at all. Used only
    to give `hypothesis_generation.py`'s existing model call the context it
    needs to judge whether the current objective corrects a prior NOVA
    statement (`is_correction` on the reply below) -- never persisted by
    this engine itself, never used for any other purpose."""
    schema_version: int = 1


@register_payload("reasoning.reason.reply")
class ReasoningReplyPayload(BaseModel):
    reasoning_process_id: UUID
    decision_id: UUID | None = None
    chosen_description: str | None = None
    explanation: str | None = None
    confidence_score: float | None = None
    outcome: ReasoningOutcome
    trace_id: UUID | None = None
    error: str | None = None
    """Set only when `outcome` is `failed`/`abandoned` -- an informative
    reply, not a bus timeout with no diagnostic (the same additive pattern
    ADR-024 established for `GenerateReplyPayload.error` in Phase 2A)."""
    is_correction: bool | None = None
    """Phase 2D-D §5.1 -- set only when `prior_nova_utterance` was supplied
    on the request; `None` means no judgment was attempted (no prior
    utterance existed, or the process degraded/failed before hypothesis
    generation ran), not "not a correction." `True` means this engine's own
    model call judged the current objective as substantively contradicting
    or correcting content NOVA itself previously delivered -- never set for
    mere uncertainty, disagreement, a clarification request, or the user
    correcting their own prior statement (§5.1's exact exclusions)."""
    schema_version: int = 1


@register_payload("reasoning.process.completed")
class ReasoningProcessCompletedPayload(BaseModel):
    """Published for every terminal outcome that produced a decision --
    `decided` or `degraded` alike (design doc §5) -- the event-bus mirror of
    the `reasoning_process`/`decision` rows `ReasoningRepository` persists."""

    reasoning_process_id: UUID
    correlation_id: UUID
    requesting_engine: str
    user_id: UUID
    reasoning_mode: ReasoningMode
    reasoning_level: int
    confidence_score: float
    execution_duration_ms: float
    outcome: ReasoningOutcome
    objective_text: str
    """Phase 3B Fork 3B-4 (docs/design/phase-3/
    10-3b-4-resolution-and-preimplementation-verification.md §4, §15-16) --
    carried verbatim from `ReasoningProcess.objective_text` so
    a downstream consumer (`planning-engine`) can seed decomposition without
    a synchronous read-back call, keeping this edge additive and
    event-driven rather than introducing a new RPC. Additive per ADR-024 --
    no `schema_version` bump. **Potentially privacy-sensitive**
    (user-content-derived): `PrivacyLevel` propagation on this payload was
    considered and explicitly deferred, not silently added -- see this
    engine's README "Known limitations" for the recorded follow-up
    requirement before any objective above `PrivacyLevel.INTERNAL` (today's
    hardcoded default; no real caller can set it higher yet) is allowed to
    flow through this path in production."""
    chosen_description: str | None = None
    """Same rationale and privacy note as `objective_text` above -- the
    chosen alternative's own `description`. Both of this payload's current
    publish sites (`domain/pipeline.py`'s Reactive and main paths) always
    populate a real value in practice -- `_resolve_reactive` always
    constructs exactly one `Alternative`, and the main path only reaches
    `_completed_outbox_event` after confirming at least one eligible
    alternative exists. Optional here, not because either path leaves it
    unset today, but to mirror `ReasoningReplyPayload.chosen_description`'s
    already-established shape (which genuinely can be `None`, for
    `abandoned`/`failed` outcomes never reaching a chosen alternative) and
    to stay defensive against a future call site that might."""
    schema_version: int = 1


@register_payload("reasoning.process.failed")
class ReasoningProcessFailedPayload(BaseModel):
    """Published when Failure Recovery (design doc §17) cannot produce any
    decision -- `outcome in {"failed", "abandoned"}`."""

    reasoning_process_id: UUID
    correlation_id: UUID
    requesting_engine: str
    stage: str
    action: FailureAction
    reason: str
    retry_count: int = 0
    schema_version: int = 1


@register_payload("reasoning.human_override.applied")
class HumanOverrideAppliedPayload(BaseModel):
    """Design doc §18 -- published whenever a human confirms, redirects, or
    rejects a decision awaiting override."""

    reasoning_process_id: UUID
    action: OverrideAction
    redirect_alternative_id: UUID | None = None
    note: str | None = None
    schema_version: int = 1
