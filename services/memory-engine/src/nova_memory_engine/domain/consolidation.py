"""Consolidation -- docs/design/phase-1/01-memory-engine.md §6: duplicate
detection, merge-target selection, and lifecycle-advance planning. Pure decision
logic; performs no I/O and executes nothing -- `workers/consolidation_worker.py`
executes the returned plan against `MemoryRepository`.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from nova_memory_engine.domain import lifecycle
from nova_memory_engine.domain.models import LifecycleState

DUPLICATE_SIMILARITY_THRESHOLD = 0.92


@dataclass(frozen=True)
class ConsolidationCandidate:
    """One long-term memory under consideration during a consolidation run."""

    memory_id: UUID
    user_id: UUID
    project_id: UUID | None
    embedding: list[float] | None
    confidence: float | None
    importance_score: float
    lifecycle_state: LifecycleState
    days_since_last_access: float
    has_active_project_reference: bool


@dataclass(frozen=True)
class MergeDecision:
    """`keep_id` is the highest-confidence member of a duplicate cluster;
    `superseded_ids` are scheduled for deletion (docs/design/phase-1/
    01-memory-engine.md §6 step 4), never hard-deleted directly."""

    keep_id: UUID
    superseded_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class LifecycleAdvanceDecision:
    memory_id: UUID
    from_state: LifecycleState
    to_state: LifecycleState
    reason: str


@dataclass(frozen=True)
class ConsolidationPlan:
    merges: tuple[MergeDecision, ...]
    lifecycle_advances: tuple[LifecycleAdvanceDecision, ...]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"Embedding dimension mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def find_duplicate_clusters(
    candidates: list[ConsolidationCandidate], *, threshold: float = DUPLICATE_SIMILARITY_THRESHOLD
) -> list[MergeDecision]:
    """Groups candidates by `(user_id, project_id)` before comparing embeddings --
    never across users, which would otherwise be both a correctness bug (unrelated
    memories "merged") and a privacy one. Only candidates with a computed embedding
    participate; a memory still awaiting `embedding_worker` is simply not compared
    this run (it will be, next run).
    """
    groups: dict[tuple[UUID, UUID | None], list[ConsolidationCandidate]] = defaultdict(list)
    for c in candidates:
        if c.embedding is not None:
            groups[(c.user_id, c.project_id)].append(c)

    decisions: list[MergeDecision] = []
    for group in groups.values():
        clustered: set[UUID] = set()
        for i, anchor in enumerate(group):
            if anchor.memory_id in clustered:
                continue
            cluster = [anchor]
            for other in group[i + 1 :]:
                if other.memory_id in clustered:
                    continue
                assert anchor.embedding is not None and other.embedding is not None
                if _cosine_similarity(anchor.embedding, other.embedding) > threshold:
                    cluster.append(other)
                    clustered.add(other.memory_id)
            if len(cluster) > 1:
                clustered.add(anchor.memory_id)
                keep = max(cluster, key=lambda c: c.confidence or 0.0)
                superseded = tuple(c.memory_id for c in cluster if c.memory_id != keep.memory_id)
                decisions.append(MergeDecision(keep_id=keep.memory_id, superseded_ids=superseded))
    return decisions


def plan_lifecycle_advances(
    candidates: list[ConsolidationCandidate],
) -> list[LifecycleAdvanceDecision]:
    """Passive, time-based advances only (`lifecycle.next_state_on_idle`) -- never
    produces `SCHEDULED_FOR_DELETION`, matching that function's own guarantee."""
    decisions: list[LifecycleAdvanceDecision] = []
    for c in candidates:
        next_state = lifecycle.next_state_on_idle(
            c.lifecycle_state,
            days_since_last_access=c.days_since_last_access,
            importance_score=c.importance_score,
            has_active_project_reference=c.has_active_project_reference,
        )
        if next_state != c.lifecycle_state:
            decisions.append(
                LifecycleAdvanceDecision(
                    memory_id=c.memory_id,
                    from_state=c.lifecycle_state,
                    to_state=next_state,
                    reason=(
                        f"{c.days_since_last_access:.1f}d since last access, "
                        f"importance={c.importance_score:.2f}"
                    ),
                )
            )
    return decisions


def plan_consolidation(candidates: list[ConsolidationCandidate]) -> ConsolidationPlan:
    """The full run: find duplicate clusters, then plan lifecycle advances over the
    *non-superseded* candidates (a record about to be merged away doesn't also need
    its own lifecycle recomputed this run)."""
    merges = find_duplicate_clusters(candidates)
    superseded_ids = {mid for merge in merges for mid in merge.superseded_ids}
    survivors = [c for c in candidates if c.memory_id not in superseded_ids]
    advances = plan_lifecycle_advances(survivors)
    return ConsolidationPlan(merges=tuple(merges), lifecycle_advances=tuple(advances))
