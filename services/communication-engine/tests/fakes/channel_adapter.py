"""`FakeChannelAdapter` -- an in-memory `domain.ports.ChannelAdapter`,
recording every delivered message so tests can assert exactly what would
have reached the user."""

from __future__ import annotations

from nova_communication_engine.domain.models import (
    ChannelCapabilities,
    InboundMessage,
    OutboundMessage,
)


class FakeChannelAdapter:
    def __init__(self, *, channel_type: str = "text") -> None:
        self.channel_type = channel_type
        self.delivered: list[OutboundMessage] = []
        self._inbound_queue: list[InboundMessage] = []

    def queue_inbound(self, message: InboundMessage) -> None:
        self._inbound_queue.append(message)

    async def receive(self) -> InboundMessage:
        return self._inbound_queue.pop(0)

    async def deliver(self, message: OutboundMessage) -> None:
        self.delivered.append(message)

    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            streaming=True, audio=self.channel_type == "voice", text=self.channel_type == "text"
        )
