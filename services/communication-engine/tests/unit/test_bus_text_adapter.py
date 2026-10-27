"""`BusTextChannelAdapter` -- the channel that carries a browser session's
reply, whose transport is the Event Bus rather than a socket this engine
holds.

Its whole contract is what it accepts and what it refuses, so that is what
these tests pin. The refusals matter more than the acceptance: an adapter
that quietly accepted audio, or an empty utterance, would make the intent
gate report `delivered=True` for something no browser could ever render.
"""

from __future__ import annotations

import pytest
from nova_communication_engine.channels.bus_text_adapter import (
    BusTextChannelAdapter,
    ChannelNotReceivableError,
    UnsupportedOutboundKindError,
)
from nova_communication_engine.domain.models import OutboundMessage, OutboundMessageKind
from nova_communication_engine.domain.ports import ChannelAdapter


def test_it_satisfies_the_channel_adapter_protocol() -> None:
    """`deliver_intent` accepts any `ChannelAdapter`; this proves the new one
    actually is one rather than merely looking like it at the call site."""
    assert isinstance(BusTextChannelAdapter(), ChannelAdapter)
    assert BusTextChannelAdapter().channel_type == "text"


async def test_a_finalized_text_utterance_is_accepted() -> None:
    adapter = BusTextChannelAdapter()
    await adapter.deliver(
        OutboundMessage(kind=OutboundMessageKind.TEXT, content="Hello, I'm here.")
    )


async def test_audio_is_refused() -> None:
    """`communication.intent.delivered` has no audio field, so accepting a
    voice utterance here would announce a reply that carries nothing."""
    adapter = BusTextChannelAdapter()
    with pytest.raises(UnsupportedOutboundKindError, match="text only"):
        await adapter.deliver(
            OutboundMessage(kind=OutboundMessageKind.AUDIO_CHUNK, audio=b"\x00\x01")
        )


@pytest.mark.parametrize("content", ["", None])
async def test_an_empty_utterance_is_refused(content: str | None) -> None:
    adapter = BusTextChannelAdapter()
    with pytest.raises(UnsupportedOutboundKindError, match="empty utterance"):
        await adapter.deliver(OutboundMessage(kind=OutboundMessageKind.TEXT, content=content))


async def test_receive_raises_rather_than_blocking_forever() -> None:
    """The WebSocket receive loop drives `receive()` in a loop. This adapter
    can never produce an inbound message -- those arrive over REST -- so it
    must fail loudly instead of hanging the loop that called it."""
    adapter = BusTextChannelAdapter()
    with pytest.raises(ChannelNotReceivableError, match="outbound-only"):
        await adapter.receive()


def test_capabilities_report_a_non_streaming_text_channel() -> None:
    capabilities = BusTextChannelAdapter().capabilities()
    assert capabilities.text is True
    assert capabilities.audio is False
    # Not a gap to close later: the subject carries an utterance the intent
    # gate has already finalized, so there is nothing partial to stream.
    assert capabilities.streaming is False
