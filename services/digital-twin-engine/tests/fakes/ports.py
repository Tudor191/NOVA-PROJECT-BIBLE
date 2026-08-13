"""`FakeCommunicationPort` -- an in-memory `domain.ports.CommunicationPort`
(Phase 2D-D docs/design/phase-2d/06-personal-companion.md Sec10.2, Fork D),
deterministic and configurable per test, mirroring `communication-engine`'s
own `tests/fakes/ports.py` convention."""

from __future__ import annotations

from uuid import UUID


class FakeCommunicationPort:
    def __init__(
        self,
        *,
        connected_session_id: UUID | None = None,
        deliver_result: bool = True,
        raise_lookup_timeout: bool = False,
        raise_deliver_timeout: bool = False,
    ) -> None:
        self.connected_session_id = connected_session_id
        self.deliver_result = deliver_result
        self.raise_lookup_timeout = raise_lookup_timeout
        self.raise_deliver_timeout = raise_deliver_timeout
        self.get_connected_session_calls: list[UUID] = []
        self.deliver_intent_calls: list[tuple[UUID, str]] = []

    async def get_connected_session(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> UUID | None:
        self.get_connected_session_calls.append(user_id)
        if self.raise_lookup_timeout:
            raise TimeoutError("communication.session.lookup_by_user timed out")
        return self.connected_session_id

    async def deliver_intent(
        self, *, session_id: UUID, content: str, correlation_id: UUID | None = None
    ) -> bool:
        self.deliver_intent_calls.append((session_id, content))
        if self.raise_deliver_timeout:
            raise TimeoutError("communication.intent.deliver timed out")
        return self.deliver_result
