"""Every subject Communication Engine is permitted to subscribe to -- docs/
design/phase-2d/01-communication-engine.md Sec11, extended by
docs/design/phase-2d/04-conversation-intelligence.md Sec10/Sec21 item 2 and
docs/design/phase-2d/06-personal-companion.md Sec10.2 (Fork D).

`communication.intent.deliver.request`, `communication.session.create.
request`, `communication.session.close.request`, and `communication.
session.lookup_by_user.request` are here, not `published.py`:
`BoundEventBus.serve()` checks the *subscribable* allow-list, matching
`subscribe()`'s convention (the same reason every prior engine's own
served RPCs live here).

`perception.addressee_signal.candidate` is a genuine publish/subscribe
event, not a served RPC -- registered in `nova_contracts.events.perception`
per Sec0.6's prerequisite, consumed by `domain/addressee_fusion.py` via
`events/handlers.py::make_addressee_signal_handler`.
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "communication.intent.deliver.request",
        "communication.session.create.request",
        "communication.session.close.request",
        "communication.session.lookup_by_user.request",
        "perception.addressee_signal.candidate",
    }
)
