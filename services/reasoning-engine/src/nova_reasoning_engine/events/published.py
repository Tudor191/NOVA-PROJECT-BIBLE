"""Every subject Reasoning Engine is permitted to publish -- docs/design/
phase-2b/00-reasoning-engine.md §19, §23. See ADR-004
(docs/architecture/00-overview-and-decisions.md).

`reasoning.reason.reply` is not here -- reply payloads are returned directly
from a `BoundEventBus.serve()` handler, never published (the same convention
as every other engine's own served-RPC reply subject).

The `memory.*`/`knowledge.*`/`world_model.*`/`ai_model.*` request subjects
are here, not in `subscribed.py`, because `BoundEventBus.request()` checks
the *publishable* allow-list (this engine is initiating each call, even
though the subject grammatically looks like something it "receives a reply
to") -- the same convention `nova_memory_engine.events.published`
established for its own outbound `knowledge.*.request` calls.
"""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "reasoning.process.completed",
        "reasoning.process.failed",
        "reasoning.human_override.applied",
        "memory.retrieve.request",
        "knowledge.retrieve.request",
        "knowledge.traverse.request",
        "world_model.context.request",
        "ai_model.generate.request",
        "planning.goals.current.request",
    }
)
