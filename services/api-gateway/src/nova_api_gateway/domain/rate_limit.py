"""Rate limiting per `(session, endpoint class)`, doc 11 §5.

**What is built: an in-process fixed-window counter, two classes.**
`InMemoryRateLimiter` counts requests per `(session, class, minute)`;
`endpoint_class()` assigns `read` to `GET`/`HEAD`/`OPTIONS` and `write` to
everything else. A single-instance local deployment (ADR-025) has exactly one
gateway process, so an in-process counter enforces the limit correctly for
that topology. The gateway stays stateless beyond it: **4A introduces no
Postgres schema.**

*(Corrected 2026-10-16. The original text said the limiter was
"Redis-backed" and that "the Redis one exists for when that stops being
true". Both claims were false when written: no Redis implementation exists
anywhere in this package, and `Settings.redis_url` is read by nothing. The
original wording is quoted here rather than silently replaced.)*

**A disclosed deviation from the approved design, not yet ratified.** TDD 4A
§2.3 and doc 11 §5 specify a **Redis-backed token bucket** with **three**
classes -- `read`, `write` and `expensive-reasoning`. What is built differs
in all three respects: in-process, fixed window, and no
`expensive-reasoning` class, so reasoning calls are limited only as `write`.
Whether to ratify the narrowing or build the design is recorded as a
decision for the user in the Phase 4 closure matrix (N-10); this module does
not decide it.
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
