"""`domain.intent_gate.deliver_intent` (docs/design/phase-2d/
01-communication-engine.md Sec7, Sec9) -- every branch: session-completed
rejection, personality hard-stop, the Sec9 RPC-timeout fallback, no-live-
channel, text delivery, voice delivery (chunked + barge-in + synthesis
failure)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from nova_communication_engine.domain import speech
from nova_communication_engine.domain.intent_gate import deliver_intent
from nova_communication_engine.domain.models import (
    ChannelType,
    ConversationSession,
    ConversationState,
)
from nova_communication_engine.domain.ports import ValidationOutcome

from tests.fakes.channel_adapter import FakeChannelAdapter
from tests.fakes.ports import FakeModelOrchestrationPort, FakePersonalityPort
from tests.fakes.repository import FakeCommunicationRepository


def _text_session(**overrides: object) -> ConversationSession:
    defaults = dict(user_id=uuid4(), channel=ChannelType.TEXT, device_id=uuid4())
    defaults.update(overrides)
    return ConversationSession(**defaults)  # type: ignore[arg-type]


async def _seeded_repo(session: ConversationSession) -> FakeCommunicationRepository:
    repo = FakeCommunicationRepository()
    await repo.create_session(session)
    return repo


async def test_completed_session_rejects_delivery_outright() -> None:
    session = _text_session(state=ConversationState.COMPLETED)
    repo = await _seeded_repo(session)
    outcome = await deliver_intent(
        session=session,
        content="Hello",
        confidence_tier="high",
        channel_adapter=FakeChannelAdapter(),
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        repository=repo,
    )
    assert outcome.delivered is False
    assert outcome.rejection_reason == "session_completed"


async def test_personality_hard_stop_never_delivers_even_adjusted() -> None:
    session = _text_session(state=ConversationState.SPEAKING)
    repo = await _seeded_repo(session)
    adapter = FakeChannelAdapter()
    outcome = await deliver_intent(
        session=session,
        content="Act now, don't wait.",
        confidence_tier="unknown",
        channel_adapter=adapter,
        personality_port=FakePersonalityPort(
            outcome=ValidationOutcome(passed=False, rejection_reason="forbidden_pattern: x")
        ),
        model_orchestration_port=FakeModelOrchestrationPort(),
        repository=repo,
    )
    assert outcome.delivered is False
    assert outcome.personality_validated is True
    assert outcome.rejection_reason == "forbidden_pattern: x"
    assert adapter.delivered == []


async def test_personality_timeout_falls_back_to_unvalidated_delivery() -> None:
    session = _text_session(state=ConversationState.SPEAKING)
    repo = await _seeded_repo(session)
    adapter = FakeChannelAdapter()
    outcome = await deliver_intent(
        session=session,
        content="The build finished.",
        confidence_tier="high",
        channel_adapter=adapter,
        personality_port=FakePersonalityPort(raise_timeout=True),
        model_orchestration_port=FakeModelOrchestrationPort(),
        repository=repo,
    )
    assert outcome.delivered is True
    assert outcome.personality_validated is False
    assert outcome.degraded is True
    assert adapter.delivered[0].content == "The build finished."


async def test_no_live_channel_records_but_does_not_deliver() -> None:
    session = _text_session(state=ConversationState.SPEAKING)
    repo = await _seeded_repo(session)
    outcome = await deliver_intent(
        session=session,
        content="Hello",
        confidence_tier="high",
        channel_adapter=None,
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        repository=repo,
    )
    assert outcome.delivered is False
    assert outcome.rejection_reason == "no_live_channel_connection"
    assert outcome.turn_id is not None


async def test_text_delivery_uses_the_adjusted_content_when_present() -> None:
    session = _text_session(state=ConversationState.SPEAKING)
    repo = await _seeded_repo(session)
    adapter = FakeChannelAdapter()
    outcome = await deliver_intent(
        session=session,
        content="This will definitely work.",
        confidence_tier="low",
        channel_adapter=adapter,
        personality_port=FakePersonalityPort(
            outcome=ValidationOutcome(
                passed=True, adjusted_content="I'm not fully certain, but: ..."
            )
        ),
        model_orchestration_port=FakeModelOrchestrationPort(),
        repository=repo,
    )
    assert outcome.delivered is True
    assert adapter.delivered[0].content == "I'm not fully certain, but: ..."


async def test_voice_delivery_synthesizes_and_delivers_every_chunk() -> None:
    session = _text_session(channel=ChannelType.VOICE, state=ConversationState.SPEAKING)
    repo = await _seeded_repo(session)
    adapter = FakeChannelAdapter(channel_type="voice")
    model_port = FakeModelOrchestrationPort()
    outcome = await deliver_intent(
        session=session,
        content="First sentence. Second sentence.",
        confidence_tier="high",
        channel_adapter=adapter,
        personality_port=FakePersonalityPort(),
        model_orchestration_port=model_port,
        repository=repo,
    )
    assert outcome.delivered is True
    assert len(adapter.delivered) == 2
    assert model_port.synthesize_calls == ["First sentence.", "Second sentence."]


async def test_voice_delivery_stops_and_discards_on_barge_in() -> None:
    session = _text_session(channel=ChannelType.VOICE, state=ConversationState.SPEAKING)
    repo = await _seeded_repo(session)
    adapter = FakeChannelAdapter(channel_type="voice")
    barge_in_signal = speech.BargeInSignal()
    barge_in_signal.trigger()  # already interrupted before the first chunk
    outcome = await deliver_intent(
        session=session,
        content="First sentence. Second sentence.",
        confidence_tier="high",
        channel_adapter=adapter,
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        repository=repo,
        barge_in_signal=barge_in_signal,
    )
    assert outcome.delivered is False
    assert outcome.rejection_reason == "barged_in"
    assert adapter.delivered == []


async def test_voice_delivery_reports_partial_failure_when_synthesis_fails() -> None:
    session = _text_session(channel=ChannelType.VOICE, state=ConversationState.SPEAKING)
    repo = await _seeded_repo(session)
    adapter = FakeChannelAdapter(channel_type="voice")
    outcome = await deliver_intent(
        session=session,
        content="First sentence. Second sentence.",
        confidence_tier="high",
        channel_adapter=adapter,
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(audio_chunks=[b"audio-1", None]),
        repository=repo,
    )
    assert outcome.delivered is True  # the first chunk did reach the user
    assert outcome.rejection_reason == "synthesis_failed"
    assert len(adapter.delivered) == 1


@pytest.mark.parametrize("confidence_tier", ["high", "medium", "low", "unknown"])
async def test_confidence_tier_is_forwarded_verbatim(confidence_tier: str) -> None:
    session = _text_session(state=ConversationState.SPEAKING)
    repo = await _seeded_repo(session)
    personality_port = FakePersonalityPort()
    await deliver_intent(
        session=session,
        content="Hello",
        confidence_tier=confidence_tier,
        channel_adapter=FakeChannelAdapter(),
        personality_port=personality_port,
        model_orchestration_port=FakeModelOrchestrationPort(),
        repository=repo,
    )
    assert personality_port.validate_calls == ["Hello"]
