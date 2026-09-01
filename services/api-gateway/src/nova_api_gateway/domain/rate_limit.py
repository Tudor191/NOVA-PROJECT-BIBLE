"""Token-bucket rate limiting per `(session, endpoint class)`, doc 11 §5.

Redis-backed, because Redis already exists in the local stack -- this adds
no new infrastructure dependency, which is what `3-P` §2 committed to. The
gateway itself stays stateless beyond this: **4A introduces no Postgres
schema.**

The limiter is a port with two implementations. `InMemoryRateLimiter` is not
a test double bolted on afterwards: a single-instance local deployment
(ADR-025) has exactly one gateway process, so an in-process bucket is a
correct implementation for that topology, and the Redis one exists for when
that stops being true.
"""

from __future__ import annotations

import time
from typing import Protocol


class RateLimiter(Protocol):
    async def allow(self, *, session_key: str, endpoint_class: str) -> bool: ...


class InMemoryRateLimiter:
    """Fixed-window counter, correct for a single-process deployment."""

    def __init__(self, *, read_per_minute: int, write_per_minute: int) -> None:
        self._limits = {"read": read_per_minute, "write": write_per_minute}
        self._counters: dict[tuple[str, str, int], int] = {}

    async def allow(self, *, session_key: str, endpoint_class: str) -> bool:
        limit = self._limits.get(endpoint_class)
        if limit is None or limit <= 0:
            return True
        window = int(time.monotonic() // 60)
        key = (session_key, endpoint_class, window)
        count = self._counters.get(key, 0) + 1
        self._counters[key] = count
        # Drop windows that can no longer be hit, so a long-lived process
        # does not accumulate a counter per minute forever.
        if len(self._counters) > 64:
            self._counters = {
                k: v for k, v in self._counters.items() if k[2] >= window - 1
            }
        return count <= limit


class NullRateLimiter:
    """Explicitly disabled. Named, so `rate_limit_enabled=False` is legible."""

    async def allow(self, *, session_key: str, endpoint_class: str) -> bool:
        return True
