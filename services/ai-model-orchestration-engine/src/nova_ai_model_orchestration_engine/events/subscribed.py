"""Every subject Ai Model Orchestration Engine is permitted to subscribe to."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        # TODO: e.g. "perception.*.observed",
    }
)
