"""Every subject Knowledge Engine is permitted to subscribe to -- docs/design/
phase-1/02-knowledge-engine.md §13.

`knowledge.retrieve.request`/`.traverse.request`/`.link.request` are here, not
`published.py`: `BoundEventBus.serve()` checks the *subscribable* allow-list,
matching `subscribe()`'s convention -- serving a request is a form of subscribing,
from the allow-list's point of view (same convention Memory Engine's
`events/subscribed.py` documents for `memory.retrieve.request`).

Per docs/design/phase-1/04-cross-engine-integration.md, `memory.long_term.created`
has no real Phase 1 producer yet -- see `events/handlers.py` for how it's handled
today.

`reasoning.result` was removed here (Project Health Review, August 2026):
`reasoning-engine` was built in Phase 2B and never published a subject by that
name -- its real completion events are `reasoning.process.completed`/
`.failed`/`.human_override.applied` (`reasoning-engine/events/published.py`).
The subscription was a stale reference to a Phase-1-era placeholder subject,
not a live contract; wiring this engine's usage-tracking (`domain/evolution.py`'s
Connected -> Applied / Expert -> Strategic transitions) to reasoning-engine's
actual events is a real design decision deferred to Phase 2D-C planning, not a
mechanical rename.
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "memory.long_term.created",
        "perception.filesystem.observed",
        "knowledge.retrieve.request",
        "knowledge.traverse.request",
        "knowledge.link.request",
    }
)
