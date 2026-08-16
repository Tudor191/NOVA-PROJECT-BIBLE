"""Every subject Planning Engine is permitted to subscribe to."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "reasoning.process.completed",
    }
)
