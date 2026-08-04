"""Importance scoring -- docs/design/phase-1/01-memory-engine.md §6. A pure
function: `(memory, access_stats) -> float`. Performs no I/O; recomputed on every
access by whichever caller has the access stats at hand (`long_term.py` on read,
`workers/consolidation_worker.py` during a run).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ImportanceWeights:
    """Named constants, not inline literals, so they can be tuned without touching
    call sites (docs/design/phase-1/01-memory-engine.md §6). Sums to 1.0 by
    convention, though the formula does not require it -- `clamp` bounds the final
    result regardless."""

    frequency: float = 0.25
    recency: float = 0.30
    project: float = 0.15
    feedback: float = 0.15
    confidence: float = 0.15


DEFAULT_WEIGHTS = ImportanceWeights()
DEFAULT_HALF_LIFE_DAYS = 30.0
INACTIVE_PROJECT_FACTOR = 0.3


def compute_importance(
    *,
    access_count: int,
    access_count_p95: int,
    days_since_last_access: float,
    is_active_project: bool,
    user_feedback_score: float = 0.0,
    confidence: float | None = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    weights: ImportanceWeights = DEFAULT_WEIGHTS,
) -> float:
    """`docs/design/phase-1/01-memory-engine.md`'s importance formula, clamped to
    `[0.0, 1.0]`.

    - `access_count_p95` is the 95th-percentile access count across the caller's
      comparison population (typically the user's memories) -- callers with no
      population yet (a brand-new user) should pass `1` so the frequency term
      degrades gracefully instead of dividing by zero.
    - `user_feedback_score` is `-1.0..1.0`; `0.0` (no feedback) contributes nothing.
    - `confidence` of `None` contributes nothing, matching a memory that has not yet
      been confidence-scored.
    """
    if access_count < 0:
        raise ValueError("access_count must be >= 0")
    if days_since_last_access < 0:
        raise ValueError("days_since_last_access must be >= 0")
    if not -1.0 <= user_feedback_score <= 1.0:
        raise ValueError("user_feedback_score must be in [-1.0, 1.0]")
    if confidence is not None and not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0.0, 1.0]")

    p95 = max(access_count_p95, 1)
    frequency_term = math.log1p(access_count) / math.log1p(p95) if p95 > 0 else 0.0
    recency_term = math.exp(-days_since_last_access / half_life_days)
    project_term = 1.0 if is_active_project else INACTIVE_PROJECT_FACTOR
    confidence_value = confidence if confidence is not None else 0.0

    raw = (
        weights.frequency * frequency_term
        + weights.recency * recency_term
        + weights.project * project_term
        + weights.feedback * user_feedback_score
        + weights.confidence * confidence_value
    )
    return max(0.0, min(1.0, raw))


def recency_decay(
    days_since_last_access: float, *, half_life_days: float = DEFAULT_HALF_LIFE_DAYS
) -> float:
    """The same exponential-decay shape as importance's recency term, exposed
    standalone for `domain/ranking.py`'s `w3*recency_decay` term (docs/design/
    phase-1/01-memory-engine.md §7 step 5) -- one formula, not two definitions of
    "how fast does recency fade" that could drift apart."""
    if days_since_last_access < 0:
        raise ValueError("days_since_last_access must be >= 0")
    return math.exp(-days_since_last_access / half_life_days)
