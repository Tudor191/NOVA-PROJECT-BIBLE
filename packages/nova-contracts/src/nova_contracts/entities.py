"""Shared internal domain reference types -- never published on the Event Bus
directly (no `@register_payload`, unlike everything under `events/`), so not
schema-versioned (ADR-024 governs *public* wire interfaces; these aren't
one). `docs/architecture/02-repository-and-folder-structure.md` §4's own
canonical design already anticipated a `schemas/entities/` space for "shared
domain entities" alongside `events/` -- never built until now.

Extracted per `docs/design/nova-service-kit/boilerplate-extraction-proposal.md`
Extraction E, after a design review confirmed these three types are
genuinely semantically identical between `executive-cognition-engine` and
`reasoning-engine` (byte-identical construction logic in each engine's own
`memory_client.py`/`world_model_client.py`/`personal_context_client.py`,
reading the same `nova_contracts` request/reply payloads), not merely
coincidentally similar in shape. `communication-engine`'s own
`WorldModelSnapshot` is deliberately excluded -- it is a genuinely narrower,
5-of-8-field projection for a different use case (design doc §8.7), not the
same concept, and stays local to that engine.

`Goal` and `HumanOverrideRequest` were considered and explicitly rejected for
this extraction: `Goal` has already diverged (`executive-cognition-engine`
added `goal_tier` per ADR-029, `reasoning-engine` has not);
`HumanOverrideRequest` was never actually the same type across the two
engines that have one (different foreign keys into different aggregates,
different-but-deliberately-separate action enums).
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

__all__ = [
    "MemoryReference",
    "PersonalContext",
    "WorldModelSnapshot",
]


class MemoryReference(BaseModel):
    """Carries Memory Engine's own ID and a bounded summary only, never the
    memory's full content -- the narrow ID+summary anti-corruption-layer
    pattern applied to a value shared identically by two peer consumers
    reading the same upstream `memory.retrieve.request` reply."""

    memory_id: UUID
    summary: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class WorldModelSnapshot(BaseModel):
    """A read-only snapshot of World Model's Active Context, as read from
    `world_model.context.request`. `degraded` mirrors
    `ContextReplyPayload.degraded`: not an error, a signal to proceed
    without (or with reduced-confidence) grounding rather than failing."""

    user_id: UUID
    objective: str | None = None
    project_id: UUID | None = None
    device: str | None = None
    task: str | None = None
    activity: str | None = None
    confidence: float | None = None
    degraded: bool = False


class PersonalContext(BaseModel):
    """A thin projection of `WorldModelSnapshot` -- the shared honest
    placeholder both engines use pending a dedicated Digital Twin Engine
    (Bible Part 16, future phase). Named as its own type now so only this
    shape (and each engine's one adapter) changes when that engine ships."""

    user_id: UUID
    objective: str | None = None
    project_id: UUID | None = None
    device: str | None = None
    task: str | None = None
