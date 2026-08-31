"""Every subject Executive Cognition Engine is permitted to publish (docs/
design/phase-2c/00-executive-cognition-engine.md §5.3, §5.5, §18). See
ADR-004 (docs/architecture/00-overview-and-decisions.md).

`executive.arbitrate.reply` and `executive.outcome.report.reply` are not
here -- reply payloads are returned directly from a `BoundEventBus.serve()`
handler, never published (the same convention as every other engine's own
served-RPC reply subject). `world_model.context.request` and
`memory.retrieve.request` are here, not in `subscribed.py`, because
`BoundEventBus.request()` checks the *publishable* allow-list (this engine
is initiating each call) -- the same convention Reasoning Engine's own
`events/published.py` established for its outbound `*.request` calls.
"""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "executive.decision.completed",
        "executive.decision.failed",
        "executive.human_override.applied",
        "world_model.context.request",
        "memory.retrieve.request",
        "planning.goals.current.request",
    }
)
