"""Duplicate/redundancy removal (docs/design/phase-1/02-knowledge-engine.md §1-2).
Structurally mirrors Memory Engine's `domain/consolidation.py` duplicate-finding --
same cosine-similarity clustering approach, applied to `KnowledgeNode` instead of
`MemoryRecord`. Driven by `workers/maintenance_worker.py`; never merges nodes
across scopes.
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_knowledge_engine.domain.discovery import cosine_similarity
from nova_knowledge_engine.domain.models import KnowledgeNode

DUPLICATE_SIMILARITY_THRESHOLD = 0.93


@dataclass(frozen=True, slots=True)
class MergeDecision:
    keep_id: str
    superseded_ids: tuple[str, ...]


def _grouping_key(node: KnowledgeNode) -> tuple[str, str, str]:
    return (
        node.scope.value,
        str(node.project_id) if node.project_id else "",
        str(node.user_id) if node.user_id else "",
    )


def find_duplicate_clusters(
    nodes: list[KnowledgeNode], *, threshold: float = DUPLICATE_SIMILARITY_THRESHOLD
) -> list[MergeDecision]:
    """Groups by `(scope, project_id, user_id)` first, then by `label` -- never
    proposes merging across scopes or labels: a Personal-knowledge node must never
    be silently folded into a Global one, and a `:Concept` must never absorb a
    `:Technology` just because their names embed closely."""
    embedded = [n for n in nodes if n.embedding is not None]
    groups: dict[tuple[str, str, str], list[KnowledgeNode]] = {}
    for node in embedded:
        groups.setdefault(_grouping_key(node), []).append(node)

    decisions: list[MergeDecision] = []
    for group in groups.values():
        by_label: dict[str, list[KnowledgeNode]] = {}
        for node in group:
            by_label.setdefault(node.label, []).append(node)
        for candidates in by_label.values():
            decisions.extend(_cluster_within(candidates, threshold=threshold))
    return decisions


def _cluster_within(candidates: list[KnowledgeNode], *, threshold: float) -> list[MergeDecision]:
    remaining = sorted(candidates, key=lambda n: n.confidence, reverse=True)
    decisions: list[MergeDecision] = []
    used: set[str] = set()
    for i, anchor in enumerate(remaining):
        if anchor.node_id in used:
            continue
        superseded = []
        for other in remaining[i + 1 :]:
            if other.node_id in used:
                continue
            assert anchor.embedding is not None
            assert other.embedding is not None
            if cosine_similarity(anchor.embedding, other.embedding) >= threshold:
                superseded.append(other.node_id)
                used.add(other.node_id)
        if superseded:
            used.add(anchor.node_id)
            decisions.append(
                MergeDecision(keep_id=anchor.node_id, superseded_ids=tuple(superseded))
            )
    return decisions
