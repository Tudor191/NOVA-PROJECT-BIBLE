"""`domain.silence_policy` (design doc Sec5.2/Sec5.3) --
`should_suppress_proactive_notification`'s dnd/active-session gating."""

from __future__ import annotations

from uuid import uuid4

import pytest
from nova_communication_engine.domain.models import (
    ChannelType,
    ConversationSession,
    ConversationState,
)
from nova_communication_engine.domain.silence_policy import (
    should_suppress_proactive_notification,
)


def _session(**overrides: object) -> ConversationSession:
    defaults: dict[str, object] = dict(
        user_id=uuid4(), channel=ChannelType.VOICE, device_id=uuid4()
    )
    defaults.update(overrides)
    return ConversationSession(**defaults)  # type: ignore[arg-type]


def test_no_session_context_is_never_suppressed() -> None:
    assert should_suppress_proactive_notification(None) is False


def test_dnd_override_suppresses_regardless_of_state() -> None:
    session = _session(state=ConversationState.IDLE, dnd_override=True)
    assert should_suppress_proactive_notification(session) is True


@pytest.mark.parametrize(
    "state",
    [
        ConversationState.LISTENING,
        ConversationState.THINKING,
        ConversationState.SPEAKING,
        ConversationState.WAITING,
    ],
)
def test_an_active_session_suppresses_even_without_dnd(state: ConversationState) -> None:
    session = _session(state=state, dnd_override=False)
    assert should_suppress_proactive_notification(session) is True


@pytest.mark.parametrize("state", [ConversationState.IDLE, ConversationState.COMPLETED])
def test_an_idle_or_completed_session_does_not_suppress(state: ConversationState) -> None:
    session = _session(state=state, dnd_override=False)
    assert should_suppress_proactive_notification(session) is False
