"""Bible Part 7 "Fallback Strategy" -- "If the preferred model fails.
Automatically. Retry. Select another model. Reduce context if necessary. Notify
the user only if recovery fails." Implemented as a pure function over an ordered
candidate list, so the sequence a request actually walked through is exactly
what `RoutingDecision.candidates` records (ADR-021) -- never a retry loop whose
attempts go unrecorded.
"""

from __future__ import annotations

from nova_ai_model_orchestration_engine.domain.models import ScoredCandidate

__all__ = ["FallbackExhaustedError", "next_candidate"]


class FallbackExhaustedError(Exception):
    """Raised when every ranked candidate has been tried and failed -- Part 7:
    "notify the user only if recovery fails." This engine notifies its *caller*
    by raising; notifying an actual end user is Communication Engine's job
    (Phase 2D), outside this engine's boundary (design doc §0)."""

    def __init__(self, attempted: list[ScoredCandidate]) -> None:
        super().__init__(f"All {len(attempted)} candidate model(s) failed.")
        self.attempted = attempted


def next_candidate(
    ranked_candidates: list[ScoredCandidate], *, already_tried: list[ScoredCandidate]
) -> ScoredCandidate:
    """Returns the next untried candidate from `ranked_candidates`, in rank
    order. Raises `FallbackExhaustedError` once every candidate has been tried.
    `already_tried` is compared by `model_id`, not object identity, since a
    candidate list is frequently rebuilt (fresh registry snapshot) between
    attempts."""
    tried_ids = {c.model_id for c in already_tried}
    for candidate in ranked_candidates:
        if candidate.model_id not in tried_ids:
            return candidate
    raise FallbackExhaustedError(already_tried)
