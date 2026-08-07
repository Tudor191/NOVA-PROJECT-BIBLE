"""Every subject Memory Engine is permitted to subscribe to -- docs/design/phase-1/
01-memory-engine.md §13.

`memory.retrieve.request` is here, not `published.py`: `BoundEventBus.serve()`
checks the *subscribable* allow-list, matching `subscribe()`'s convention -- serving
a request is a form of subscribing, from the allow-list's point of view.

Per docs/design/phase-1/04-cross-engine-integration.md, most of these subjects have
no real Phase 1 producer yet (Perception/Planning ship later) -- they are
contracts this engine is ready to serve now, exercised today only via the synthetic
event harness, not a live upstream engine.

`reasoning.result` was removed here (Project Health Review, August 2026):
`reasoning-engine` was built in Phase 2B and never published a subject by that
name -- its real completion events are `reasoning.process.completed`/
`.failed`/`.human_override.applied` (`reasoning-engine/events/published.py`).
The subscription was a stale reference to a Phase-1-era placeholder subject,
not a live contract; wiring this engine to reasoning-engine's actual events is
a real design decision (which event(s) should feed an episodic memory, and
with what content) deferred to Phase 2D-C planning, not a mechanical rename.
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "perception.*.observed",
        "action.result",
        "communication.intent.received",
        "agent_os.task.completed",
        "knowledge.contradiction.detected",
        "memory.retrieve.request",
    }
)
