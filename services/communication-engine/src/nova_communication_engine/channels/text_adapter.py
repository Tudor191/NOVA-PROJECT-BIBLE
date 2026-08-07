"""`TextChannelAdapter` -- implements `domain.ports.ChannelAdapter` over a
FastAPI WebSocket (design doc Sec5). Wire-format translation only (JSON
frames <-> `InboundMessage`/`OutboundMessage`) -- no session state, no
content generation, no personality validation (design doc Sec2's own
responsibility table for this component).
"""

from __future__ import annotations

from fastapi import WebSocket

from nova_communication_engine.domain.models import (
    ChannelCapabilities,
    InboundMessage,
    InboundMessageKind,
    OutboundMessage,
)

__all__ = ["TextChannelAdapter"]


class TextChannelAdapter:
    channel_type = "text"

    def __init__(self, websocket: WebSocket) -> None:
        self._websocket = websocket

    async def receive(self) -> InboundMessage:
        data = await self._websocket.receive_json()
        return InboundMessage(kind=InboundMessageKind.TEXT, content=data.get("content"))

    async def deliver(self, message: OutboundMessage) -> None:
        await self._websocket.send_json({"kind": message.kind.value, "content": message.content})

    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(streaming=True, audio=False, text=True)
