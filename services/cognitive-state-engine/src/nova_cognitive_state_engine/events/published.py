"""Every subject Cognitive State Engine is permitted to publish. See ADR-004
(docs/architecture/00-overview-and-decisions.md).

**`autonomy.decision.requested` is the only entry, and that is the security
property.** Phase 4F.6, TDD 4F D-4F-9 (4F.6 §14).

This engine delivers its initiative trigger to `autonomy-engine` over one
**internal**, request/reply subject. It is never in `PUBLIC_TOPICS`, never
browser-visible and never gateway-exposed; exactly one engine serves it.

**The prohibition this set enforces is unchanged.** TDD 4F §6.2 forbids this
engine from publishing `action.execute`, and `BoundEventBus` checks this
frozenset on `publish()` and `request()` alike -- so there is still no subject
at which an execution request could be emitted. The trigger is a *request for a
decision*, and `autonomy-engine` -- the control plane -- decides. §16 control 11
is the test half, retargeted to assert this exact set.

*(Until 4F.6 this set was **empty**, and this docstring read: "Empty, and
deliberately so -- in 4F.1 and beyond. TDD 4F §11.3 (ratified decision
**D-4F-6**): this engine publishes **no Event Bus subject at all**. ... The
initiative trigger this engine gains in **4F.6** is a `DecisionRequest` handed
to `autonomy-engine`, which is the control plane -- not an event published
here." 4F.6's preparation found that statement, together with TDD 4F §11.4 and
§12, left the trigger no transport at all; D-4F-9 resolves it with this one
internal subject. **D-4F-6 still stands**: this is not a cognitive-*state*
subject and publishes no cognitive state. Preserved per protocol §0.3.4.)*
"""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset({"autonomy.decision.requested"})
