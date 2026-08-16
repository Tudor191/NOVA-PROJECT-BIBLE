"""Every subject Planning Engine is permitted to publish. See ADR-004
(docs/architecture/00-overview-and-decisions.md).

`ai_model.generate.request` is a request/reply RPC call, not a wire event
this engine owns -- listed here because `BoundEventBus.request()` enforces
this same allow-list for outbound RPC subjects, identically to how
`reasoning-engine`'s own `events/published.py` lists it (ADR-020)."""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "ai_model.generate.request",
    }
)
