"""`RedisWorkingMemoryStore` -- implements `domain.ports.WorkingMemoryStore` against
Redis (docs/design/phase-1/01-memory-engine.md §2). Working Memory's primary store,
not a cache of anything else (docs/design/phase-1/00-shared-foundations.md).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from redis.asyncio import Redis


def _key(user_id: UUID, session_id: str) -> str:
    return f"wm:working:{user_id}:{session_id}"


class RedisWorkingMemoryStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def put(self, *, user_id: UUID, session_id: str, key: str, value: str) -> None:
        await self._redis.hset(_key(user_id, session_id), key, value)  # type: ignore[misc]

    async def get_all(self, *, user_id: UUID, session_id: str) -> dict[str, str]:
        raw: dict[object, object] = await self._redis.hgetall(_key(user_id, session_id))  # type: ignore[misc]
        return {_decode(k): _decode(v) for k, v in raw.items()}

    async def clear(self, *, user_id: UUID, session_id: str) -> None:
        await self._redis.delete(_key(user_id, session_id))


def _decode(value: object) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)
