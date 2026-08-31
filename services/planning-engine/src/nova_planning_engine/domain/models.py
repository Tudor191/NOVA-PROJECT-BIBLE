"""Planning Engine's core domain model (Bible Part 9), per
docs/design/phase-3/05-tdd-3b-planning-engine.md §2 and
docs/architecture/06-ai-layer-architecture.md §3 (the schema source of
truth, reproduced verbatim below).

`TaskNode`/`TaskGraph`/`Estimate` are domain-local, not `nova_contracts`
types -- mirroring every other engine's own "domain model distinct from any
wire payload" convention (e.g. `reasoning-engine`'s `ReasoningProcess`/
`Decision`, never imported from `nova_contracts` despite that engine also
publishing wire payloads for the same events). No other Phase 3 TDD
references `TaskNode`/`TaskGraph`/`Estimate` by name (confirmed:
`06-tdd-3c-capability-engine.md` and `07-tdd-3d-action-engine.md` neither
mention either type), so nothing outside this engine needs them as a
shared, importable type today. `RiskLevel` is the one exception -- it is
reused directly by `action-engine`'s own domain model (TDD 3D), so it is
defined once in `nova_contracts.events.planning` and imported here, the
same "simple shared enum" pattern `ReasoningMode` already establishes for
`reasoning-engine`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from nova_contracts import RiskLevel
from pydantic import BaseModel, Field

__all__ = [
    "Estimate",
    "RiskLevel",
    "TaskGraph",
    "TaskNode",
    "TaskNodeStatus",
]

TaskNodeStatus = Literal["pending", "ready", "running", "blocked", "completed", "failed"]
"""doc06 §3's own six-state schema, verbatim -- mirrors the `LifecycleStatus`
type-alias-over-`Literal` convention `reasoning-engine`'s own
`domain/models.py` already establishes, rather than a `StrEnum`."""


class Estimate(BaseModel):
    """§2.1 Fork 3B-1 (approved): the minimum shape needed to support
    Critical Path Analysis (a duration figure) while acknowledging effort
    estimates are inherently uncertain (Bible Part 9's own "No task should
    remain too large for accurate estimation" framing,
    `part-09-planning-engine.md:107-156`). No canonical `Estimate` shape
    exists anywhere else in this project (confirmed by repo-wide search) --
    this is the one place it is defined."""

    effort_hours: float = Field(gt=0.0)
    confidence: float = Field(ge=0.0, le=1.0)


class TaskNode(BaseModel):
    """One node of a `TaskGraph` -- doc06 §3's schema verbatim, four of
    Bible Part 9's seven WBS fields mapped directly (`Estimated effort` ->
    `estimated_effort`, `Dependencies` -> `depends_on`, `Responsible agents`
    -> `assigned_agent_category`, plus `risk` from Part 9's own "Risk
    Analysis" section); the remaining three (`Completion criteria`,
    `Deliverables`, `Required knowledge`, `Required tools` -- Fork 3B-2)
    are deliberately absent for Phase 3, confirmed via
    `docs/design/phase-3/06-tdd-3c-capability-engine.md` and
    `07-tdd-3d-action-engine.md` that no downstream Phase 3 TDD references
    any of them -- Bible-Part-9-only, historical/document-only fields for
    now, not required-for-Phase-3 or required-for-a-named-later-phase
    fields, revisited if a real future consumer ever needs one."""

    id: UUID = Field(default_factory=uuid4)
    objective: str
    depends_on: list[UUID] = Field(default_factory=list)
    assigned_agent_category: str | None = None
    estimated_effort: Estimate
    risk: RiskLevel
    status: TaskNodeStatus = "pending"


class TaskGraph(BaseModel):
    """doc06 §3's schema verbatim. `critical_path` is a plain, caller-supplied
    field here (as doc06 §3 itself specifies), not a computed property --
    `domain/task_graph.py`'s `compute_critical_path()` is the pure function
    that produces its value; keeping the two separate mirrors this
    codebase's established "domain functions operate on and return plain
    models" style (e.g. `reasoning-engine`'s `decision_matrix.rank_alternatives()`)
    over Pydantic `@model_validator`-based auto-computation, for which no
    precedent exists anywhere in this codebase's domain layers today."""

    id: UUID = Field(default_factory=uuid4)
    root_objective: str
    nodes: list[TaskNode] = Field(default_factory=list)
    critical_path: list[UUID] = Field(default_factory=list)
    approved_at: datetime | None = None
    """§5 (`phase-3b-planning-persistence`): set by `POST /v1/plans/{id}/approve`.
    Behaviorally meaningful (gates future Kernel dispatch, TDD 3E), so it
    lives on the domain model itself -- the same reasoning that puts
    `installed_at`/`health_status` directly on `nova_contracts.Capability`
    rather than leaving them ORM-only. Plain audit timestamps
    (`created_at`/`updated_at`) stay ORM-only instead, mirroring
    `action-engine`'s own `Action`/`ActionORM` asymmetry."""
