"""Bible Part 6's cognitive state, as types.

Three subsystems, named exactly as Part 6 names them:

* **Active Thoughts** (Part 6 lines 101-137) -- *"a collection of Active
  Thoughts... Each thought represents an ongoing reasoning process."* Every
  field Part 6 lists is present and none is invented: priority, confidence,
  dependencies, estimated completion, related memories, related projects,
  current progress.
* **Attention Layers** (lines 165-189) -- five, in Part 6's own order, with
  *"Thoughts move naturally between layers."* The movement rules live in
  `attention.py`.
* **The Focus System** (lines 139-163) -- *"Only a limited number of cognitive
  processes receive maximum computational attention."* The selection lives in
  `focus.py`.

**What this module deliberately does not have.** No execution verb, no
capability reference, and no way to *do* anything. TDD 4F §6.2 is explicit that
this engine *proposes* and never acts. Since Phase 4F.6 a thought **may carry a
`ProposedAction`** -- an authored proposal naming a permission category, a risk
tier and three execution fields -- because §6.2 lists *"an action type"*,
*"subject / context"* and *"a rationale"* among what this engine **MAY
produce**, and a `DecisionRequest` cannot be built without them (A-4F6-2a).
**A proposal is data, not a verb**: nothing here can execute it, only
`autonomy-engine` can decide on it, and only `action-engine` can run it. The
`DecisionRequest` itself is still `autonomy-engine`'s type, not one defined
here.

*(Until 4F.6 this paragraph read: "No execution verb, no action type, no
capability reference, no way to express "do this". ... the cheapest way to keep
that true is for the vocabulary to be unable to say otherwise." That was true
until 4F.6 ratified `ProposedAction`, which makes the "no action type" clause
false. Preserved per protocol §0.3.4.)*

**Invariants are validators, not conventions** -- Phase 4E's lesson (TDD 4E
§1.2, carried forward by TDD 4F §16). A thought that claims progress it cannot
have, or depends on itself, raises at construction rather than reaching the
panel.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from nova_contracts.events.action import ActionType
from nova_contracts.events.autonomy import PermissionCategory
from nova_contracts.events.planning import RiskLevel
from pydantic import BaseModel, Field, model_validator

__all__ = [
    "ATTENTION_LAYER_ORDER",
    "FOCUSABLE_LAYERS",
    "ActiveThought",
    "AttentionLayer",
    "FocusInputs",
    "FocusSignal",
    "FocusedThought",
    "ProposedAction",
]


class AttentionLayer(StrEnum):
    """Part 6 lines 165-189, verbatim and in the Bible's own order.

    The order is the ladder `attention.py` moves thoughts along, so it is
    declared once here rather than re-derived anywhere else.
    """

    IMMEDIATE = "immediate"
    """*"Critical events requiring instant action."*"""

    ACTIVE = "active"
    """*"Current tasks."*"""

    PASSIVE = "passive"
    """*"Background monitoring."*"""

    DORMANT = "dormant"
    """*"Information stored for future use."*"""

    ARCHIVED = "archived"
    """*"Historical information no longer requiring active processing."*"""


ATTENTION_LAYER_ORDER: tuple[AttentionLayer, ...] = (
    AttentionLayer.IMMEDIATE,
    AttentionLayer.ACTIVE,
    AttentionLayer.PASSIVE,
    AttentionLayer.DORMANT,
    AttentionLayer.ARCHIVED,
)
"""Most attention first. `StrEnum` iteration order already matches, but the
ladder is what `attention.py` and `focus.py` both depend on, so it is stated
as data rather than inferred from declaration order."""


FOCUSABLE_LAYERS: frozenset[AttentionLayer] = frozenset(
    {AttentionLayer.IMMEDIATE, AttentionLayer.ACTIVE}
)
"""The only layers the Focus System may draw from.

Part 6 defines `PASSIVE` as *"background monitoring"*, `DORMANT` as
*"information stored for future use"* and `ARCHIVED` as *"no longer requiring
active processing"* -- none of which is a description of something receiving
*"maximum computational attention"*. An allow-list rather than a deny-list, so
a layer added later is excluded by default: the same fail-closed shape Phase 4E
used for its privacy levels."""


class FocusSignal(StrEnum):
    """The seven inputs Part 6 lines 147-161 names, and only those.

    Part 6 says focus *"changes dynamically according to"* these seven. It
    assigns them **no weights**, so neither does this module -- see
    `focus.combine_signals` for why equal weighting is the honest reading
    rather than a modelling choice.
    """

    USER_ACTIVITY = "user_activity"
    TASK_IMPORTANCE = "task_importance"
    DEADLINES = "deadlines"
    SYSTEM_HEALTH = "system_health"
    CURRENT_RISKS = "current_risks"
    AGENT_WORKLOAD = "agent_workload"
    LEARNING_OPPORTUNITIES = "learning_opportunities"


class ProposedAction(BaseModel):
    """An action a thought **proposes**, authored in full -- Phase 4F.6,
    A-4F6-2a.

    **All-or-nothing.** Every field but `detail` is required, so a partial
    proposal fails at construction instead of being completed by guesswork. A
    thought carries a complete one or none at all, and **a thought with none
    never triggers** -- absence is never read as a low-risk default, the same
    fail-closed reading as *"absent policy means approval"*.

    **Every value is authored, and none is derived.** In particular `risk` is
    **never** computed from `confidence`, `priority`, `current_progress` or the
    Focus System's `current_risks` signal: that signal is a 0.0-1.0 ranking
    weight, not a `RiskLevel`, and coercing one into the other would fabricate
    the tier every downstream gate is evaluated against.

    The three shared vocabularies come from `nova-contracts`, never from
    `autonomy-engine` (ADR-004): `PermissionCategory` is canonical in
    `events/autonomy.py`, `RiskLevel` in `events/planning.py`, and `ActionType`
    is `action.execute`'s own literal, so a type `action-engine` could never run
    is rejected here rather than at dispatch.
    """

    category: PermissionCategory
    risk: RiskLevel
    action_type: ActionType
    execution_target: str = Field(min_length=1)
    verification_method: str = Field(min_length=1)
    title: str = Field(min_length=1)
    detail: str = ""


class ActiveThought(BaseModel):
    """*"Each thought represents an ongoing reasoning process."* (Part 6:103)

    Every field Part 6's *"Each thought should have"* list names is here.
    `description` and the identity/bookkeeping fields are this implementation's;
    they carry no semantics Part 6 does not imply.
    """

    thought_id: UUID
    user_id: UUID
    """ADR-025: one trusted user per instance. The column exists because the
    schema is keyed by it, **not** because 4F introduces multi-user."""

    description: str = Field(min_length=1)
    """Part 6's own examples are descriptions -- *"Improve deployment
    architecture"*, *"Monitor Docker containers"*. Non-empty because a thought
    nobody can read is not an ongoing reasoning process."""

    priority: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    dependencies: tuple[UUID, ...] = ()
    estimated_completion: datetime | None = None
    """`None` is an honest *"not estimated"*. Phase 4E's discipline: an unknown
    is represented, never guessed."""

    related_memories: tuple[UUID, ...] = ()
    related_projects: tuple[UUID, ...] = ()
    current_progress: float = Field(ge=0.0, le=1.0)

    attention_layer: AttentionLayer
    created_at: datetime
    updated_at: datetime

    proposed_action: ProposedAction | None = None
    """**Phase 4F.6.** `None` is the honest *"this thought proposes no
    action"* and is the only state in which the trigger can never fire. A
    partial proposal is not representable: `ProposedAction`'s own fields are
    required. **No existing field changes meaning.**"""

    @model_validator(mode="after")
    def _cannot_depend_on_itself(self) -> Self:
        if self.thought_id in self.dependencies:
            raise ValueError(
                f"thought {self.thought_id} lists itself as a dependency; a "
                "self-dependency can never be satisfied"
            )
        return self

    @model_validator(mode="after")
    def _relations_are_sets(self) -> Self:
        """Duplicates in any of the three relation tuples are rejected rather
        than silently deduplicated: a repeated dependency means the producer
        believes something the model does not, and quietly collapsing it hides
        that."""
        for field, values in (
            ("dependencies", self.dependencies),
            ("related_memories", self.related_memories),
            ("related_projects", self.related_projects),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"{field} contains duplicate ids: {values!r}")
        return self

    @model_validator(mode="after")
    def _archived_thoughts_are_not_in_progress(self) -> Self:
        """Part 6 defines `ARCHIVED` as *"historical information no longer
        requiring active processing"*. A thought that is simultaneously
        archived and partially progressing is the one combination those words
        forbid, so it is unconstructible rather than merely discouraged.

        Progress of exactly `0.0` or `1.0` is permitted: never started, or
        finished and filed."""
        if self.attention_layer is AttentionLayer.ARCHIVED and 0.0 < self.current_progress < 1.0:
            raise ValueError(
                f"thought {self.thought_id} is archived at progress "
                f"{self.current_progress}; Part 6 defines archived as 'no longer "
                "requiring active processing', so partial progress cannot be archived"
            )
        return self

    @model_validator(mode="after")
    def _updated_at_is_not_before_created_at(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError(
                f"thought {self.thought_id} was updated at {self.updated_at}, "
                f"before it was created at {self.created_at}"
            )
        return self


class FocusInputs(BaseModel):
    """The seven Part 6 signals, as scores the caller supplies.

    **This engine does not compute these in 4F.1**, and the type is shaped so
    that absence is visible: a signal not supplied is `None`, not `0.0`. A
    missing signal and a signal that is genuinely zero are different claims,
    and collapsing them is how a degraded input starts looking like a confident
    one -- the same failure mode 4D's Trust Engine avoids by reporting
    unavailable rather than `0.0` (CF-10).
    """

    user_activity: float | None = Field(default=None, ge=0.0, le=1.0)
    task_importance: float | None = Field(default=None, ge=0.0, le=1.0)
    deadlines: float | None = Field(default=None, ge=0.0, le=1.0)
    system_health: float | None = Field(default=None, ge=0.0, le=1.0)
    current_risks: float | None = Field(default=None, ge=0.0, le=1.0)
    agent_workload: float | None = Field(default=None, ge=0.0, le=1.0)
    learning_opportunities: float | None = Field(default=None, ge=0.0, le=1.0)

    def supplied(self) -> dict[FocusSignal, float]:
        """Only the signals that were actually given. An empty dict is a valid
        and meaningful answer -- see `focus.combine_signals`."""
        by_signal = {
            FocusSignal.USER_ACTIVITY: self.user_activity,
            FocusSignal.TASK_IMPORTANCE: self.task_importance,
            FocusSignal.DEADLINES: self.deadlines,
            FocusSignal.SYSTEM_HEALTH: self.system_health,
            FocusSignal.CURRENT_RISKS: self.current_risks,
            FocusSignal.AGENT_WORKLOAD: self.agent_workload,
            FocusSignal.LEARNING_OPPORTUNITIES: self.learning_opportunities,
        }
        return {signal: value for signal, value in by_signal.items() if value is not None}


class FocusedThought(BaseModel):
    """One entry in the focus set, carrying why it is there.

    The score and the signals that produced it travel with the thought so the
    panel can show *why* something holds NOVA's attention rather than only
    *that* it does -- Part 6's Thinking Visualization requirement in the small.
    """

    thought: ActiveThought
    score: float = Field(ge=0.0)
    signals_used: tuple[FocusSignal, ...]
    """Empty when no signal was supplied: the ranking then rests on priority
    alone, and saying so is more useful than implying evidence that was absent."""
