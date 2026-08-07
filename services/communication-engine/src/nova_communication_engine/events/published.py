"""Every subject Communication Engine is permitted to publish -- docs/design/
phase-2d/01-communication-engine.md Sec11. See ADR-004
(docs/architecture/00-overview-and-decisions.md).

Two categories: the four domain events this engine is the source of truth
for (`communication.session.*`, `communication.turn.received`), dispatched
by `repository/outbox_dispatcher.py`; and the five outbound RPC `*.request`
subjects this engine calls as a client (`personality.*`, `ai_model.*`,
`world_model.context.request`) -- `BoundEventBus.request()` checks the
*publishable* allow-list even though the subject grammatically looks like
something this engine "receives a reply to," the same convention every
prior engine's own `events/published.py` follows (executive-cognition-
engine's own README documents this explicitly).
"""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "communication.session.created",
        "communication.session.state_changed",
        "communication.session.completed",
        "communication.turn.received",
        "personality.validate_response.request",
        "personality.style.select.request",
        "ai_model.transcribe.request",
        "ai_model.synthesize.request",
        "world_model.context.request",
    }
)
