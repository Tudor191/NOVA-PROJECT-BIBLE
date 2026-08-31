"""`FakeAgentInstancePort` -- an in-memory `domain.ports.AgentInstancePort`
for `domain/peer_review.py` unit tests. Lets a test script exactly what a
reviewer instance's `on_message` reply would be (a `PEER_REVIEW_RESULT`
`AgentMessage`, `None`, or a simulated `TimeoutError`) without a real
Event Bus round trip."""

from __future__ import annotations

from nova_contracts import AgentMessage

__all__ = ["FakeAgentInstancePort"]


class FakeAgentInstancePort:
    def __init__(
        self, *, reply: AgentMessage | None = None, raise_timeout: bool = False
    ) -> None:
        self._reply = reply
        self._raise_timeout = raise_timeout
        self.delivered: list[AgentMessage] = []

    async def deliver(
        self, message: AgentMessage, *, timeout_ms: int = 30000
    ) -> AgentMessage | None:
        self.delivered.append(message)
        if self._raise_timeout:
            raise TimeoutError("simulated agent instance timeout")
        return self._reply
