"""Every subject World Model Engine is permitted to subscribe to -- docs/design/
phase-1/03-world-model-engine.md §13.

`world_model.context.request` is here, not `published.py`: `BoundEventBus.
serve()` checks the *subscribable* allow-list, matching `subscribe()`'s
convention (same as Memory/Knowledge Engine's own `events/subscribed.py`).

Per docs/design/phase-1/04-cross-engine-integration.md, none of the subscribed
subjects below have a real Phase 1 producer yet -- Perception, Planning, and
Agent OS ship in later phases; see `events/handlers.py` for how each subject is
handled today. `agent_os.task.*` is registered as a no-op now (§13: "Phase 3+,
no-op subscription registered now") specifically so the allow-list and
subscription wiring exist ahead of the producer, not as a functional handler.
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "perception.*.observed",
        "action.result",
        "agent_os.task.*",
        "nova.mode.changed",
        "world_model.context.request",
    }
)
