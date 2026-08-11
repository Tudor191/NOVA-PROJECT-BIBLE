"""`domain.response_shaping` (design doc Sec7/Sec8/Sec0.9) -- the
situation-hint heuristic and the `personality.style.select` degraded
fallback. Phase 2D-D (docs/design/phase-2d/06-personal-companion.md Sec7.2,
Fork A) adds the optional `digital_twin_port`/`user_id` pacing/timing path,
covered separately below."""

from __future__ import annotations

from uuid import uuid4

from nova_communication_engine.domain.ports import PreferenceSelection, StyleSelection
from nova_communication_engine.domain.response_shaping import (
    derive_situation_hint,
    resolve_response_shaping,
)

from tests.fakes.ports import FakeDigitalTwinPort, FakePersonalityPort


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


async def test_no_digital_twin_port_supplied_leaves_pacing_and_timing_none() -> None:
    """The default, and every production call site as of this phase (Fork
    F/Sec7.2's own disclosed gap) -- `resolve_response_shaping` never calls
    an RPC nothing asked for."""
    port = FakePersonalityPort()

    result = await resolve_response_shaping(
        personality_port=port, channel="text", situation_hint=None
    )

    assert result.conversation_pacing is None
    assert result.habit_timing_hint is None


async def test_digital_twin_port_supplied_with_user_id_populates_pacing_and_timing() -> None:
    personality_port = FakePersonalityPort()
    digital_twin_port = FakeDigitalTwinPort(
        preferences=PreferenceSelection(
            conversation_pacing="unhurried", habit_timing_hint="evenings"
        )
    )
    user_id = uuid4()

    result = await resolve_response_shaping(
        personality_port=personality_port,
        channel="text",
        situation_hint=None,
        digital_twin_port=digital_twin_port,
        user_id=user_id,
    )

    assert result.conversation_pacing == "unhurried"
    assert result.habit_timing_hint == "evenings"
    assert digital_twin_port.get_preferences_calls == [user_id]


async def test_digital_twin_port_supplied_without_user_id_is_never_called() -> None:
    digital_twin_port = FakeDigitalTwinPort(
        preferences=PreferenceSelection(conversation_pacing="unhurried", habit_timing_hint=None)
    )

    result = await resolve_response_shaping(
        personality_port=FakePersonalityPort(),
        channel="text",
        situation_hint=None,
        digital_twin_port=digital_twin_port,
        user_id=None,
    )

    assert result.conversation_pacing is None
    assert digital_twin_port.get_preferences_calls == []


async def test_digital_twin_timeout_degrades_pacing_and_timing_without_flipping_degraded() -> None:
    digital_twin_port = FakeDigitalTwinPort(raise_timeout=True)

    result = await resolve_response_shaping(
        personality_port=FakePersonalityPort(),
        channel="text",
        situation_hint=None,
        digital_twin_port=digital_twin_port,
        user_id=uuid4(),
    )

    assert result.degraded is False
    assert result.conversation_pacing is None
    assert result.habit_timing_hint is None


async def test_digital_twin_port_with_no_stored_preferences_leaves_pacing_and_timing_none() -> None:
    """`digital-twin-engine`'s own reply carries `preferences=None` for a
    brand-new user (`domain/models.py`'s own default-profile convention) --
    distinct from a timeout, but degrades to the same observable result."""
    digital_twin_port = FakeDigitalTwinPort(preferences=None)

    result = await resolve_response_shaping(
        personality_port=FakePersonalityPort(),
        channel="text",
        situation_hint=None,
        digital_twin_port=digital_twin_port,
        user_id=uuid4(),
    )

    assert result.conversation_pacing is None
    assert result.habit_timing_hint is None
