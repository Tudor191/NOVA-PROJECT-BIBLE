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
    """Doc 12 §3's `agent.yaml` fields, verbatim."""

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
