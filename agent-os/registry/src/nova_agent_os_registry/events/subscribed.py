"""Every subject Registry is permitted to subscribe to.

`agent_os.registry.find_healthy_package.request` is the one addition, a
disclosed gap-closing RPC serving the Kernel Scheduler's own "query Registry
for healthy candidates in the required category" step (TDD 3E §4) -- see
`events/find_healthy_package_handler.py`'s own docstring. Installation
itself remains filesystem-discovery- and startup-driven (doc 12 §15), not
Event-Bus-triggered.

`agent_os.registry.list_packages.request` is the second, added by Phase 4C
milestone 4C.2a: the Kernel needs "what is installed" to serve
`GET /v1/agents` (decision D-4), and the dispatch RPC above answers a
different question -- one winner, health- and version-filtered. See
`events/list_packages_handler.py`.

**Both are internal RPC subjects and neither is browser-facing.** They are
absent from `ws-gateway`'s `PUBLIC_TOPICS` and match none of its
subscribable patterns; `services/ws-gateway/tests/unit/test_protocol.py`
asserts that for every `agent_os.*` RPC subject rather than leaving it to
this docstring."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "agent_os.registry.find_healthy_package.request",
        "agent_os.registry.list_packages.request",
    }
)
