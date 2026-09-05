"""Every subject `ws-gateway` is permitted to subscribe to.

This is the ADR-006 boundary: `BoundEventBus.subscribe` raises
`SubjectNotAllowedError` for anything absent here, so the bridge cannot
reach a subject this file does not name -- enforced by the SDK, not by
convention in the gateway.

Doc 09 §6 bounds what may ever cross to a browser: *"already-finalized
`communication.*` events plus read-only telemetry, never raw internal engine
chatter."* 4A's set is exactly that. Later milestones extend it --
`planning.task_graph.*` and `action.*` in 4B, `agent.*`/`agent_os.*` in 4C,
`autonomy.*` in 4D -- by appending here and to `PUBLIC_TOPICS`. The bridging
mechanism itself never changes.
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        # Conversation panel -- finalized communication events only.
        "communication.*",
        # Presence/identity indicator -- read-only telemetry.
        "perception.*",
        "personality.*",
        # System Pulse -- NOVA Core's heartbeat (doc 04 §4).
        "nova.heartbeat",
        # --- Phase 4B observability panels --------------------------------
        # Doc 09 §6 bounds this to "already-finalized events plus read-only
        # telemetry, never raw internal engine chatter." Each pattern below
        # is narrowed to the finalized/telemetry subjects the panels read;
        # `PUBLIC_TOPICS` narrows again to the exact set a browser may name,
        # so two independent allow-lists still guard the boundary.
        "planning.task_graph.*",
        "reasoning.process.*",
        "reasoning.human_override.*",
        "action.approval.*",
        "ai_model.model.*",
        "nova.module.status_changed",
    }
)
