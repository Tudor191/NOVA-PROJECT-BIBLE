"""Every subject Planning Engine is permitted to publish. See ADR-004
(docs/architecture/00-overview-and-decisions.md)."""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        # TODO: e.g. "your_engine.entity.created",
    }
)
