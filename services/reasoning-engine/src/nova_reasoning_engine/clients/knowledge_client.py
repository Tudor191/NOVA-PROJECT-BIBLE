"""`KnowledgeClient` -- `domain.ports.KnowledgePort` implementation, calling
`knowledge.retrieve.request` / `knowledge.traverse.request` (docs/design/
phase-2b/00-reasoning-engine.md §7.4). Degrades gracefully on timeout -- an
empty result, not an exception.
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts import (
    KnowledgeRetrieveReplyPayload,
    KnowledgeRetrieveRequestPayload,
    KnowledgeTraverseReplyPayload,
    KnowledgeTraverseRequestPayload,
)

from nova_reasoning_engine.domain.models import KnowledgeReference
from nova_reasoning_engine.domain.ports import EventPublisher

__all__ = ["KnowledgeClient"]

SOURCE_ENGINE = "reasoning-engine"
DEFAULT_TIMEOUT_MS = 2000
_TRAVERSE_PLACEHOLDER_CONFIDENCE = 0.5
"""`knowledge.traverse.reply` (Phase 1) returns bare `connected_node_ids:
list[str]` -- no name, layer, or confidence for each node, unlike
`knowledge.retrieve.reply`'s richer `KnowledgeSearchResultPayload`. Rather
than fabricate a real-looking name or confidence this engine has no basis
for, `traverse()` below labels each result with its own node ID as `name`
(the only real data available) and this fixed, clearly-named neutral
confidence -- an honest, narrow wire-contract gap between this design and
Knowledge Engine's own Phase 1 traverse RPC, not currently exercised by any
pipeline path (§13's hypothesis verification uses only the already-assembled
`retrieve()` results, never a per-hypothesis `traverse()` call)."""


class KnowledgeClient:
    def __init__(
        self, event_publisher: EventPublisher, *, timeout_ms: int = DEFAULT_TIMEOUT_MS
    ) -> None:
        self._event_publisher = event_publisher
        self._timeout_ms = timeout_ms

    async def retrieve(
        self, *, query: str, limit: int = 10, correlation_id: UUID | None = None
    ) -> list[KnowledgeReference]:
        try:
            reply = await self._event_publisher.request(
                "knowledge.retrieve.request",
                KnowledgeRetrieveRequestPayload(query_text=query, limit=limit),
                source_engine=SOURCE_ENGINE,
                correlation_id=correlation_id,
                timeout_ms=self._timeout_ms,
            )
        except TimeoutError:
            return []
        parsed = KnowledgeRetrieveReplyPayload.model_validate(reply.payload)
        return [
            KnowledgeReference(
                node_id=result.node_id,
                name=result.name,
                layer=result.layer.value,
                confidence=result.confidence,
                related_node_ids=result.related_node_ids,
            )
            for result in parsed.results
        ]

    async def traverse(
        self, *, seed_node_id: str, depth: int = 2, correlation_id: UUID | None = None
    ) -> list[KnowledgeReference]:
        try:
            reply = await self._event_publisher.request(
                "knowledge.traverse.request",
                KnowledgeTraverseRequestPayload(seed_node_id=seed_node_id, max_hops=depth),
                source_engine=SOURCE_ENGINE,
                correlation_id=correlation_id,
                timeout_ms=self._timeout_ms,
            )
        except TimeoutError:
            return []
        parsed = KnowledgeTraverseReplyPayload.model_validate(reply.payload)
        return [
            KnowledgeReference(
                node_id=node_id,
                name=node_id,
                layer="unknown",
                confidence=_TRAVERSE_PLACEHOLDER_CONFIDENCE,
            )
            for node_id in parsed.connected_node_ids
        ]
