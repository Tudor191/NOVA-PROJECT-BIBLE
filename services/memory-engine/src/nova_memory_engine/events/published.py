"""Every subject Memory Engine is permitted to publish -- docs/design/phase-1/
01-memory-engine.md §13. See ADR-004 (docs/architecture/00-overview-and-decisions.md).

`knowledge.*.request` subjects are here, not in `subscribed.py`, because
`BoundEventBus.request()` checks the *publishable* allow-list (it is Memory Engine
initiating a call, even though the subject grammatically looks like something it
"receives a reply to") -- see `nova_eventbus_sdk.boundary.BoundEventBus.request`.
"""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "memory.short_term.created",
        "memory.long_term.created",
        "memory.long_term.updated",
        "memory.consolidation.started",
        "memory.consolidation.completed",
        "memory.lifecycle.transitioned",
        "memory.decision.recorded",
        "memory.embedding.completed",
        "knowledge.link.request",
        "knowledge.traverse.request",
    }
)
