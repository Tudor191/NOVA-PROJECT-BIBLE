"""`domain.vad.TransportVad` (docs/design/phase-2d/01-communication-engine.md
Sec4) -- start/continue/end detection, the transient-gap tolerance boundary
itself (Master Blueprint Sec13.5), and barge-in detection (Sec13.4)."""

from __future__ import annotations

from nova_communication_engine.domain.vad import (
    TransportVad,
    TransportVadConfig,
    UtteranceEvent,
    detect_barge_in,
)


def test_first_energy_tick_starts_the_utterance() -> None:
    vad = TransportVad()
    assert vad.feed(energy_above_threshold=True, now_ms=0.0) is UtteranceEvent.STARTED
    assert vad.active is True


def test_subsequent_energy_ticks_continue() -> None:
    vad = TransportVad()
    vad.feed(energy_above_threshold=True, now_ms=0.0)
    assert vad.feed(energy_above_threshold=True, now_ms=50.0) is UtteranceEvent.CONTINUING


def test_no_energy_before_any_utterance_is_no_change() -> None:
    vad = TransportVad()
    assert vad.feed(energy_above_threshold=False, now_ms=0.0) is UtteranceEvent.NO_CHANGE
    assert vad.active is False


def test_gap_below_tolerance_is_bridged_not_ended() -> None:
    vad = TransportVad(TransportVadConfig(end_of_utterance_silence_ms=700.0))
    vad.feed(energy_above_threshold=True, now_ms=0.0)
    event = vad.feed(energy_above_threshold=False, now_ms=699.0)
    assert event is UtteranceEvent.CONTINUING
    assert vad.active is True


def test_gap_at_tolerance_boundary_ends_the_utterance() -> None:
    vad = TransportVad(TransportVadConfig(end_of_utterance_silence_ms=700.0))
    vad.feed(energy_above_threshold=True, now_ms=0.0)
    event = vad.feed(energy_above_threshold=False, now_ms=700.0)
    assert event is UtteranceEvent.ENDED
    assert vad.active is False


def test_gap_above_tolerance_ends_the_utterance() -> None:
    vad = TransportVad(TransportVadConfig(end_of_utterance_silence_ms=700.0))
    vad.feed(energy_above_threshold=True, now_ms=0.0)
    event = vad.feed(energy_above_threshold=False, now_ms=1500.0)
    assert event is UtteranceEvent.ENDED


def test_energy_after_a_bridged_gap_still_continues_the_same_utterance() -> None:
    vad = TransportVad(TransportVadConfig(end_of_utterance_silence_ms=700.0))
    vad.feed(energy_above_threshold=True, now_ms=0.0)
    vad.feed(energy_above_threshold=False, now_ms=300.0)
    event = vad.feed(energy_above_threshold=True, now_ms=400.0)
    assert event is UtteranceEvent.CONTINUING
    assert vad.active is True


def test_reset_clears_active_state() -> None:
    vad = TransportVad()
    vad.feed(energy_above_threshold=True, now_ms=0.0)
    vad.reset()
    assert vad.active is False
    assert vad.feed(energy_above_threshold=True, now_ms=1.0) is UtteranceEvent.STARTED


def test_detect_barge_in_is_immediate_and_unconditional() -> None:
    assert detect_barge_in(energy_above_threshold=True) is True
    assert detect_barge_in(energy_above_threshold=False) is False
