"""Every subject nova-core is permitted to publish. See ADR-004
(docs/architecture/00-overview-and-decisions.md) -- an engine cannot publish an
undeclared subject even by accident once wrapped in `BoundEventBus`.
"""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "nova.heartbeat",
        "nova.module.status_changed",
        "nova.mode.changed",
    }
)
