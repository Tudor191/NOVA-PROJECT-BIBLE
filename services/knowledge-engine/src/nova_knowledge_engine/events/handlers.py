"""Event Bus subscription handlers -- docs/design/phase-1/02-knowledge-engine.md
§13.

Per docs/design/phase-1/04-cross-engine-integration.md, Perception and Reasoning
don't exist yet in Phase 1 -- these handlers are contracts this engine is ready to
serve, exercised today by a synthetic/test-published event, not a live upstream
producer (mirroring Memory Engine's own `events/handlers.py`, same rationale).
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts import EventEnvelope
from nova_observability import get_logger

from nova_knowledge_engine.domain.ports import KnowledgeMetadataRepository

logger = get_logger("knowledge-engine.events.handlers")


def _text_from(payload: dict, *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _uuid_from(payload: dict, key: str) -> UUID | None:
    value = payload.get(key)
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def make_memory_long_term_created_handler(repository: KnowledgeMetadataRepository):  # type: ignore[no-untyped-def]
    """"candidate for graph node creation/linking" (§13). A documented placeholder,
    not an oversight: `LongTermMemoryCreatedPayload` (docs/design/phase-1/
    01-memory-engine.md §13) deliberately carries only ids, scores, and enums --
    no free-text content field a concept name could be extracted from. Real
    graph-linking here needs either that payload to grow a content field or an
    NLP-based concept-extraction pipeline (Phase 2+, docs/design/phase-1/
    02-knowledge-engine.md §20's "Knowledge marketplace / external knowledge base
    import" extension point covers the general shape of that work).
    """

    async def handle(envelope: EventEnvelope) -> None:
        memory_id = _uuid_from(envelope.payload, "memory_id")
        logger.info(
            "memory.long_term.created received, no content field to extract a "
            "concept from -- acquisition not yet possible from this payload",
            extra={"memory_id": str(memory_id) if memory_id else None},
        )

    return handle


def make_perception_filesystem_observed_handler(repository: KnowledgeMetadataRepository):  # type: ignore[no-untyped-def]
    """"triggers documentation reindexing" (§13) -- no live Perception Engine
    producer exists in Phase 1 (docs/design/phase-1/04-cross-engine-integration.md),
    and a real reindexing pipeline (parsing files, chunking, acquiring one node per
    section) is a larger feature than this event handler alone. Placeholder,
    exercised today only via the synthetic event harness."""

    async def handle(envelope: EventEnvelope) -> None:
        source_ref = _text_from(envelope.payload, "path", "source_ref")
        logger.info(
            "perception.filesystem.observed received, reindexing not yet implemented",
            extra={"source_ref": source_ref},
        )

    return handle


def make_reasoning_result_handler(repository: KnowledgeMetadataRepository):  # type: ignore[no-untyped-def]
    """Usage signal feeding `domain/evolution.py`'s Connected -> Applied and
    Expert -> Strategic transitions (§6, §13). `reasoning.result` has no
    formalized payload contract yet (Reasoning Engine is Phase 2) -- this handler
    defensively extracts `knowledge_node_id`(s) and `project_id` from whatever
    shape arrives, same pattern as Memory Engine's placeholder handlers, but the
    *effect* (`record_usage`) is real and tested via the synthetic event harness,
    not a no-op: the `node_usage` table exists specifically so this signal has
    somewhere to land the moment a real producer exists."""

    async def handle(envelope: EventEnvelope) -> None:
        project_id = _uuid_from(envelope.payload, "project_id")
        node_ids = envelope.payload.get("knowledge_node_ids") or envelope.payload.get(
            "referenced_node_ids"
        )
        single = envelope.payload.get("knowledge_node_id")
        if single and not node_ids:
            node_ids = [single]
        if not node_ids or not isinstance(node_ids, list):
            logger.warning("reasoning.result missing knowledge_node_id(s), skipping")
            return
        for node_id in node_ids:
            if isinstance(node_id, str) and node_id:
                await repository.record_usage(node_id, project_id=project_id)

    return handle
