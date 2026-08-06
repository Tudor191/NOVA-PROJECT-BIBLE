"""In-process registry of recently-submitted, presumed-in-flight
`ExecutiveRequest`s (docs/design/phase-2c/00-executive-cognition-engine.md
§3, §4) -- gathers "other in-flight requests" (§3's own Executive Cycle
table: "Rank against any other currently-contending requests") for each new
`executive.arbitrate.request` call.

Phase 2C has no durable, cross-process admission queue -- that is a named
Phase 6 extension (§24, Cognitive Load Management), and would require a
real strategy concept this phase does not have (§0.4). This registry is
intentionally bounded, single-process, in-memory state: a request most
likely still awaiting its own caller's next action within a short window,
not a durable reservation. A request leaves the registry when its
(optional, §7.3) outcome report arrives, or after `ttl_seconds` regardless,
so a caller that never reports an outcome cannot pin a stale contender
forever.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from uuid import UUID

from nova_executive_cognition_engine.domain.models import ExecutiveRequest

__all__ = ["ContenderRegistry", "DEFAULT_MAX_ENTRIES", "DEFAULT_TTL_SECONDS"]

DEFAULT_TTL_SECONDS = 30.0
DEFAULT_MAX_ENTRIES = 200


@dataclass
class ContenderRegistry:
    ttl_seconds: float = DEFAULT_TTL_SECONDS
    max_entries: int = DEFAULT_MAX_ENTRIES
    _entries: list[tuple[float, ExecutiveRequest]] = field(default_factory=list)

    def _evict_expired(self, *, now: float) -> None:
        cutoff = now - self.ttl_seconds
        self._entries = [(t, r) for (t, r) in self._entries if t >= cutoff]

    def contenders_for(self, request: ExecutiveRequest) -> list[ExecutiveRequest]:
        """Other currently in-flight requests as of this call, excluding
        `request` itself -- then registers `request` as in-flight too, so a
        second, concurrently-submitted request sees it. No `await` between
        the read and the append below: asyncio is single-threaded and
        cooperative, so this stays race-free without an explicit lock."""
        now = time.monotonic()
        self._evict_expired(now=now)
        others = [r for (_, r) in self._entries if r.correlation_id != request.correlation_id]
        self._entries.append((now, request))
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries :]
        return others

    def resolve(self, correlation_id: UUID) -> None:
        """Removes a request once it is no longer in flight -- its
        (optional, §7.3) outcome report arrived. Safe to call for a
        correlation_id the registry has already evicted or never held."""
        self._entries = [
            (t, r) for (t, r) in self._entries if r.correlation_id != correlation_id
        ]
