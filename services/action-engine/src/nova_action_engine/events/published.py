"""Every subject Action Engine is permitted to publish. See ADR-004
(docs/architecture/00-overview-and-decisions.md).

`capability.resolve.request`/`capability.invoke.request` -- `CapabilityPort`
(Fork 3C-1/3D-1's resolution). `communication.session.lookup_by_user.request`/
`communication.intent.deliver.request` -- `CommunicationPort` (TDD 3D §4's
approval-loop disclosure step). `world_model.context.request` --
`IdentityPort` (TDD 3D §7, ADR-032). `action.approval.requested`/
`action.approval.decided` -- the Phase-3-owned approval-loop events this
engine itself publishes (TDD 3D §4 points 2/5); listed here because
`BoundEventBus.publish()` enforces this same allow-list, identically to
how `.request()` does for outbound RPCs."""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "capability.resolve.request",
        "capability.invoke.request",
        "communication.session.lookup_by_user.request",
        "communication.intent.deliver.request",
        "world_model.context.request",
        "action.approval.requested",
        "action.approval.decided",
    }
)
