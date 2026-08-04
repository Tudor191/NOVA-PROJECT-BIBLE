"""Ranking -- `score = w1*similarity + w2*confidence + w3*recency + w4*layer_weight
+ w5*relationship_strength` (docs/design/phase-1/02-knowledge-engine.md §7 step 5).
`layer_weight` rewards more-mature knowledge; `relationship_strength` rewards nodes
reached via the graph traversal leg over ones found only semantically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from nova_knowledge_engine.domain.models import KnowledgeLayer

_LAYER_WEIGHT: dict[KnowledgeLayer, float] = {
    KnowledgeLayer.RAW: 0.1,
    KnowledgeLayer.PROCESSED: 0.25,
    KnowledgeLayer.VERIFIED: 0.45,
    KnowledgeLayer.CONNECTED: 0.6,
    KnowledgeLayer.APPLIED: 0.75,
    KnowledgeLayer.EXPERT: 0.9,
    KnowledgeLayer.STRATEGIC: 1.0,
}


@dataclass(frozen=True, slots=True)
class RankingWeights:
    similarity: float = 0.35
    confidence: float = 0.2
    recency: float = 0.15
    layer: float = 0.2
    relationship_strength: float = 0.1


@dataclass(frozen=True, slots=True)
class RankingCandidate:
    node_id: str
    label: str
    name: str
    layer: KnowledgeLayer
    confidence: float
    updated_at: datetime
    similarity: float | None = None
    relationship_strength: float | None = None
    related_node_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScoredResult:
    node_id: str
    label: str
    name: str
    layer: KnowledgeLayer
    confidence: float
    score: float
    similarity: float | None
    related_node_ids: tuple[str, ...]


def recency_decay(updated_at: datetime, *, now: datetime, half_life_days: float = 30.0) -> float:
    age_days = max((now - updated_at).total_seconds() / 86400.0, 0.0)
    return 0.5 ** (age_days / half_life_days)


_DEFAULT_WEIGHTS = RankingWeights()


def rank(
    candidates: list[RankingCandidate],
    *,
    now: datetime,
    weights: RankingWeights = _DEFAULT_WEIGHTS,
    limit: int = 10,
) -> list[ScoredResult]:
    scored = []
    for c in candidates:
        similarity = c.similarity or 0.0
        recency = recency_decay(c.updated_at, now=now)
        layer_weight = _LAYER_WEIGHT[c.layer]
        relationship_strength = c.relationship_strength or 0.0
        score = (
            weights.similarity * similarity
            + weights.confidence * c.confidence
            + weights.recency * recency
            + weights.layer * layer_weight
            + weights.relationship_strength * relationship_strength
        )
        scored.append(
            ScoredResult(
                node_id=c.node_id,
                label=c.label,
                name=c.name,
                layer=c.layer,
                confidence=c.confidence,
                score=score,
                similarity=c.similarity,
                related_node_ids=c.related_node_ids,
            )
        )
    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:limit]
