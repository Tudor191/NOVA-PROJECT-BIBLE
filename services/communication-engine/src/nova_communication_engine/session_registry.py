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
"""

from __future__ import annotations

from uuid import UUID

from nova_communication_engine.domain.ports import ChannelAdapter
from nova_communication_engine.domain.speech import BargeInSignal

__all__ = ["SessionRegistry"]


class SessionRegistry:
    def __init__(self) -> None:
        self._adapters: dict[UUID, ChannelAdapter] = {}
        self._barge_in_signals: dict[UUID, BargeInSignal] = {}

    def register(self, session_id: UUID, adapter: ChannelAdapter) -> None:
        self._adapters[session_id] = adapter
        self._barge_in_signals[session_id] = BargeInSignal()

    def unregister(self, session_id: UUID) -> None:
        self._adapters.pop(session_id, None)
        self._barge_in_signals.pop(session_id, None)

    def get_adapter(self, session_id: UUID) -> ChannelAdapter | None:
        return self._adapters.get(session_id)

    def get_barge_in_signal(self, session_id: UUID) -> BargeInSignal | None:
        return self._barge_in_signals.get(session_id)

    def trigger_barge_in(self, session_id: UUID) -> None:
        signal = self._barge_in_signals.get(session_id)
        if signal is not None:
            signal.trigger()

    def is_connected(self, session_id: UUID) -> bool:
        return session_id in self._adapters
