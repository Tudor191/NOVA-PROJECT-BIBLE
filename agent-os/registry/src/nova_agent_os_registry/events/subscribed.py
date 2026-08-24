"""Every subject Registry is permitted to subscribe to.

`agent_os.registry.find_healthy_package.request` is the one addition, a
disclosed gap-closing RPC serving the Kernel Scheduler's own "query Registry
for healthy candidates in the required category" step (TDD 3E §4) -- see
`events/find_healthy_package_handler.py`'s own docstring. Installation
itself remains filesystem-discovery- and startup-driven (doc 12 §15), not
Event-Bus-triggered."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "agent_os.registry.find_healthy_package.request",
    }
)
