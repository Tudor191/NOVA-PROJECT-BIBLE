"""The 2D-D conversational-trust adapter -- and the disclosed reason it
reports the source as unavailable in this release.

TDD 4D §5.3 says the read of `digital-twin-engine`'s `TrustMetric` is *"an
Event Bus request/reply"*. **No such read is implementable in 4D**, and the
finding is recorded here rather than worked around, because working around it
would mean either faking a number or quietly breaking a ratified decision.

**Four facts, each verified against the repository, 2026-09-13:**

1. **`digital-twin-engine` serves exactly one RPC subject**,
   `digital_twin.preferences.get.request`
   (`digital_twin_engine/events/subscribed.py`). There is no
   `digital_twin.trust.*` subject anywhere in the repository.
2. **Its HTTP surface exposes no trust route either** -- `GET /preferences`,
   `GET`/`PATCH /proactive-policy`, `GET`/`PATCH /profile`, `POST /reset`.
   `TrustMetric` is reachable only through its own
   `DigitalTwinRepository.get_trust_metric`, over its own tables.
3. **`BoundEventBus.request()` checks the *publishable* allow-list**
   (`nova_eventbus_sdk/boundary.py:100`). Any request/reply read would
   therefore require `PUBLISHABLE_SUBJECTS` to be non-empty -- which ratified
   decision **D-4D-1** forbids (TDD §10 item 3: *"Both allow-lists stay
   empty"*), and which TDD §16 control 8 requires to fail the suite.
4. Closing the gap needs a served subject and a `nova_contracts` payload in
   **another engine**, which this milestone's scope explicitly excludes.

This is **structurally the same error D-4D-2 already identified and withdrew
for CF-9** -- a document clause presupposing a cross-engine surface that does
not exist. It is handled the same way: named, not built around, with the
fail-closed default preserved.

**What that means for behaviour: nothing changes.** TDD §13's first row
already binds it -- *"`digital-twin-engine` unreachable -> conversational input
`None` -> trust score `None` -> fail-closed. Panel shows 'insufficient
evidence', never a number."* This adapter is that row, and
`UNAVAILABLE` (rather than `NO_DATA`) is what keeps it from being reported as
an empty success, per TDD §16 control 12.

**This is not a stub.** `ConversationalTrustSource` is a real port with real,
asserted semantics: the Trust Engine consumes a snapshot when one is supplied
(`tests/unit/test_trust.py` drives every 2D-D field path, `None`s included,
through a fake source), and the shipped adapter reports the one true answer
available today. When a transport exists, only this file changes.
"""

from __future__ import annotations

from uuid import UUID

from nova_autonomy_engine.domain.models import TrustInputStatus
from nova_autonomy_engine.domain.ports import ConversationalTrustRead

__all__ = ["UnavailableConversationalTrustSource"]

_DETAIL = (
    "digital-twin-engine exposes no read surface for its 2D-D TrustMetric: it serves only "
    "digital_twin.preferences.get.request on the Event Bus and no trust route over HTTP. "
    "Autonomy Engine claims no Event Bus subject in this release (decision D-4D-1), so the "
    "conversational trust input is unavailable and every trust score is reported as "
    "insufficient evidence rather than as a number."
)


class UnavailableConversationalTrustSource:
    """Reports the conversational trust input as **unavailable**, with the
    reason attached.

    Never raises -- `ConversationalTrustSource` forbids it, so that a decision
    degrades to "insufficient evidence" instead of failing (TDD §13).
    """

    async def read(self, user_id: UUID) -> ConversationalTrustRead:
        del user_id  # the answer does not depend on which user is asked
        return ConversationalTrustRead(
            status=TrustInputStatus.UNAVAILABLE, snapshot=None, detail=_DETAIL
        )
