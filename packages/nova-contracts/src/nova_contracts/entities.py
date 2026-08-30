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

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from nova_contracts.events.capability import CapabilityHandle
from nova_contracts.events.planning import TaskNodeSnapshot

__all__ = [
    "AgentContext",
    "AgentHealth",
    "AgentMetrics",
    "AgentResult",
    "KnowledgeReference",
    "MemoryReference",
    "PermissionSet",
    "PersonalContext",
    "ResourceUsage",
    "ValidationOutcome",
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


class KnowledgeReference(BaseModel):
    """Mirrors `MemoryReference` exactly -- the identical narrow
    ID+bounded-summary anti-corruption pattern, applied to
    `knowledge-engine`'s own `knowledge.retrieve.reply`
    (`KnowledgeSearchResultPayload`, which this type never imports directly
    -- an agent-os-side caller builds this from that reply at the RPC
    boundary, the same translation-function pattern used everywhere else in
    this codebase for a wire payload -> in-process entity)."""

    node_id: str
    summary: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


# --- Phase 3E (`agent-os`) entities -----------------------------------------
#
# `docs/design/phase-3/08-tdd-3e-agent-os.md` §6 states `AgentContext`/
# `AgentHealth`/`AgentMetrics`/`AgentHandler` are "used verbatim from doc 12
# §4 ... no proposed changes; already fully specified there." That is true at
# the level of *those four types' own field names* -- it is not true one
# level deeper: six of the concrete field *types* doc 12 §4 references
# (`WorldModelView`, `MemoryRecord`, `KnowledgeNode`, `PermissionSet`,
# `ResourceUsage`, `ValidationOutcome`) have no field-level definition
# reachable from `agent-os` anywhere in the repository -- confirmed by a
# full-repo class-definition search before writing this module. Two of the
# six names collide with an *unrelated* type of the same name already
# defined elsewhere (`knowledge-engine`'s own domain `KnowledgeNode`,
# `communication-engine`'s own domain `ValidationOutcome` -- a different
# concept, "the intent gate's own view of a `personality.validate_response`
# result"); two more (`memory-engine`'s `MemoryRecord`, `knowledge-engine`'s
# `KnowledgeNode`) are genuine domain types but live inside another engine's
# own package, which ADR-004 forbids `agent-os` from importing directly.
#
# This is the same "flag a proposed, non-extracted shape rather than invent
# past the gap silently" discipline this TDD's own §6 already applies to
# `AgentResult`/`AgentMessage`, extended to the six supporting types its
# research pass did not catch -- not a new architectural fork (no ownership,
# boundary, or design-direction question is open here), disclosed in the
# Phase 3E Gate Review. Where an existing, already-extracted entity already
# covers the concept, it is reused rather than duplicated:
# `world_model_slice: WorldModelSnapshot` (already covers doc 12's
# "pre-scoped view of the world model" prose exactly), `relevant_memory:
# list[MemoryReference]` (already the narrow retrieve-reply projection),
# `relevant_knowledge: list[KnowledgeReference]` (new, mirroring
# `MemoryReference` -- see above), `task: TaskNodeSnapshot` (the published
# wire type, per the Phase 3B Domain Foundation Gate Review's own forward
# note: "3E's future Kernel Scheduler will consume TaskNode... from a
# *published* TaskGraph," never `nova_planning_engine`'s domain-internal
# `TaskNode`), `granted_capabilities: list[CapabilityHandle]` (already
# exists, TDD 3C §2.2).


class ResourceUsage(BaseModel):
    """Proposed, not extracted -- doc 12 §4's `AgentHealth.resource_usage`
    has no field-level definition anywhere. Minimal shape grounded in
    `agent.yaml`'s own `resource_profile` categories (doc 12 §3:
    `cpu`/`memory`/`gpu`), narrowed to the two backends Phase 3's
    `inprocess`-only execution can actually observe -- `gpu` is not sampled
    since no Phase-3 agent declares GPU usage and there is no
    `container`/`remote` backend yet to make it observable differently."""

    cpu_percent: float = Field(ge=0.0)
    memory_mb: float = Field(ge=0.0)


class PermissionSet(BaseModel):
    """Declared-intent-only (TDD 3E §5/§12's resolution: no `nova-auth`
    exists in Phase 3; the Registry's "Permission review" step is a local
    diff-and-display, and Kernel-side `execute()`-time re-validation is an
    explicitly disclosed, deferred gap). Mirrors `agent.yaml`'s own
    `required_permissions: list[str]` shape verbatim (doc 12 §3) -- this is
    the ceiling an instance was granted at install time, carried into
    `AgentContext` for the agent's own informational use, never an
    independently-enforced authorization mechanism in Phase 3."""

    granted: list[str] = Field(default_factory=list)


class ValidationOutcome(BaseModel):
    """`AgentHandler.self_validate()`'s return type (doc 12 §4) -- **not**
    the same concept as `communication-engine`'s own, unrelated, domain-local
    `ValidationOutcome` (that one is the intent gate's view of a
    `personality.validate_response` result; this one is an agent's own
    self-assessment of its `AgentResult`). The two share a name doc 12
    happens to reuse, not a shared type -- disambiguated here explicitly so
    the collision is never silently assumed to mean shared meaning. Proposed
    shape, grounded directly in the lifecycle state machine (doc 12 §5):
    `SelfValidation -> PeerValidation` iff `requires_peer_review`,
    `-> ResultSubmission` otherwise."""

    passed: bool
    requires_peer_review: bool
    reason: str | None = None


class AgentContext(BaseModel):
    """Doc 12 §4, verbatim field set -- the pre-scoped context an
    `AgentHandler.on_assign()`/`execute()` receives. In-process only, never
    serialized onto the Event Bus (the `inprocess` backend passes this as a
    live Python object, confirmed in
    `01-tdd-preparation-and-fork-resolutions.md` §5.5's Fact 4) -- this is
    why it belongs here, in `entities.py`, and not in `events/agent_os.py`."""

    task: TaskNodeSnapshot
    world_model_slice: WorldModelSnapshot
    relevant_memory: list[MemoryReference] = Field(default_factory=list)
    relevant_knowledge: list[KnowledgeReference] = Field(default_factory=list)
    granted_permissions: PermissionSet
    granted_capabilities: list[CapabilityHandle] = Field(default_factory=list)
    correlation_id: UUID


class AgentHealth(BaseModel):
    """Doc 12 §4, verbatim field set."""

    status: Literal["healthy", "degraded", "unhealthy"]
    latency_ms: float
    error_rate: float
    resource_usage: ResourceUsage


class AgentMetrics(BaseModel):
    """Doc 12 §4, verbatim field set."""

    tasks_completed: int
    tasks_failed: int
    average_duration_ms: float
    average_confidence: float
    resource_efficiency: float


class AgentResult(BaseModel):
    """TDD 3E §6, Fork 3E-1 (RESOLVED, approved as proposed) -- what a
    Supervisor collects for the primary result AND for every peer-review
    round (`PEER_REVIEW_RESULT`). In-process by default (a Supervisor
    collects it directly from `execute()`'s return value); also carried
    inside an `AgentMessage.payload` when reported across the Agent Mailbox
    (e.g. a peer reviewer's result reaching the Supervisor) -- placed here,
    not in `events/agent_os.py`, because it is never independently published
    under its own Event Bus subject (only `AgentMessage` is)."""

    agent_instance_id: UUID
    task_node_id: UUID
    status: Literal["success", "failure", "needs_revision"]
    output: dict
    confidence: float | None = None
    self_validation_passed: bool
    correlation_id: UUID
