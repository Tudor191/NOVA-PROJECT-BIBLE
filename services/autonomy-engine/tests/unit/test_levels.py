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
def test_control_2_only_levels_zero_one_and_two_are_selectable() -> None:
    """**Negative control 2, retargeted by 4F.5.** Adding Level 3, 4 or 5 to
    `SELECTABLE_LEVELS` fails here.

    *(4D asserted `{OBSERVATION_ONLY, SUGGESTIVE} == SELECTABLE_LEVELS` and
    `ASSISTED not in SELECTABLE_LEVELS`, because D-1 deferred enabling Level 2
    to milestone 4F. 4F.5 is that milestone. The control is not weakened --
    it still pins the exact set, and the levels with no defined semantics are
    still refused.)*

    **Selecting Level 2 is not permission to execute.** That separation is
    `test_control_1_eligibility_is_not_permission` below."""
    assert {
        AutonomyLevel.OBSERVATION_ONLY,
        AutonomyLevel.SUGGESTIVE,
        AutonomyLevel.ASSISTED,
    } == SELECTABLE_LEVELS
    for undefined in (
        AutonomyLevel.SUPERVISED,
        AutonomyLevel.HIGHLY_AUTONOMOUS,
        AutonomyLevel.FULL_ORGANIZATIONAL,
    ):
        assert undefined not in SELECTABLE_LEVELS


def test_control_2_selectable_never_exceeds_defined() -> None:
    """A level can never be *selectable* without being *defined*.

    *(4D asserted the stronger `SELECTABLE_LEVELS < DEFINED_LEVELS`, a strict
    subset, because Level 2 was defined and disabled. 4F.5 enabled it, so the
    two sets now coincide. The invariant that survives -- and the dangerous
    direction -- is that selectable may never grow beyond defined; a level with
    no semantics must never become choosable.)*

    They remain two separate constants, so a future level can be defined
    without being enabled, which is the distinction D-1 turned on."""
    assert SELECTABLE_LEVELS <= DEFINED_LEVELS


def test_require_selectable_accepts_zero_and_one() -> None:
    for level in (AutonomyLevel.OBSERVATION_ONLY, AutonomyLevel.SUGGESTIVE):
        assert require_selectable(level) is level


def test_require_selectable_accepts_level_two_since_4f5() -> None:
    """4F.5 enabled Level 2, so `require_selectable` returns it unchanged.

    *(4D asserted this raised `LevelNotSelectableError` with a reason naming
    "defined", "4F" and "D-1" -- Level 2 was real but not yet enabled. It is
    enabled now; the 422 path for Levels 3-5 is asserted immediately below and
    is unchanged.)*"""
    assert require_selectable(AutonomyLevel.ASSISTED) is AutonomyLevel.ASSISTED


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
def test_control_1_execution_eligibility_starts_at_level_two(level: AutonomyLevel) -> None:
    """**Negative control 1, retargeted by 4F.5 (D-4F5-4).**

    *(4D asserted `permits_execution(level) is False` for **every** level --
    "no level, selectable, merely defined, or named only, permits unattended
    execution in this release". D-1 deferred Level 2 to 4F; 4F.5 enabled it.)*

    **Eligibility, not permission.** Lowering the boundary below `ASSISTED`
    fails here, and `test_control_1_eligibility_is_not_permission` asserts that
    a `True` here authorizes nothing on its own."""
    assert permits_execution(level) is (level >= AutonomyLevel.ASSISTED)


def test_level_name_is_the_bibles_wording() -> None:
    assert level_name(AutonomyLevel.OBSERVATION_ONLY) == "Observation Only"
    assert level_name(AutonomyLevel.ASSISTED) == "Assisted"
