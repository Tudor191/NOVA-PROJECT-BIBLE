"""Every subject Memory Engine is permitted to subscribe to -- docs/design/phase-1/
01-memory-engine.md §13.

`memory.retrieve.request` is here, not `published.py`: `BoundEventBus.serve()`
checks the *subscribable* allow-list, matching `subscribe()`'s convention -- serving
a request is a form of subscribing, from the allow-list's point of view.

Per docs/design/phase-1/04-cross-engine-integration.md, most of these subjects have
no real Phase 1 producer yet (Perception/Reasoning/Planning ship later) -- they are
contracts this engine is ready to serve now, exercised today only via the synthetic
event harness, not a live upstream engine.
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "perception.*.observed",
        "reasoning.result",
        "action.result",
        "communication.intent.received",
        "agent_os.task.completed",
        "knowledge.contradiction.detected",
        "memory.retrieve.request",
    }
)
