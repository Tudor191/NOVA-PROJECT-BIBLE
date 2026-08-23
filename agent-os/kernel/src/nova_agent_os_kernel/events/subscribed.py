"""Every subject Kernel is permitted to subscribe to."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        # TODO: e.g. "planning.task_graph.created",
    }
)
