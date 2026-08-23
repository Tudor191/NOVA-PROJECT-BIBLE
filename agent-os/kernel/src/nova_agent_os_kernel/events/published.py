"""Every subject Kernel is permitted to publish. See ADR-004
(docs/architecture/00-overview-and-decisions.md)."""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "agent_os.task.completed",
    }
)
