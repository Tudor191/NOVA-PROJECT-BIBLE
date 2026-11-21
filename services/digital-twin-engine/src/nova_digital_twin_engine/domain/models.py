"""Domain entities -- not ORM models (docs/design/phase-2d/
06-personal-companion.md, Bible Part 16). This phase's minimal slice of the
eleven Bible Part 16 domains: Communication Profile, a conversation-scoped
Preference Evolution/Habit Detection slice, a correction-frequency trust
metric, and a proactive-communication boundary policy (Sec2's approved
scope) -- every other domain (goals, projects, hardware, software, skills,
knowledge, productivity, general workflow) is Phase 4 (Sec18).

**`CommunicationProfile`'s five learned fields ship at their static
defaults this phase.** Fork A (Sec8) approves the *wire path* for
`verbosity`/`technical_depth`/`terminology_preference` (via
`personality.memory.update`) and `conversation_pacing`/`habit_timing_hint`
(via `digital_twin.preferences.get`), but no evidence source for actually
computing any of the five was approved -- `ConversationMemory`'s free-text
categories (`corrections`/`preferences`/`decisions`/`feedback`) cannot be
turned into a structured value without inventing a text-classification
heuristic, which this project's standing instruction explicitly forbids.
`preference_evolution.evolve_field()` below is the real, fully-tested
mechanism Bible Part 16's "never overwrite immediately, require consistent
evidence" discipline requires -- built and ready, but no production call
site feeds it an inferred candidate yet, mirroring this codebase's own
precedent for a defined-now/wired-later contract (e.g.
`DigitalTwinPreferencesGetReplyPayload`'s own docstring). A future phase
plugs in real evidence extraction additively, once one is approved.

Correction-frequency (`trust_metric.py`) is different: `ConversationMemory
.corrections` is genuine, already-flowing evidence (Phase 2D-D Steps 1-4),
so that metric is real, not deferred.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

__all__ = [
    "PART_16_DOMAIN_ORDER",
    "PHASE_4E_DOMAINS",
    "SHIPPED_2DD_DOMAINS",
    "CommunicationProfile",
    "CompletedSessionEvidence",
    "DomainEvidence",
    "DomainModel",
    "DomainReason",
    "DomainReasonCode",
    "DomainState",
    "EvidenceKind",
    "HabitSignal",
    "PreferenceEvolutionEntry",
    "ProactiveBoundaryPolicy",
    "ProactiveDeliveryRecord",
    "ProactiveSuggestion",
    "ProactiveSuggestionDecision",
    "ProjectModel",
    "TrustMetric",
    "TrustMetricHistoryEntry",
    "TwinDomain",
]


class CommunicationProfile(BaseModel):
    """Bible Part 16's "Communication Style" domain -- current *resolved*
    values, one per user (mirrors personality-engine's own `MemoryProfile`
    shape and defaults exactly, since three of these five fields publish
    directly into it via `personality.memory.update`). `source` mirrors
    `MemoryProfile.source`'s own "static_default" vs a real value
    convention -- `"learned"` only once `preference_evolution.evolve_field`
    has actually promoted at least one field past its default."""

    user_id: UUID
    verbosity: str = "moderate"
    technical_depth: str = "moderate"
    terminology_preference: dict[str, Any] | None = None
    conversation_pacing: str | None = None
    habit_timing_hint: str | None = None
    source: str = "static_default"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PreferenceEvolutionEntry(BaseModel):
    """Bible Part 16's "Digital Twin Memory" -- append-only: what changed,
    when, why, confidence, source. One row per field actually promoted by
    `preference_evolution.evolve_field` (never one row per observation --
    only real changes are recorded)."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    field: str
    previous_value: str | None
    new_value: str
    confidence: float
    source: str
    reason: str
    changed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HabitSignal(BaseModel):
    """Bible Part 16's Habit Detection -- a raw, conversation-scoped
    interaction-timing observation, deliberately *structural* (turn count,
    duration, timestamp), never an inferred label like "morning routine":
    labeling a pattern is exactly the kind of heuristic this phase does not
    invent (see module docstring). Recording the raw observation is still
    genuine, non-fabricated evidence -- a future phase's pattern-detection
    logic can consume this history without this phase guessing at it."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    session_id: UUID
    turn_count: int
    session_duration_seconds: float | None = None
    observed_at: datetime


class CompletedSessionEvidence(BaseModel):
    """This engine's own narrower view of the enriched
    `communication.session.completed` payload (the "port defines its own
    result type" convention every other engine already establishes for a
    wire payload it consumes) -- the sole input to correction-frequency
    (`trust_metric.py`) and, once a future phase approves an evidence
    source, to Preference Evolution."""

    session_id: UUID
    user_id: UUID
    turn_count: int
    corrections: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    feedback: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    closed_at: datetime


class TrustMetric(BaseModel):
    """Fork C (partial, by design): `correction_frequency` is a real,
    evidence-based value (Sec9's formula). `clarification_acceptance_rate`
    and `proactive_suggestion_acceptance_rate` are reserved, nullable,
    and **never computed this phase** -- Bible Part 16's own "every stored
    element should indicate origin, purpose, confidence" applies to
    *absence* of a signal too, so the columns exist now and stay `None`
    rather than being added later as a migration."""

    user_id: UUID
    correction_frequency: float | None = None
    window_session_count: int = 0
    clarification_acceptance_rate: float | None = None
    proactive_suggestion_acceptance_rate: float | None = None
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TrustMetricHistoryEntry(BaseModel):
    """Append-only history for `TrustMetric.correction_frequency`, mirroring
    `PreferenceEvolutionEntry`'s own "every important change becomes part
    of historical evolution" discipline (Bible Part 16)."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    correction_frequency: float | None
    window_session_count: int
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProactiveBoundaryPolicy(BaseModel):
    """Sec10.1 -- user-configured limits on proactive messaging.
    `max_per_topic_per_window` intentionally has no implicit default per
    topic (`proactive_boundary.evaluate_proactive_suggestion` declines
    rather than guessing one, mirroring `maybe_activate_listening`'s own
    "no signal is better than a wrong one" discipline, Doc 22 Principle
    6)."""

    user_id: UUID
    enabled: bool = True
    max_per_topic_per_window: dict[str, int] = Field(default_factory=dict)
    window_hours: int = 24


class ProactiveSuggestion(BaseModel):
    """A proposed proactive message -- content plus the topic tag
    `ProactiveBoundaryPolicy.max_per_topic_per_window` is keyed on."""

    topic: str
    content: str


class ProactiveDeliveryRecord(BaseModel):
    """One row per proactive message this engine has already delivered --
    `proactive_boundary.evaluate_proactive_suggestion`'s own frequency-limit
    check counts these within the policy's configured window. `user_id`
    (Phase 2D-D Step 9, Sec10.2) is required here -- unlike `ProactiveSuggestion`,
    which is never persisted, this type is the one Fork D actually stores
    and queries per user, mirroring every other stored/history model in
    this module (`HabitSignal`, `TrustMetricHistoryEntry`, etc.)."""

    user_id: UUID
    topic: str
    delivered_at: datetime


class ProactiveSuggestionDecision(BaseModel):
    """Sec10.1's pure allow/deny outcome -- always carries `reason`
    (Doc 22 Principle 7: never a silent binary), regardless of the
    verdict."""

    allowed: bool
    reason: str


# ---------------------------------------------------------------------------
# Phase 4E -- Bible Part 16's eleven domains (TDD 4E Sec4, Sec12)
# ---------------------------------------------------------------------------


class TwinDomain(StrEnum):
    """Bible Part 16's eleven domains, named verbatim from its own list
    (Part 16 Secs71-95), in Part 16's own order.

    Eleven, not nine: `COMMUNICATION_STYLE` and `PREFERENCES` shipped in Phase
    2D-D and are listed here so the vocabulary is Part 16's rather than this
    milestone's. 11 - 2 = 9 is exactly what 4E adds (TDD 4E Sec4, Sec0.1.1,
    Sec0.1.2). No domain is renamed, merged, split or invented.
    """

    PERSONAL_WORKFLOW = "personal_workflow"
    PROJECTS = "projects"
    SOFTWARE_ENVIRONMENT = "software_environment"
    HARDWARE_ENVIRONMENT = "hardware_environment"
    KNOWLEDGE_PROFILE = "knowledge_profile"
    SKILL_PROFILE = "skill_profile"
    COMMUNICATION_STYLE = "communication_style"
    PRODUCTIVITY_PATTERNS = "productivity_patterns"
    GOALS = "goals"
    PREFERENCES = "preferences"
    LEARNING_PROGRESS = "learning_progress"


PART_16_DOMAIN_ORDER: tuple[TwinDomain, ...] = tuple(TwinDomain)
"""Part 16's own declaration order, which `GET /domains` renders in. Derived
from the enum rather than restated, so the two cannot drift."""

SHIPPED_2DD_DOMAINS: frozenset[TwinDomain] = frozenset(
    {TwinDomain.COMMUNICATION_STYLE, TwinDomain.PREFERENCES}
)
"""The two already-shipped domains (`CommunicationProfileORM`,
`PreferenceEvolutionHistoryORM`). 4E reports their state from the rows 2D-D
already writes and **changes neither of them** (TDD 4E Sec7's "existing routes
are unchanged")."""

PHASE_4E_DOMAINS: frozenset[TwinDomain] = frozenset(TwinDomain) - SHIPPED_2DD_DOMAINS
"""The nine 4E adds. Computed, so the arithmetic cannot drift from the enum."""


class DomainState(StrEnum):
    """TDD 4E Sec12, ratified. Four states, not three.

    `PARTIALLY_POPULATED` exists because `Knowledge Profile` and `Skill Profile`
    are genuinely half-derived, and 4D's three-state `TrustInputStatus` could not
    say so -- it would have had to round one way or the other, and both roundings
    are a false claim.
    """

    POPULATED = "populated"
    PARTIALLY_POPULATED = "partially_populated"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"


class DomainReasonCode(StrEnum):
    """The machine-readable half of every non-`populated` state (TDD 4E Sec12,
    Sec14.5 control 10).

    Enumerated rather than free text so the panel can render it and a test can
    assert it -- 4D's lesson that a reason string nobody can branch on is a
    comment, not a contract.
    """

    NO_SOURCE_ENGINE = "no_source_engine"
    """No engine in this release produces evidence for this domain at all. Its
    populator is a later milestone's (`Software`/`Hardware Environment` -> 4F's
    `nova-companion`, TDD 4E Sec5.3)."""

    NO_AUTONOMOUS_PRODUCER = "no_autonomous_producer"
    """The subject exists, is real, and is consumed -- but nothing in a stock
    deployment emits it, so no evidence arrives (TDD 4E Sec0.1.4, the CF-11
    shape). Distinct from `NO_SOURCE_ENGINE`: the wiring is real and one
    `POST /v1/perception/observations` would start populating it."""

    NO_EVIDENCE_OBSERVED = "no_evidence_observed"
    """The source is real and reachable, and this user has produced nothing for
    it yet. A new install, not a defect."""

    EVIDENCE_PARTIAL = "evidence_partial"
    """Some fields derived from real evidence; the rest have no source. Always
    accompanied by `DomainModel.unavailable_fields`, so "partial" names *which*
    part rather than leaving the reader to guess."""

    SOURCE_UNAVAILABLE = "source_unavailable"
    """The source could not be reached. Never reported as `EMPTY`: "we asked and
    got nothing" and "we could not ask" are different claims, and 2D-D's own
    discipline is that collapsing them is how a zero becomes a lie."""

    SOURCE_TIMESTAMP_MISSING = "source_timestamp_missing"
    """Evidence arrived without its source's own `created_at`, so it cannot be
    placed on a timeline (TDD 4E Sec0.1.5 -- the field is optional for backwards
    compatibility, and its absence is reported rather than filled in)."""


class DomainReason(BaseModel):
    """An enumerated code plus human-readable detail. Both, always: the code is
    what a test and the panel branch on, the detail is what a person reads."""

    code: DomainReasonCode
    detail: str = Field(min_length=1)


class EvidenceKind(StrEnum):
    """Which real, already-published subject an evidence row came from.

    These are the three subjects TDD 4E Sec8.1 subscribes to, and 4E registers
    **no new subject**. The values are the subject strings themselves so a row's
    provenance is legible without a lookup table.
    """

    MEMORY_LONG_TERM_CREATED = "memory.long_term.created"
    MEMORY_DECISION_RECORDED = "memory.decision.recorded"
    PERCEPTION_ATTENTION_OBSERVED = "perception.attention.observed"


class DomainEvidence(BaseModel):
    """One source record that contributed to one domain's derivation.

    This is what makes Part 16's *"Never create assumptions without evidence"*
    structural rather than aspirational (TDD 4E Sec9): a domain with no rows here
    **cannot** report `populated`, enforced by `DomainModel` below rather than by
    reviewer vigilance.

    **`attributes` never carries memory content.** The three subscribed payloads
    do not include it (TDD 4E Sec5.2), which is a property worth keeping rather
    than an accident: a derived domain that cannot hold a memory's text cannot
    leak one. What it holds is bounded metadata -- a memory type, a knowledge
    node id, an attention state -- all of it already on the wire.
    """

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    domain: TwinDomain
    kind: EvidenceKind
    source_record_id: UUID
    """The `memory_id`/`decision_id` this row came from. Deduplication key: one
    source record contributes at most one row per domain."""

    source_created_at: datetime | None = None
    """When the *source* record was created, not when this row was written. The
    distinction is AC-6's whole subject -- see `observed_at`."""

    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    """When this engine learned of it. For a historically-dated memory this is
    weeks after `source_created_at`, and conflating the two is exactly the error
    that would make a multi-week gap disappear."""

    attributes: dict[str, Any] = Field(default_factory=dict)


class ProjectModel(BaseModel):
    """Bible Part 16's Project Model, derived from `MemoryRecord.project_id` --
    **the only project identity anywhere in this repository** (TDD 4E Sec5.2).

    `last_activity_at` and `gap_days` are AC-6's answer to *"what was I doing on
    Project X"* after a multi-week absence: both are computed from persisted
    `created_at` values carried on `memory.long_term.created`, never from the
    clock at read time and never from when the event was delivered.
    """

    user_id: UUID
    project_id: UUID
    memory_count: int = Field(ge=0)
    memory_type_counts: dict[str, int] = Field(default_factory=dict)
    first_activity_at: datetime | None = None
    last_activity_at: datetime | None = None
    gap_days: float | None = Field(default=None, ge=0.0)
    """Days between `last_activity_at` and `derived_at`. `None` when no evidence
    row carried a timestamp -- never `0.0`, which would read as "active today"
    (2D-D's own rule that absence and zero are different claims)."""

    derived_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _counts_agree_with_evidence(self) -> Self:
        if self.memory_count == 0 and (
            self.first_activity_at is not None or self.last_activity_at is not None
        ):
            raise ValueError(
                "a project with no memories cannot have activity timestamps -- "
                "this is a derivation bug, not a renderable state"
            )
        if (
            self.first_activity_at is not None
            and self.last_activity_at is not None
            and self.first_activity_at > self.last_activity_at
        ):
            raise ValueError("first_activity_at is after last_activity_at")
        return self


class DomainModel(BaseModel):
    """One Part 16 domain's current derived state.

    **The invariants below are TDD 4E Sec14.5 control 5 and control 10, expressed
    as a type rather than as a test.** A derivation bug that would have reported
    an unevidenced domain as `populated` -- the single failure Part 16 Sec69
    forbids -- raises here instead of rendering, so it cannot reach the panel
    even if every test were deleted.

    The per-domain floor (Sec12, ratified Sec19.1) is enforced the same way:
    `Software Environment` and `Hardware Environment` are unrepresentable as
    anything but `empty`/`unavailable`, and `Knowledge Profile`/`Skill Profile`
    cannot claim `populated`.
    """

    user_id: UUID
    domain: TwinDomain
    state: DomainState
    reason: DomainReason | None = None
    evidence_count: int = Field(default=0, ge=0)
    facts: dict[str, Any] = Field(default_factory=dict)
    """What was actually derived -- counts, timestamps, bounded identifier lists.
    Never a memory's content; see `DomainEvidence.attributes`."""

    unavailable_fields: list[str] = Field(default_factory=list)
    """Part 16 fields this domain names that have no evidence source in this
    release. Required whenever the state is `partially_populated`: "partial" is
    not a claim a reader can act on unless it says which part."""

    derived_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _state_is_supported_by_its_evidence(self) -> Self:
        if self.state is DomainState.POPULATED:
            if self.reason is not None:
                raise ValueError(
                    f"{self.domain.value} is populated and still carries a reason: a "
                    "reason explains an absence, and there is none to explain"
                )
            if self.evidence_count == 0:
                raise ValueError(
                    f"{self.domain.value} claims populated with zero evidence rows. "
                    "Part 16: 'Never create assumptions without evidence.'"
                )
        elif self.reason is None:
            raise ValueError(
                f"{self.domain.value} is {self.state.value} without a machine-readable "
                "reason (TDD 4E Sec14.5 control 10)"
            )

        if self.state is DomainState.PARTIALLY_POPULATED:
            if self.evidence_count == 0:
                raise ValueError(
                    f"{self.domain.value} claims partially_populated with zero evidence "
                    "rows -- that is `empty`, and saying otherwise overstates it"
                )
            if not self.unavailable_fields:
                raise ValueError(
                    f"{self.domain.value} is partially_populated without naming which "
                    "fields are unavailable"
                )

        if self.state in (DomainState.EMPTY, DomainState.UNAVAILABLE) and self.facts:
            raise ValueError(
                f"{self.domain.value} is {self.state.value} and still carries derived "
                "facts -- a domain reporting nothing must render nothing, not a default"
            )
        return self

    @model_validator(mode="after")
    def _respects_the_ratified_per_domain_floor(self) -> Self:
        if self.domain in _NO_SOURCE_UNTIL_4F and self.state not in (
            DomainState.EMPTY,
            DomainState.UNAVAILABLE,
        ):
            raise ValueError(
                f"{self.domain.value} reported {self.state.value}. TDD 4E Sec12's "
                "ratified floor permits only empty or unavailable until a real "
                "Phase 4F source exists; anything else is fabricated data"
            )
        if self.domain in _PARTIAL_AT_MOST and self.state is DomainState.POPULATED:
            raise ValueError(
                f"{self.domain.value} reported populated. TDD 4E Sec12's ratified "
                "floor permits partially_populated at most, from real existing data"
            )
        return self


_NO_SOURCE_UNTIL_4F: frozenset[TwinDomain] = frozenset(
    {TwinDomain.SOFTWARE_ENVIRONMENT, TwinDomain.HARDWARE_ENVIRONMENT}
)
"""TDD 4E Sec12/Sec19.1: `empty` or `unavailable` only. No engine reports installed
tooling or hardware inventory in this release."""

_PARTIAL_AT_MOST: frozenset[TwinDomain] = frozenset(
    {TwinDomain.KNOWLEDGE_PROFILE, TwinDomain.SKILL_PROFILE}
)
"""TDD 4E Sec12/Sec19.1: derivable only in part, and only from real existing data."""
