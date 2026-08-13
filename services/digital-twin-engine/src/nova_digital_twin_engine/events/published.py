"""Every subject digital-twin-engine is permitted to publish -- docs/design/
phase-2d/06-personal-companion.md Sec7.1, Sec10.2. See ADR-004
(docs/architecture/00-overview-and-decisions.md).

`communication.intent.deliver.request` and `communication.session.
lookup_by_user.request` (Sec10.2, Fork D, Step 9) are now real, tested
outbound RPC calls -- `proactive_delivery.attempt_proactive_delivery`,
via `clients/communication_client.py::CommunicationClient`. Neither has a
production *trigger* yet (no scheduler or other source proposes a
`ProactiveSuggestion` in this codebase -- `proactive_delivery.py`'s own
module docstring), but the calls themselves are real and reach the real
wire contract when invoked directly, unlike `personality.memory.update`
below.

`personality.memory.update` (Sec7.3) remains an approved capability with
no real call site -- it awaits an approved evidence source for
`CommunicationProfile`'s learned fields (Fork F, `domain/models.py`'s own
module docstring). Mirrors personality-engine's own precedent: "the
subject is defined in nova-contracts now, per ADR-024 versioning
discipline, but no handler exists ... until" a real caller does.
"""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "communication.intent.deliver.request",
        "communication.session.lookup_by_user.request",
    }
)
