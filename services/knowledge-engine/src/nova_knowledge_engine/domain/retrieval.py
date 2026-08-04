"""Unified knowledge retrieval pipeline (docs/design/phase-1/02-knowledge-engine.md
§7). Fans out semantic (`VectorIndex`) + graph traversal (`GraphStore`) + name
search (`KnowledgeMetadataRepository`) concurrently, merges by `node_id`, ranks.
Knows nothing about Neo4j/pgvector specifics -- only `ports.py` types (§1's
component table).

The "fulltext/exact-name" leg §7 step 3 describes uses `KnowledgeMetadataRepository.
list_nodes(name_contains=...)` (a Postgres `name` lookup) rather than Neo4j's native
fulltext index -- `GraphStore`'s Protocol (ADR-007) is deliberately backend-agnostic
and has no label-agnostic fulltext primitive, and `node_metadata.name` already
mirrors the graph node's name, so this is a faithful substitute rather than a
missing capability. Documented as a Phase 1 simplification, matching how Memory
Engine documents its own known limitations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from nova_graphstore_sdk import GraphStore, TraversalDirection, TraversalSpec
from nova_observability import get_logger
from nova_vectorstore_sdk import VectorQuery

from nova_knowledge_engine.domain import ranking
from nova_knowledge_engine.domain.models import KnowledgeScope
from nova_knowledge_engine.domain.ports import (
    EmbeddingProvider,
    KnowledgeMetadataRepository,
    VectorIndex,
)

logger = get_logger("knowledge-engine.domain.retrieval")

DEFAULT_VECTOR_COLLECTION = "knowledge_nodes"
DEFAULT_MAX_HOPS = 2


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    correlation_id: UUID
    query_text: str | None = None
    seed_node_id: str | None = None
    scope: KnowledgeScope | None = None
    project_id: UUID | None = None
    user_id: UUID | None = None
    max_hops: int = DEFAULT_MAX_HOPS
    limit: int = 10


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    results: list[ranking.ScoredResult]
    degraded: bool
    """Set when `VectorIndex` or `GraphStore` was unreachable and results fell back
    to a narrower search mode -- docs/design/phase-1/02-knowledge-engine.md §17's
    "Neo4j unreachable during a read" failure mode."""


async def retrieve(
    query: RetrievalQuery,
    *,
    repository: KnowledgeMetadataRepository,
    vector_index: VectorIndex,
    embedding_provider: EmbeddingProvider,
    graph_store: GraphStore,
    vector_collection: str = DEFAULT_VECTOR_COLLECTION,
    now: datetime | None = None,
) -> RetrievalResult:
    now = now or datetime.now(UTC)
    degraded = False

    async def _semantic() -> dict[str, float]:
        nonlocal degraded
        if not query.query_text:
            return {}
        try:
            embedded = await embedding_provider.embed(query.query_text)
        except Exception:
            degraded = True
            return {}
        filters: dict[str, object] = {}
        if query.scope is not None:
            filters["scope"] = query.scope.value
        if query.project_id is not None:
            filters["project_id"] = str(query.project_id)
        if query.user_id is not None:
            filters["user_id"] = str(query.user_id)
        try:
            matches = await vector_index.search(
                vector_collection,
                VectorQuery(vector=embedded.vector, top_k=query.limit * 2, filters=filters),
            )
        except Exception:
            degraded = True
            return {}
        return {m.id: m.score for m in matches}

    async def _graph(seed: str | None) -> tuple[set[str], dict[str, list[str]]]:
        nonlocal degraded
        if seed is None:
            return set(), {}
        try:
            result = await graph_store.traverse(
                seed,
                TraversalSpec(
                    direction=TraversalDirection.BOTH,
                    max_hops=query.max_hops,
                    limit=query.limit * 3,
                ),
            )
        except Exception:
            degraded = True
            return set(), {}
        node_ids = {node.id for node in result.nodes if node.id != seed}
        related: dict[str, list[str]] = {}
        for rel in result.relationships:
            related.setdefault(rel.from_id, []).append(rel.to_id)
            related.setdefault(rel.to_id, []).append(rel.from_id)
        return node_ids, related

    async def _by_name() -> set[str]:
        if not query.query_text:
            return set()
        matches = await repository.list_nodes(
            scope=query.scope,
            project_id=query.project_id,
            user_id=query.user_id,
            name_contains=query.query_text,
            limit=query.limit,
        )
        return {n.node_id for n in matches}

    semantic_matches = await _semantic()
    seed = query.seed_node_id
    if seed is None and semantic_matches:
        # Best-scoring semantic hit seeds the traversal leg too, so a text query
        # still benefits from graph context even without an explicit seed id.
        seed = max(semantic_matches, key=lambda k: semantic_matches[k])
    graph_node_ids, related_by_id = await _graph(seed)
    name_node_ids = await _by_name()

    all_ids = set(semantic_matches) | graph_node_ids | name_node_ids
    candidates: list[ranking.RankingCandidate] = []
    for node_id in all_ids:
        node = await repository.get_node(node_id)
        if node is None:
            continue
        candidates.append(
            ranking.RankingCandidate(
                node_id=node.node_id,
                label=node.label,
                name=node.name,
                layer=node.layer,
                confidence=node.confidence,
                updated_at=node.updated_at,
                similarity=semantic_matches.get(node_id),
                relationship_strength=1.0 if node_id in graph_node_ids else None,
                related_node_ids=tuple(related_by_id.get(node_id, ())),
            )
        )

    ranked = ranking.rank(candidates, now=now, limit=query.limit)
    return RetrievalResult(results=ranked, degraded=degraded)
