"""Tracks "is a conversation session currently active with this speaker"
(Master Blueprint Sec5.1) -- one of Sec10's addressee-candidate signals. The
one piece of genuinely live, in-memory state this engine keeps from
`communication-engine`'s own events (Sec0.7, Sec13.3), mirroring
`communication-engine`'s own `session_registry.py` precedent: safe to lose
on restart (a missed "session active" signal degrades addressee-candidate
quality slightly, never causes an incorrect identity/presence fact -- Sec10's
own event carries no verdict, so this state is advisory, not authoritative).
"""

from __future__ import annotations

from uuid import UUID

__all__ = ["SessionActivityTracker"]


class SessionActivityTracker:
    def __init__(self) -> None:
        self._active_sessions_by_user: dict[UUID, set[UUID]] = {}

    def session_created(self, *, user_id: UUID, session_id: UUID) -> None:
        self._active_sessions_by_user.setdefault(user_id, set()).add(session_id)

    def session_ended(self, *, user_id: UUID, session_id: UUID) -> None:
        sessions = self._active_sessions_by_user.get(user_id)
        if sessions is not None:
            sessions.discard(session_id)
            if not sessions:
                del self._active_sessions_by_user[user_id]

    def is_active(self, *, user_id: UUID) -> bool:
        return bool(self._active_sessions_by_user.get(user_id))
