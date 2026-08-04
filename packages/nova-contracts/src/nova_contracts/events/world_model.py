"""World Model Engine event payloads -- implements the merged Bible Part 5 + Part
18, per docs/design/phase-1/03-world-model-engine.md §4 (schema), §6 (object
state model), and §13 (event flow).

`ObjectState` is defined here rather than in World Model's own domain layer
because it appears directly in wire payloads other engines consume
(docs/design/phase-1/00-shared-foundations.md's shared-schema convention).

World Model has no `PrivacyLevel` of its own -- it reuses `nova_contracts.events.
memory.PrivacyLevel` (imported by `nova_world_model_engine.domain.models`, not
re-exported from here), since it is the same one classification scheme every
Phase 1 engine shares.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from nova_contracts.registry import register_payload


class ObjectState(StrEnum):
    """World Model's object-state model (docs/design/phase-1/
    03-world-model-engine.md §6) -- deliberately not a "lifecycle" in Memory
    Engine's sense: there is no forgetting/deletion path here, only transitions
    between states of *current* reality. `UNKNOWN` is the only state with no
    incoming transition from another state (`[*] --> Unknown` in §6's diagram)."""

    UNKNOWN = "unknown"
    ACTIVE = "active"
    IDLE = "idle"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"
    LEARNING = "learning"


@register_payload("world_model.object.created")
@register_payload("world_model.object.updated")
@register_payload("world_model.object.deleted")
class WorldObjectChangedPayload(BaseModel):
    """Shared shape for `.created`/`.updated`/`.deleted` -- the three subjects
    differ only in when they fire (docs/design/phase-1/03-world-model-engine.md
    §13)."""

    object_id: str
    label: str
    user_id: UUID
    previous_state: ObjectState | None = None
    new_state: ObjectState
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


@register_payload("world_model.context.changed")
class ContextChangedPayload(BaseModel):
    """One fused Active Context update (docs/design/phase-1/
    03-world-model-engine.md §3) -- `domain/fusion.py` publishes at most one of
    these per correlation window, never one per raw signal."""

    user_id: UUID
    objective: str | None = None
    project_id: UUID | None = None
    device: str | None = None
    task: str | None = None
    activity: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


@register_payload("world_model.attention.shifted")
class AttentionShiftedPayload(BaseModel):
    user_id: UUID
    entity_id: str
    attention_score: float = Field(ge=0.0)


@register_payload("world_model.prediction.generated")
class PredictionPayload(BaseModel):
    prediction_id: UUID
    user_id: UUID
    prediction: str
    confidence: float = Field(ge=0.0, le=1.0)
    predicted_for: datetime | None = None


@register_payload("world_model.context.request")
class ContextRequestPayload(BaseModel):
    """The highest-QPS internal call in the whole Phase 1 surface -- every
    Reasoning pipeline execution calls it (docs/design/phase-1/
    03-world-model-engine.md §14-15). `scope` selects Agent-Awareness filtering
    (Part 11), e.g. `"agent:coding-agent"`; `None` returns the full Active
    Context."""

    user_id: UUID
    scope: str | None = None


@register_payload("world_model.context.reply")
class ContextReplyPayload(BaseModel):
    user_id: UUID
    objective: str | None = None
    project_id: UUID | None = None
    device: str | None = None
    task: str | None = None
    activity: str | None = None
    confidence: float | None = None
    updated_at: datetime | None = None
    degraded: bool = False
    """Set when Redis (Active Context's primary store, not a cache) was
    unreachable -- docs/design/phase-1/03-world-model-engine.md §17: World Model
    fails fast rather than silently returning stale/empty context; the caller
    (Executive Cognition) has its own documented fallback for this signal."""
