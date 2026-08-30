"""Repository-internal domain types for `agent-os/kernel` -- `AgentInstance`
(TDD 3E §4, the `agent_instance` Postgres-schema row shape) stays local to
this component; nothing here is promoted to `nova_contracts` because it is
never independently published under its own Event Bus subject (only
`AgentOsTaskCompletedPayload`, in `nova_contracts.events.agent_os`, crosses
that boundary) -- mirrors `action-engine`'s own `PendingApproval`/
`IdentityConfidencePolicy` convention: repository-internal bookkeeping types
that never leave the owning engine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from nova_contracts import AgentResult, ValidationOutcome
from pydantic import BaseModel

__all__ = ["AgentInstance", "AgentInstanceHandle"]


class AgentInstance(BaseModel):
    """TDD 3E §4's `agent_instance` field set, verbatim, plus the
    `status`/`health_status` vocabularies that TDD names but does not
    enumerate -- proposed here as the minimal, disclosed shape (same
    discipline already applied to `RiskLevel`/`ActionStatus` when each was
    first introduced), not extracted from any document. Flagged for review
    at the Phase 3E Gate Review, per this milestone's own instructions.
    """

    id: UUID
    agent_package_id: UUID
    """No FK constraint to an `agent_package` row in this component's own
    migration -- `agent_package` is `agent-os/registry`'s table (TDD 3E
    §5), a separate, not-yet-built component. Enforcing referential
    integrity across two independently-migrated components is deferred to
    Registry's own build, the same discipline every engine's per-schema
    Alembic chain already follows (each engine's DSN points at the same
    physical `nova` database, but only within its own migrated schema)."""
    category: str
    execution_backend: Literal["inprocess"]
    """Phase 3 ships `inprocess` only (TDD 3E §2, doc 12 §8) -- the other
    three `agent-os/execution-backends/` subdirectories are not created by
    this TDD."""
    status: Literal["running", "completed", "failed"]
    assigned_task_node_id: UUID | None = None
    supervisor_id: UUID | None = None
    """Populated once `agent-os/supervisors` exists -- not this milestone."""
    started_at: datetime
    health_status: Literal["healthy", "degraded", "unhealthy", "unknown"] = "unknown"


class AgentInstanceHandle(BaseModel):
    """The outcome of `AgentExecutionBackend.spawn()` (doc 12 §8) --
    disclosed addition: doc 12 §8 gives the Protocol's signature
    (`spawn(...) -> AgentInstanceHandle`) but never a field-level shape for
    the handle itself. Phase 3's `inprocess` backend runs an instance's full
    assigned-task lifecycle (`on_load` -> `on_assign` -> `execute` ->
    `self_validate` -> `on_unload`) synchronously inside `spawn()` itself
    (single scripted task per dispatch, TDD 3E §9 -- none of the five Phase
    3 agents' behaviors span multiple dispatch cycles), so the handle
    carries the already-completed outcome rather than a live reference to
    poll later. `result`/`validation` are both `None` only when `error` is
    set (an exception during `on_load`/`on_assign`/`execute`/`self_validate`
    itself, not a `status="failure"` `AgentResult`, which is a normal,
    successfully-produced result)."""

    instance_id: UUID
    result: AgentResult | None = None
    validation: ValidationOutcome | None = None
    error: str | None = None
