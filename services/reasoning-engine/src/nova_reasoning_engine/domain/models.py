"""Domain entities -- not ORM models (docs/design/phase-2b/00-reasoning-engine.md
§1, §20). `ReasoningMode`, `ReasoningOutcome`, `FailureAction`, `OverrideAction`,
and `ConstraintKind` are re-exported from `nova_contracts.events.reasoning` rather
than redefined here, the same shared-enum convention every prior engine follows
for cross-cutting classification schemes (e.g. `PrivacyLevel`).

`MemoryReference` and `WorldModelSnapshot` (§7.3, §7.2), along with
`PersonalContext` (§7.5), are re-exported from `nova_contracts.entities` rather
than redefined here, as of a design review (`docs/design/nova-service-kit/
boilerplate-extraction-proposal.md` Extraction E) that confirmed they are
genuinely semantically identical to Executive Cognition Engine's own copies --
not merely coincidentally similar in shape: both engines' `clients/`
implementations call the same upstream subject/payload with byte-identical
translation logic. This is the same sanctioned shared-vocabulary exception to
ADR-004 the enum re-exports above already rely on, not a new kind of
cross-engine dependency -- neither engine imports the other's internals; both
import a third, neutral package. `KnowledgeReference` (§7.4) has no equivalent
anywhere else in the repository and stays local, unextracted.

**The boundary this file exists to enforce** (ADR-026, design doc §0): every
model here either describes *this engine's own reasoning process* (a
`ReasoningProcess`, a `Hypothesis`, a `Decision`, a `ReasoningTrace`) or is a
lightweight *reference* into another engine's owned data (`MemoryReference`,
`KnowledgeReference`, `WorldModelSnapshot` -- IDs and summaries, never full
content). If a future change to this file would make it cache a memory's full
content, a knowledge node's full properties, or persist World Model state
independently, it belongs in a different engine instead -- this engine never
becomes another storage layer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from nova_contracts.entities import MemoryReference, PersonalContext, WorldModelSnapshot
from nova_contracts.events.reasoning import (
    ConstraintKind,
    FailureAction,
    OverrideAction,
    ReasoningMode,
    ReasoningOutcome,
)
from pydantic import BaseModel, Field

__all__ = [
    "Alternative",
    "ConfidenceBreakdown",
    "Constraint",
    "ContextBundle",
    "Decision",
    "DecisionExplanation",
    "DecisionMatrixScores",
    "Evidence",
    "FailureAction",
    "FailureRecovery",
    "Goal",
    "HumanOverrideRequest",
    "Hypothesis",
    "HypothesisGenerationRequest",
    "KnowledgeReference",
    "LifecycleStatus",
    "MemoryReference",
    "ModeConfig",
    "MultiStepConfig",
    "OverrideAction",
    "PersonalContext",
    "ReasoningMode",
    "ReasoningOutcome",
    "ReasoningProcess",
    "ReasoningRequest",
    "ReasoningTrace",
    "WorldModelSnapshot",
]

# Design doc §5's Decision Lifecycle state machine -- distinct from the Cognitive
# Pipeline's own processing steps (§4).
LifecycleStatus = Literal[
    "received",
    "context_assembling",
    "hypotheses_generating",
    "alternatives_evaluating",
    "decision_scoring",
    "awaiting_human_override",
    "decided",
    "degraded",
    "failed",
    "abandoned",
]


class Goal(BaseModel):
    """One Current Goal, as read from `GoalsPort` (§7.1, §8) -- a caller-supplied
    placeholder until Planning Engine exists."""

    id: UUID
    description: str
    priority: float = Field(ge=0.0, le=1.0)


class Constraint(BaseModel):
    """A hard gate applied before scoring, never blended into the Decision Matrix
    (§9). `hard=False` contributes a scoring penalty instead of a filter."""

    kind: ConstraintKind
    description: str
    hard: bool = True


class KnowledgeReference(BaseModel):
    """§7.4 -- carries Knowledge Engine's own node ID and its maturity layer
    (Phase 1, ADR-015), used by Confidence Estimation's `knowledge_quality` factor
    (§10) -- never a duplicate of the node's own properties."""

    node_id: str
    name: str
    layer: str
    confidence: float = Field(ge=0.0, le=1.0)
    related_node_ids: list[str] = Field(default_factory=list)


class ContextBundle(BaseModel):
    """The output of `context_assembly.py`'s parallel fan-out (§7) -- everything
    the rest of the pipeline reasons over. Assembled once per `ReasoningProcess`,
    never re-fetched per hypothesis (§13)."""

    memories: list[MemoryReference] = Field(default_factory=list)
    knowledge: list[KnowledgeReference] = Field(default_factory=list)
    world_model: WorldModelSnapshot | None = None
    personal_context: PersonalContext | None = None
    goals: list[Goal] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)


class ReasoningRequest(BaseModel):
    """Domain equivalent of `nova_contracts.ReasoningRequestPayload` -- the
    boundary-validated shape `pipeline.run()` actually operates on."""

    objective_text: str
    user_id: UUID
    requesting_engine: str
    correlation_id: UUID = Field(default_factory=uuid4)
    reasoning_mode_hint: ReasoningMode | None = None
    reasoning_level_hint: int | None = Field(default=None, ge=1, le=4)
    thinking_mode_hint: str | None = None
    goals: list[Goal] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    parent_process_id: UUID | None = None
    prior_nova_utterance: str | None = None
    """Phase 2D-D (docs/design/phase-2d/06-personal-companion.md Sec5.2) --
    mirrors `nova_contracts.ReasoningRequestPayload`'s own field of the same
    name. Threaded into `HypothesisGenerationRequest` unchanged; see
    `hypothesis_generation.py` for how it's used."""


class ReasoningProcess(BaseModel):
    """One `reasoning.reasoning_process` row (§20) -- the persisted identity a
    `ReasoningTrace` and `Decision` both hang off of."""

    id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID
    requesting_engine: str
    user_id: UUID
    parent_process_id: UUID | None = None
    objective_text: str
    reasoning_mode: ReasoningMode
    reasoning_level: int
    status: LifecycleStatus = "received"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


class HypothesisGenerationRequest(BaseModel):
    """§12 -- the only pipeline step that legitimately calls a model, since
    generating candidate explanations *is* the cognitive task Bible Part 8
    assigns this engine, not a meta-decision about how to reason."""

    objective: str
    context: ContextBundle
    minimum_hypotheses: int = 3
    thinking_mode_hint: str | None = None
    prior_nova_utterance: str | None = None
    """Phase 2D-D Sec5.2/5.3 -- when set, `generate_hypotheses` adds one more
    prompt context component and asks the same model call to also judge
    whether `objective` corrects `prior_nova_utterance` (Sec5.1's exact,
    narrow definition). `None` (the default for every caller except
    `communication-engine` mid-conversation) means no such judgment is
    requested at all."""


class Hypothesis(BaseModel):
    """One `reasoning.hypothesis` row (§20)."""

    id: UUID = Field(default_factory=uuid4)
    reasoning_process_id: UUID
    description: str
    status: Literal["investigating", "supported", "unsupported"] = "investigating"


class Evidence(BaseModel):
    """One `reasoning.evidence` row (§13, §20). `source_ref` is the upstream
    engine's own ID -- never duplicated content -- and `weight` is derived from
    that source's own reliability signal, never a weight this engine invents."""

    id: UUID = Field(default_factory=uuid4)
    hypothesis_id: UUID
    source: Literal["memory", "knowledge", "world_model", "user_input"]
    source_ref: str
    weight: float = Field(ge=0.0, le=1.0)


class Alternative(BaseModel):
    """§14 -- a concrete candidate decision, converted from a supported
    `Hypothesis`. `reasoning_process_id` is not in the design doc's own §14
    code block, but §20's DDL requires it as a direct NOT NULL foreign key
    (every other persisted entity is scoped to its owning process the same
    way) -- added here to make the domain model actually persistable against
    its own schema, the same class of internal design-doc gap this project's
    standing discipline resolves in the open rather than silently."""

    id: UUID = Field(default_factory=uuid4)
    reasoning_process_id: UUID
    hypothesis_id: UUID
    description: str
    supporting_evidence_ids: list[UUID] = Field(default_factory=list)
    constraint_status: Literal["eligible", "rejected_constraint_violation"] = "eligible"
    matrix_scores: DecisionMatrixScores | None = None


class DecisionMatrixScores(BaseModel):
    """§15 -- Bible Part 8's twelve-criteria weighted Decision Matrix, plus
    optional `goal_alignment` (§8, omitted rather than defaulted when no goals
    were supplied) and the weighted `composite` score."""

    accuracy: float
    complexity: float  # lower is better; stored as an inverted score
    maintainability: float
    performance: float
    security: float
    scalability: float
    development_effort: float  # lower is better; inverted
    future_flexibility: float
    cost: float  # lower is better; inverted
    user_experience: float
    compatibility: float
    reliability: float
    goal_alignment: float | None = None
    composite: float = 0.0


class ConfidenceBreakdown(BaseModel):
    """§10 -- Bible Part 8's seven confidence factors, structurally computed,
    never a model's self-reported confidence. `historical_success` and
    `model_agreement` are `None`, not `0.0`, when no signal exists yet -- absence
    is visible, never silently defaulted to a penalizing zero."""

    evidence_quality: float
    evidence_quantity: float
    historical_success: float | None = None
    model_agreement: float | None = None
    memory_consistency: float
    knowledge_quality: float
    reasoning_completeness: float
    predicted_uncertainty: float
    composite: float = 0.0


class DecisionExplanation(BaseModel):
    """§16 -- derived mechanically from already-computed structured fields,
    never authored independently."""

    chosen_reason: str
    rejected_reasons: dict[UUID, str] = Field(default_factory=dict)
    strongest_evidence: list[UUID] = Field(default_factory=list)
    remaining_uncertainty: str


class Decision(BaseModel):
    """One `reasoning.decision` row (§20) -- this pipeline's final artifact.
    `selected_alternative_id` is `None` for `abandoned`/`failed` outcomes."""

    id: UUID = Field(default_factory=uuid4)
    reasoning_process_id: UUID
    selected_alternative_id: UUID | None = None
    explanation: DecisionExplanation
    confidence_score: float = Field(ge=0.0, le=1.0)
    human_override: HumanOverrideRequest | None = None
    is_correction: bool | None = None
    """Phase 2D-D Sec5.1 -- carried straight from `generate_hypotheses`'s own
    judgment (via `pipeline.run()`, computed once per process, not
    per-alternative). `None` when no judgment was attempted (no
    `prior_nova_utterance` on the request, or the process failed before
    hypothesis generation ran)."""


class MultiStepConfig(BaseModel):
    """§11 -- recursion with a hard depth cap, never an unbounded loop."""

    max_depth: int = 3
    parent_process_id: UUID | None = None


class FailureRecovery(BaseModel):
    """§17 -- Bible Part 8's failure-recovery action set. Every failure still
    produces a `ReasoningTrace` (§19) -- failure is a recorded outcome, not a
    process with no record."""

    stage: str
    action: FailureAction
    reason: str
    retry_count: int = 0


class HumanOverrideRequest(BaseModel):
    """§18 -- override is available on any decision, not only low-confidence
    ones (ADR-025: the user is always the final authority)."""

    reasoning_process_id: UUID
    action: OverrideAction
    redirect_alternative_id: UUID | None = None
    note: str | None = None


class ReasoningTrace(BaseModel):
    """§19 -- the structured reasoning trace: metadata *about* the process, not
    a chain-of-thought transcript *of* it. Built incrementally as the pipeline
    runs, on every run, success or failure alike."""

    id: UUID = Field(default_factory=uuid4)
    reasoning_process_id: UUID
    correlation_id: UUID
    reasoning_mode: ReasoningMode
    reasoning_level: int
    retrieved_memory_ids: list[UUID] = Field(default_factory=list)
    knowledge_ids: list[str] = Field(default_factory=list)
    world_model_entities: list[str] = Field(default_factory=list)
    goals_considered: list[UUID] = Field(default_factory=list)
    constraints_considered: list[Constraint] = Field(default_factory=list)
    selected_capabilities: list[str] = Field(default_factory=list)
    """§25 -- placeholder field until Capability Engine (Bible Part 15) exists."""
    confidence_score: float
    confidence_breakdown: ConfidenceBreakdown
    execution_duration_ms: float
    model_used: str | None = None
    alternatives_evaluated: list[UUID] = Field(default_factory=list)
    alternatives_rejected: dict[UUID, str] = Field(default_factory=dict)
    final_decision_explanation: str
    steps: list[ReasoningTrace] = Field(default_factory=list)  # §11
    outcome: ReasoningOutcome
    multistep_recursion_exhausted: bool = False
    """Phase 3A -- `True` when this trace (or a descendant in `steps`) hit
    `MultiStepConfig.max_step_depth` while its own confidence was still
    below `verify_threshold`, so no further recursion was attempted.
    Domain-only (never published on the Event Bus): `observability.py`'s
    own module docstring is explicit that `domain/` may never import it,
    so this field is how the one internal fact the recursion-exhausted
    metric needs crosses that boundary -- the API/event layer reads it off
    the already-returned trace, the same way `reasoning_requests_total` is
    already derived from `trace.outcome` today, rather than a new
    injected-callback mechanism."""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    schema_version: int = 1  # ADR-024


class ModeConfig(BaseModel):
    """§6 -- one Reasoning Mode's own configuration of which pipeline steps
    run, how deep, and with what cost budget. `pipeline.py` dispatches to the
    selected mode's `ModeConfig` rather than branching internally on mode
    throughout the pipeline (§2)."""

    mode: ReasoningMode
    minimum_hypotheses: int = 3
    skip_hypothesis_generation: bool = False  # Reactive (§6): no alternatives generated
    require_goals: bool = False  # Goal-driven, Strategic (§6): meaningless without goals
    goal_weight_boost: bool = False  # Goal-driven (§6): foregrounds goal alignment
    engage_self_evaluation: bool = False  # Self-evaluation (§6): runs as a first-class step
    max_step_depth: int = 1  # Multi-step (§11): >1 engages recursion
    default_confidence_penalty: float = 0.0
    """Long-term planning (§6): wider horizon, less certainty by construction."""
