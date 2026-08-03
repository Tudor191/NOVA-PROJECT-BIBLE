"""Every subject nova-core is permitted to subscribe to.

Empty in Phase 0: nova-core doesn't yet consume any other engine's events (none
exist). Roadmap Phase 6 ("Executive Cognition & Full Orchestration") adds
`*.status_changed`-style subscriptions from every engine once they exist, to drive
the aggregate System Health Index (Bible Part 20, "Health Management").
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset()
