"""`PersonalContextClient` -- `domain.ports.PersonalContextPort`
implementation (docs/design/phase-2b/00-reasoning-engine.md §7.5). Phase 2B's
honest placeholder for Bible Part 16's future Digital Twin Engine: a thin
wrapper around `WorldModelPort.get_context`, projecting `WorldModelSnapshot`'s
existing fields into a `PersonalContext` shape -- never its own RPC. Named as
its own port and client now so only this one adapter changes when Digital
Twin Engine ships (§25), the same "future extension point, not a redesign"
precedent ADR-020 established for future model providers.
"""

from __future__ import annotations

from uuid import UUID

from nova_reasoning_engine.domain.models import PersonalContext
from nova_reasoning_engine.domain.ports import WorldModelPort

__all__ = ["PersonalContextClient"]


class PersonalContextClient:
    def __init__(self, world_model_port: WorldModelPort) -> None:
        self._world_model_port = world_model_port

    async def get_personal_context(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> PersonalContext | None:
        snapshot = await self._world_model_port.get_context(
            user_id=user_id, correlation_id=correlation_id
        )
        if snapshot is None:
            return None
        return PersonalContext(
            user_id=snapshot.user_id,
            objective=snapshot.objective,
            project_id=snapshot.project_id,
            device=snapshot.device,
            task=snapshot.task,
        )
