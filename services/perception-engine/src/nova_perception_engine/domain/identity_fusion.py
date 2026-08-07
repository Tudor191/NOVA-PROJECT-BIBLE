"""Multi-factor identity confidence -- continuous evidence fusion
(docs/design/phase-2d/03-perception-engine.md Sec8). The mechanical
implementation of Sec0.4's foundational principle (no single signal is ever
sufficient) and Sec0.10's foundational principle (recognition is an ongoing
process, not a single event).

`fuse_window` mirrors World Model Engine's own `domain/fusion.py:fuse_window`
correlation-window pattern deliberately, not coincidentally -- both solve
"combine several imperfect signals into one confidence-scored verdict without
letting agreement fabricate false certainty." `smooth` is this module's own
addition: World Model's fusion has no continuous-reassessment concept because
Active Context updates are already treated as the current snapshot; identity
confidence here is explicitly a stream (Sec0.10), so a window's raw verdict
never reaches a consumer directly -- it always updates a smoothed running
state first (step 6).

Pure, deterministic computation over already-scored per-modality signals --
never calls a model itself (mirrors `personality-engine`'s own rule-based-by-
construction validator, Sec0.3 of that document)."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from nova_perception_engine.domain.models import ConfidenceTier, IdentityConfidenceState

__all__ = [
    "AGREEMENT_BONUS",
    "ALPHA",
    "MAX_CONFIDENCE",
    "SINGLE_SIGNAL_CONFIDENCE_CEILING",
    "ModalitySignal",
    "FusedWindowResult",
    "fuse_window",
    "smooth",
    "tier_for",
]

AGREEMENT_BONUS = 0.15
"""Reused verbatim from World Model's own `fuse_window` -- an intentional
architectural consistency (this module's own docstring)."""

MAX_CONFIDENCE = 0.99

SINGLE_SIGNAL_CONFIDENCE_CEILING = 0.75
"""The mechanical enforcement of Sec0.4: when only one modality contributed a
signal this window, fused confidence is capped here regardless of that
signal's own raw confidence. Since `high` begins at 0.85 (below), a single
signal can never, by construction, produce a High-confidence identity
verdict -- a structural property of this function, not a policy an
implementer could accidentally weaken by tuning a threshold."""

ALPHA = 0.4
"""Exponential-smoothing rate for `smooth` (Sec8 step 6, Sec0.10) -- low
enough that one anomalous window cannot swing the visible state, high enough
that a real, sustained change in evidence is reflected within a handful of
windows. A considered starting point, not a scientifically validated
calibration (Sec24) -- Sec20's calibration tests are the mechanism for
revising it with real data."""

_TIER_BOUNDARIES: tuple[tuple[float, ConfidenceTier], ...] = (
    (0.85, "high"),
    (0.6, "medium"),
    (0.35, "low"),
)


def tier_for(confidence: float) -> ConfidenceTier:
    """Doc 23 Sec5.2's four tiers, reused per Doc 22 Principle 7."""
    for threshold, tier in _TIER_BOUNDARIES:
        if confidence >= threshold:
            return tier
    return "unknown"


@dataclass(frozen=True, slots=True)
class ModalitySignal:
    """One modality's opinion for this correlation window (voice match, face
    match, or session-continuity -- "the same identity as the immediately
    preceding confirmed observation within the correlation window")."""

    modality: str
    candidate_identity_id: UUID | None
    confidence: float


@dataclass(frozen=True, slots=True)
class FusedWindowResult:
    identity_id: UUID | None
    fused_confidence: float
    confidence_tier: ConfidenceTier
    per_modality_signals: dict[str, object] = field(default_factory=dict)
    disagreement: bool = False


def fuse_window(signals: list[ModalitySignal]) -> FusedWindowResult:
    """Steps 1-5 of Sec8. `signals` is every available per-modality signal
    for one correlation window -- may be empty (no signal this window, e.g.
    both sensors momentarily unavailable, Sec12), one (single-modality
    environment), or many."""
    if not signals:
        return FusedWindowResult(
            identity_id=None, fused_confidence=0.0, confidence_tier="unknown"
        )

    # Step 1: group signals by candidate identity.
    groups: dict[UUID | None, list[ModalitySignal]] = {}
    for signal in signals:
        groups.setdefault(signal.candidate_identity_id, []).append(signal)

    per_modality_signals: dict[str, object] = {
        s.modality: {
            "candidate_identity_id": str(s.candidate_identity_id)
            if s.candidate_identity_id
            else None,
            "confidence": s.confidence,
        }
        for s in signals
    }

    if len(groups) > 1:
        # Step 4: disagreement is suppressed, never averaged -- forced into
        # the low/unknown band and recorded verbatim for later review,
        # mirroring World Model's own ConflictLogEntry precedent.
        winning_id, agreeing = max(groups.items(), key=lambda kv: len(kv[1]))
        base = max(s.confidence for s in agreeing)
        capped = min(base, 0.5)  # forced into low/unknown regardless of raw confidence
        return FusedWindowResult(
            identity_id=winning_id,
            fused_confidence=capped,
            confidence_tier=tier_for(capped),
            per_modality_signals=per_modality_signals,
            disagreement=True,
        )

    # Step 2: winning identity = the one (only) candidate, agreement-weighted.
    ((winning_id, agreeing),) = groups.items()
    base = max(s.confidence for s in agreeing)
    fused = min(base + AGREEMENT_BONUS * (len(agreeing) - 1), MAX_CONFIDENCE)

    # Step 3: the single-signal confidence ceiling.
    if len(agreeing) == 1:
        fused = min(fused, SINGLE_SIGNAL_CONFIDENCE_CEILING)

    return FusedWindowResult(
        identity_id=winning_id,
        fused_confidence=fused,
        confidence_tier=tier_for(fused),
        per_modality_signals=per_modality_signals,
        disagreement=False,
    )


def smooth(
    previous: IdentityConfidenceState | None,
    window: FusedWindowResult,
    *,
    presence_session_id: UUID,
    user_id: UUID,
) -> IdentityConfidenceState:
    """Step 6 of Sec8, the mechanical enforcement of Sec0.10. Exponential
    moving average over `window.fused_confidence` -- lets confidence
    increase, decrease, or hold steady as new evidence arrives, without the
    jitter that would come from surfacing each raw window's verdict
    directly. A sustained decrease is treated with the same seriousness as a
    sustained increase: several consecutive low-agreement windows lower
    `smoothed_confidence` through this same formula, never held artificially
    high by "benefit of the doubt" (Doc 22 Principle 9's trust-through-
    consistency discipline, applied here to confidence decay)."""
    if previous is None:
        smoothed_confidence = window.fused_confidence
    else:
        smoothed_confidence = (
            ALPHA * window.fused_confidence + (1 - ALPHA) * previous.smoothed_confidence
        )

    identity_id = window.identity_id if window.fused_confidence > 0.0 else (
        previous.identity_id if previous is not None else None
    )

    return IdentityConfidenceState(
        presence_session_id=presence_session_id,
        user_id=user_id,
        identity_id=identity_id,
        smoothed_confidence=smoothed_confidence,
        smoothed_tier=tier_for(smoothed_confidence),
        observation_count=(previous.observation_count if previous is not None else 0) + 1,
    )
