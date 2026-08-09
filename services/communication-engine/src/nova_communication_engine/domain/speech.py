"""Voice delivery -- design doc Sec4, Sec13: chunked `synthesize` calls
(never a single streaming RPC, ADR-004) with unconditional, immediate
barge-in cancellation (Master Blueprint Sec13.4).

`barge_in_signal` is checked at two points per chunk -- before requesting
synthesis and again after receiving it, before delivering it -- so a
barge-in detected mid-loop both "stops issuing further per-chunk synthesize
calls" and "discards any audio already returned but not yet played" (design
doc Sec4's exact two requirements), without needing to cancel an in-flight
RPC itself.
"""

from __future__ import annotations

from pydantic import BaseModel

from nova_communication_engine.domain.chunking import split_into_chunks
from nova_communication_engine.domain.models import OutboundMessage, OutboundMessageKind
from nova_communication_engine.domain.ports import ChannelAdapter, ModelOrchestrationPort

__all__ = ["BargeInSignal", "SpeakResult", "StartListeningSignal", "speak_response"]


class BargeInSignal:
    """A minimal, synchronous, pollable signal -- deliberately not
    `asyncio.Event` in `domain/` (framework-free per every prior engine's
    own boundary); the voice channel adapter/websocket layer sets it via
    `trigger()`, this module only ever reads `is_set()`.

    `SessionRegistry.register()` constructs exactly one instance per
    connection, reused for every response delivered on it -- so `clear()`
    (Phase 2D-C Closure Priority 4 review, §1.3) must be called once a
    barge-in has actually been consumed by `speak_response` below, or every
    later response on the same connection would see a permanently-set
    signal and abort before its first chunk."""

    def __init__(self) -> None:
        self._set = False

    def trigger(self) -> None:
        self._set = True

    def is_set(self) -> bool:
        return self._set

    def clear(self) -> None:
        self._set = False


class StartListeningSignal:
    """A minimal, synchronous, pollable, one-shot signal -- the server-
    triggered counterpart to the client's `TRIGGER_START` message (Phase 2D-C
    Closure Priority 4, docs/design/phase-2d/
    05-conversation-intelligence-closure.md §6). Unlike `BargeInSignal`
    (continuously re-read across an entire response's chunk loop),
    `api/websocket.py`'s receive loop consumes this in a single check per
    tick and must clear it itself immediately after -- `trigger()` fires
    once from `conversation_orchestration.maybe_activate_listening`, and is
    consumed at most once."""

    def __init__(self) -> None:
        self._set = False

    def trigger(self) -> None:
        self._set = True

    def is_set(self) -> bool:
        return self._set

    def clear(self) -> None:
        self._set = False


class SpeakResult(BaseModel):
    total_chunks: int
    delivered_chunks: int
    barged_in: bool


async def speak_response(
    *,
    content: str,
    channel_adapter: ChannelAdapter,
    model_orchestration_port: ModelOrchestrationPort,
    barge_in_signal: BargeInSignal,
) -> SpeakResult:
    chunks = split_into_chunks(content)
    delivered_chunks = 0

    for chunk in chunks:
        if barge_in_signal.is_set():
            break

        audio = await model_orchestration_port.synthesize(text=chunk)

        if barge_in_signal.is_set():
            break  # Sec4: discard audio already returned but not yet played

        if audio is None:
            # Sec9: synthesize failed after the Model Router's fallback
            # chain was exhausted -- stop this response's remaining chunks
            # rather than deliver a partial, silently-truncated one; the
            # caller (intent_gate) surfaces this as a failed turn.
            break

        await channel_adapter.deliver(
            OutboundMessage(kind=OutboundMessageKind.AUDIO_CHUNK, audio=audio)
        )
        delivered_chunks += 1

    barged_in = barge_in_signal.is_set()
    if barged_in:
        # This response has now fully consumed the barge-in it was
        # interrupted by -- reset it so it does not silently truncate every
        # later response on this same connection-lifetime signal (§1.3).
        barge_in_signal.clear()

    return SpeakResult(
        total_chunks=len(chunks),
        delivered_chunks=delivered_chunks,
        barged_in=barged_in,
    )
