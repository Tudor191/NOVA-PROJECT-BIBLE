"""Every subject Communication Engine is permitted to subscribe to -- docs/
design/phase-2d/01-communication-engine.md Sec11.

`communication.intent.deliver.request`, `communication.session.create.
request`, and `communication.session.close.request` are here, not
`published.py`: `BoundEventBus.serve()` checks the *subscribable* allow-list,
matching `subscribe()`'s convention (the same reason every prior engine's
own served RPCs live here).
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "communication.intent.deliver.request",
        "communication.session.create.request",
        "communication.session.close.request",
    }
)
