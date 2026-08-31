"""Capability Engine event payloads and shared entities (Bible Part 15), per
docs/design/phase-3/06-tdd-3c-capability-engine.md.

`Capability` and `CapabilityHandle` are entities -- never independently
published on the Event Bus (no `@register_payload`), the same treatment
`RiskLevel` gets in `events/planning.py` -- embedded in-process in
`AgentContext.granted_capabilities` (doc 12) or nested inside the
request/reply RPC payloads below.

`capability.resolve.*` and `capability.invoke.*` are the two event-bus
request/reply RPC subject families `action-engine`'s future `CapabilityPort`
will call (Fork 3C-1/3D-1's resolution: `capability-engine` owns and
executes every adapter; `action-engine` never receives adapter code, only a
result) -- structurally identical to `ai_model.generate.request`/`.reply`
(ADR-004's request/reply pattern, not a publish/subscribe event stream).
`capability-engine` only *serves* these subjects in this phase; the first
real caller (`action-engine`, TDD 3D) does not exist yet.

Every payload carries `schema_version: int = 1` from its first commit
(ADR-024).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from nova_contracts.registry import register_payload

__all__ = [
    "Capability",
    "CapabilityHandle",
    "CapabilityHealthStatus",
    "CapabilityInvokeOutcome",
    "CapabilityInvokeReplyPayload",
    "CapabilityInvokeRequestPayload",
    "CapabilityResolveReplyPayload",
    "CapabilityResolveRequestPayload",
]

CapabilityHealthStatus = Literal["unknown", "healthy", "degraded", "unhealthy"]
"""TDD 3C §2.1's 4-value enum -- a coarse capability-level "is this adapter
currently working" signal, architecturally distinct from `RiskLevel`
(risk = "how dangerous is this specific action," owned by `3B`/`3D`)."""

CapabilityInvokeOutcome = Literal["success", "failure", "sandbox_violation"]


class Capability(BaseModel):
    """TDD 3C §2.1's 13-field Phase-3-scoped subset of Bible Part 15's
    18-field Capability Object Model. `author`, `confidence`,
    `performance_metrics`, `documentation`, `example_workflows`, and
    `Supported Platforms` are explicitly deferred, not silently dropped."""

    id: UUID
    name: str
    description: str
    category: str
    version: str
    dependencies: list[str] = Field(default_factory=list)
    required_permissions: list[str]
    required_resources: list[str] = Field(default_factory=list)
    input_schema: dict
    output_schema: dict
    execution_adapter: str
    health_status: CapabilityHealthStatus
    installed_at: datetime


class CapabilityHandle(BaseModel):
    """TDD 3C §2.2 -- deliberately minimal, in-process-only identifier for a
    granted capability; the full `Capability` record stays in
    `capability-engine`'s own registry, never duplicated into every
    `AgentContext`. Fork 3C-2 (declared-intent only, resolved as Option C):
    this type carries no runtime authority of its own -- capability
    resolution/health-checking happens live, via `capability.resolve.*`,
    at the point a capability is actually invoked."""

    capability_id: UUID
    name: str
    execution_adapter: str


@register_payload("capability.resolve.request")
class CapabilityResolveRequestPayload(BaseModel):
    """Action-Principle-lifecycle stage 5, "Prepare Resources"
    (docs/design/phase-3/07-tdd-3d-action-engine.md §6) -- resolve a
    `Capability` by id or by name and confirm `health_status`.

    **Additive extension, Phase 3D research pass, approved
    (`docs/design/phase-3/13-3d-action-engine-research.md` §5.1):**
    `name` was added alongside the original `capability_id` so
    `action-engine` can resolve `Action.execution_target` (a stable
    capability name, e.g. `"git"`) without needing to know a
    Postgres-generated `capability_id` in advance. Per ADR-024, adding a
    field to an existing payload is never a version bump -- the original
    by-id resolution path (every existing caller) is unaffected. Exactly
    one of `capability_id`/`name` must be set; validated below."""

    capability_id: UUID | None = None
    name: str | None = None
    requesting_engine: str
    correlation_id: UUID
    schema_version: int = 1

    @model_validator(mode="after")
    def _exactly_one_of_capability_id_or_name(self) -> CapabilityResolveRequestPayload:
        if (self.capability_id is None) == (self.name is None):
            raise ValueError("exactly one of capability_id or name must be set")
        return self


@register_payload("capability.resolve.reply")
class CapabilityResolveReplyPayload(BaseModel):
    found: bool
    capability: Capability | None = None
    schema_version: int = 1


@register_payload("capability.invoke.request")
class CapabilityInvokeRequestPayload(BaseModel):
    """Action-Principle-lifecycle stage 6, "Execute" -- invoke a resolved
    capability's adapter. `capability-engine`'s own process performs the
    real git/filesystem/terminal/http operation (Fork 3C-1's resolution);
    the caller never receives adapter code, only a structured result.

    `operation`/`parameters` are deliberately adapter-agnostic (mirrors
    `Capability.input_schema`/`output_schema` already being untyped
    `dict`s rather than per-adapter fields) -- e.g. a `filesystem`
    capability's `operation` might be `"read"`/`"write"`/`"list"`, a
    `terminal` capability's might be `"execute"`. Exact per-adapter
    operation vocabularies are adapter-implementation detail, not fixed
    here (same discipline as every other new payload in this package)."""

    capability_id: UUID
    operation: str
    parameters: dict = Field(default_factory=dict)
    requesting_engine: str
    correlation_id: UUID
    schema_version: int = 1


@register_payload("capability.invoke.reply")
class CapabilityInvokeReplyPayload(BaseModel):
    outcome: CapabilityInvokeOutcome
    result: dict | None = None
    error: str | None = None
    """Set only when `outcome != "success"` -- an informative reply, not a
    bus timeout with no diagnostic (same convention as
    `GenerateReplyPayload.error`)."""
    schema_version: int = 1
