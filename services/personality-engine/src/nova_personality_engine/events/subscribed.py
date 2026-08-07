"""Every subject Personality Engine is permitted to subscribe to -- docs/
design/phase-2d/02-personality-engine.md Sec10.

`personality.validate_response.request` / `personality.style.select.request`
are here, not `published.py`: `BoundEventBus.serve()` checks the
*subscribable* allow-list, matching `subscribe()`'s convention (the same
reason every prior engine's own served RPCs live here, e.g. World Model's
`world_model.context.request`).

`personality.memory.update` (design doc Sec7.2, Sec10) is deliberately not
listed yet -- the subject is defined in nova-contracts now, per ADR-024
versioning discipline, but no handler exists to subscribe to it until Phase
2D-D's `digital-twin-engine` is the one actually publishing it.
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "personality.validate_response.request",
        "personality.style.select.request",
    }
)
