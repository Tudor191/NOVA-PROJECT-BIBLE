"""Every subject AI Model Orchestration Engine is permitted to subscribe to --
docs/design/phase-2a/00-ai-model-orchestration-engine.md §13.

`ai_model.generate.request` / `ai_model.embed.request` are here, not
`published.py`: `BoundEventBus.serve()` checks the *subscribable* allow-list,
matching `subscribe()`'s convention (same as World Model Engine's own
`events/subscribed.py`, where `world_model.context.request` lives here for the
identical reason).

Per §13, this engine has no *subscribed* subject (in the "reacts to another
engine's event" sense) in Phase 2A -- Reasoning Engine (2B) will be its first
real event-driven caller. The two entries below are served RPCs, not reactions
to an upstream producer.
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "ai_model.generate.request",
        "ai_model.embed.request",
    }
)
