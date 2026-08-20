"""Every subject Planning Engine is permitted to subscribe to.

`planning.decompose.request` is the single request/reply RPC this engine
serves (TDD 3B §6.2, doc 12 §11, `phase-3b-planning-persistence`
precursor) -- no real caller exists until Phase 3E's Kernel/Supervisor;
tested via the established "second `BoundEventBus`" pattern, mirroring
`action-engine`'s own `action.execute` treatment."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "reasoning.process.completed",
        "planning.decompose.request",
    }
)
