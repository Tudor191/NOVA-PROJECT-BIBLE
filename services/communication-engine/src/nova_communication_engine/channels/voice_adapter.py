"""`VoiceChannelAdapter` -- implements `domain.ports.ChannelAdapter` over a
FastAPI WebSocket (design doc Sec5): binary frames carry raw audio, JSON
text frames carry the Sec0.4 explicit-trigger control signals
(`trigger_start`/`trigger_stop` -- push-to-talk-style, never acoustic
wake-word detection). Wire-format translation only, the same boundary
`TextChannelAdapter` observes.
"""

from __future__ import annotations

import json

from fastapi import WebSocket, WebSocketDisconnect

from nova_communication_engine.domain.models import (
    ChannelCapabilities,
    InboundMessage,
    InboundMessageKind,
    OutboundMessage,
    OutboundMessageKind,
)

__all__ = ["VoiceChannelAdapter"]


class VoiceChannelAdapter:
    channel_type = "voice"

    def __init__(self, websocket: WebSocket) -> None:
        self._websocket = websocket

    async def receive(self) -> InboundMessage:
        message = await self._websocket.receive()
        if message["type"] == "websocket.disconnect":
            # `WebSocket.receive()` is the raw ASGI-level call (needed here
            # since a single voice-channel connection carries both binary
            # audio and JSON control frames, unlike `TextChannelAdapter`'s
            # single-mode `receive_json()`) -- unlike `receive_text()`/
            # `receive_bytes()`/`receive_json()`, it does not itself raise
            # `WebSocketDisconnect` on this message type, so this adapter
            # must (mirrors Starlette's own `WebSocket._raise_on_disconnect`
            # precedent, used internally by those three methods).
            raise WebSocketDisconnect(message.get("code", 1000), message.get("reason"))

        audio = message.get("bytes")
        if audio is not None:
            return InboundMessage(kind=InboundMessageKind.AUDIO_CHUNK, audio=audio)

        text = message.get("text")
        if text is not None:
            data = json.loads(text)
            kind = data.get("kind")
            if kind == "trigger_start":
                return InboundMessage(kind=InboundMessageKind.TRIGGER_START)
            if kind == "trigger_stop":
                return InboundMessage(kind=InboundMessageKind.TRIGGER_STOP)

        raise ValueError(f"Unrecognized voice channel WebSocket message: {message!r}")

    async def deliver(self, message: OutboundMessage) -> None:
        if message.kind is OutboundMessageKind.AUDIO_CHUNK and message.audio is not None:
            await self._websocket.send_bytes(message.audio)
        elif message.content is not None:
            await self._websocket.send_json(
                {"kind": message.kind.value, "content": message.content}
            )

    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(streaming=True, audio=True, text=False)
