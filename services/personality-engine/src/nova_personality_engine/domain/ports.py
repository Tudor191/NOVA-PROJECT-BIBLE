"""Protocols this package depends on -- implements nothing itself
(docs/design/phase-2d/02-personality-engine.md Sec1). `domain/` may only
import this module, `domain/models.py`, and other `domain/` modules -- never
FastAPI, SQLAlchemy, `nova_eventbus_sdk`, or (per ADR-020) any LLM/AI provider
SDK directly. This engine defines no model-orchestration port at all -- per
design doc Sec0.3, it calls no model, by construction, mirroring Executive
Cognition Engine's identical absence of a `ModelOrchestrationPort`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from nova_personality_engine.domain.models import CoreIdentity, MemoryProfile, ValidationResult

__all__ = ["PersonalityRepository"]


@runtime_checkable
class PersonalityRepository(Protocol):
    """Persistence port for the `personality` schema (design doc Sec9):
    `core_identity`, `memory_profile`, `validation_audit`. No transactional
    outbox -- this engine publishes nothing this phase (design doc Sec10)."""

    async def get_core_identity(self) -> CoreIdentity | None: ...

    async def get_memory_profile(self) -> MemoryProfile: ...

    async def update_memory_profile(self, profile: MemoryProfile) -> MemoryProfile:
        """Design doc Sec7.2, Sec10 -- applied only when `digital-twin-engine`
        publishes `personality.memory.update` (Phase 2D-D onward). No
        Phase 2D-A code path calls this yet."""
        ...

    async def record_validation_audit(
        self,
        *,
        session_id: UUID,
        result: ValidationResult,
        selected_style: str | None,
    ) -> None:
        """Design doc Sec4, Sec9 -- every validation call is recorded,
        passed or failed, for Doc 23 Sec8's trust-through-inspectability
        requirement."""
        ...
