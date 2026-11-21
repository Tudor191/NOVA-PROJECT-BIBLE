"""Attention Layer movement -- Part 6 line 189's *"Thoughts move naturally
between layers."*"""

from __future__ import annotations

import pytest
from nova_cognitive_state_engine.domain.attention import next_layer
from nova_cognitive_state_engine.domain.models import ATTENTION_LAYER_ORDER, AttentionLayer


def test_the_five_layers_are_part_6s_own_in_part_6s_own_order() -> None:
    """Part 6:165-189 names Immediate, Active, Passive, Dormant, Archived, in
    that order. Neither the set nor the order is this implementation's to
    choose."""
    assert ATTENTION_LAYER_ORDER == (
        AttentionLayer.IMMEDIATE,
        AttentionLayer.ACTIVE,
        AttentionLayer.PASSIVE,
        AttentionLayer.DORMANT,
        AttentionLayer.ARCHIVED,
    )
    assert len(set(AttentionLayer)) == 5


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        (AttentionLayer.ARCHIVED, AttentionLayer.DORMANT),
        (AttentionLayer.DORMANT, AttentionLayer.PASSIVE),
        (AttentionLayer.PASSIVE, AttentionLayer.ACTIVE),
        (AttentionLayer.ACTIVE, AttentionLayer.IMMEDIATE),
    ],
)
def test_promote_moves_one_step_toward_immediate(
    start: AttentionLayer, expected: AttentionLayer
) -> None:
    assert next_layer(start, "promote") is expected


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        (AttentionLayer.IMMEDIATE, AttentionLayer.ACTIVE),
        (AttentionLayer.ACTIVE, AttentionLayer.PASSIVE),
        (AttentionLayer.PASSIVE, AttentionLayer.DORMANT),
        (AttentionLayer.DORMANT, AttentionLayer.ARCHIVED),
    ],
)
def test_demote_moves_one_step_toward_archived(
    start: AttentionLayer, expected: AttentionLayer
) -> None:
    assert next_layer(start, "demote") is expected


def test_promoting_the_top_is_undefined_not_clamped() -> None:
    """`None` rather than `IMMEDIATE`: clamping would make "already at the top"
    and "moved to the top" indistinguishable to the caller."""
    assert next_layer(AttentionLayer.IMMEDIATE, "promote") is None


def test_demoting_the_bottom_is_undefined_not_clamped() -> None:
    assert next_layer(AttentionLayer.ARCHIVED, "demote") is None


def test_no_transition_skips_a_layer() -> None:
    """Adjacent-only is the whole of what Part 6's *"move naturally between
    layers"* supports. A jump straight to `IMMEDIATE` is **not** built: nothing
    in 4F produces an interrupt yet, and 4F.1 adds no abstraction for later
    work."""
    for start in AttentionLayer:
        for action in ("promote", "demote"):
            result = next_layer(start, action)  # type: ignore[arg-type]
            if result is None:
                continue
            distance = abs(
                ATTENTION_LAYER_ORDER.index(result) - ATTENTION_LAYER_ORDER.index(start)
            )
            assert distance == 1, f"{start} -{action}-> {result} skipped a layer"


def test_promote_and_demote_are_inverse_where_both_are_defined() -> None:
    for start in AttentionLayer:
        promoted = next_layer(start, "promote")
        if promoted is not None:
            assert next_layer(promoted, "demote") is start
