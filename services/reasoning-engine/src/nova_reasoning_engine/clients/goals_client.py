"""`GoalsClient` -- `domain.ports.GoalsPort` implementation (docs/design/
phase-2b/00-reasoning-engine.md §7.1). Planning Engine (Phase 3) does not
exist yet, so this is an honest placeholder, not a real RPC: it always
returns an empty list. `context_assembly.assemble_context` already prefers
the caller-supplied `ReasoningRequest.goals` over this port's own result
(§8), so Goal Evaluation stays real and testable today, and the moment
Planning Engine ships, this file becomes a real `planning.goals.request`
adapter without changing `GoalsPort`'s own shape or any caller (§25).
"""

from __future__ import annotations

from uuid import UUID

from nova_reasoning_engine.domain.models import Goal

__all__ = ["GoalsClient"]


class GoalsClient:
    async def current_goals(
        self, *, user_id: UUID, scope: str | None = None, correlation_id: UUID | None = None
    ) -> list[Goal]:
        return []
