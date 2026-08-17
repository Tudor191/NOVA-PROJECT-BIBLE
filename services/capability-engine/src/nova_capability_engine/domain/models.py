"""`CapabilityManifest` -- the not-yet-installed shape of a capability, before
the installation pipeline mints `id`/`health_status`/`installed_at`
(TDD 3C §2.3's 8-stage pipeline). `nova_contracts.Capability` is used
directly as this engine's own domain model once installed -- Capability is
cross-engine from day one (embedded in `AgentContext.granted_capabilities`,
resolved via `capability.resolve.*`), unlike `TaskNode`/`TaskGraph`
(`planning-engine`'s own domain-local types), so there is no separate
engine-local "installed capability" type to keep in sync with the contract.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["CapabilityManifest"]


class CapabilityManifest(BaseModel):
    """Every field `nova_contracts.Capability` has, minus the three the
    installation pipeline itself mints (`id`, `health_status`,
    `installed_at`)."""

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
