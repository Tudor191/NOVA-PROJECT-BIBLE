"""The Focus System -- Part 6 lines 139-163.

*"Human attention is limited. NOVA should simulate intelligent focus. Only a
limited number of cognitive processes receive maximum computational attention."*

Two properties carry that sentence:

1. **A hard capacity.** `select_focus` returns at most `capacity` thoughts. The
   limit is the feature, not a tuning parameter -- *"The Focus System prevents
   unnecessary computation while improving reasoning quality"* (line 163) is
   only true if something is actually excluded.
2. **Only focusable layers are eligible.** `FOCUSABLE_LAYERS` is an allow-list
   (`models.py`); background, dormant and archived thoughts are not candidates
   for *maximum* attention by Part 6's own definitions of those layers.

**On weights, stated plainly.** Part 6 names seven signals and assigns them no
weights, no ordering and no formula. This module therefore weights them
**equally** and says so, rather than inventing a hierarchy the Bible does not
contain and presenting it as derived. Equal weighting is a placeholder that is
*visible* as one; a hand-tuned vector would look like a decision somebody made
on evidence. When real signal producers exist there will be something to tune
against -- 4F.1 has nothing, so it tunes nothing.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from nova_cognitive_state_engine.domain.models import (
    FOCUSABLE_LAYERS,
    ActiveThought,
    FocusedThought,
    FocusInputs,
    FocusSignal,
)

__all__ = ["combine_signals", "select_focus"]


def combine_signals(inputs: FocusInputs) -> tuple[float, tuple[FocusSignal, ...]]:
    """The mean of the signals that were actually supplied, and which those were.

    **Absent signals are excluded from the mean, not counted as zero.** Treating
    a missing signal as `0.0` would drag every score toward the floor and make a
    degraded input indistinguishable from a confidently low one -- the failure
    mode 4D's Trust Engine avoids by reporting unavailable rather than `0.0`
    (CF-10), and 4E's domain states avoid with machine-readable reason codes.

    With no signals supplied the multiplier is **`1.0`, not `0.0`**: no evidence
    about focus conditions means the ranking falls back to priority alone, which
    is a defensible ordering. Zero would instead claim that every thought is
    maximally unimportant, which no input said.
    """
    supplied = inputs.supplied()
    if not supplied:
        return 1.0, ()
    signals = tuple(sorted(supplied, key=lambda signal: signal.value))
    return sum(supplied.values()) / len(supplied), signals


def select_focus(
    thoughts: Iterable[ActiveThought],
    *,
    capacity: int,
    inputs: FocusInputs | None = None,
) -> Sequence[FocusedThought]:
    """The at-most-`capacity` thoughts receiving maximum attention, best first.

    Ranking is `priority * signal_multiplier`, tie-broken by `priority`, then by
    `thought_id` so the order is **total and deterministic** -- an unstable focus
    set would make the panel flicker between equally-ranked thoughts on every
    read, and 4E's keyset-pagination lesson is that ties need an explicit
    tiebreaker or the boundary is not reproducible.

    Raises on a negative capacity rather than returning an empty list: a
    negative limit is a caller bug, and silently treating it as "focus on
    nothing" would hide it. `capacity=0` is legal and means exactly what it
    says.
    """
    if capacity < 0:
        raise ValueError(f"focus capacity must not be negative; got {capacity}")

    multiplier, signals = combine_signals(inputs or FocusInputs())
    candidates = [
        FocusedThought(
            thought=thought,
            score=thought.priority * multiplier,
            signals_used=signals,
        )
        for thought in thoughts
        if thought.attention_layer in FOCUSABLE_LAYERS
    ]
    candidates.sort(
        key=lambda entry: (-entry.score, -entry.thought.priority, str(entry.thought.thought_id))
    )
    return candidates[:capacity]
