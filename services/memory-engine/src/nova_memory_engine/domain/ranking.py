"""Retrieval ranking -- docs/design/phase-1/01-memory-engine.md §7 step 5. A pure
function combining component scores; `domain/retrieval.py` is the only caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from nova_memory_engine.domain.models import MemoryType


@dataclass(frozen=True)
class RankingWeights:
    similarity: float = 0.40
    importance: float = 0.25
    recency: float = 0.20
    confidence: float = 0.15


DEFAULT_RANKING_WEIGHTS = RankingWeights()


@dataclass(frozen=True)
class RankingCandidate:
    """One merged candidate, deduplicated across search modes, before ranking.

    Carries `content`/`memory_type` (not just an id and component scores) so a
    caller can use the ranked output directly as search results -- without them,
    every caller would need a second round-trip per result just to show what was
    found, which is not what docs/design/phase-1/01-memory-engine.md §7's sequence
    diagram (a single ranked reply) describes.
    """

    memory_id: UUID
    memory_type: MemoryType
    content: str
    importance_score: float
    similarity: float | None = None
    recency_decay: float | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class ScoredResult:
    """A ranked candidate with every component score preserved -- this is what
    makes retrieval explainable (docs/design/phase-1/01-memory-engine.md §7 step 7,
    Part 8's Confidence System applied to Memory)."""

    memory_id: UUID
    memory_type: MemoryType
    content: str
    score: float
    similarity: float | None
    importance_score: float
    recency_decay: float | None
    confidence: float | None


def rank(
    candidates: list[RankingCandidate], *, weights: RankingWeights = DEFAULT_RANKING_WEIGHTS
) -> list[ScoredResult]:
    """Score and sort `candidates` descending. Missing component scores (a
    candidate that only matched via timeline search has no `similarity`, for
    example) contribute zero to the weighted sum rather than being excluded --
    absence of a signal is not evidence against relevance."""
    scored = [
        ScoredResult(
            memory_id=c.memory_id,
            memory_type=c.memory_type,
            content=c.content,
            score=(
                weights.similarity * (c.similarity or 0.0)
                + weights.importance * c.importance_score
                + weights.recency * (c.recency_decay or 0.0)
                + weights.confidence * (c.confidence or 0.0)
            ),
            similarity=c.similarity,
            importance_score=c.importance_score,
            recency_decay=c.recency_decay,
            confidence=c.confidence,
        )
        for c in candidates
    ]
    scored.sort(key=lambda r: r.score, reverse=True)
    return scored
