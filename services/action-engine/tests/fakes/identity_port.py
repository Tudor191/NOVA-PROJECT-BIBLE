"""`FakeIdentityPort` -- an in-memory `domain.ports.IdentityPort`,
scriptable per test: set `confidence_by_user` to script a per-user
confidence, or leave a user absent to simulate `None` (ADR-032's
fail-closed path, TDD 3D §10)."""

from __future__ import annotations

from uuid import UUID


class FakeIdentityPort:
    def __init__(self) -> None:
        self.confidence_by_user: dict[UUID, float] = {}

    async def get_confidence(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> float | None:
        return self.confidence_by_user.get(user_id)
