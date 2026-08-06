"""In-memory fakes for this engine's upstream ports (`domain/ports.py`, §5) --
configurable, deterministic, no real network call, the same `FakeConnector`-
shaped determinism precedent Phase 2A established."""

from __future__ import annotations

from uuid import UUID

from nova_executive_cognition_engine.domain.models import (
    Goal,
    MemoryReference,
    PersonalContext,
    WorldModelSnapshot,
)


class FakeMemoryPort:
    def __init__(self, results: list[MemoryReference] | None = None) -> None:
        self.results = results if results is not None else []
        self.calls: list[tuple[UUID, str]] = []

    async def retrieve(
        self,
        *,
        user_id: UUID,
        query: str,
        limit: int = 10,
        correlation_id: UUID | None = None,
    ) -> list[MemoryReference]:
        self.calls.append((user_id, query))
        return self.results[:limit]


class FakeWorldModelPort:
    def __init__(self, snapshot: WorldModelSnapshot | None = None) -> None:
        self.snapshot = snapshot
        self.calls: list[UUID] = []

    async def get_context(
        self, *, user_id: UUID, scope: str | None = None, correlation_id: UUID | None = None
    ) -> WorldModelSnapshot | None:
        self.calls.append(user_id)
        return self.snapshot


class FakePersonalContextPort:
    def __init__(self, context: PersonalContext | None = None) -> None:
        self.context = context

    async def get_personal_context(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> PersonalContext | None:
        return self.context


class FakeGoalsPort:
    def __init__(self, goals: list[Goal] | None = None) -> None:
        self.goals = goals if goals is not None else []
        self.calls: list[UUID] = []

    async def current_goals(
        self, *, user_id: UUID, scope: str | None = None, correlation_id: UUID | None = None
    ) -> list[Goal]:
        self.calls.append(user_id)
        return self.goals
