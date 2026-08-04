"""The unified retrieval pipeline orchestrator -- docs/design/phase-1/
01-memory-engine.md §7. Fans out to semantic (`VectorIndex`), timeline
(`MemoryRepository`), and -- optionally -- relationship (`relationship.py`, a
cross-engine call) search, merges by id, and ranks (`ranking.py`). This is the only
module that knows all three search modes exist; every other `domain/` module knows
at most one.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from nova_vectorstore_sdk import VectorMatch, VectorQuery

from nova_memory_engine.domain import importance, ranking, relationship
from nova_memory_engine.domain.models import MemoryRecord, MemoryType
from nova_memory_engine.domain.ports import (
    EmbeddingProvider,
    EventPublisher,
    MemoryRepository,
    VectorIndex,
)

DEFAULT_VECTOR_COLLECTION = "memory_records"


@dataclass(frozen=True)
class RetrievalQuery:
    user_id: UUID
    correlation_id: UUID
    query_text: str | None = None
    project_id: UUID | None = None
    memory_type: MemoryType | None = None
    include_relationships: bool = False
    limit: int = 10


@dataclass(frozen=True)
class RetrievalResult:
    results: list[ranking.ScoredResult]
    degraded: bool
    """Set when `VectorIndex` was unreachable and results fell back to timeline
    (and, if requested, relationship) search only -- docs/design/phase-1/
    01-memory-engine.md §17's read-path degradation, applied here."""


def _days_since(moment: datetime, now: datetime) -> float:
    return max((now - moment).total_seconds() / 86400.0, 0.0)


def _as_float(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None


async def retrieve(
    query: RetrievalQuery,
    *,
    repository: MemoryRepository,
    vector_index: VectorIndex,
    embedding_provider: EmbeddingProvider,
    event_publisher: EventPublisher | None = None,
    vector_collection: str = DEFAULT_VECTOR_COLLECTION,
    now: datetime | None = None,
) -> RetrievalResult:
    now = now or datetime.now(UTC)
    degraded = False

    async def _semantic() -> list[VectorMatch]:
        nonlocal degraded
        if not query.query_text:
            return []
        try:
            embedded = await embedding_provider.embed(query.query_text)
        except Exception:
            degraded = True
            return []
        filters: dict[str, object] = {"user_id": str(query.user_id)}
        if query.memory_type is not None:
            filters["memory_type"] = query.memory_type.value
        try:
            return list(
                await vector_index.search(
                    vector_collection,
                    VectorQuery(vector=embedded.vector, top_k=query.limit, filters=filters),
                )
            )
        except Exception:
            degraded = True
            return []

    async def _timeline() -> list[MemoryRecord]:
        return await repository.list_by_timeline(
            user_id=query.user_id,
            project_id=query.project_id,
            memory_type=query.memory_type,
            limit=query.limit,
        )

    semantic_matches, timeline_records = await asyncio.gather(_semantic(), _timeline())

    candidates: dict[UUID, ranking.RankingCandidate] = {}
    for record in timeline_records:
        anchor = record.last_accessed_at or record.created_at
        candidates[record.id] = ranking.RankingCandidate(
            memory_id=record.id,
            memory_type=record.memory_type,
            content=record.content,
            importance_score=record.importance_score,
            confidence=record.confidence,
            recency_decay=importance.recency_decay(_days_since(anchor, now)),
        )

    top_seed_node_id: str | None = None
    for i, match in enumerate(semantic_matches):
        memory_id = UUID(match.id)
        existing = candidates.get(memory_id)
        if existing is not None:
            candidates[memory_id] = dataclasses.replace(existing, similarity=match.score)
        else:
            # A semantic-only match (not also found via timeline) carries its own
            # content/memory_type back from the vector store's whitelisted metadata
            # columns (docs/architecture: `PgVectorCollection.metadata_columns`) --
            # see `main.py`'s collection registration for the full whitelist.
            match_type = match.metadata.get("memory_type")
            candidates[memory_id] = ranking.RankingCandidate(
                memory_id=memory_id,
                memory_type=MemoryType(match_type) if match_type else MemoryType.SEMANTIC,
                content=str(match.metadata.get("content", "")),
                importance_score=_as_float(match.metadata.get("importance_score")) or 0.5,
                similarity=match.score,
                confidence=_as_float(match.metadata.get("confidence")),
            )
        if i == 0:
            node_id = match.metadata.get("knowledge_node_id")
            top_seed_node_id = str(node_id) if node_id else None

    if query.include_relationships and event_publisher is not None and top_seed_node_id:
        # A relationship traversal deliberately does not merge new candidates into
        # `candidates` (docs/design/phase-1/04-cross-engine-integration.md §5 notes
        # this as exactly the kind of gap a Phase 2 requirement should surface, not
        # something to guess at now): Knowledge Graph node ids are not memory ids,
        # and translating "connected concept" back to "which memories reference it"
        # is not yet a defined Knowledge Engine capability. The call is still made
        # -- so the code path, timeout handling, and contract are all real and
        # tested -- its result is presently informational only.
        await relationship.traverse(
            event_publisher, seed_node_id=top_seed_node_id, correlation_id=query.correlation_id
        )

    scored = ranking.rank(list(candidates.values()))
    limited = scored[: query.limit]

    if limited:
        await _record_access(repository, [r.memory_id for r in limited], now)

    return RetrievalResult(results=limited, degraded=degraded)


async def _record_access(
    repository: MemoryRepository, memory_ids: list[UUID], now: datetime
) -> None:
    """Access bookkeeping that must never fail a read (docs/design/phase-1/
    01-memory-engine.md §7 step 6): awaited inline (fast Postgres/Redis updates,
    well within the p95 budget) rather than detached as a background task, which
    would be harder to test deterministically and could be silently dropped if the
    event loop shuts down mid-request."""
    for memory_id in memory_ids:
        with contextlib.suppress(Exception):  # access bookkeeping must never fail a read
            await repository.record_access(memory_id, accessed_at=now)
