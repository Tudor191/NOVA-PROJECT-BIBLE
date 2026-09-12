"""Every subject `ws-gateway` is permitted to subscribe to.

This is the ADR-006 boundary: `BoundEventBus.subscribe` raises
`SubjectNotAllowedError` for anything absent here, so the bridge cannot
reach a subject this file does not name -- enforced by the SDK, not by
convention in the gateway.

Doc 09 §6 bounds what may ever cross to a browser: *"already-finalized
`communication.*` events plus read-only telemetry, never raw internal engine
chatter."* 4A's set is exactly that. Later milestones extend it --
`planning.task_graph.*` and `action.*` in 4B, `agent_os.task.*` in 4C,
`autonomy.*` in 4D -- by appending here and to `PUBLIC_TOPICS`. The bridging
mechanism itself never changes.

**Correction (4C.2e, 2026-09-10).** This docstring previously predicted 4C
would add *"`agent.*`/`agent_os.*`"*. It added neither. `agent.*` is the
`agent.{instance_id}.{state}` lifecycle family that Phase 3E never built and
CF-8 ratified as a narrowing, and `agent_os.*` is far too wide -- see the
entry below. The written prediction is corrected rather than the code bent to
match it.
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
        # --- Phase 4C milestone 4C.2e -------------------------------------
        # `agent_os.task.*`, deliberately **not** `agent_os.*`.
        #
        # `BoundEventBus` matches with `fnmatchcase`, where `*` spans dots, so
        # `agent_os.*` would subscribe this gateway to every Registry and
        # Supervisor RPC subject -- `agent_os.registry.list_packages.request`
        # among them. `PUBLIC_TOPICS` would still stop a browser naming one,
        # but the gateway process would be receiving internal request/reply
        # traffic that is not "already-finalized events plus read-only
        # telemetry" (doc 09 §6). The narrow prefix reaches
        # `agent_os.task.completed` and nothing else;
        # `test_no_agent_os_rpc_subject_is_subscribable` fails if that ever
        # stops being true.
        "agent_os.task.*",
    }
)
