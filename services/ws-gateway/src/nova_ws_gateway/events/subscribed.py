"""Every subject Ws Gateway is permitted to subscribe to."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        # TODO: e.g. "perception.*.observed",
    }
)
