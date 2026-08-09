"""`domain.speech` (docs/design/phase-2d/01-communication-engine.md Sec4,
Sec13; Phase 2D-C Closure Priority 4 review Sec1.2/Sec1.3) -- `BargeInSignal`/
`StartListeningSignal`'s own trigger/is_set/clear semantics in isolation, and
`speak_response`'s barge-in handling including the Priority 4 review's own
fix: a barge-in must not permanently mute every later response delivered
over the same connection-lifetime signal."""

from __future__ import annotations

from nova_communication_engine.domain import speech
from nova_communication_engine.domain.speech import BargeInSignal, StartListeningSignal

from tests.fakes.channel_adapter import FakeChannelAdapter
from tests.fakes.ports import FakeModelOrchestrationPort


def test_barge_in_signal_starts_unset() -> None:
    signal = BargeInSignal()
    assert signal.is_set() is False


def test_barge_in_signal_trigger_then_clear() -> None:
    signal = BargeInSignal()
    signal.trigger()
    assert signal.is_set() is True
    signal.clear()
    assert signal.is_set() is False


def test_barge_in_signal_clear_before_trigger_is_a_safe_no_op() -> None:
    signal = BargeInSignal()
    signal.clear()
    assert signal.is_set() is False


def test_barge_in_signal_trigger_after_clear_still_works() -> None:
    signal = BargeInSignal()
    signal.trigger()
    signal.clear()
    signal.trigger()
    assert signal.is_set() is True


def test_start_listening_signal_starts_unset() -> None:
    signal = StartListeningSignal()
    assert signal.is_set() is False


def test_start_listening_signal_trigger_then_clear() -> None:
    signal = StartListeningSignal()
    signal.trigger()
    assert signal.is_set() is True
    signal.clear()
    assert signal.is_set() is False


def test_start_listening_signal_clear_before_trigger_is_a_safe_no_op() -> None:
    signal = StartListeningSignal()
    signal.clear()
    assert signal.is_set() is False


def test_start_listening_signal_trigger_after_clear_still_works() -> None:
    signal = StartListeningSignal()
    signal.trigger()
    signal.clear()
    signal.trigger()
    assert signal.is_set() is True


async def test_speak_response_clears_the_signal_once_a_barge_in_is_consumed() -> None:
    """Priority 4 review Sec1.3: `SessionRegistry.register()` constructs one
    `BargeInSignal` per connection, reused for every response -- without
    `speak_response` clearing it, every later response would see an
    already-set signal and abort before its first chunk, forever."""
    signal = BargeInSignal()
    signal.trigger()  # already interrupted before this call, mirrors the real barge-in path
    first = await speech.speak_response(
        content="First sentence. Second sentence.",
        channel_adapter=FakeChannelAdapter(channel_type="voice"),
        model_orchestration_port=FakeModelOrchestrationPort(),
        barge_in_signal=signal,
    )
    assert first.barged_in is True
    assert first.delivered_chunks == 0
    assert signal.is_set() is False  # consumed and reset, not left permanently set

    adapter = FakeChannelAdapter(channel_type="voice")
    second = await speech.speak_response(
        content="A brand new response.",
        channel_adapter=adapter,
        model_orchestration_port=FakeModelOrchestrationPort(),
        barge_in_signal=signal,
    )
    assert second.barged_in is False
    assert second.delivered_chunks == second.total_chunks
    assert len(adapter.delivered) == second.total_chunks


async def test_speak_response_leaves_a_never_triggered_signal_unset() -> None:
    signal = BargeInSignal()
    result = await speech.speak_response(
        content="Nothing interrupts this one.",
        channel_adapter=FakeChannelAdapter(channel_type="voice"),
        model_orchestration_port=FakeModelOrchestrationPort(),
        barge_in_signal=signal,
    )
    assert result.barged_in is False
    assert signal.is_set() is False
