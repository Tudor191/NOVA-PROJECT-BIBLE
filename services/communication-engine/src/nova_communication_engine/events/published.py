"""Every subject Communication Engine is permitted to publish -- docs/design/
phase-2d/01-communication-engine.md Sec11. See ADR-004
(docs/architecture/00-overview-and-decisions.md).

Two categories: the five domain events this engine is the source of truth
for (`communication.session.*`, `communication.turn.received`,
`communication.intent.delivered`), dispatched by
`repository/outbox_dispatcher.py`; and the seven outbound RPC `*.request`
subjects this engine calls as a client (`personality.*`, `ai_model.*`,
`world_model.context.request`, `reasoning.reason.request`,
`digital_twin.preferences.get.request`) --
`BoundEventBus.request()` checks the *publishable* allow-list even though
the subject grammatically looks like something this engine "receives a
reply to," the same convention every prior engine's own
`events/published.py` follows (executive-cognition-engine's own README
documents this explicitly).

`communication.intent.delivered` (Phase 4A, docs/design/phase-4/
01-tdd-4a-gateways-and-web-client.md) -- the reply half of a conversation,
published after the ADR-005 intent gate passes an utterance. Before it, the
only broadcast half was the user's own `communication.turn.received`: a
reply reached the user solely over this engine's channel adapter, so no
subscriber could observe what NOVA said, and the web client (which doc 11
Sec1 forbids from calling an engine directly) had no source for it.

`reasoning.reason.request` (docs/design/phase-2d/
05-conversation-intelligence-closure.md Sec5, Priority 3) -- the missing
communication-engine-to-reasoning-engine leg of the conversation loop,
closed via the same synchronous request/reply pattern as every other
outbound RPC on this list, not a new event-driven mechanism.

`digital_twin.preferences.get.request` (Phase 2D-D docs/design/phase-2d/
06-personal-companion.md Sec7.2) -- listed here per this file's own
established convention (`BoundEventBus.request()` checks the caller's
*publishable* list, not a served-RPC list) even though, per
`domain/response_shaping.py`'s own docstring, no production call currently
supplies the optional `digital_twin_port`/`user_id` arguments that would
actually trigger it this phase.
"""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "communication.intent.delivered",
        "communication.session.created",
        "communication.session.state_changed",
        "communication.session.completed",
        "communication.turn.received",
        "personality.validate_response.request",
        "personality.style.select.request",
        "ai_model.transcribe.request",
        "ai_model.synthesize.request",
        "world_model.context.request",
        "reasoning.reason.request",
        "digital_twin.preferences.get.request",
    }
)
