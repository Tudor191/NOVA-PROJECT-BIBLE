"""Ranking -- orders World Objects by current relevance for listing/context
assembly (docs/design/phase-1/03-world-model-engine.md §1's file list). Unlike
Memory/Knowledge Engine's `ranking.py`, there is no similarity score to blend
in (§10: World Model doesn't embed) -- relevance here is Attention alone,
Attention's own recency-decay already folded in (`domain/attention.py`).
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_world_model_engine.domain.attention import ScoredEntity
from nova_world_model_engine.domain.models import WorldObject


@dataclass(frozen=True, slots=True)
class RankedObject:
    object: WorldObject
    attention_score: float


def rank_objects(
    objects: list[WorldObject], attention: list[ScoredEntity], *, limit: int = 10
) -> list[RankedObject]:
    scores = {s.entity_id: s.score for s in attention}
    ranked = [
        RankedObject(object=obj, attention_score=scores.get(obj.object_id, 0.0))
        for obj in objects
    ]
    ranked.sort(key=lambda r: r.attention_score, reverse=True)
    return ranked[:limit]
