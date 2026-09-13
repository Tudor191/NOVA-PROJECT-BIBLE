"""Autonomy Level semantics, and **negative controls 1 and 2** (TDD §16).

Control 1 -- *forcing `execute` at Level 1 must fail the suite*.
Control 2 -- *making Level 2 selectable must fail the suite*.

Both are written so that the property, not the test, is what holds them: each
asserts against `SELECTABLE_LEVELS` / `permits_execution` directly, so removing
the property breaks the test rather than the test needing to be remembered.
"""

from __future__ import annotations

import pytest
from nova_autonomy_engine.domain.levels import (
    LevelNotDefinedError,
    LevelNotSelectableError,
    level_name,
    parse_level,
    permits_execution,
    permits_proposal,
    require_selectable,
)
from nova_autonomy_engine.domain.models import (
    AUTONOMY_LEVEL_NAMES,
    DEFINED_LEVELS,
    SELECTABLE_LEVELS,
    AutonomyLevel,
)


def test_all_six_bible_levels_are_named() -> None:
    """docs/bible/part-14-autonomy-engine.md "AUTONOMY LEVELS", verbatim."""
    assert [(int(level), AUTONOMY_LEVEL_NAMES[level]) for level in AutonomyLevel] == [
        (0, "Observation Only"),
        (1, "Suggestive"),
        (2, "Assisted"),
        (3, "Supervised"),
        (4, "Highly Autonomous"),
        (5, "Full Organizational Autonomy"),
    ]


def test_levels_zero_to_two_are_defined_and_three_to_five_are_not() -> None:
    assert {
        AutonomyLevel.OBSERVATION_ONLY,
        AutonomyLevel.SUGGESTIVE,
        AutonomyLevel.ASSISTED,
    } == DEFINED_LEVELS


# --- Negative control 2 ------------------------------------------------------
def test_control_2_only_levels_zero_and_one_are_selectable() -> None:
    """**Negative control 2.** Adding Level 2 to `SELECTABLE_LEVELS` fails
    here. Decision D-1 assigns enabling it to milestone 4F."""
    assert {AutonomyLevel.OBSERVATION_ONLY, AutonomyLevel.SUGGESTIVE} == SELECTABLE_LEVELS
    assert AutonomyLevel.ASSISTED not in SELECTABLE_LEVELS


def test_control_2_selectable_is_a_strict_subset_of_defined() -> None:
    """"Defined" and "enabled" must stay different ideas -- collapsing the two
    sets is exactly what D-1 turns on."""
    assert SELECTABLE_LEVELS < DEFINED_LEVELS


def test_require_selectable_accepts_zero_and_one() -> None:
    for level in (AutonomyLevel.OBSERVATION_ONLY, AutonomyLevel.SUGGESTIVE):
        assert require_selectable(level) is level


def test_require_selectable_rejects_level_two_as_defined_but_disabled() -> None:
    """TDD §13: *"Level set to 2-5 -> 422 with the reason. Not silently
    clamped."* The reason must say Level 2 is real and arrives in 4F."""
    with pytest.raises(LevelNotSelectableError) as excinfo:
        require_selectable(AutonomyLevel.ASSISTED)
    message = str(excinfo.value)
    assert "defined" in message
    assert "4F" in message
    assert "D-1" in message


@pytest.mark.parametrize(
    "level",
    [AutonomyLevel.SUPERVISED, AutonomyLevel.HIGHLY_AUTONOMOUS, AutonomyLevel.FULL_ORGANIZATIONAL],
)
def test_require_selectable_rejects_undefined_levels_with_a_different_reason(
    level: AutonomyLevel,
) -> None:
    """Levels 3-5 are named only. "Level 2 arrives in 4F" and "Level 4 has no
    semantics" are different answers and must not share wording."""
    with pytest.raises(LevelNotSelectableError) as excinfo:
        require_selectable(level)
    assert "no defined semantics" in str(excinfo.value)


def test_parse_level_rejects_an_integer_that_is_not_a_level() -> None:
    with pytest.raises(LevelNotDefinedError):
        parse_level(6)
    with pytest.raises(LevelNotDefinedError):
        parse_level(-1)


def test_parse_level_accepts_every_defined_integer() -> None:
    for level in AutonomyLevel:
        assert parse_level(int(level)) is level


def test_level_zero_never_proposes_and_level_one_does() -> None:
    """Bible Part 14: Level 0 *"NOVA never acts. Only monitors and reports."*;
    Level 1 *"NOVA proposes actions."*"""
    assert permits_proposal(AutonomyLevel.OBSERVATION_ONLY) is False
    assert permits_proposal(AutonomyLevel.SUGGESTIVE) is True
    assert permits_proposal(AutonomyLevel.ASSISTED) is True


# --- Negative control 1 ------------------------------------------------------
@pytest.mark.parametrize("level", list(AutonomyLevel))
def test_control_1_no_level_permits_execution(level: AutonomyLevel) -> None:
    """**Negative control 1.** No level -- selectable, merely defined, or named
    only -- permits unattended execution in this release. Making
    `permits_execution` return `True` anywhere fails here, and again in
    `test_decision_pipeline.py` where the pipeline raises on it."""
    assert permits_execution(level) is False


def test_level_name_is_the_bibles_wording() -> None:
    assert level_name(AutonomyLevel.OBSERVATION_ONLY) == "Observation Only"
    assert level_name(AutonomyLevel.ASSISTED) == "Assisted"
