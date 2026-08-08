"""Addressee-detection fusion (docs/design/phase-2d/
04-conversation-intelligence.md Sec4) -- fuses Phase 2D-B's
`perception.addressee_signal.candidate` signal with World Model's
`present_identities` corroboration and this engine's own live session state
into a confidence-scored `high`/`uncertain`/`low` outcome. Pure, deterministic,
no model call (Master Blueprint Sec13.7's "quality over feature count" -- a
deterministic rule table, the same discipline `personality-engine`'s own
Style Selector already established).

Voice channel only -- text has no addressee ambiguity (Sec4's own scope
statement); the explicit trigger (`domain/models.py::InboundMessageKind.
TRIGGER_START`/`TRIGGER_STOP`) remains available unconditionally, alongside
fusion, never replaced by it (Doc 22 Principle 5 -- wake-word/trigger
detection is one signal, never the only one a design may depend on).

Doc 22 Principle 6's asymmetric cost (a false-positive response is strictly
worse than a false-negative) is encoded in `DEFAULT_WEIGHTS.high_threshold`
sitting well above the sum of any two signals alone -- no single signal, or
even any two together at typical confidence, can reach `high` unassisted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

__all__ = [
    "DEFAULT_WEIGHTS",
    "FusionOutcome",
    "FusionSignals",
    "FusionWeights",
    "confidence_tier_label",
    "corroborate_identity_confidence",
    "fuse",
]


@dataclass(frozen=True)
class FusionWeights:
    """User-configurable sensitivity (Master Blueprint Risk Sec11.2) -- not
    a hardcoded constant baked into `fuse()` itself. Weights sum to 1.0 at
    every signal's own maximum contribution; `high_threshold`/`low_threshold`
    define the asymmetric three-band outcome (Sec4)."""

    wake_word: float = 0.35
    identity: float = 0.30
    gaze: float = 0.20
    session_active: float = 0.15
    high_threshold: float = 0.70
    low_threshold: float = 0.35


DEFAULT_WEIGHTS = FusionWeights()


@dataclass(frozen=True)
class FusionSignals:
    """Every input `fuse()` scores, already extracted/resolved from
    `perception.addressee_signal.candidate` and a World Model corroboration
    check (`corroborate_identity_confidence`) -- this is a pure function of
    already-typed values, never a raw event-payload parser itself, so it
    stays trivially unit-testable without any Event Bus involved."""

    wake_word_matched: bool
    wake_word_confidence: float
    identity_id: UUID | None
    identity_confidence: float
    gaze_toward_device: bool
    session_active: bool


@dataclass(frozen=True)
class FusionOutcome:
    score: float
    tier: Literal["high", "uncertain", "low"]
    """The three-band *action* decision (Sec4) -- not the general Doc
    22/Bible Part 17 Confidence Expression vocabulary. Use
    `confidence_tier_label` for that."""
    action: Literal["activated", "clarify", "silent"]


def confidence_tier_label(score: float) -> Literal["high", "medium", "low", "unknown"]:
    """Maps a fusion score onto Doc 22 Principle 7 / Bible Part 17's
    standard four-tier Confidence Expression vocabulary, for
    `ConversationDecisionTrace.confidence_tier` (Sec15) -- a distinct
    concern from `FusionOutcome.tier`'s three-band action decision above.
    Reuses `perception-engine`'s own `identity_fusion.py` tier boundaries
    (0.85/0.6/0.35) for consistency with the already-established numeric
    scale for identity/addressee confidence in this codebase, rather than
    inventing a second one."""
    if score >= 0.85:
        return "high"
    if score >= 0.6:
        return "medium"
    if score >= 0.35:
        return "low"
    return "unknown"


def fuse(signals: FusionSignals, *, weights: FusionWeights = DEFAULT_WEIGHTS) -> FusionOutcome:
    """Sec4's exact weighted-sum formula. Ambiguous cases resolve toward
    clarification, never silence or an unprompted response (Master
    Blueprint Sec5 item 4)."""
    score = 0.0
    if signals.wake_word_matched:
        score += weights.wake_word * signals.wake_word_confidence
    if signals.identity_id is not None:
        score += weights.identity * signals.identity_confidence
    if signals.gaze_toward_device:
        score += weights.gaze
    if signals.session_active:
        score += weights.session_active

    if score >= weights.high_threshold:
        return FusionOutcome(score=score, tier="high", action="activated")
    if score < weights.low_threshold:
        return FusionOutcome(score=score, tier="low", action="silent")
    return FusionOutcome(score=score, tier="uncertain", action="clarify")


def corroborate_identity_confidence(
    *,
    perception_confidence: float,
    identity_id: UUID | None,
    world_model_present_identity_ids: frozenset[UUID],
) -> float:
    """Sec4 -- World Model's `present_identities` is "a second,
    independently-sourced confirmation, not a duplicate read of the same
    fact": when it independently lists the same `identity_id` Perception's
    own candidate signal named, that corroboration raises confidence toward
    (never above) certainty; when World Model has no opinion (degraded, or
    genuinely doesn't list this identity), Perception's own confidence
    passes through unchanged -- corroboration can only help, an absent or
    disagreeing second source is never treated as contradicting evidence
    (Doc 22 Principle 7: every identity judgment is probabilistic, so an
    independent source that simply doesn't confirm is not the same claim as
    one that actively denies)."""
    if identity_id is not None and identity_id in world_model_present_identity_ids:
        return min(1.0, perception_confidence + (1.0 - perception_confidence) * 0.5)
    return perception_confidence
