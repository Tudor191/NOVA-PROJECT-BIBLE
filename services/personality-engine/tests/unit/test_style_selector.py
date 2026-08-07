"""`domain.style_selector.select_style` (docs/design/phase-2d/
02-personality-engine.md Sec5) -- every context-hint mapping, the no-hint
default, and that `verbosity`/`technical_depth` always come from the current
`MemoryProfile`, never a hardcoded value."""

from __future__ import annotations

import pytest
from nova_personality_engine.domain.models import CommunicationStyle, MemoryProfile
from nova_personality_engine.domain.style_selector import select_style

_PROFILE = MemoryProfile(verbosity="concise", technical_depth="deep")


@pytest.mark.parametrize(
    ("situation_hint", "expected_style"),
    [
        ("debugging", CommunicationStyle.ANALYTICAL),
        ("learning_session", CommunicationStyle.EDUCATIONAL),
        ("emergency", CommunicationStyle.EMERGENCY),
        ("executive_meeting", CommunicationStyle.EXECUTIVE),
        ("brainstorming", CommunicationStyle.CREATIVE),
        ("quick_check", CommunicationStyle.MINIMAL),
        ("casual", CommunicationStyle.FRIENDLY),
        ("technical_review", CommunicationStyle.TECHNICAL),
    ],
)
def test_every_documented_situation_hint_maps_to_its_style(
    situation_hint: str, expected_style: CommunicationStyle
) -> None:
    style, _, _ = select_style(situation_hint=situation_hint, channel=None, memory_profile=_PROFILE)
    assert style == expected_style


def test_situation_hint_matching_is_case_insensitive() -> None:
    style, _, _ = select_style(situation_hint="DEBUGGING", channel=None, memory_profile=_PROFILE)
    assert style == CommunicationStyle.ANALYTICAL


@pytest.mark.parametrize("situation_hint", [None, "", "unrecognized_hint"])
def test_missing_or_unrecognized_hint_defaults_to_professional(situation_hint: str | None) -> None:
    style, _, _ = select_style(
        situation_hint=situation_hint, channel=None, memory_profile=_PROFILE
    )
    assert style == CommunicationStyle.PROFESSIONAL


def test_verbosity_and_technical_depth_come_from_the_memory_profile() -> None:
    _, verbosity, technical_depth = select_style(
        situation_hint="debugging", channel=None, memory_profile=_PROFILE
    )
    assert verbosity == "concise"
    assert technical_depth == "deep"


def test_channel_does_not_influence_style_selection_this_phase() -> None:
    # domain/style_selector.py: channel is accepted for forward
    # compatibility only -- no Phase 2D-A acceptance criterion depends on
    # it yet (Master Blueprint Sec13.6).
    voice_style, _, _ = select_style(
        situation_hint="debugging", channel="voice", memory_profile=_PROFILE
    )
    text_style, _, _ = select_style(
        situation_hint="debugging", channel="text", memory_profile=_PROFILE
    )
    assert voice_style == text_style == CommunicationStyle.ANALYTICAL
