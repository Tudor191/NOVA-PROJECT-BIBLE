"""Every subject Reasoning Engine is permitted to subscribe to -- docs/design/
phase-2b/00-reasoning-engine.md §23. `reasoning.reason.request` is the one
served RPC this engine exposes (`events/handlers.py`)."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "reasoning.reason.request",
    }
)
