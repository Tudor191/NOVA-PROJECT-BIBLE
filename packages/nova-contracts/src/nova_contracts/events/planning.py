"""Planning Engine shared vocabulary (Bible Part 9), per
docs/design/phase-3/05-tdd-3b-planning-engine.md.

`RiskLevel` lives here, not in `nova_planning_engine.domain.models`, because
it is reused directly by a second engine's own domain model
(`action-engine`'s `ActionObject.risk: RiskLevel`, TDD 3D §2.1/§3.3) --
the identical "simple, structurally-shared enum defined once in
`nova_contracts`, imported by every domain layer that needs it" shape
`ReasoningMode` (`events/reasoning.py`) already establishes, rather than a
second, independently-defined risk scale that TDD 3D would otherwise have to
reinterpret. `TaskNode`/`TaskGraph`/`Estimate` themselves stay engine-local
to `nova_planning_engine.domain.models` (the disclosed deviation from TDD
3B §11's original proposal, recorded in
`docs/roadmap/architecture-reviews/phase-3b-domain-foundation-gate-review.md`
§1) -- no other Phase 3 TDD references them directly, so nothing forces them
into this shared package.

**`planning.task_graph.created`/`planning.decompose.request`/`.reply`
(added, `phase-3b-planning-persistence` precursor, TDD 3B §4/§5/§6.2)**:
these are wire payloads, independently defined here with their own
snapshot types (`TaskNodeSnapshot`/`TaskGraphSnapshot`) rather than
importing `nova_planning_engine.domain.models.TaskNode`/`TaskGraph`
directly -- consistent with the domain-vs-wire-payload split above (the
domain types stay engine-local; a wire payload that needs the same *shape*
gets its own, independently-defined type here, translated at
`planning-engine`'s own publish boundary, the same "repository/publish
translation function" pattern `action-engine`'s
`postgres_action_repository.py::_to_domain` already establishes for the
domain-vs-ORM boundary)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from nova_contracts.registry import register_payload

__all__ = [
    "PlanningDecomposeReplyPayload",
    "PlanningDecomposeRequestPayload",
    "PlanningTaskGraphCreatedPayload",
    "RiskLevel",
    "TaskGraphSnapshot",
    "TaskNodeSnapshot",
]


class RiskLevel(StrEnum):
    """Bible Part 14's risk classification scale
    (`docs/bible/part-14-autonomy-engine.md:271-279`), reused verbatim --
    the one canonical risk-tier scale anywhere in this project, rather than
    a second, `planning-engine`-specific scale that `action-engine` (TDD 3D)
    would otherwise have to reinterpret or map."""

    NEGLIGIBLE = "negligible"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class TaskNodeSnapshot(BaseModel):
    """Wire-shaped mirror of `nova_planning_engine.domain.models.TaskNode`
    (field-for-field), independently defined per this module's own
    docstring -- never imports the domain type."""

    id: UUID
    objective: str
    depends_on: list[UUID] = Field(default_factory=list)
    assigned_agent_category: str | None = None
    effort_hours: float
    confidence: float
    risk: RiskLevel
    status: Literal["pending", "ready", "running", "blocked", "completed", "failed"]


class TaskGraphSnapshot(BaseModel):
    """Wire-shaped mirror of `nova_planning_engine.domain.models.TaskGraph`
    at the moment of publication -- the full graph, not a delta, matching
    every other "snapshot event" convention in this codebase (e.g.
    `world_model.active_context.updated`)."""

    id: UUID
    root_objective: str
    nodes: list[TaskNodeSnapshot]
    critical_path: list[UUID]
    approved_at: datetime | None = None


@register_payload("planning.task_graph.created")
class PlanningTaskGraphCreatedPayload(BaseModel):
    """TDD 3B §6.2: published on graph creation *and* on major mutation
    (doc 10 row 6's own "creation/major mutation" wording) -- the same
    subject and payload shape for both, distinguished only by whether
    `graph.id` was already seen by a subscriber, not by a second subject."""

    graph: TaskGraphSnapshot
    correlation_id: UUID
    schema_version: int = 1


@register_payload("planning.decompose.request")
class PlanningDecomposeRequestPayload(BaseModel):
    """TDD 3B §6.2, per doc 12 §11: a Supervisor (agent-os, not built until
    TDD 3E) or any other caller may request further decomposition of one
    `TaskNode` "still too coarse for a single leaf agent," scoped to that
    node's own subtree. `requesting_engine`/`correlation_id` follow the
    same request/reply RPC shape as every other `nova_contracts` RPC
    payload (e.g. `CapabilityResolveRequestPayload`)."""

    task_node_id: UUID
    requesting_engine: str
    correlation_id: UUID
    schema_version: int = 1


@register_payload("planning.decompose.reply")
class PlanningDecomposeReplyPayload(BaseModel):
    """`already_minimal=True` and `new_nodes=[]` together are TDD 3B §8's
    own explicitly-required "already minimal" case -- a structured,
    distinguishable reply, never a silent no-op indistinguishable from
    success."""

    already_minimal: bool
    new_nodes: list[TaskNodeSnapshot] = Field(default_factory=list)
    schema_version: int = 1
