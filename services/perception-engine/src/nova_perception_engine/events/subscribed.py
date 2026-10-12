"""Every subject Perception Engine is permitted to subscribe to --
docs/design/phase-2d/03-perception-engine.md Sec13.3. This engine's own
"is a session currently active with this speaker" addressee-candidate signal
(Master Blueprint Sec5.1) is the one genuine dependency direction from this
engine toward `communication-engine` -- the inverse of Sec0.7's producer/
consumer asymmetry. `communication.session.state_changed` carries no
`user_id` (only `session_id`) and Paused is not "ended" for this tracker's
purpose, so only `.created`/`.completed` -- the two subjects that actually
carry `user_id` and mark a clean start/end -- are subscribed.
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "communication.session.created",
        "communication.session.completed",
        # Phase 4F.8, A-4F8-2 (a): the existing subject carrying
        # `MemoryRecord.project_id`, so this engine learns which project
        # identities NOVA holds over the bus, never from `memory-engine`'s store
        # (TDD 4F §4.1; ADR-004). No new subject; the registry is unchanged.
        "memory.long_term.created",
    }
)
