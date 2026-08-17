"""Every subject Capability Engine is permitted to subscribe to.

Both subjects are request/reply RPCs this engine serves (`bus.serve()`,
Fork 3C-1/3D-1) -- `action-engine`'s future `CapabilityPort`/client is
the caller, not built in this PR. `BoundEventBus.serve()` enforces this
same allow-list, identically to how `subscribe()` does for fire-and-forget
subscriptions."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "capability.resolve.request",
        "capability.invoke.request",
    }
)
