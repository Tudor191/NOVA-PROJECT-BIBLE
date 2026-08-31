"""`FakeCommunicationPort` -- an in-memory `domain.ports.CommunicationPort`
for pipeline unit tests that need to observe the Permission Review stage's
disclosure calls without a real Event Bus round trip (that round trip is
covered separately in `tests/integration/test_communication_client.py`)."""

from __future__ import annotations

from uuid import UUID


class FakeCommunicationPort:
    def __init__(
        self, *, session_id: UUID | None, deliver_result: bool = True, raise_timeout: bool = False
    ) -> None:
        self._session_id = session_id
        self._deliver_result = deliver_result
        self._raise_timeout = raise_timeout
        self.delivered_content: list[str] = []

    async def get_connected_session(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> UUID | None:
        if self._raise_timeout:
            raise TimeoutError("simulated communication-engine timeout")
        return self._session_id

    async def deliver_intent(
        self, *, session_id: UUID, content: str, correlation_id: UUID | None = None
    ) -> bool:
        self.delivered_content.append(content)
        return self._deliver_result
