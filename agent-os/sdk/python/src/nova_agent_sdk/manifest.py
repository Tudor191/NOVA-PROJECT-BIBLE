"""`AgentManifest` -- the `agent.yaml` schema (doc 12 §3, verbatim field
set) an Agent Package's manifest is validated against by the Registry's
Manifest Validation stage (TDD 3E §5). Proposed here, not extracted --
doc 12 §3 shows one worked YAML example, never a formal schema -- the same
disclosure discipline already applied to every other supporting type this
project has introduced (`RiskLevel`, `CapabilityHandle`,
`RetryPolicy`/`RollbackStrategy`). Flagged for the Phase 3E Gate Review.

Lives in `nova_agent_sdk`, not `nova_contracts`: `AgentManifest` is never
independently published under its own Event Bus subject -- it is read from
a local `agent.yaml` file by the Registry and passed in-process to
`AgentHandler.on_load()` (doc 12 §4), the same "package-local, not a wire
payload" placement rule already applied to `CapabilityManifest` in
`capability-engine`'s own `domain/models.py`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

__all__ = [
    "AgentManifest",
    "CompatibilityInfo",
    "HealthCheckConfig",
    "ResourceProfile",
]

ExecutionBackend = Literal["inprocess", "subprocess", "container", "remote"]
"""Doc 12 §8's full target vocabulary. Phase 3 *implements* `inprocess`
only (TDD 3E §2) -- a manifest may still *declare* support for the other
three (forward-declared intent for a future phase); the Registry's
Dependency & Capability Resolution stage is what enforces that at least
`inprocess` is among a package's declared backends, since no other backend
can actually be dispatched yet."""


class ResourceProfile(BaseModel):
    """Doc 12 §3, verbatim."""

    cpu: str
    memory: str
    gpu: str


class HealthCheckConfig(BaseModel):
    """Doc 12 §3, verbatim."""

    interval_seconds: int


class CompatibilityInfo(BaseModel):
    """Doc 12 §3, verbatim."""

    min_kernel_version: str


class AgentManifest(BaseModel):
    """Doc 12 §3's `agent.yaml` fields, verbatim, plus `peer_reviewer_category`."""

    id: str
    version: str
    category: str
    display_name: str
    required_capabilities: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    supported_execution_backends: list[ExecutionBackend]
    resource_profile: ResourceProfile
    health_check: HealthCheckConfig
    compatibility: CompatibilityInfo
    peer_reviewer_category: str | None = None
    """Disclosed addition, coding-agent slice: doc 12 §3's own worked
    `agent.yaml` example (the coding-agent one, verbatim) never shows a
    reviewer-declaring field, and TDD 3E §9's table gives the pairing only
    as prose ("architect-agent... consumes coding-agent's AgentResult").
    A package-level, manifest-declared fact is the smallest way to make
    that pairing machine-readable: the Kernel Scheduler reads this
    directly off the dispatched package's own manifest when
    `ValidationOutcome.requires_peer_review=True`, needing no new
    Supervisor-side policy lookup for what is, in Phase 3, a single static
    fact per agent category. `None` (the default, e.g. research-agent's
    manifest) means "no peer review configured for this category" -- the
    Scheduler then finalizes the primary result exactly as it does today,
    unchanged from `agent_os.registry.find_healthy_package`'s own
    already-approved shape. Flagged for the Phase 3E Gate Review, same
    discipline as every other proposed-not-extracted field on this type."""
