"""Every subject Autonomy Engine is permitted to subscribe to.

**`autonomy.decision.requested` is the only entry** -- Phase 4F.6, TDD 4F.6
§19 rows 2 and 5. This engine is that subject's **exactly one** consumer, via
one `serve()` in `main.py`. `BoundEventBus` checks this frozenset on
`subscribe()`, `serve()` and `open_stream()` alike, so consuming anything else
requires editing this file -- which `tests/contract/test_autonomy_boundaries.py`
asserts against.

The subject is **internal**: never in `PUBLIC_TOPICS`, never browser-visible and
never gateway-exposed (TDD 4F D-4F-9, 4F.6 §14).

*(Until 4F.6 this set was empty, holding only the scaffold's placeholder
comment `# TODO: e.g. "perception.*.observed",`, and `events/published.py`
recorded that "`SUBSCRIBABLE_SUBJECTS` stays **empty**: this engine consumes
nothing from the bus." Preserved per protocol §0.3.4.)*
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset({"autonomy.decision.requested"})
