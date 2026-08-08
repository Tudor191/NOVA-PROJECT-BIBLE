"""`domain.response_shaping` (design doc Sec7/Sec8/Sec0.9) -- the
situation-hint heuristic and the `personality.style.select` degraded
fallback."""

from __future__ import annotations

from nova_communication_engine.domain.ports import StyleSelection
from nova_communication_engine.domain.response_shaping import (
    derive_situation_hint,
    resolve_response_shaping,
)

from tests.fakes.ports import FakePersonalityPort


def test_no_signals_derives_no_situation_hint() -> None:
    assert derive_situation_hint() is None


def test_repeated_corrections_derive_frustration() -> None:
    assert derive_situation_hint(recent_correction_count=2) == "frustration"


def test_repeated_clarifications_derive_frustration() -> None:
    assert derive_situation_hint(recent_clarification_count=3) == "frustration"


def test_a_single_correction_is_not_enough_to_derive_frustration() -> None:
    assert derive_situation_hint(recent_correction_count=1, recent_clarification_count=1) is None


async def test_resolve_response_shaping_returns_the_selected_style() -> None:
    port = FakePersonalityPort(
        style_selection=StyleSelection(
            style="technical", verbosity="verbose", technical_depth="deep"
        )
    )

    result = await resolve_response_shaping(
        personality_port=port, channel="voice", situation_hint="debugging"
    )

    assert result.style == "technical"
    assert result.verbosity == "verbose"
    assert result.technical_depth == "deep"
    assert result.situation_hint == "debugging"
    assert result.degraded is False
    assert port.select_style_calls == [("debugging", "voice")]


async def test_resolve_response_shaping_degrades_on_timeout_never_raises() -> None:
    port = FakePersonalityPort(raise_style_timeout=True)

    result = await resolve_response_shaping(
        personality_port=port, channel="text", situation_hint=None
    )

    assert result.degraded is True
    assert result.style == "professional"
    assert result.verbosity == "moderate"
    assert result.technical_depth == "moderate"
