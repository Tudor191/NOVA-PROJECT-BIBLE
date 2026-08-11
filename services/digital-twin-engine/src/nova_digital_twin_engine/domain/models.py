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
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

__all__ = [
    "CommunicationProfile",
    "CompletedSessionEvidence",
    "HabitSignal",
    "PreferenceEvolutionEntry",
    "ProactiveBoundaryPolicy",
    "ProactiveDeliveryRecord",
    "ProactiveSuggestion",
    "ProactiveSuggestionDecision",
    "TrustMetric",
    "TrustMetricHistoryEntry",
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
    check counts these within the policy's configured window."""

    topic: str
    delivered_at: datetime


class ProactiveSuggestionDecision(BaseModel):
    """Sec10.1's pure allow/deny outcome -- always carries `reason`
    (Doc 22 Principle 7: never a silent binary), regardless of the
    verdict."""

    allowed: bool
    reason: str
