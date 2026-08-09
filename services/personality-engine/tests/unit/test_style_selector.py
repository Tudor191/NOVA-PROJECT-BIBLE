"""`domain.style_selector.select_style` (docs/design/phase-2d/
02-personality-engine.md Sec5) -- every context-hint mapping, the no-hint
default, that `verbosity`/`technical_depth` come from the current
`MemoryProfile` by default, and (Phase 2D-C Closure Priority 5,
docs/roadmap/architecture-reviews/phase-2d-c-closure-priority-5-research.md)
the one channel-based exception: `channel == "voice"` overrides `verbosity`
to a fixed "concise" value; every other channel, including `None`, leaves
`memory_profile.verbosity` untouched, and `style`/`technical_depth` are
never affected by `channel` at all."""

from __future__ import annotations

import pytest
from nova_personality_engine.domain.models import CommunicationStyle, MemoryProfile
from nova_personality_engine.domain.style_selector import select_style

_PROFILE = MemoryProfile(verbosity="concise", technical_depth="deep")
_MODERATE_PROFILE = MemoryProfile(verbosity="moderate", technical_depth="deep")
"""A profile whose verbosity is *not* already "concise" -- needed to prove
the voice override actually changes something, rather than coincidentally
matching `_PROFILE`'s own value."""


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
    style, _, _ = select_style(situation_hint=situation_hint, channel=None, memory_profile=_PROFILE)
    assert style == CommunicationStyle.PROFESSIONAL


def test_verbosity_and_technical_depth_come_from_the_memory_profile() -> None:
    _, verbosity, technical_depth = select_style(
        situation_hint="debugging", channel=None, memory_profile=_PROFILE
    )
    assert verbosity == "concise"
    assert technical_depth == "deep"


def test_voice_channel_overrides_verbosity_to_concise() -> None:
    """Priority 5, Fork B decision B1: a fixed override to the one
    already-precedented value, not a graduated scale."""
    _, verbosity, _ = select_style(
        situation_hint=None, channel="voice", memory_profile=_MODERATE_PROFILE
    )
    assert verbosity == "concise"


@pytest.mark.parametrize("channel", [None, "text", "sms", "notification", ""])
def test_non_voice_channel_preserves_the_memory_profile_verbosity(
    channel: str | None,
) -> None:
    """The approved scope ("non-voice or None") means every channel value
    other than the literal string "voice" -- not only "text" -- leaves the
    pre-existing default path completely unchanged."""
    _, verbosity, _ = select_style(
        situation_hint=None, channel=channel, memory_profile=_MODERATE_PROFILE
    )
    assert verbosity == "moderate"


def test_voice_channel_override_is_idempotent_when_the_profile_is_already_concise() -> None:
    _, verbosity, _ = select_style(situation_hint=None, channel="voice", memory_profile=_PROFILE)
    assert verbosity == "concise"


def test_channel_never_affects_style_or_technical_depth() -> None:
    """Priority 5's own explicit boundary: `channel` may vary `verbosity`
    only -- style and technical_depth stay identical across every channel
    value, even though verbosity itself now differs for "voice"."""
    results = {
        channel: select_style(
            situation_hint="debugging", channel=channel, memory_profile=_MODERATE_PROFILE
        )
        for channel in (None, "voice", "text", "sms")
    }
    styles = {style for style, _, _ in results.values()}
    technical_depths = {technical_depth for _, _, technical_depth in results.values()}
    assert styles == {CommunicationStyle.ANALYTICAL}
    assert technical_depths == {"deep"}
    # And the one dimension that *is* allowed to vary actually does, proving
    # this test would have caught a regression either way.
    assert results["voice"][1] == "concise"
    assert results["text"][1] == results["sms"][1] == results[None][1] == "moderate"
