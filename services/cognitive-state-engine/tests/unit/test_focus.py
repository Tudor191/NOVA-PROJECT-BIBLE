"""The Focus System -- Part 6:139-163.

The property that matters most is that the cap **actually excludes something**:
*"The Focus System prevents unnecessary computation"* is only true if it does.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from nova_cognitive_state_engine.domain.focus import combine_signals, select_focus
from nova_cognitive_state_engine.domain.models import (
    FOCUSABLE_LAYERS,
    ActiveThought,
    AttentionLayer,
    FocusInputs,
    FocusSignal,
)

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


def _thought(
    *,
    priority: int,
    layer: AttentionLayer = AttentionLayer.ACTIVE,
    thought_id: UUID | None = None,
) -> ActiveThought:
    # Progress is 0.0 for an archived thought: the model forbids archiving
    # something at partial progress, and a helper that quietly violated the
    # invariant would be testing a shape the system cannot produce.
    progress = 0.0 if layer is AttentionLayer.ARCHIVED else 0.1
    return ActiveThought(
        thought_id=thought_id or uuid4(),
        user_id=uuid4(),
        description="Monitor Docker containers.",
        priority=priority,
        confidence=0.6,
        current_progress=progress,
        attention_layer=layer,
        created_at=NOW,
        updated_at=NOW,
    )


def test_the_seven_signals_are_part_6s_own() -> None:
    """Part 6:147-161 lists seven factors focus *"changes dynamically according
    to"*. Exactly those, no more."""
    assert {signal.value for signal in FocusSignal} == {
        "user_activity",
        "task_importance",
        "deadlines",
        "system_health",
        "current_risks",
        "agent_workload",
        "learning_opportunities",
    }


def test_capacity_actually_excludes() -> None:
    thoughts = [_thought(priority=p) for p in range(10)]
    focused = select_focus(thoughts, capacity=3)
    assert len(focused) == 3
    assert [entry.thought.priority for entry in focused] == [9, 8, 7]


def test_capacity_zero_focuses_on_nothing() -> None:
    assert select_focus([_thought(priority=5)], capacity=0) == []


def test_negative_capacity_is_a_caller_bug_not_an_empty_focus() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        select_focus([], capacity=-1)


@pytest.mark.parametrize(
    "layer",
    [AttentionLayer.PASSIVE, AttentionLayer.DORMANT, AttentionLayer.ARCHIVED],
)
def test_non_focusable_layers_are_never_candidates(layer: AttentionLayer) -> None:
    """Part 6 defines these three as background, stored-for-later and
    historical. None is a description of something receiving *maximum*
    attention."""
    focused = select_focus([_thought(priority=99, layer=layer)], capacity=5)
    assert focused == []


def test_focusable_layers_are_an_allow_list() -> None:
    """A layer added later is excluded by default -- the fail-closed shape 4E
    used for privacy levels."""
    assert frozenset({AttentionLayer.IMMEDIATE, AttentionLayer.ACTIVE}) == FOCUSABLE_LAYERS


def test_absent_signals_are_not_counted_as_zero() -> None:
    """A missing signal and a genuinely-zero signal are different claims.
    Counting absence as `0.0` would drag every score to the floor -- the
    failure mode CF-10's trust input avoids by reporting unavailable."""
    multiplier, signals = combine_signals(FocusInputs(task_importance=1.0))
    assert multiplier == 1.0
    assert signals == (FocusSignal.TASK_IMPORTANCE,)


def test_no_signals_falls_back_to_priority_not_to_zero() -> None:
    multiplier, signals = combine_signals(FocusInputs())
    assert multiplier == 1.0
    assert signals == ()

    thoughts = [_thought(priority=1), _thought(priority=8)]
    focused = select_focus(thoughts, capacity=1)
    assert focused[0].thought.priority == 8
    assert focused[0].signals_used == ()


def test_a_genuinely_zero_signal_does_suppress() -> None:
    """The distinction is only meaningful if a real zero behaves differently
    from an absent one."""
    multiplier, signals = combine_signals(FocusInputs(system_health=0.0))
    assert multiplier == 0.0
    assert signals == (FocusSignal.SYSTEM_HEALTH,)


def test_signals_are_weighted_equally_and_the_mean_is_over_supplied_only() -> None:
    """Part 6 assigns no weights, so neither does the implementation. Two
    signals at 1.0 and 0.0 average to 0.5 -- not 2/7."""
    multiplier, signals = combine_signals(
        FocusInputs(user_activity=1.0, agent_workload=0.0)
    )
    assert multiplier == 0.5
    assert len(signals) == 2


def test_ordering_is_total_so_the_focus_set_does_not_flicker() -> None:
    """Equal priorities must still produce a deterministic order, or the panel
    reorders itself on every read. 4E's keyset lesson: a tie needs an explicit
    tiebreaker."""
    low = UUID("00000000-0000-0000-0000-0000000000aa")
    high = UUID("00000000-0000-0000-0000-0000000000bb")
    tied = [_thought(priority=4, thought_id=high), _thought(priority=4, thought_id=low)]

    first = [entry.thought.thought_id for entry in select_focus(tied, capacity=2)]
    second = [entry.thought.thought_id for entry in select_focus(list(reversed(tied)), capacity=2)]
    assert first == second


def test_the_focus_entry_carries_why_it_is_there() -> None:
    focused = select_focus(
        [_thought(priority=3)], capacity=1, inputs=FocusInputs(deadlines=0.5)
    )
    assert focused[0].score == pytest.approx(1.5)
    assert focused[0].signals_used == (FocusSignal.DEADLINES,)
