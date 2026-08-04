"""Every subject Knowledge Engine is permitted to subscribe to -- docs/design/
phase-1/02-knowledge-engine.md §13.

`knowledge.retrieve.request`/`.traverse.request`/`.link.request` are here, not
`published.py`: `BoundEventBus.serve()` checks the *subscribable* allow-list,
matching `subscribe()`'s convention -- serving a request is a form of subscribing,
from the allow-list's point of view (same convention Memory Engine's
`events/subscribed.py` documents for `memory.retrieve.request`).

Per docs/design/phase-1/04-cross-engine-integration.md, `memory.long_term.created`
and `reasoning.result` have no real Phase 1 producer yet (Reasoning Engine ships
later) -- see `events/handlers.py` for how each subject is handled today.
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "memory.long_term.created",
        "perception.filesystem.observed",
        "reasoning.result",
        "knowledge.retrieve.request",
        "knowledge.traverse.request",
        "knowledge.link.request",
    }
)
