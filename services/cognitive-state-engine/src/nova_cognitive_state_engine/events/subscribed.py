"""Every subject Cognitive State Engine is permitted to subscribe to.

**Empty in 4F.1.** TDD 4F §13 records that this engine consumes perception
observations and World Model context *"via the Event Bus only"* -- but 4F.1 is
the domain and persistence slice, and it has no handler to route a subject to.
Declaring a subscription before a consumer exists would create exactly the dead
subscription `ws-gateway`'s own `PUBLIC_TOPICS` docstring warns about: *"A dead
topic is not harmless here: the client subscribes successfully and then waits
forever."*

Subjects arrive with the handlers that consume them, in **4F.6**, and every one
of them already exists -- this engine will be a new *consumer* of existing
contracts, never the author of a new one (D-4D-1).
"""

from __future__ import annotations

SUBSCRIBABLE_SUBJECTS: frozenset[str] = frozenset()
