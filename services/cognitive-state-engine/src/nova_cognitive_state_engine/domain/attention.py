"""Attention Layer movement -- Part 6 line 189: *"Thoughts move naturally
between layers."*

**A transition table, not a set of `if`s**, following `perception-engine`'s own
`domain/sensor.py::next_state` precedent exactly: every legal `(layer, action)`
pair is data, every other pair returns `None`, and `None` means *no defined
transition*, which callers treat as a no-op rather than an error. That
convention is already established twice in this repository -- the Sensor
Abstraction Layer and World Model's `state_management` -- and a third
divergent spelling would be the drift.

**Adjacent moves only, and why.** Part 6 says thoughts move *"naturally"*
between layers and gives the five layers a clear ordering, from *"critical
events requiring instant action"* down to *"historical information no longer
requiring active processing"*. Adjacent promotion and demotion is the whole of
what that sentence supports. Part 6's INTERRUPTIONS section (line 331) plausibly
implies a jump straight to `IMMEDIATE`, and this module deliberately **does not
build one**: nothing in 4F produces an interrupt yet, and TDD 4F's scope rule is
that 4F.1 adds no abstraction for later work. When a real producer needs
escalation it will arrive with a caller that justifies its rules, rather than as
a guess made in advance.
"""

from __future__ import annotations

from typing import Literal

from nova_cognitive_state_engine.domain.models import ATTENTION_LAYER_ORDER, AttentionLayer

__all__ = ["AttentionAction", "next_layer"]

AttentionAction = Literal["promote", "demote"]
"""`promote` moves one step toward `IMMEDIATE`; `demote` one step toward
`ARCHIVED`. Two verbs rather than a target layer, so a caller cannot ask for a
jump the ladder does not define."""


def _build_transitions() -> dict[tuple[AttentionLayer, AttentionAction], AttentionLayer]:
    transitions: dict[tuple[AttentionLayer, AttentionAction], AttentionLayer] = {}
    for index, layer in enumerate(ATTENTION_LAYER_ORDER):
        if index > 0:
            transitions[(layer, "promote")] = ATTENTION_LAYER_ORDER[index - 1]
        if index < len(ATTENTION_LAYER_ORDER) - 1:
            transitions[(layer, "demote")] = ATTENTION_LAYER_ORDER[index + 1]
    return transitions


_TRANSITIONS: dict[tuple[AttentionLayer, AttentionAction], AttentionLayer] = _build_transitions()
"""Derived from `ATTENTION_LAYER_ORDER` rather than written out, so the ladder
has exactly one definition. Promoting `IMMEDIATE` and demoting `ARCHIVED` are
absent by construction -- there is nowhere further to go in either direction --
which is why they return `None` rather than silently clamping."""


def next_layer(current: AttentionLayer, action: AttentionAction) -> AttentionLayer | None:
    """Pure. The resulting layer, or `None` if `(current, action)` is not a
    defined transition.

    `None` at the ends of the ladder is the point: a caller that promotes an
    already-`IMMEDIATE` thought learns that nothing happened, instead of the
    call appearing to succeed. Clamping would make "already at the top" and
    "moved to the top" indistinguishable.
    """
    return _TRANSITIONS.get((current, action))
