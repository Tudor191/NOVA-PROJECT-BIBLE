"""Memory Engine event payloads -- implements Bible Part 3, per
docs/design/phase-1/01-memory-engine.md §4 (schema) and §13 (event flow).

`MemoryType`, `LifecycleState`, and `PrivacyLevel` are defined here rather than in
Memory Engine's own domain layer because they appear directly in wire payloads other
engines consume (docs/design/phase-1/00-shared-foundations.md's "Confidence and
privacy, everywhere" convention) -- `nova-contracts` is the single schema source of
truth (docs/architecture/02-repository-and-folder-structure.md §4), and Memory
Engine's `domain/models.py` imports these rather than redefining them, exactly as
`nova-core`'s domain layer already imports `ModuleStatus` from
`nova_contracts.events.system`.

`schema_version: int = 1` (Project Health Review, August 2026): backfilled onto
every `@register_payload`-decorated class here per ADR-024 (interface
versioning from day one) -- this module predates ADR-024's adoption (Phase 1)
and was never retroactively updated. Purely additive (a defaulted field), no
behavior change. `MemorySearchResultPayload` is a nested value object embedded
in `MemoryRetrieveReplyPayload`, not itself a registered wire payload, so it
does not carry its own `schema_version`.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from nova_contracts.registry import register_payload


class MemoryType(StrEnum):
    """The six persisted long-term memory categories (Bible Part 3). Sensory,
    Working, and Short Term memory are not `memory_type` values -- they are held in
    distinct stores (in-process buffer, Redis, `short_term_record`), per
    docs/design/phase-1/01-memory-engine.md §2. Relationship Memory is not stored
    here at all (§5: delegated entirely to Knowledge Engine)."""

    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    EPISODIC = "episodic"
    PROJECT = "project"
    PREFERENCE = "preference"
    DECISION = "decision"


class LifecycleState(StrEnum):
    """The five-stage forgetting state machine, docs/design/phase-1/
    01-memory-engine.md §6. `ARCHIVED -> SCHEDULED_FOR_DELETION` is never a passive
    time-based transition in Phase 1 -- see that section for the explicit triggers
    required."""

    ACTIVE = "active"
    WEAK = "weak"
    ARCHIVED = "archived"
    SCHEDULED_FOR_DELETION = "scheduled_for_deletion"
    DELETED = "deleted"


class PrivacyLevel(StrEnum):
    """Bible Part 7's privacy classification, propagated on every entity per
    docs/design/phase-1/00-shared-foundations.md's "Confidence and privacy,
    everywhere" convention. Enforcement point is the Model Orchestration Engine
    (Phase 2); Phase 1 stores and propagates the field correctly from day one."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    HIGHLY_SENSITIVE = "highly_sensitive"


@register_payload("memory.short_term.created")
class ShortTermMemoryCreatedPayload(BaseModel):
    short_term_id: UUID
    user_id: UUID
    project_id: UUID | None = None
    category: str
    expires_at: datetime
    schema_version: int = 1


@register_payload("memory.long_term.created")
class LongTermMemoryCreatedPayload(BaseModel):
    memory_id: UUID
    user_id: UUID
    project_id: UUID | None = None
    memory_type: MemoryType
    importance_score: float = Field(ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    privacy_level: PrivacyLevel
    knowledge_node_id: str | None = None
    schema_version: int = 1


@register_payload("memory.long_term.updated")
class LongTermMemoryUpdatedPayload(BaseModel):
    memory_id: UUID
    user_id: UUID
    updated_fields: list[str]
    version: int = Field(ge=1)
    schema_version: int = 1


@register_payload("memory.consolidation.started")
class ConsolidationStartedPayload(BaseModel):
    run_id: UUID
    schema_version: int = 1


@register_payload("memory.consolidation.completed")
class ConsolidationCompletedPayload(BaseModel):
    run_id: UUID
    records_scanned: int = Field(ge=0)
    records_merged: int = Field(ge=0)
    records_advanced: int = Field(ge=0)
    records_deleted: int = Field(ge=0)
    status: str
    schema_version: int = 1


@register_payload("memory.lifecycle.transitioned")
class LifecycleTransitionedPayload(BaseModel):
    memory_id: UUID
    user_id: UUID
    previous_state: LifecycleState
    new_state: LifecycleState
    reason: str
    schema_version: int = 1


@register_payload("memory.decision.recorded")
class DecisionRecordedPayload(BaseModel):
    decision_id: UUID
    memory_id: UUID
    user_id: UUID
    objective: str
    chosen_alternative: str
    confidence_at_decision: float | None = Field(default=None, ge=0.0, le=1.0)
    schema_version: int = 1


@register_payload("memory.embedding.completed")
class EmbeddingCompletedPayload(BaseModel):
    memory_id: UUID
    embedding_model: str
    dimensions: int = Field(gt=0)
    schema_version: int = 1


class MemorySearchResultPayload(BaseModel):
    """One ranked result within a `MemoryRetrieveReplyPayload`. Component scores are
    included per docs/design/phase-1/01-memory-engine.md §7 step 7 -- retrieval is
    explainable, not just a bare ranked list."""

    memory_id: UUID
    memory_type: MemoryType
    content: str
    score: float
    similarity: float | None = None
    importance_score: float = Field(ge=0.0, le=1.0)
    recency_decay: float | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


@register_payload("memory.retrieve.request")
class MemoryRetrieveRequestPayload(BaseModel):
    """Request/reply RPC served by Memory Engine
    (docs/design/phase-1/01-memory-engine.md §13, §14)."""

    user_id: UUID
    query_text: str | None = None
    project_id: UUID | None = None
    memory_type: MemoryType | None = None
    include_relationships: bool = False
    limit: int = Field(default=10, ge=1, le=100)
    schema_version: int = 1


@register_payload("memory.retrieve.reply")
class MemoryRetrieveReplyPayload(BaseModel):
    results: list[MemorySearchResultPayload] = Field(default_factory=list)
    degraded: bool = False
    """Set when `VectorStore` (or, if requested, Knowledge Engine) was unreachable
    and results fell back to a narrower search mode -- docs/design/phase-1/
    01-memory-engine.md §17's "Read-path degradation"."""
    schema_version: int = 1
