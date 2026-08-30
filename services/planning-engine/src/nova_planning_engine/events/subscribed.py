"""Every subject Planning Engine is permitted to subscribe to.

`planning.decompose.request` is the single request/reply RPC this engine
serves (TDD 3B §6.2, doc 12 §11, `phase-3b-planning-persistence`
precursor) -- no real caller exists until Phase 3E's Kernel/Supervisor;
tested via the established "second `BoundEventBus`" pattern, mirroring
`action-engine`'s own `action.execute` treatment.

`planning.goals.current.request` (TDD 3E §8) is this engine's second served
RPC -- the real-RPC replacement for `reasoning-engine`'s and
`executive-cognition-engine`'s own `GoalsPort` placeholder.

`agent_os.task.completed` (TDD 3E §4/§12, TDD 3B §6.1's own deferred
subscription) is a fire-and-forget subscription -- `agent-os/kernel`'s own
restart-reconciliation and Scheduler failure paths, wired now that
`agent-os/kernel` exists (`events/task_completed_handler.py`)."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "reasoning.process.completed",
        "planning.decompose.request",
        "planning.goals.current.request",
        "agent_os.task.completed",
    }
)
