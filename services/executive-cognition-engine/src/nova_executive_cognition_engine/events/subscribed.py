"""Every subject Executive Cognition Engine is permitted to subscribe to
(docs/design/phase-2c/00-executive-cognition-engine.md §5.1-§5.2, §7.3,
§23). `executive.arbitrate.request` and `executive.outcome.report` are the
two served RPCs this engine exposes (`events/handlers.py`).
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "executive.arbitrate.request",
        "executive.outcome.report",
    }
)
