"""Every subject Registry is permitted to publish. See ADR-004
(docs/architecture/00-overview-and-decisions.md).

Both subjects are request/reply RPC calls this component makes as a
caller (the Permission Review pipeline stage's best-effort disclosure,
TDD 3E §5's resolved note), not wire events this component owns -- listed
here because `BoundEventBus.request()` enforces this same allow-list for
outbound RPC subjects, identically to how `capability-engine`'s own
`events/published.py` lists the same two subjects for the same Fork D
precedent."""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "communication.session.lookup_by_user.request",
        "communication.intent.deliver.request",
    }
)
