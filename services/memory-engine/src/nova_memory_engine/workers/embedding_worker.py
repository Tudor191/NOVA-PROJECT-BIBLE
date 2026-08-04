"""Embedding worker -- Arq job driving async embedding generation, docs/design/
phase-1/01-memory-engine.md §10. Keeps write latency independent of embedding
latency: a memory is written with `embedding = NULL`; this worker polls, embeds in
batch, and writes the result back via `VectorIndex.upsert_batch` -- never through
`MemoryRepository` (see that port's `list_needing_embedding` docstring for why).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nova_contracts import EmbeddingCompletedPayload, EventEnvelope
from nova_eventbus_sdk.interface import EventBus
from nova_observability import get_logger
from nova_vectorstore_sdk import VectorRecord

from nova_memory_engine.domain.ports import EmbeddingProvider, MemoryRepository, VectorIndex

if TYPE_CHECKING:
    from nova_memory_engine.observability import MemoryEngineMetrics

logger = get_logger("memory-engine.workers.embedding")

DEFAULT_BATCH_SIZE = 50
DEFAULT_VECTOR_COLLECTION = "memory_records"


async def run_embedding_pass(
    repository: MemoryRepository,
    vector_index: VectorIndex,
    embedding_provider: EmbeddingProvider,
    bus: EventBus,
    *,
    current_model: str,
    source_engine: str = "memory-engine",
    batch_size: int = DEFAULT_BATCH_SIZE,
    vector_collection: str = DEFAULT_VECTOR_COLLECTION,
    metrics: MemoryEngineMetrics | None = None,
) -> int:
    """Embeds every not-yet-embedded (or stale-model) row, oldest first.

    `memory.embedding.completed` is published directly here, not via the
    transactional outbox: a crash between the `VectorIndex` write and this publish
    leaves the embedding correctly persisted (searchable) but the event unsent --
    the exact "visible, not silently wrong" failure mode docs/design/phase-1/
    01-memory-engine.md §17 already accepts for embedding, so the outbox's extra
    row buys nothing here that the next poll wouldn't already fix in the common
    case. One narrower guarantee than every other event in this engine falls out of
    that: an already-embedded row won't be re-picked-up by `list_needing_embedding`,
    so a crash in that exact window can lose the *event* (not the embedding, which
    is what actually matters for retrieval) permanently. Documented, not accidental.

    Returns the number of rows embedded.
    """
    candidates = await repository.list_needing_embedding(
        current_model=current_model, limit=batch_size
    )
    if not candidates:
        return 0

    embeddings = await embedding_provider.embed_batch([c.content for c in candidates])
    records = [
        VectorRecord(
            id=str(candidate.id),
            vector=embedding.vector,
            metadata={"embedding_model": embedding.model},
        )
        for candidate, embedding in zip(candidates, embeddings, strict=True)
    ]
    await vector_index.upsert_batch(vector_collection, records)

    for candidate, embedding in zip(candidates, embeddings, strict=True):
        envelope = EventEnvelope(
            subject="memory.embedding.completed",
            source_engine=source_engine,
            correlation_id=candidate.id,
            payload=EmbeddingCompletedPayload(
                memory_id=candidate.id,
                embedding_model=embedding.model,
                dimensions=embedding.dimensions,
            ).model_dump(mode="json"),
        )
        await bus.publish(envelope)

    if metrics is not None:
        metrics.embeddings_total.add(len(records))
    logger.info("embedding pass completed", extra={"records_embedded": len(records)})
    return len(records)


async def arq_run_embedding_pass(ctx: dict) -> None:
    """Arq entrypoint (`WorkerSettings.cron_jobs` in `workers/__init__.py`)."""
    await run_embedding_pass(
        ctx["memory_repository"],
        ctx["vector_index"],
        ctx["embedding_provider"],
        ctx["bus"],
        current_model=ctx["embedding_model"],
        metrics=ctx.get("metrics"),
    )
