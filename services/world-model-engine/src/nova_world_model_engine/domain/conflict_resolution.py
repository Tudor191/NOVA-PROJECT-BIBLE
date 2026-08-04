"""Conflict resolution -- docs/design/phase-1/03-world-model-engine.md §6, §19.
Resolves disagreeing observations about the same object. Must never silently
prefer the most recent without checking confidence/policy first (§1's component
table) -- confidence is checked first, then source policy priority, then a
recency window; only once all three are inconclusive does this fall back to
recency, and even then the result is labeled `unresolved` rather than claimed as
a confident resolution.

Always produces a value (§17: "§6's algorithm has no 'give up' branch") --
`resolve()` never returns a result with `resolved_value=None`; the write is
never blocked. `resolution_strategy='unresolved'` is a *visible flag* for later
Reasoning Engine review (Phase 2+), not a silent default.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

CONFIDENCE_MARGIN = 0.1
"""Confidence difference below which two observations are treated as tied --
not confidently distinguishable by confidence alone."""

RECENCY_WINDOW = timedelta(seconds=2)
"""Observations arriving within this window of each other are too close in
time for "most recent" to be a meaningful tiebreaker on its own."""

DEFAULT_SOURCE_PRIORITY: dict[str, int] = {
    "user": 100,
    "explicit_action": 80,
    "calendar": 50,
    "filesystem": 40,
    "voice": 30,
}
"""Policy priority order (§6) -- unlisted sources default to 0. Values are
relative ranks, not scores; the specific numbers only matter for their
ordering, tuned as a starting point (no usage data exists yet to derive it
from, same caveat as `attention.DEFAULT_HALF_LIFE`)."""

ResolutionStrategy = Literal["confidence", "recency", "policy", "unresolved"]


@dataclass(frozen=True, slots=True)
class Observation:
    object_id: str
    value: dict[str, Any]
    confidence: float
    observed_at: datetime
    source: str


@dataclass(frozen=True, slots=True)
class Resolution:
    object_id: str
    resolution_strategy: ResolutionStrategy
    resolved_value: dict[str, Any]
    observation_a: dict[str, Any]
    observation_b: dict[str, Any]


def resolve(
    a: Observation, b: Observation, *, source_priority: dict[str, int] | None = None
) -> Resolution:
    priority = source_priority or DEFAULT_SOURCE_PRIORITY

    if abs(a.confidence - b.confidence) >= CONFIDENCE_MARGIN:
        winner = a if a.confidence > b.confidence else b
        return _resolution(a, b, "confidence", winner)

    pa, pb = priority.get(a.source, 0), priority.get(b.source, 0)
    if pa != pb:
        winner = a if pa > pb else b
        return _resolution(a, b, "policy", winner)

    if abs((a.observed_at - b.observed_at).total_seconds()) > RECENCY_WINDOW.total_seconds():
        winner = a if a.observed_at > b.observed_at else b
        return _resolution(a, b, "recency", winner)

    # Genuinely ambiguous: confidence tied, no policy difference, and arrived
    # within the recency window too. Still writes a value -- the most recent
    # one, as the least-arbitrary available choice -- but labels the strategy
    # `unresolved` so this is a visible flag, not a claimed confident result.
    fallback = a if a.observed_at >= b.observed_at else b
    return _resolution(a, b, "unresolved", fallback)


def _resolution(
    a: Observation, b: Observation, strategy: ResolutionStrategy, winner: Observation
) -> Resolution:
    return Resolution(
        object_id=a.object_id,
        resolution_strategy=strategy,
        resolved_value=winner.value,
        observation_a=a.value,
        observation_b=b.value,
    )
