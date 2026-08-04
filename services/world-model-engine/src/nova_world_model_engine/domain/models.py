"""Domain entities -- not ORM models (docs/design/phase-1/03-world-model-engine.md
§1). `ObjectState` is re-exported from `nova-contracts` rather than redefined here
(docs/design/phase-1/00-shared-foundations.md's shared schema convention) --
`PrivacyLevel` likewise, reused from `nova_contracts.events.memory` since it is one
classification scheme shared by every Phase 1 engine, not redefined per engine.

**The boundary this file exists to enforce** (standing architectural constraint):
World Model represents *current* reality, never accumulated history (that's Memory
Engine) and never validated, cross-referenced facts (that's Knowledge Engine).
Every model here is either present-tense state (`WorldObject`, `ActiveContext`,
`AttentionEntry`) or a narrow, append-only record of *when a transition happened*
(`ObjectStateHistoryEntry`) -- never a content-versioned entity the way
`nova_knowledge_engine.domain.models.KnowledgeNode` is. If a future change to this
file would make it hold opinions about *why* something is true (Knowledge's job)
or a growing narrative of *what happened* (Memory's job), it belongs in a
different engine instead.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from nova_contracts import ObjectState
from nova_contracts.events.memory import PrivacyLevel
from pydantic import BaseModel, Field

__all__ = [
    "ActiveContext",
    "AttentionEntry",
    "ConflictLogEntry",
    "ObjectState",
    "ObjectStateHistoryEntry",
    "Prediction",
    "PrivacyLevel",
    "Snapshot",
    "WorldObject",
]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class WorldObject(BaseModel):
    """The Postgres-side projection of a Neo4j World Object node (docs/design/
    phase-1/03-world-model-engine.md §5) -- current state only. `object_id`
    matches the Neo4j node's `id` property; unlike Knowledge Engine's `node_id`,
    it is never derived from a name (World Objects are identified by their
    perception-source-assigned handle -- a window handle, a file path hash, a
    project UUID -- not a slugified concept name)."""

    object_id: str
    label: str
    user_id: UUID
    state: ObjectState = ObjectState.UNKNOWN
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    privacy_level: PrivacyLevel = PrivacyLevel.CONFIDENTIAL
    """Confidential by default, not internal -- §18: live activity is more
    sensitive than an isolated memory fact."""
    properties: dict[str, Any] = Field(default_factory=dict)
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ActiveContext(BaseModel):
    """`world:context:<user_id>` (§4) -- Redis is the primary store, not a cache
    of this. This model is the in-process representation `domain/context.py`
    reads/writes through `ContextRepository`; it is never itself persisted to
    Postgres."""

    user_id: UUID
    objective: str | None = None
    project_id: UUID | None = None
    device: str | None = None
    task: str | None = None
    activity: str | None = None
    platform: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    updated_at: datetime = Field(default_factory=_utcnow)


class AttentionEntry(BaseModel):
    """One `world:attention:<user_id>` ZSET member (§4) -- `raw_weight` is
    boosted (never overwritten) by `domain/attention.py`; current attention is
    always recomputed lazily from `(raw_weight, last_boosted_at)` at read time
    (§6), never maintained by a scheduled decay job."""

    entity_id: str
    raw_weight: float = Field(default=0.0, ge=0.0)
    last_boosted_at: datetime = Field(default_factory=_utcnow)


class ObjectStateHistoryEntry(BaseModel):
    """docs/design/phase-1/03-world-model-engine.md §4 `object_state_history` --
    an append-only log that *is* the version history (§12): unlike Knowledge
    Engine, there is no separate content-diff table, because World Object
    properties don't need diffing the way knowledge node content does -- only
    the state transition itself is the fact worth recording."""

    id: int | None = None
    object_id: str
    object_label: str
    user_id: UUID
    previous_state: ObjectState | None = None
    new_state: ObjectState
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    changed_at: datetime = Field(default_factory=_utcnow)
    correlation_id: UUID | None = None


class Snapshot(BaseModel):
    """docs/design/phase-1/03-world-model-engine.md §4 `snapshot` -- a
    coarse-grained, point-in-time version of the *entire* context (Active
    Context + object graph summary, not the full graph), restorable wholesale
    rather than replayed field-by-field (§12)."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    taken_at: datetime = Field(default_factory=_utcnow)
    snapshot_data: dict[str, Any] = Field(default_factory=dict)
    trigger: Literal["scheduled", "manual", "pre_risky_action"] = "manual"


class Prediction(BaseModel):
    """docs/design/phase-1/03-world-model-engine.md §4 `prediction`."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    prediction: str
    confidence: float = Field(ge=0.0, le=1.0)
    predicted_for: datetime | None = None
    outcome: Literal["confirmed", "refuted", "unknown"] | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class ConflictLogEntry(BaseModel):
    """docs/design/phase-1/03-world-model-engine.md §4 `conflict_log` --
    `domain/conflict_resolution.py` always produces a value (never blocks the
    write, §17), but every resolution is logged here regardless of strategy, so
    an `unresolved` entry is a visible signal for later Reasoning Engine review
    (Phase 2+), not a silent default."""

    id: UUID = Field(default_factory=uuid4)
    object_id: str
    observation_a: dict[str, Any]
    observation_b: dict[str, Any]
    resolution_strategy: Literal["confidence", "recency", "policy", "unresolved"]
    resolved_value: dict[str, Any] | None = None
    resolved_at: datetime = Field(default_factory=_utcnow)
