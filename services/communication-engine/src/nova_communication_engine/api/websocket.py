"""`WS /sessions/{id}` (docs/design/phase-2d/01-communication-engine.md
Sec12) -- the voice channel + streaming text channel. Registers this
connection's `ChannelAdapter` in `session_registry` so the `communication.
intent` gate (driven by `events/handlers.py`'s served RPC) can deliver
generated content to it; unregisters on disconnect and pauses the session
(design doc Sec9's "Channel Adapter disconnects mid-Speaking" row, applied
uniformly to any disconnect, not only mid-`Speaking`).

Disconnect uses `session_lifecycle.recover_session_to_paused` -- the same
FSM-bypassing direct write Sec3.5's restart recovery uses -- rather than
`pause_session`'s FSM-validated `PAUSE` event: "no channel connection is
live" is true regardless of which state the session was in when the
connection dropped (including `Idle`, which has no `PAUSE` edge in Sec3.1's
diagram), the identical reasoning restart recovery already applies.

Voice-channel audio ticks drive `domain.vad.TransportVad` via a short
receive timeout (`_SILENCE_POLL_INTERVAL_S`) standing in for a continuous
audio stream's natural cadence -- when no frame arrives within that window,
that itself is fed to the VAD as "no energy this tick," the same signal a
real gap in the incoming audio would produce.
"""

from __future__ import annotations

import asyncio
import time
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from nova_communication_engine.channels.text_adapter import TextChannelAdapter
from nova_communication_engine.channels.voice_adapter import VoiceChannelAdapter
from nova_communication_engine.domain import session_lifecycle
from nova_communication_engine.domain.models import (
    ChannelType,
    ConversationState,
    InboundMessageKind,
    OutboundMessage,
    OutboundMessageKind,
)
from nova_communication_engine.domain.ports import ChannelAdapter
from nova_communication_engine.domain.vad import TransportVad, TransportVadConfig, UtteranceEvent

router = APIRouter(tags=["websocket"])

_SILENCE_POLL_INTERVAL_S = 0.1
_TRANSCRIBE_UNAVAILABLE_NOTICE = "Voice is temporarily unavailable. Please try again shortly."


def _now_ms() -> float:
    return time.monotonic() * 1000


@router.websocket("/sessions/{session_id}")
async def session_websocket(websocket: WebSocket, session_id: UUID) -> None:
    state = websocket.app.state
    session = await state.repository.get_session(session_id)
    if session is None:
        await websocket.close(code=4404)
        return

    await websocket.accept()

    adapter: ChannelAdapter
    if session.channel is ChannelType.VOICE:
        adapter = VoiceChannelAdapter(websocket)
    else:
        adapter = TextChannelAdapter(websocket)

    state.session_registry.register(session_id, adapter)

    silence_ms = state.settings.communication_engine_vad_end_of_utterance_silence_ms
    vad_config = TransportVadConfig(end_of_utterance_silence_ms=silence_ms)
    vad = TransportVad(vad_config)
    audio_buffer = bytearray()
    turn_active = False

    async def _finalize_utterance() -> None:
        nonlocal audio_buffer
        if not audio_buffer:
            return
        transcript = await state.model_orchestration_port.transcribe(
            audio=bytes(audio_buffer), correlation_id=session_id
        )
        audio_buffer = bytearray()
        current = await state.repository.get_session(session_id)
        if current is None:
            return
        if transcript is None:
            # Design doc Sec9: fallback chain exhausted -- an honest,
            # mechanical notice, not generated content, so it bypasses the
            # intent gate (intent_gate.py's own docstring documents this
            # one exception).
            notice = OutboundMessage(
                kind=OutboundMessageKind.TEXT, content=_TRANSCRIBE_UNAVAILABLE_NOTICE
            )
            await adapter.deliver(notice)
            return
        await session_lifecycle.record_inbound_turn(
            session=current,
            content=transcript,
            repository=state.repository,
            correlation_id=session_id,
        )

    try:
        while True:
            try:
                inbound = await asyncio.wait_for(
                    adapter.receive(), timeout=_SILENCE_POLL_INTERVAL_S
                )
            except TimeoutError:
                if turn_active:
                    event = vad.feed(energy_above_threshold=False, now_ms=_now_ms())
                    if event is UtteranceEvent.ENDED:
                        await _finalize_utterance()
                        turn_active = False
                continue

            if inbound.kind is InboundMessageKind.TEXT:
                current = await state.repository.get_session(session_id)
                if current is not None:
                    await session_lifecycle.record_inbound_turn(
                        session=current,
                        content=inbound.content or "",
                        repository=state.repository,
                        correlation_id=session_id,
                    )
                continue

            if inbound.kind is InboundMessageKind.TRIGGER_START:
                vad.reset()
                audio_buffer = bytearray()
                turn_active = True
                continue

            if inbound.kind is InboundMessageKind.TRIGGER_STOP:
                if turn_active:
                    await _finalize_utterance()
                turn_active = False
                continue

            if inbound.kind is InboundMessageKind.AUDIO_CHUNK and inbound.audio is not None:
                current = await state.repository.get_session(session_id)
                if current is not None and current.state is ConversationState.SPEAKING:
                    # Design doc Sec4, Master Blueprint Sec13.4: unconditional,
                    # immediate barge-in -- any audio while Speaking.
                    state.session_registry.trigger_barge_in(session_id)
                    await session_lifecycle.mark_barge_in(
                        session=current, repository=state.repository, correlation_id=session_id
                    )
                    vad.reset()
                    audio_buffer = bytearray()
                    turn_active = True

                if turn_active:
                    audio_buffer.extend(inbound.audio)
                    event = vad.feed(energy_above_threshold=True, now_ms=_now_ms())
                    if event is UtteranceEvent.ENDED:
                        await _finalize_utterance()
                        turn_active = False
                continue
    except WebSocketDisconnect:
        pass
    finally:
        state.session_registry.unregister(session_id)
        current = await state.repository.get_session(session_id)
        if current is not None and current.state is not ConversationState.COMPLETED:
            await session_lifecycle.recover_session_to_paused(
                session=current, repository=state.repository, correlation_id=session_id
            )
