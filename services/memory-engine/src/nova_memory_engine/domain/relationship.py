"""Relationship Memory -- docs/design/phase-1/01-memory-engine.md §5. A thin client
into Knowledge Engine's graph, never a local graph write: Memory Engine owns no
graph of its own (see that section for why). Both calls degrade gracefully on
timeout, matching docs/design/phase-1/01-memory-engine.md §17's read-path
degradation discipline -- a memory is still valid without a graph link.
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts import (
    KnowledgeLinkReplyPayload,
    KnowledgeLinkRequestPayload,
    KnowledgeTraverseReplyPayload,
    KnowledgeTraverseRequestPayload,
)

from nova_memory_engine.domain.ports import EventPublisher

SOURCE_ENGINE = "memory-engine"
DEFAULT_LINK_TIMEOUT_MS = 500
DEFAULT_TRAVERSE_TIMEOUT_MS = 500
DEFAULT_MAX_HOPS = 2


async def link(
    event_publisher: EventPublisher,
    *,
    memory_id: UUID,
    concept_name: str,
    correlation_id: UUID,
    timeout_ms: int = DEFAULT_LINK_TIMEOUT_MS,
) -> str | None:
    """Create-or-find a Knowledge Graph node for `concept_name` and link it to
    `memory_id`. Returns the `knowledge_node_id`, or `None` if Knowledge Engine did
    not reply in time -- the caller stores `None` on `memory_record.knowledge_node_id`
    and the memory remains otherwise fully valid."""
    try:
        reply = await event_publisher.request(
            "knowledge.link.request",
            KnowledgeLinkRequestPayload(memory_id=memory_id, concept_name=concept_name),
            source_engine=SOURCE_ENGINE,
            correlation_id=correlation_id,
            timeout_ms=timeout_ms,
        )
    except TimeoutError:
        return None
    return KnowledgeLinkReplyPayload.model_validate(reply.payload).knowledge_node_id


async def traverse(
    event_publisher: EventPublisher,
    *,
    seed_node_id: str,
    correlation_id: UUID,
    max_hops: int = DEFAULT_MAX_HOPS,
    timeout_ms: int = DEFAULT_TRAVERSE_TIMEOUT_MS,
) -> list[str]:
    """Bounded traversal from `seed_node_id`. Returns connected node ids, or an
    empty list on timeout (docs/design/phase-1/01-memory-engine.md §7 step 3 /
    §17) -- `domain/retrieval.py` treats an empty result as "no relationship
    context available this call", not as an error."""
    try:
        reply = await event_publisher.request(
            "knowledge.traverse.request",
            KnowledgeTraverseRequestPayload(seed_node_id=seed_node_id, max_hops=max_hops),
            source_engine=SOURCE_ENGINE,
            correlation_id=correlation_id,
            timeout_ms=timeout_ms,
        )
    except TimeoutError:
        return []
    return KnowledgeTraverseReplyPayload.model_validate(reply.payload).connected_node_ids
