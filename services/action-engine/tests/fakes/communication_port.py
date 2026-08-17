"""`FakeCommunicationPort` -- an in-memory `domain.ports.CommunicationPort`,
scriptable per test: set `connected_session_id` (or leave `None` to
simulate no connected session) and `deliver_intent_error` to simulate a
`TimeoutError` on the best-effort disclosure step."""

from __future__ import annotations

from uuid import UUID


class FakeCommunicationPort:
    def __init__(self) -> None:
        self.connected_session_id: UUID | None = None
        self.deliver_intent_error: Exception | None = None
        self.delivered_content: list[str] = []

    async def get_connected_session(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> UUID | None:
        return self.connected_session_id

    async def deliver_intent(
        self, *, session_id: UUID, content: str, correlation_id: UUID | None = None
    ) -> bool:
        if self.deliver_intent_error is not None:
            raise self.deliver_intent_error
        self.delivered_content.append(content)
        return True
