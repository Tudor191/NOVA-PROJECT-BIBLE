"""Every subject digital-twin-engine is permitted to subscribe to --
docs/design/phase-2d/06-personal-companion.md Sec7.1 and TDD 4E Sec8.1.

`digital_twin.preferences.get.request` is here, not `published.py`:
`BoundEventBus.serve()` checks the *subscribable* allow-list, matching
`subscribe()`'s own convention (the same reason every prior engine's own
served RPCs live here, e.g. personality-engine's `personality.style.
select.request`).

**Phase 4E adds three, and registers none.** All three already exist in
`nova-contracts` with real publishers that have been shipping since Phase 1 and
2D-B; 4E is a **new consumer of existing contracts**, which is exactly the
relationship D-4D-1's governing principle requires -- *do not introduce an Event
Bus contract without a genuine producer/consumer need*.

They are also the **only** way this engine reads another (TDD 4E Sec0.1.5):
ADR-004 forbids a raw HTTP call from one engine into another, so the HTTP read
the TDD originally drew was withdrawn and these subscriptions carry the whole
load.

* `memory.long_term.created` -- published by `memory-engine`. Serves Personal
  Workflow, Projects, Knowledge Profile, Skill Profile and Learning Progress.
* `memory.decision.recorded` -- published by `memory-engine`. Serves Goals.
* `perception.attention.observed` -- published by `perception-engine`. Serves
  Productivity Patterns, subject to Sec5.1's producer limitation.

`PUBLISHABLE_SUBJECTS` is untouched: 4E publishes nothing new, and
`ws-gateway`'s `PUBLIC_TOPICS` stays byte-identical at its 18 strings
(TDD 4E Sec8.2, Sec8.3).
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "communication.session.completed",
        "digital_twin.preferences.get.request",
        # Phase 4E (TDD 4E Sec8.1). Existing subjects, existing publishers.
        "memory.long_term.created",
        "memory.decision.recorded",
        "perception.attention.observed",
    }
)
