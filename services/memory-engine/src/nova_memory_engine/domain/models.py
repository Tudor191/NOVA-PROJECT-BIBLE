"""Domain entities -- not ORM models (docs/design/phase-1/01-memory-engine.md §1).

`MemoryType`, `LifecycleState`, `PrivacyLevel` are re-exported from `nova-contracts`
rather than redefined here (docs/design/phase-1/00-shared-foundations.md's shared
schema convention) -- they appear in wire payloads other engines consume, so
`nova-contracts` is their one source of truth.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from nova_contracts import LifecycleState, MemoryType, PrivacyLevel
from pydantic import BaseModel, Field

__all__ = [
    "DecisionData",
    "DecisionRecord",
    "EpisodicData",
    "LifecycleState",
    "MemoryRecord",
    "MemoryType",
    "PreferenceData",
    "PrivacyLevel",
    "ProceduralData",
    "ProjectData",
    "SemanticData",
    "ShortTermRecord",
]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class EpisodicData(BaseModel):
    memory_type: Literal[MemoryType.EPISODIC] = MemoryType.EPISODIC
    participants: list[str] = Field(default_factory=list)
    timeline_start: datetime | None = None
    timeline_end: datetime | None = None
    outcome: str | None = None
    lessons_learned: str | None = None


class ProceduralData(BaseModel):
    memory_type: Literal[MemoryType.PROCEDURAL] = MemoryType.PROCEDURAL
    steps: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    tools_required: list[str] = Field(default_factory=list)


class PreferenceData(BaseModel):
    memory_type: Literal[MemoryType.PREFERENCE] = MemoryType.PREFERENCE
    key: str
    value: str
    evidence_count: int = Field(default=1, ge=1)
    first_observed_at: datetime = Field(default_factory=_utcnow)


class SemanticData(BaseModel):
    memory_type: Literal[MemoryType.SEMANTIC] = MemoryType.SEMANTIC
    concept: str
    related_concepts: list[str] = Field(default_factory=list)


class ProjectData(BaseModel):
    """No extra shape of its own (docs/design/phase-1/01-memory-engine.md §4) --
    Project Memory is `project_id`-scoped, cross-cutting rather than a distinct
    content shape."""

    memory_type: Literal[MemoryType.PROJECT] = MemoryType.PROJECT


class DecisionData(BaseModel):
    memory_type: Literal[MemoryType.DECISION] = MemoryType.DECISION


TypeData = Annotated[
    EpisodicData | ProceduralData | PreferenceData | SemanticData | ProjectData | DecisionData,
    Field(discriminator="memory_type"),
]


class MemoryRecord(BaseModel):
    """The unified long-term memory row (docs/design/phase-1/01-memory-engine.md
    §4). One table, discriminated by `memory_type`, per the design's accepted
    tradeoff over one-table-per-type."""

    id: UUID = Field(default_factory=uuid4)
    memory_type: MemoryType
    content: str
    embedding: list[float] | None = None
    embedding_model: str | None = None
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL
    lifecycle_state: LifecycleState = LifecycleState.ACTIVE
    source: str | None = None
    source_ref: UUID | None = None
    project_id: UUID | None = None
    user_id: UUID
    knowledge_node_id: str | None = None
    type_data: dict[str, Any] = Field(default_factory=dict)
    access_count: int = Field(default=0, ge=0)
    last_accessed_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    version: int = Field(default=1, ge=1)


class ShortTermRecord(BaseModel):
    """docs/design/phase-1/01-memory-engine.md §4 `short_term_record`."""

    id: UUID = Field(default_factory=uuid4)
    content: str
    category: str
    project_id: UUID | None = None
    user_id: UUID
    source_ref: UUID | None = None
    expires_at: datetime
    created_at: datetime = Field(default_factory=_utcnow)


class DecisionRecord(BaseModel):
    """docs/design/phase-1/01-memory-engine.md §4 `decision_record`, always paired
    1:1 with a `MemoryRecord` whose `memory_type == DECISION`."""

    id: UUID = Field(default_factory=uuid4)
    memory_record_id: UUID
    objective: str
    alternatives: list[str] = Field(default_factory=list)
    chosen_alternative: str
    reasoning: str
    tradeoffs: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    outcome: str | None = None
    outcome_recorded_at: datetime | None = None
    confidence_at_decision: float | None = Field(default=None, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=_utcnow)
