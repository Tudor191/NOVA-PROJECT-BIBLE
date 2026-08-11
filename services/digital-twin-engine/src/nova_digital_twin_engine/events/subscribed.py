"""Every subject digital-twin-engine is permitted to subscribe to --
docs/design/phase-2d/06-personal-companion.md Sec7.1.

`digital_twin.preferences.get.request` is here, not `published.py`:
`BoundEventBus.serve()` checks the *subscribable* allow-list, matching
`subscribe()`'s own convention (the same reason every prior engine's own
served RPCs live here, e.g. personality-engine's `personality.style.
select.request`).
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "communication.session.completed",
        "digital_twin.preferences.get.request",
    }
)
