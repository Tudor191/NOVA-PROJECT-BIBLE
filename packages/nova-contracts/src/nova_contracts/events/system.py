"""System-level event payloads owned by nova-core: nova.heartbeat, nova.mode.changed,
nova.module.status_changed -- see docs/bible/part-20-nova-core.md ("Heartbeat System",
"System Synchronization") and docs/architecture/09-event-bus-architecture.md §4.

`schema_version: int = 1` (Project Health Review, August 2026): backfilled onto
every payload here per ADR-024 (interface versioning from day one) -- this
module predates ADR-024's adoption (Phase 1, before Phase 2A) and was never
retroactively updated. Purely additive (a defaulted field), no behavior change.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from nova_contracts.registry import register_payload


class ModuleStatus(StrEnum):
    """Mirrors the module lifecycle states from Part 20's Module Lifecycle."""

    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class SystemMode(StrEnum):
    """Part 20 "Execution Modes"."""

    INTERACTIVE = "interactive"
    SILENT = "silent"
    DEVELOPER = "developer"
    RESEARCH = "research"
    PRESENTATION = "presentation"
    GAMING = "gaming"
    TRAVEL = "travel"
    OFFLINE = "offline"
    EMERGENCY = "emergency"


@register_payload("nova.heartbeat")
class HeartbeatPayload(BaseModel):
    module: str
    status: ModuleStatus
    uptime_seconds: float = Field(ge=0.0)
    boot_phase: int | None = None
    schema_version: int = 1


@register_payload("nova.module.status_changed")
class ModuleStatusChangedPayload(BaseModel):
    module: str
    previous_status: ModuleStatus | None = None
    status: ModuleStatus
    reason: str | None = None
    schema_version: int = 1


@register_payload("nova.mode.changed")
class ModeChangedPayload(BaseModel):
    mode: SystemMode
    previous_mode: SystemMode | None = None
    changed_by: str
    schema_version: int = 1
