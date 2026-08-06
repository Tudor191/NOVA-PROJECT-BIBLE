"""`GoalsClient` -- `domain.ports.GoalsPort` implementation (docs/design/
phase-2c/00-executive-cognition-engine.md §5.7). Planning Engine (Phase 3)
does not exist yet, so this is an honest placeholder, not a real RPC: it
always returns an empty list. Callers submit `ExecutiveRequest.goal_id`
directly (§5.1, §8); this port exists so `long_term_alignment` (§6.1) can
be computed against a real goal's `goal_tier` once Planning Engine ships,
without changing this port's own shape or any caller (§24).
"""

from __future__ import annotations

from uuid import UUID

from nova_executive_cognition_engine.domain.models import Goal

__all__ = ["GoalsClient"]


class GoalsClient:
    async def current_goals(
        self, *, user_id: UUID, scope: str | None = None, correlation_id: UUID | None = None
    ) -> list[Goal]:
        return []
