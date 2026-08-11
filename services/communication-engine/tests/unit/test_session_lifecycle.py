"""`domain.session_lifecycle` (docs/design/phase-2d/01-communication-engine.md
Sec6, Sec8.7, Sec11) -- create/close/pause/resume, inbound-turn recording,
and restart recovery, each asserting both the resulting state and the
outbox event enqueued for the Dashboard/Reasoning Engine."""

from __future__ import annotations

from uuid import uuid4

import pytest
from nova_communication_engine.domain import session_lifecycle
from nova_communication_engine.domain.models import (
    ChannelType,
    ConversationMemory,
    ConversationSession,
    ConversationState,
)
from nova_communication_engine.domain.ports import WorldModelSnapshot
from nova_communication_engine.domain.session_lifecycle import InvalidCloseStateError
from nova_communication_engine.domain.state_machine import InvalidTransitionError

from tests.fakes.ports import FakeWorldModelPort
from tests.fakes.repository import FakeCommunicationRepository


def _session(state: ConversationState) -> ConversationSession:
    return ConversationSession(
        user_id=uuid4(), channel=ChannelType.TEXT, device_id=uuid4(), state=state
    )


async def _seeded_repo(session: ConversationSession) -> FakeCommunicationRepository:
    repo = FakeCommunicationRepository()
    await repo.create_session(session)
    return repo


async def test_create_session_starts_idle_and_publishes_created() -> None:
    repo = FakeCommunicationRepository()
    session = await session_lifecycle.create_session(
        user_id=uuid4(),
        channel=ChannelType.TEXT,
        device_id=uuid4(),
        repository=repo,
        world_model_port=FakeWorldModelPort(),
        correlation_id=uuid4(),
    )
    assert session.state is ConversationState.IDLE
    assert [e.subject for e in repo.outbox] == ["communication.session.created"]


async def test_create_session_adopts_world_model_objective() -> None:
    repo = FakeCommunicationRepository()
    snapshot = WorldModelSnapshot(user_id=uuid4(), objective="finish the quarterly report")
    session = await session_lifecycle.create_session(
        user_id=uuid4(),
        channel=ChannelType.TEXT,
        device_id=uuid4(),
        repository=repo,
        world_model_port=FakeWorldModelPort(snapshot=snapshot),
        correlation_id=uuid4(),
    )
    assert session.objective == "finish the quarterly report"


async def test_record_inbound_turn_moves_idle_to_thinking_via_listening() -> None:
    session = _session(ConversationState.IDLE)
    repo = await _seeded_repo(session)
    updated, turn = await session_lifecycle.record_inbound_turn(
        session=session, content="Hello NOVA", repository=repo, correlation_id=uuid4()
    )
    assert updated.state is ConversationState.THINKING
    assert turn.content == "Hello NOVA"
    subjects = [e.subject for e in repo.outbox]
    assert subjects.count("communication.session.state_changed") == 2  # trigger, then captured
    assert "communication.turn.received" in subjects


async def test_record_inbound_turn_from_waiting_reuses_the_trigger_edge() -> None:
    session = _session(ConversationState.WAITING)
    repo = await _seeded_repo(session)
    updated, _turn = await session_lifecycle.record_inbound_turn(
        session=session, content="And another thing", repository=repo, correlation_id=uuid4()
    )
    assert updated.state is ConversationState.THINKING


async def test_record_inbound_turn_from_listening_skips_the_redundant_trigger() -> None:
    """Phase 2D-C Closure Priority 4 review Sec1.3: a barge-in
    (`mark_barge_in`) already moves the session `Speaking -> Listening`
    before the user's continuing speech is captured -- applying `TRIGGER`
    again here used to raise `InvalidTransitionError` (`(Listening,
    TRIGGER)` is not a defined edge), crashing the WebSocket connection on
    every utterance that followed a barge-in."""
    session = _session(ConversationState.LISTENING)
    repo = await _seeded_repo(session)
    updated, turn = await session_lifecycle.record_inbound_turn(
        session=session, content="...as I was saying", repository=repo, correlation_id=uuid4()
    )
    assert updated.state is ConversationState.THINKING
    assert turn.content == "...as I was saying"
    subjects = [e.subject for e in repo.outbox]
    assert subjects.count("communication.session.state_changed") == 1  # captured only, no trigger
    assert "communication.turn.received" in subjects


async def test_record_inbound_turn_from_thinking_still_raises() -> None:
    """Not `Idle`/`Waiting`/`Listening` -- an invalid transition genuinely
    is still an error, unchanged by the Listening-tolerant fix above."""
    session = _session(ConversationState.THINKING)
    repo = await _seeded_repo(session)
    with pytest.raises(InvalidTransitionError):
        await session_lifecycle.record_inbound_turn(
            session=session, content="stray audio", repository=repo, correlation_id=uuid4()
        )


async def test_close_session_requires_waiting_state() -> None:
    session = _session(ConversationState.THINKING)
    repo = await _seeded_repo(session)
    with pytest.raises(InvalidCloseStateError):
        await session_lifecycle.close_session(
            session=session, repository=repo, correlation_id=uuid4()
        )


async def test_close_session_from_waiting_publishes_completed_with_turn_count() -> None:
    session = _session(ConversationState.WAITING)
    repo = await _seeded_repo(session)
    updated = await session_lifecycle.close_session(
        session=session, repository=repo, correlation_id=uuid4()
    )
    assert updated.state is ConversationState.COMPLETED
    assert updated.closed_at is not None
    completed_events = [e for e in repo.outbox if e.subject == "communication.session.completed"]
    assert len(completed_events) == 1
    assert completed_events[0].payload["turn_count"] == 0


async def test_close_session_publishes_the_session_s_conversation_memory() -> None:
    """Phase 2D-D (docs/design/phase-2d/06-personal-companion.md Sec6, Fork
    B) -- the already-loaded ConversationMemory, not a fresh read; digital-
    twin-engine's own learning input."""
    session = _session(ConversationState.WAITING).model_copy(
        update={
            "conversation_memory": ConversationMemory(
                corrections=["It's Tuesday, not Wednesday."],
                preferences=["Prefers concise responses."],
                feedback=["That was helpful."],
                decisions=["Proceed with option B."],
            )
        }
    )
    repo = await _seeded_repo(session)
    await session_lifecycle.close_session(session=session, repository=repo, correlation_id=uuid4())

    completed_events = [e for e in repo.outbox if e.subject == "communication.session.completed"]
    assert len(completed_events) == 1
    payload = completed_events[0].payload
    assert payload["corrections"] == ["It's Tuesday, not Wednesday."]
    assert payload["preferences"] == ["Prefers concise responses."]
    assert payload["feedback"] == ["That was helpful."]
    assert payload["decisions"] == ["Proceed with option B."]


async def test_pause_and_resume_round_trip() -> None:
    session = _session(ConversationState.LISTENING)
    repo = await _seeded_repo(session)
    paused = await session_lifecycle.pause_session(
        session=session, repository=repo, correlation_id=uuid4()
    )
    assert paused.state is ConversationState.PAUSED
    resumed = await session_lifecycle.resume_session(
        session=paused, repository=repo, correlation_id=uuid4()
    )
    assert resumed.state is ConversationState.LISTENING


async def test_pause_from_idle_is_rejected() -> None:
    session = _session(ConversationState.IDLE)
    repo = await _seeded_repo(session)
    with pytest.raises(InvalidTransitionError):
        await session_lifecycle.pause_session(
            session=session, repository=repo, correlation_id=uuid4()
        )


async def test_recover_session_to_paused_is_idempotent_for_already_paused() -> None:
    session = _session(ConversationState.PAUSED)
    repo = await _seeded_repo(session)
    result = await session_lifecycle.recover_session_to_paused(
        session=session, repository=repo, correlation_id=uuid4()
    )
    assert result.state is ConversationState.PAUSED
    assert repo.outbox == []


@pytest.mark.parametrize(
    "state",
    [
        ConversationState.LISTENING,
        ConversationState.THINKING,
        ConversationState.SPEAKING,
        ConversationState.IDLE,
    ],
)
async def test_recover_session_to_paused_forces_paused_from_any_non_terminal_state(
    state: ConversationState,
) -> None:
    session = _session(state)
    repo = await _seeded_repo(session)
    result = await session_lifecycle.recover_session_to_paused(
        session=session, repository=repo, correlation_id=uuid4()
    )
    assert result.state is ConversationState.PAUSED
    assert [e.subject for e in repo.outbox] == ["communication.session.state_changed"]
