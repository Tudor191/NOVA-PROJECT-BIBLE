"""Validation -- cross-reference, check logical consistency, assign initial
confidence (docs/design/phase-1/02-knowledge-engine.md §1-2). Must never silently
overwrite conflicting existing knowledge -- `acquisition.py`'s orchestration routes
that through `contradiction.py`, this module only computes a confidence score.
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_knowledge_engine.domain.models import KnowledgeNode
from nova_knowledge_engine.domain.normalization import NormalizedCandidate
from nova_knowledge_engine.domain.ports import KnowledgeMetadataRepository

_SOURCE_BASE_CONFIDENCE: dict[str, float] = {
    "user": 0.8,
    "document": 0.6,
    "website": 0.5,
    "book": 0.65,
    "paper": 0.7,
    "meeting": 0.6,
    "conversation": 0.55,
    "reasoning": 0.5,
    "hypothesis": 0.3,
}
"""Per-source-type base confidence (Bible Part 8's Confidence System) --
deliberately conservative for inferred/low-trust sources, high for direct user
statements. Unlisted source types fall back to `_DEFAULT_BASE_CONFIDENCE`."""

_DEFAULT_BASE_CONFIDENCE = 0.5
_CORROBORATION_BONUS = 0.05
_CORROBORATION_BONUS_CAP = 0.25


def _initial_confidence(source_type: str, *, prior_source_count: int) -> float:
    base = _SOURCE_BASE_CONFIDENCE.get(source_type, _DEFAULT_BASE_CONFIDENCE)
    bonus = min(prior_source_count * _CORROBORATION_BONUS, _CORROBORATION_BONUS_CAP)
    return min(base + bonus, 1.0)


@dataclass(frozen=True, slots=True)
class ValidatedCandidate:
    candidate: NormalizedCandidate
    confidence: float
    existing: KnowledgeNode | None
    prior_source_count: int


async def validate(
    candidate: NormalizedCandidate, *, repository: KnowledgeMetadataRepository
) -> ValidatedCandidate:
    existing = await repository.get_node(candidate.node_id)
    prior_sources = await repository.list_sources(candidate.node_id) if existing else []
    confidence = _initial_confidence(candidate.source_type, prior_source_count=len(prior_sources))
    if existing is not None:
        # Corroboration never lowers confidence below what's already recorded -- a
        # new low-trust source shouldn't demote an already-verified node.
        confidence = max(confidence, existing.confidence)
    return ValidatedCandidate(
        candidate=candidate,
        confidence=confidence,
        existing=existing,
        prior_source_count=len(prior_sources),
    )
