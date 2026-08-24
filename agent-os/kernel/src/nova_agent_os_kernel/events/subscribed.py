"""Every subject Kernel is permitted to subscribe to.

`planning.task_graph.created` is the Kernel Scheduler's own trigger (TDD 3E
§4, disclosed implementation -- see `domain/scheduler.py`'s own module
docstring for what was previously flagged as "not yet built")."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "planning.task_graph.created",
    }
)
