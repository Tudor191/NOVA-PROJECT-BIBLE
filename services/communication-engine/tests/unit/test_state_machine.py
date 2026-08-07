"""`domain.state_machine.transition` (docs/design/phase-2d/
01-communication-engine.md Sec3.1) -- every documented edge, the two
implementation clarifications the module's own docstring names, and that
undocumented (state, event) pairs raise rather than silently no-op."""

from __future__ import annotations

import pytest
from nova_communication_engine.domain.models import ConversationState
from nova_communication_engine.domain.state_machine import (
    ConversationEvent,
    InvalidTransitionError,
    transition,
    valid_events_from,
)


@pytest.mark.parametrize(
    ("current", "event", "expected"),
    [
        (ConversationState.IDLE, ConversationEvent.TRIGGER, ConversationState.LISTENING),
        (ConversationState.WAITING, ConversationEvent.TRIGGER, ConversationState.LISTENING),
        (ConversationState.LISTENING, ConversationEvent.CAPTURED, ConversationState.THINKING),
        (ConversationState.THINKING, ConversationEvent.CONTENT_READY, ConversationState.SPEAKING),
        (ConversationState.SPEAKING, ConversationEvent.DELIVERED, ConversationState.WAITING),
        (ConversationState.SPEAKING, ConversationEvent.BARGE_IN, ConversationState.LISTENING),
        (ConversationState.WAITING, ConversationEvent.CLOSE, ConversationState.COMPLETED),
        (ConversationState.LISTENING, ConversationEvent.PAUSE, ConversationState.PAUSED),
        (ConversationState.THINKING, ConversationEvent.PAUSE, ConversationState.PAUSED),
        (ConversationState.SPEAKING, ConversationEvent.PAUSE, ConversationState.PAUSED),
        (ConversationState.WAITING, ConversationEvent.PAUSE, ConversationState.PAUSED),
        (ConversationState.PAUSED, ConversationEvent.RESUME, ConversationState.LISTENING),
    ],
)
def test_every_documented_transition(
    current: ConversationState, event: ConversationEvent, expected: ConversationState
) -> None:
    assert transition(current, event) is expected


@pytest.mark.parametrize(
    ("current", "event"),
    [
        (ConversationState.IDLE, ConversationEvent.CAPTURED),
        (ConversationState.IDLE, ConversationEvent.PAUSE),
        (ConversationState.COMPLETED, ConversationEvent.TRIGGER),
        (ConversationState.LISTENING, ConversationEvent.DELIVERED),
        (ConversationState.WAITING, ConversationEvent.BARGE_IN),
        (ConversationState.PAUSED, ConversationEvent.PAUSE),
        (ConversationState.LISTENING, ConversationEvent.RESUME),
    ],
)
def test_undocumented_transitions_raise(
    current: ConversationState, event: ConversationEvent
) -> None:
    with pytest.raises(InvalidTransitionError):
        transition(current, event)


def test_completed_is_terminal() -> None:
    assert valid_events_from(ConversationState.COMPLETED) == frozenset()


def test_valid_events_from_waiting_includes_trigger_close_and_pause() -> None:
    events = valid_events_from(ConversationState.WAITING)
    assert events == frozenset(
        {ConversationEvent.TRIGGER, ConversationEvent.CLOSE, ConversationEvent.PAUSE}
    )
