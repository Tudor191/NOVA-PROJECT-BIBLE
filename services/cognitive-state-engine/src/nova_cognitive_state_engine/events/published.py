"""Every subject Cognitive State Engine is permitted to publish. See ADR-004
(docs/architecture/00-overview-and-decisions.md).

**Empty, and deliberately so -- in 4F.1 and beyond.**

TDD 4F §11.3 (ratified decision **D-4F-6**): this engine publishes **no Event
Bus subject at all**. A cognitive-state subject was considered and declined --
`PUBLIC_TOPICS` is `ws-gateway`'s sole browser allow-list, so a realtime panel
would need a *public* subject, and the panel reads normalized state over REST
instead (§12). D-4D-1's rule governs: a subject exists to be consumed, not to be
complete, and no non-UI consumer of cognitive state exists.

**This emptiness also carries a security property.** TDD 4F §6.2 forbids this
engine from publishing `action.execute`. An empty publish allow-list is the
structural half of that prohibition: `BoundEventBus.publish()` checks this set,
so there is no subject at which an execution request could be emitted even if
some future edit tried. §16 control 11 is the test half.

The initiative trigger this engine gains in **4F.6** is a `DecisionRequest`
handed to `autonomy-engine`, which is the control plane -- not an event
published here.
"""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset()
