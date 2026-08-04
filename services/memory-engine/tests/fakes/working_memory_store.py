"""`FakeWorkingMemoryStore` -- an in-memory `domain.ports.WorkingMemoryStore`."""

from __future__ import annotations

from uuid import UUID


class FakeWorkingMemoryStore:
    def __init__(self) -> None:
        self._data: dict[tuple[UUID, str], dict[str, str]] = {}

    async def put(self, *, user_id: UUID, session_id: str, key: str, value: str) -> None:
        self._data.setdefault((user_id, session_id), {})[key] = value

    async def get_all(self, *, user_id: UUID, session_id: str) -> dict[str, str]:
        return dict(self._data.get((user_id, session_id), {}))

    async def clear(self, *, user_id: UUID, session_id: str) -> None:
        self._data.pop((user_id, session_id), None)
