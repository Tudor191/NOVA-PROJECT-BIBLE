"""Repository-internal domain types for `agent-os/registry` -- `AgentPackage`
(TDD 3E §5, the `agent_package` Postgres-schema row shape) stays local to
this component, mirroring `agent-os/kernel`'s own `AgentInstance` treatment
(Phase 3E Milestone 2) and `action-engine`'s `PendingApproval`/
`IdentityConfidencePolicy` convention.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

__all__ = ["AgentPackage"]


class AgentPackage(BaseModel):
    """TDD 3E §5's `agent_package` field set (`id`, `category`, `version`,
    `manifest_json`, `installed_at`, `health_status`), plus `checksum` (the
    Registry's own Integrity Verification stage bookkeeping -- see
    `domain/pipeline.py`'s module docstring for why a real SHA-256 digest
    is computed and stored despite no signing infrastructure existing yet).

    `id` here is the *manifest's own* `AgentManifest.id` (e.g.
    `"coding-agent"`), never a surrogate UUID -- natural-key idempotency is
    keyed on `(id, version)`, not `(category, version)`; see
    `domain/pipeline.py`'s module docstring for the exact TDD 3E §5 wording
    this resolves and why.
    """

    id: str
    category: str
    version: str
    manifest_json: dict
    installed_at: datetime
    health_status: Literal["unknown", "healthy", "degraded", "unhealthy"] = "unknown"
    checksum: str
    supervisor_notified_new_permissions: list[str] = Field(default_factory=list)
    """Bookkeeping only -- the permissions surfaced to the user at this
    install (empty for a version identical in permissions to its
    predecessor, or a first install with no permissions declared)."""
