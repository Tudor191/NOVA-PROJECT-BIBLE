"""Knowledge Engine request/reply payloads Memory Engine depends on today
(docs/design/phase-1/01-memory-engine.md §5, docs/design/phase-1/
04-cross-engine-integration.md §1 -- the one real, exercised Phase 1 cross-engine
integration). Defined here, ahead of Knowledge Engine's own implementation, because
`memory-engine.domain.relationship` needs a typed contract to call against; Knowledge
Engine implements the serving side against this same schema when it's built next.
Kept intentionally minimal (primitives, not `nova-graphstore-sdk` types) -- a wire
contract should not depend on another package's internal representation.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from nova_contracts.registry import register_payload

DEFAULT_MAX_HOPS = 2
MAX_HOPS_LIMIT = 5


@register_payload("knowledge.link.request")
class KnowledgeLinkRequestPayload(BaseModel):
    """Create-or-find a Concept (or other labeled) node and link it to a memory.
    Served by Knowledge Engine's `graph_operations.py`."""

    memory_id: UUID
    concept_name: str


@register_payload("knowledge.link.reply")
class KnowledgeLinkReplyPayload(BaseModel):
    knowledge_node_id: str


@register_payload("knowledge.traverse.request")
class KnowledgeTraverseRequestPayload(BaseModel):
    """Bounded graph traversal from an existing node -- unbounded traversal is
    deliberately not expressible (docs/design/phase-1/02-knowledge-engine.md §7)."""

    seed_node_id: str
    max_hops: int = Field(default=DEFAULT_MAX_HOPS, ge=1, le=MAX_HOPS_LIMIT)


@register_payload("knowledge.traverse.reply")
class KnowledgeTraverseReplyPayload(BaseModel):
    connected_node_ids: list[str] = Field(default_factory=list)
