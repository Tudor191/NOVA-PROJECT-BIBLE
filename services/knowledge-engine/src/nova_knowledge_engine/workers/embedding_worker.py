"""Embedding worker -- Arq job driving async embedding generation, docs/design/
phase-1/02-knowledge-engine.md §10 (identical mechanism to Memory Engine's §01
§10 -- same model, same re-embedding-on-model-change job, same
`nova-embeddings-sdk` code path against a different table).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nova_observability import get_logger
from nova_vectorstore_sdk import VectorRecord

from nova_knowledge_engine.domain.ports import (
    EmbeddingProvider,
    KnowledgeMetadataRepository,
    VectorIndex,
)

if TYPE_CHECKING:
    from nova_knowledge_engine.observability import KnowledgeEngineMetrics

logger = get_logger("knowledge-engine.workers.embedding")

DEFAULT_BATCH_SIZE = 50
DEFAULT_VECTOR_COLLECTION = "knowledge_nodes"


async def run_embedding_pass(
    repository: KnowledgeMetadataRepository,
    vector_index: VectorIndex,
    embedding_provider: EmbeddingProvider,
    *,
    current_model: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    vector_collection: str = DEFAULT_VECTOR_COLLECTION,
    metrics: KnowledgeEngineMetrics | None = None,
) -> int:
    """Embeds every not-yet-embedded (or stale-model) node, oldest first. Writes
    directly to `VectorIndex` -- never through `KnowledgeMetadataRepository`, same
    separation Memory Engine's embedding worker documents (that port already owns
    the `embedding`/`embedding_model` columns via this write path).

    Returns the number of nodes embedded.
    """
    candidates = await repository.list_needing_embedding(
        current_model=current_model, limit=batch_size
    )
    if not candidates:
        return 0

    embeddings = await embedding_provider.embed_batch([c.name for c in candidates])
    records = [
        VectorRecord(
            id=candidate.node_id,
            vector=embedding.vector,
            metadata={
                "embedding_model": embedding.model,
                "scope": candidate.scope.value,
                "project_id": str(candidate.project_id) if candidate.project_id else None,
                "user_id": str(candidate.user_id) if candidate.user_id else None,
                "label": candidate.label,
            },
        )
        for candidate, embedding in zip(candidates, embeddings, strict=True)
    ]
    await vector_index.upsert_batch(vector_collection, records)

    if metrics is not None:
        metrics.embeddings_total.add(len(records))
    logger.info("embedding pass completed", extra={"nodes_embedded": len(records)})
    return len(records)


async def arq_run_embedding_pass(ctx: dict) -> None:
    """Arq entrypoint (`WorkerSettings.cron_jobs` in `workers/__init__.py`)."""
    await run_embedding_pass(
        ctx["repository"],
        ctx["vector_index"],
        ctx["embedding_provider"],
        current_model=ctx["embedding_model"],
        metrics=ctx.get("metrics"),
    )
