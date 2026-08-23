"""Every subject Registry is permitted to subscribe to.

Empty: TDD 3E §10's full event-contract list names no RPC or subscribed
event owned by `agent-os/registry` -- installation is filesystem-discovery-
and startup-driven in Phase 3 (doc 12 §15), not Event-Bus-triggered."""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset(set())
