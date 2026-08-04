"""Attention Model -- docs/design/phase-1/03-world-model-engine.md §6.
Computed lazily at read time; must never be maintained by a write-heavy decay
job (§1's component table "Must never" column) -- `boost()` is the only write,
`current_score()` is a pure function of the stored `(raw_weight,
last_boosted_at)` pair and the caller-supplied `now`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from nova_world_model_engine.domain.models import AttentionEntry

DEFAULT_HALF_LIFE = timedelta(minutes=30)
"""How long it takes a boosted entity's attention to decay back toward zero if
never boosted again -- tuned as a starting point, not derived from data (no
usage data exists yet to derive it from; §15 has no attention-specific latency
budget to back into either)."""


def current_score(
    entry: AttentionEntry, *, now: datetime, half_life: timedelta = DEFAULT_HALF_LIFE
) -> float:
    """`attention(entity, now) = raw_weight(entity) * exp(-(now -
    last_boosted_at) / half_life)` -- the exact formula from §6, implemented
    literally (not "corrected" to the more common `0.5 ** (t / half_life)`
    half-life convention Memory Engine's `recency_decay` uses) since the design
    doc states this formula specifically for World Model's Attention Model."""
    elapsed_seconds = max((now - entry.last_boosted_at).total_seconds(), 0.0)
    half_life_seconds = half_life.total_seconds()
    if half_life_seconds <= 0:
        return entry.raw_weight
    return entry.raw_weight * math.exp(-elapsed_seconds / half_life_seconds)


@dataclass(frozen=True, slots=True)
class ScoredEntity:
    entity_id: str
    score: float


def rank_by_attention(
    entries: list[AttentionEntry],
    *,
    now: datetime,
    half_life: timedelta = DEFAULT_HALF_LIFE,
    limit: int = 10,
) -> list[ScoredEntity]:
    scored = [
        ScoredEntity(entity_id=e.entity_id, score=current_score(e, now=now, half_life=half_life))
        for e in entries
    ]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:limit]


def boost(
    entry: AttentionEntry | None, *, entity_id: str, amount: float, at: datetime
) -> AttentionEntry:
    """Boosts (never overwrites) `raw_weight` -- called on every relevant
    perception event touching `entity_id` (§6). `entry=None` starts a fresh
    entry (first-ever boost for this entity)."""
    if entry is None:
        return AttentionEntry(entity_id=entity_id, raw_weight=amount, last_boosted_at=at)
    return AttentionEntry(
        entity_id=entity_id, raw_weight=entry.raw_weight + amount, last_boosted_at=at
    )
