"""Domain entities -- not ORM models (docs/design/phase-1/02-knowledge-engine.md
§1). `KnowledgeLayer`, `KnowledgeScope`, `PrivacyLevel` are re-exported from
`nova-contracts` rather than redefined here (docs/design/phase-1/
00-shared-foundations.md's shared schema convention) -- they appear in wire
payloads other engines consume, so `nova-contracts` is their one source of truth.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from nova_contracts import KnowledgeLayer, KnowledgeScope, PrivacyLevel
from pydantic import BaseModel, Field

__all__ = [
    "Contradiction",
    "GraphWriteIntent",
    "GraphWriteOp",
    "KnowledgeLayer",
    "KnowledgeNode",
    "KnowledgeScope",
    "NodeVersionHistoryEntry",
    "PrivacyLevel",
    "SourceAttribution",
    "UsageSummary",
]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class KnowledgeNode(BaseModel):
    """The unified `node_metadata` row (docs/design/phase-1/02-knowledge-engine.md
    §4) -- the Postgres-side projection of a Neo4j node. `node_id` is a `TEXT`
    primary key that also matches the Neo4j node's `id` property (Neo4j has no
    native UUID type), deterministically derived by `domain/normalization.py` from
    `label` + `name` + `scope` (+ `project_id`/`user_id` when scoped) so repeated
    acquisition of the same concept upserts the same node rather than duplicating
    it."""

    node_id: str
    label: str
    name: str
    domain: str | None = None
    scope: KnowledgeScope = KnowledgeScope.GLOBAL
    project_id: UUID | None = None
    user_id: UUID | None = None
    embedding: list[float] | None = None
    embedding_model: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL
    layer: KnowledgeLayer = KnowledgeLayer.RAW
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class SourceAttribution(BaseModel):
    """docs/design/phase-1/02-knowledge-engine.md §4 `source_attribution` -- one row
    per corroborating source a node has accumulated; count of rows for a node is
    the corroboration signal `domain/validation.py` and `domain/evolution.py` both
    read."""

    id: UUID = Field(default_factory=uuid4)
    node_id: str
    source_type: str
    source_ref: str | None = None
    excerpt: str | None = None
    confidence_contribution: float | None = None
    recorded_at: datetime = Field(default_factory=_utcnow)


class NodeVersionHistoryEntry(BaseModel):
    """docs/design/phase-1/02-knowledge-engine.md §4 `node_version_history` --
    Part 10's required content history ("nothing important should disappear
    permanently"), stronger than Memory's reliance on `updated_at` alone."""

    id: UUID = Field(default_factory=uuid4)
    node_id: str
    version: int
    change_type: str
    previous_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    changed_by: str
    changed_at: datetime = Field(default_factory=_utcnow)


class Contradiction(BaseModel):
    """docs/design/phase-1/02-knowledge-engine.md §4 `contradiction` --
    `domain/contradiction.py` may create and (via an explicit resolve call) close
    these, but never silently delete either side of the conflict."""

    id: UUID = Field(default_factory=uuid4)
    node_a_id: str
    node_b_id: str
    description: str
    status: Literal["open", "investigating", "resolved"] = "open"
    resolution: str | None = None
    detected_at: datetime = Field(default_factory=_utcnow)
    resolved_at: datetime | None = None


class UsageSummary(BaseModel):
    """Usage signal feeding `domain/evolution.py`'s Applied/Expert/Strategic
    transitions (docs/design/phase-1/02-knowledge-engine.md §6), sourced from
    `memory.long_term.created` and `reasoning.result` events per §13. Not part of
    §4's literal schema listing -- a minimal, explicitly justified extension (see
    `repository/models.py`'s `NodeUsageORM`), since those transitions would
    otherwise be permanently unreachable."""

    usage_count: int = 0
    distinct_project_ids: list[UUID] = Field(default_factory=list)


class GraphWriteOp(BaseModel):
    """One Neo4j operation, backend-agnostic enough to serialize into
    `outbox_event.graph_write` JSONB and be replayed later by the saga dispatcher
    (docs/design/phase-1/02-knowledge-engine.md §17)."""

    kind: Literal["upsert_node", "upsert_relationship"]
    node_id: str | None = None
    label: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    from_id: str | None = None
    to_id: str | None = None
    relationship_type: str | None = None


class GraphWriteIntent(BaseModel):
    """The pending Neo4j write for one outbox row -- `domain/graph_operations.py`
    is the only module that produces one; `repository/outbox_dispatcher.py` is the
    only place one is ever applied against a real `GraphStore` (via
    `graph_operations.apply_graph_write`)."""

    ops: list[GraphWriteOp] = Field(default_factory=list)
