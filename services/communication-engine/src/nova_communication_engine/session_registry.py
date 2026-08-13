"""In-memory registry of currently-connected sessions -- process-local, live
WebSocket connection state, which is why this lives outside `domain/`
(framework-free) and `channels/` (protocol implementations, not registries).

Design doc Sec14's own scalability admission applies directly: "this phase's
real deployment is one concurrent session per instance" (ADR-025's
single-user default), so an in-process dict is the correct scope for this
phase -- not a premature Redis-backed presence registry Phase 8's real
multi-tenant scale-out would actually need.

The `communication.intent` gate (`domain/intent_gate.py`) looks up a
session's live adapter here rather than holding its own reference --
design doc Sec7's "only the gate holds a reference to Channel Adapter
instances" is satisfied by "the gate looks it up from this one registry,"
not by adapters being passed around ad hoc.

`register()`'s optional `user_id` (Phase 2D-D docs/design/phase-2d/
06-personal-companion.md Sec10.2, Fork D) feeds `get_connected_session_id`
-- the "small, new capability" the TDD calls for: does this user have a
currently-connected session, and if so, which one. Exactly one connected
session per user, matching this registry's own documented single-
concurrent-session-per-instance scope (ADR-025) -- not a general
multi-session index. `user_id` is optional only because most existing
callers (this module's own tests) never needed it before this phase; the
one real production call site (`api/websocket.py`) always supplies it.
"""

from __future__ import annotations

from uuid import UUID

from nova_communication_engine.domain.ports import ChannelAdapter
from nova_communication_engine.domain.speech import BargeInSignal, StartListeningSignal

__all__ = ["SessionRegistry"]


class SessionRegistry:
    def __init__(self) -> None:
        self._adapters: dict[UUID, ChannelAdapter] = {}
        self._barge_in_signals: dict[UUID, BargeInSignal] = {}
        self._start_listening_signals: dict[UUID, StartListeningSignal] = {}
        self._session_users: dict[UUID, UUID] = {}
        self._user_sessions: dict[UUID, UUID] = {}

    def register(
        self, session_id: UUID, adapter: ChannelAdapter, *, user_id: UUID | None = None
    ) -> None:
        self._adapters[session_id] = adapter
        self._barge_in_signals[session_id] = BargeInSignal()
        self._start_listening_signals[session_id] = StartListeningSignal()
        if user_id is not None:
            self._session_users[session_id] = user_id
            self._user_sessions[user_id] = session_id

    def unregister(self, session_id: UUID) -> None:
        self._adapters.pop(session_id, None)
        self._barge_in_signals.pop(session_id, None)
        self._start_listening_signals.pop(session_id, None)
        user_id = self._session_users.pop(session_id, None)
        if user_id is not None and self._user_sessions.get(user_id) == session_id:
            del self._user_sessions[user_id]

    def get_connected_session_id(self, user_id: UUID) -> UUID | None:
        return self._user_sessions.get(user_id)

    def get_adapter(self, session_id: UUID) -> ChannelAdapter | None:
        return self._adapters.get(session_id)

    def get_barge_in_signal(self, session_id: UUID) -> BargeInSignal | None:
        return self._barge_in_signals.get(session_id)

    def trigger_barge_in(self, session_id: UUID) -> None:
        signal = self._barge_in_signals.get(session_id)
        if signal is not None:
            signal.trigger()

    def get_start_listening_signal(self, session_id: UUID) -> StartListeningSignal | None:
        return self._start_listening_signals.get(session_id)

    def trigger_start_listening(self, session_id: UUID) -> None:
        signal = self._start_listening_signals.get(session_id)
        if signal is not None:
            signal.trigger()

    def is_connected(self, session_id: UUID) -> bool:
        return session_id in self._adapters
