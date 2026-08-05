"""`domain.modes.resolve_mode_and_level`'s "Understand intent" heuristic
(docs/design/phase-2b/00-reasoning-engine.md §4, §6) exercised directly,
branch by branch -- every other test in this suite reaches the pipeline via
an explicit `reasoning_mode_hint`, which short-circuits this heuristic
entirely (line 70-71), leaving its structural fallback logic otherwise
unexercised.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from nova_reasoning_engine.domain import modes
from nova_reasoning_engine.domain.models import Constraint, Goal, ReasoningMode


def test_explicit_hint_short_circuits_the_heuristic_entirely() -> None:
    # Even a hard constraint + goals + a low level all present -- the hint still wins.
    mode, level = modes.resolve_mode_and_level(
        reasoning_mode_hint=ReasoningMode.REFLECTIVE,
        reasoning_level_hint=1,
        goals=[Goal(id=uuid4(), description="ship it", priority=0.9)],
        constraints=[Constraint(kind="budget", description="under $10", hard=True)],
    )
    assert (mode, level) == (ReasoningMode.REFLECTIVE, 1)


def test_reasoning_level_hint_defaults_to_two_when_absent() -> None:
    _mode, level = modes.resolve_mode_and_level(
        reasoning_mode_hint=None, reasoning_level_hint=None, goals=[], constraints=[]
    )
    assert level == 2


def test_a_hard_constraint_selects_constraint_based_regardless_of_level() -> None:
    mode, _level = modes.resolve_mode_and_level(
        reasoning_mode_hint=None,
        reasoning_level_hint=4,
        goals=[],
        constraints=[Constraint(kind="budget", description="under $10", hard=True)],
    )
    assert mode is ReasoningMode.CONSTRAINT_BASED


def test_a_soft_constraint_alone_does_not_select_constraint_based() -> None:
    mode, _level = modes.resolve_mode_and_level(
        reasoning_mode_hint=None,
        reasoning_level_hint=2,
        goals=[],
        constraints=[Constraint(kind="policy", description="prefer local", hard=False)],
    )
    assert mode is ReasoningMode.ANALYTICAL


def test_level_one_or_below_selects_reactive() -> None:
    mode, _level = modes.resolve_mode_and_level(
        reasoning_mode_hint=None, reasoning_level_hint=1, goals=[], constraints=[]
    )
    assert mode is ReasoningMode.REACTIVE


def test_goals_at_level_three_or_above_select_goal_driven() -> None:
    mode, _level = modes.resolve_mode_and_level(
        reasoning_mode_hint=None,
        reasoning_level_hint=3,
        goals=[Goal(id=uuid4(), description="ship it", priority=0.9)],
        constraints=[],
    )
    assert mode is ReasoningMode.GOAL_DRIVEN


def test_goals_at_level_two_do_not_select_goal_driven() -> None:
    # §6: Goal-driven mode is reserved for level >= 3 -- a level-2 request with
    # goals still resolves to Analytical.
    mode, _level = modes.resolve_mode_and_level(
        reasoning_mode_hint=None,
        reasoning_level_hint=2,
        goals=[Goal(id=uuid4(), description="ship it", priority=0.9)],
        constraints=[],
    )
    assert mode is ReasoningMode.ANALYTICAL


def test_level_two_without_goals_selects_analytical() -> None:
    mode, _level = modes.resolve_mode_and_level(
        reasoning_mode_hint=None, reasoning_level_hint=2, goals=[], constraints=[]
    )
    assert mode is ReasoningMode.ANALYTICAL


def test_level_three_without_goals_selects_strategic() -> None:
    mode, _level = modes.resolve_mode_and_level(
        reasoning_mode_hint=None, reasoning_level_hint=3, goals=[], constraints=[]
    )
    assert mode is ReasoningMode.STRATEGIC


def test_level_four_and_above_selects_multi_step() -> None:
    mode, _level = modes.resolve_mode_and_level(
        reasoning_mode_hint=None, reasoning_level_hint=4, goals=[], constraints=[]
    )
    assert mode is ReasoningMode.MULTI_STEP


def test_config_for_raises_for_collaborative_mode() -> None:
    with pytest.raises(modes.NotImplementedModeError):
        modes.config_for(ReasoningMode.COLLABORATIVE)


def test_config_for_returns_a_config_for_every_other_mode() -> None:
    for mode in ReasoningMode:
        if mode is ReasoningMode.COLLABORATIVE:
            continue
        assert modes.config_for(mode).mode is mode
