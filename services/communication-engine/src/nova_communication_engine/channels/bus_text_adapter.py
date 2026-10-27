"""`BusTextChannelAdapter` -- implements `domain.ports.ChannelAdapter` for a
text session whose transport is the Event Bus rather than a socket this
engine holds.

Design doc Sec5 defines a channel adapter as wire-format translation only.
For this adapter "the wire" is the bus: a finalized utterance leaves as a
`communication.intent.delivered` event, which `ws-gateway` -- the sole
component permitted to bridge bus subjects to a browser (doc 09 Sec6) --
forwards to the subscribed client. The web client cannot be a
`TextChannelAdapter`, because doc 11 Sec1 forbids it from opening a
connection to an engine at all; without this adapter a browser session has
no channel, and the ADR-005 intent gate correctly refuses to call its reply
delivered.

**This adapter publishes nothing.** It accepts an utterance for
transmission and returns; the outbox row that carries it is written by
`events/handlers.py`, which is and remains the single emission point for
`communication.intent.delivered`. Publishing here instead would need
`turn_id`, `confidence_tier`, `personality_validated` and `degraded` --
none of which exist on `OutboundMessage` -- and would put domain-event
construction inside a wire-format adapter, which is exactly the boundary
Sec5 draws.

It is stateless, so one instance serves every session (`main.py` builds it
once as `app.state.bus_text_adapter`). It is deliberately **not** placed in
`SessionRegistry`: that registry holds process-local live connection state,
and a bus-backed channel has no connection. Registering it there would also
make it vanish on restart with nothing to re-register it, and exist only on
the replica that served the request.
"""

from __future__ import annotations

from nova_communication_engine.domain.models import (
    ChannelCapabilities,
    InboundMessage,
    OutboundMessage,
    OutboundMessageKind,
)

__all__ = [
    "BusTextChannelAdapter",
    "ChannelNotReceivableError",
    "UnsupportedOutboundKindError",
]


class ChannelNotReceivableError(RuntimeError):
    """Raised by `receive()` on an outbound-only channel."""


class UnsupportedOutboundKindError(ValueError):
    """Raised when an utterance is not something this channel can carry."""


class BusTextChannelAdapter:
    channel_type = "text"

    async def receive(self) -> InboundMessage:
        """Always raises: this channel is outbound-only.

        Inbound turns for a bus-backed session arrive over REST
        (`POST /v1/communication/sessions/{id}/messages`), never here. Raising
        rather than blocking forever is what keeps `api/websocket.py`'s
        receive loop from ever driving this adapter by accident -- that loop
        would otherwise hang on a channel that can never produce a message.
        """
        raise ChannelNotReceivableError(
            "BusTextChannelAdapter is outbound-only; inbound turns for a "
            "bus-backed session arrive over the REST surface."
        )

    async def deliver(self, message: OutboundMessage) -> None:
        """Accept a finalized text utterance for transmission, or raise.

        Returning is the whole contract: per ADR-005 the gate reads a clean
        return as "a channel accepted this", which is strictly weaker than
        "a person saw it" -- the same thing a socket write has always meant.
        """
        if message.kind is not OutboundMessageKind.TEXT:
            raise UnsupportedOutboundKindError(
                f"BusTextChannelAdapter carries text only; refusing {message.kind.value!r}. "
                "Audio has no representation in `communication.intent.delivered`."
            )
        if not message.content:
            raise UnsupportedOutboundKindError(
                "BusTextChannelAdapter refuses an empty utterance: an event announcing "
                "that NOVA said nothing would render as a blank transcript entry."
            )

    def capabilities(self) -> ChannelCapabilities:
        """`streaming=False` is not a limitation to fix later -- it is what the
        subject means. `communication.intent.delivered` announces an utterance
        the intent gate has already passed, so there are no partial tokens to
        stream (doc 09 Sec6: "already-finalized `communication.*` events")."""
        return ChannelCapabilities(streaming=False, audio=False, text=True)
