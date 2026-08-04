"""Relationship discovery -- infer new edges between existing nodes via embedding
similarity (docs/design/phase-1/02-knowledge-engine.md §1-2). Driven by
`workers/maintenance_worker.py`, off the request path -- never called synchronously
from `acquisition.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_knowledge_engine.domain.models import KnowledgeNode

DEFAULT_RELATED_TO_THRESHOLD = 0.85
"""Cosine similarity above which two otherwise-unconnected nodes are proposed as
`RELATED_TO` -- deliberately higher than a "definitely the same concept" bar (see
`compression.py`'s `DUPLICATE_SIMILARITY_THRESHOLD`) and lower than that: this is
for "meaningfully related", not "the same node"."""


@dataclass(frozen=True, slots=True)
class DiscoveredRelationship:
    from_id: str
    to_id: str
    relationship_type: str
    confidence: float


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def discover_related_to(
    candidate: KnowledgeNode,
    others: list[KnowledgeNode],
    *,
    already_connected: frozenset[str] = frozenset(),
    threshold: float = DEFAULT_RELATED_TO_THRESHOLD,
) -> list[DiscoveredRelationship]:
    """Pure: given `candidate` and a pool of `others` (already fetched by the
    caller, typically via `VectorIndex.search` -- this function never calls a
    store itself), proposes `RELATED_TO` edges for pairs above `threshold` that
    are not already directly connected (per `already_connected`, populated by the
    caller from a `GraphStore.traverse` on existing 1-hop relationships)."""
    if candidate.embedding is None:
        return []
    discovered = []
    for other in others:
        if other.node_id == candidate.node_id or other.node_id in already_connected:
            continue
        if other.embedding is None:
            continue
        similarity = cosine_similarity(candidate.embedding, other.embedding)
        if similarity >= threshold:
            discovered.append(
                DiscoveredRelationship(
                    from_id=candidate.node_id,
                    to_id=other.node_id,
                    relationship_type="RELATED_TO",
                    confidence=similarity,
                )
            )
    return discovered
