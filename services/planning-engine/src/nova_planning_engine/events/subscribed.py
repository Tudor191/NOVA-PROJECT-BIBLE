"""Every subject Planning Engine is permitted to subscribe to.

`planning.decompose.request` is the single request/reply RPC this engine
serves (TDD 3B §6.2, doc 12 §11, `phase-3b-planning-persistence`
precursor) -- no real caller exists until Phase 3E's Kernel/Supervisor;
tested via the established "second `BoundEventBus`" pattern, mirroring
`action-engine`'s own `action.execute` treatment.

`planning.goals.current.request` (TDD 3E §8) is this engine's second served
RPC -- the real-RPC replacement for `reasoning-engine`'s and
`executive-cognition-engine`'s own `GoalsPort` placeholder."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "reasoning.process.completed",
        "planning.decompose.request",
        "planning.goals.current.request",
    }
)
