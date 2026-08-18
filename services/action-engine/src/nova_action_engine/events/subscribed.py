"""Every subject Action Engine is permitted to subscribe to.

`action.execute` is the single request/reply RPC this engine serves (TDD
3D §5) -- no real caller exists until Phase 3E's Kernel Scheduler; tested
via the established "second `BoundEventBus`" pattern
(`tests/integration/test_events_action_execute.py`)."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "action.execute",
    }
)
