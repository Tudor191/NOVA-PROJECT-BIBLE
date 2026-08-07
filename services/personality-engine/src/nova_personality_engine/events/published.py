"""Every subject Personality Engine is permitted to publish -- docs/design/
phase-2d/02-personality-engine.md Sec10. See ADR-004
(docs/architecture/00-overview-and-decisions.md).

Empty by design, not by omission: this engine publishes nothing in Phase
2D-A (Sec10). `personality.validate_response.reply` / `personality.style.
select.reply` are returned directly from `BoundEventBus.serve()` handlers,
never published -- the same convention every prior engine's own served-RPC
replies follow.
"""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset()
