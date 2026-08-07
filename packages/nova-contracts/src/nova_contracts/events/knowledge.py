"""Knowledge Engine event payloads -- implements Bible Part 10, per
docs/design/phase-1/02-knowledge-engine.md §4 (schema), §6 (evolution), and §13
(event flow).

The request/reply payloads (`KnowledgeLinkRequestPayload`, etc.) were defined first,
ahead of Knowledge Engine's own implementation, because `memory-engine.domain.
relationship` needs a typed contract to call against (docs/design/phase-1/
01-memory-engine.md §5, docs/design/phase-1/04-cross-engine-integration.md §1 -- the
one real, exercised Phase 1 cross-engine integration); Knowledge Engine implements
the serving side against this same schema. Kept intentionally minimal (primitives,
not `nova-graphstore-sdk` types) -- a wire contract should not depend on another
package's internal representation.

`PrivacyLevel` is reused from `nova_contracts.events.memory` rather than redefined --
docs/design/phase-1/00-shared-foundations.md's "Confidence and privacy, everywhere"
convention is one shared classification across all three Phase 1 engines, not a
per-engine copy.

`schema_version: int = 1` (Project Health Review, August 2026): backfilled onto
every `@register_payload`-decorated class here per ADR-024 (interface
versioning from day one) -- this module predates ADR-024's adoption (Phase 1)
and was never retroactively updated. Purely additive (a defaulted field), no
behavior change. `KnowledgeSearchResultPayload` is a nested value object embedded
in `KnowledgeRetrieveReplyPayload`, not itself a registered wire payload, so it
does not carry its own `schema_version`.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from nova_contracts.registry import register_payload

DEFAULT_MAX_HOPS = 2
MAX_HOPS_LIMIT = 5


class KnowledgeLayer(StrEnum):
    """The seven-stage knowledge maturity state machine, docs/design/phase-1/
    02-knowledge-engine.md §6. Unlike Memory's lifecycle, this never terminates in
    deletion -- Part 10 has no forgetting model for knowledge, only maturation."""

    RAW = "raw"
    PROCESSED = "processed"
    VERIFIED = "verified"
    CONNECTED = "connected"
    APPLIED = "applied"
    EXPERT = "expert"
    STRATEGIC = "strategic"


class KnowledgeScope(StrEnum):
    """Part 10's Domain/Personal/Project Knowledge distinction, implemented as one
    column rather than separate tables (docs/design/phase-1/02-knowledge-engine.md
    §2)."""

    GLOBAL = "global"
    PROJECT = "project"
    PERSONAL = "personal"


@register_payload("knowledge.link.request")
class KnowledgeLinkRequestPayload(BaseModel):
    """Create-or-find a Concept (or other labeled) node and link it to a memory.
    Served by Knowledge Engine's `graph_operations.py`."""

    memory_id: UUID
    concept_name: str
    schema_version: int = 1


@register_payload("knowledge.link.reply")
class KnowledgeLinkReplyPayload(BaseModel):
    knowledge_node_id: str
    schema_version: int = 1


@register_payload("knowledge.traverse.request")
class KnowledgeTraverseRequestPayload(BaseModel):
    """Bounded graph traversal from an existing node -- unbounded traversal is
    deliberately not expressible (docs/design/phase-1/02-knowledge-engine.md §7)."""

    seed_node_id: str
    max_hops: int = Field(default=DEFAULT_MAX_HOPS, ge=1, le=MAX_HOPS_LIMIT)
    schema_version: int = 1


@register_payload("knowledge.traverse.reply")
class KnowledgeTraverseReplyPayload(BaseModel):
    connected_node_ids: list[str] = Field(default_factory=list)
    schema_version: int = 1


@register_payload("knowledge.node.created")
@register_payload("knowledge.node.updated")
class KnowledgeNodeChangedPayload(BaseModel):
    """Shared shape for both `knowledge.node.created` and `.updated` -- the two
    subjects differ only in when they fire, not in payload shape (docs/design/
    phase-1/02-knowledge-engine.md §13). Published only after the Neo4j side of the
    saga (§17) has actually applied -- consumers never see a node "created" before
    it's queryable in the graph."""

    node_id: str
    label: str
    name: str
    domain: str | None = None
    scope: KnowledgeScope
    confidence: float = Field(ge=0.0, le=1.0)
    layer: KnowledgeLayer
    version: int = Field(ge=1)
    schema_version: int = 1


@register_payload("knowledge.edge.created")
class KnowledgeEdgeCreatedPayload(BaseModel):
    from_node_id: str
    to_node_id: str
    relationship_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    schema_version: int = 1


@register_payload("knowledge.contradiction.detected")
@register_payload("knowledge.contradiction.resolved")
class ContradictionPayload(BaseModel):
    """Shared shape for `.detected` and `.resolved` -- `resolution`/`resolved_at`
    are unset on `.detected` (docs/design/phase-1/02-knowledge-engine.md §13)."""

    contradiction_id: UUID
    node_a_id: str
    node_b_id: str
    description: str
    status: str
    resolution: str | None = None
    schema_version: int = 1


@register_payload("knowledge.layer.advanced")
class LayerAdvancedPayload(BaseModel):
    node_id: str
    previous_layer: KnowledgeLayer
    new_layer: KnowledgeLayer
    reason: str
    schema_version: int = 1


class KnowledgeSearchResultPayload(BaseModel):
    """One ranked result within a `KnowledgeRetrieveReplyPayload`, richer than
    Memory's equivalent because "the surrounding context, the relationships, the
    history" is the point of Knowledge retrieval (docs/design/phase-1/
    02-knowledge-engine.md §7 step 6)."""

    node_id: str
    label: str
    name: str
    score: float
    similarity: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    layer: KnowledgeLayer
    related_node_ids: list[str] = Field(default_factory=list)


@register_payload("knowledge.retrieve.request")
class KnowledgeRetrieveRequestPayload(BaseModel):
    """Request/reply RPC served by Knowledge Engine (docs/design/phase-1/
    02-knowledge-engine.md §13, §14)."""

    query_text: str | None = None
    seed_node_id: str | None = None
    scope: KnowledgeScope | None = None
    project_id: UUID | None = None
    user_id: UUID | None = None
    max_hops: int = Field(default=DEFAULT_MAX_HOPS, ge=1, le=MAX_HOPS_LIMIT)
    limit: int = Field(default=10, ge=1, le=100)
    schema_version: int = 1


@register_payload("knowledge.retrieve.reply")
class KnowledgeRetrieveReplyPayload(BaseModel):
    results: list[KnowledgeSearchResultPayload] = Field(default_factory=list)
    degraded: bool = False
    """Set when the graph or vector index was unreachable and results fell back to
    a narrower search mode -- mirrors docs/design/phase-1/01-memory-engine.md §17's
    "Read-path degradation", applied here per §17's Neo4j-unreachable-during-a-read
    failure mode."""
    schema_version: int = 1
