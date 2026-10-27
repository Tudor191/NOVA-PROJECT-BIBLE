"""Every subject Autonomy Engine is permitted to publish. See ADR-004
(docs/architecture/00-overview-and-decisions.md).

**`action.execute` is the only entry, and that is the security property.**

4D shipped this set empty, and TDD 4D §16 control 8 asserted the stronger
claim that *"this engine never calls the bus at all"*. 4F.5 necessarily retires
that control, because Autonomy Level 2 has to reach `action-engine` somehow.
TDD 4F §11.2 anticipated and authorised the retirement -- *"Disclosed, not
silent"* -- and replaced it with the tighter property TDD 4F §16 control 6
states: **this engine may publish `action.execute` and nothing else.**

That replacement is enforced here rather than merely documented.
`BoundEventBus` raises `SubjectNotAllowedError` for any subject outside this
frozenset, on `publish()` and `request()` alike, so widening the surface
requires editing this file -- which is what
`tests/unit/test_event_boundaries.py` asserts against.

**No new subject is registered.** `action.execute` is an existing contract
(`nova_contracts.events.action`) that `action-engine` has served since Phase 3D
with no production publisher; 4F.5 supplies the first one. The registered
subject count is unchanged at 119, and `PUBLIC_TOPICS` is unchanged at 18 --
this subject is internal and is never browser-reachable.

`SUBSCRIBABLE_SUBJECTS` stays **empty**: this engine consumes nothing from the
bus.

*(Phase 4F.6 note: that last sentence is no longer true. 4F.6 makes this engine
the one consumer of the internal `autonomy.decision.requested` trigger --
see `events/subscribed.py`. **This set is unchanged by 4F.6:** `action.execute`
is still the only subject this engine may publish, and the registry went to
120 for the trigger alone. The sentence is preserved above per protocol
§0.3.4.)*
"""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "action.execute",
    }
)
