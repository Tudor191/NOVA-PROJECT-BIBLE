"""Every subject Personality Engine is permitted to subscribe to -- docs/
design/phase-2d/02-personality-engine.md Sec10.

`personality.validate_response.request` / `personality.style.select.request`
are here, not `published.py`: `BoundEventBus.serve()` checks the
*subscribable* allow-list, matching `subscribe()`'s convention (the same
reason every prior engine's own served RPCs live here, e.g. World Model's
`world_model.context.request`).

`personality.memory.update` (design doc Sec7.2, Sec10; docs/design/phase-2d/
06-personal-companion.md Sec7.1) -- Phase 2D-D's `digital-twin-engine` is
now the real publisher (`events/handlers.py::make_memory_update_handler`),
even though no production call site enqueues one yet (Fork F, that
engine's own `domain/models.py` module docstring). The subscription itself
is genuine and tested; it is simply never triggered in production this
phase.
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "personality.validate_response.request",
        "personality.style.select.request",
        "personality.memory.update",
    }
)
