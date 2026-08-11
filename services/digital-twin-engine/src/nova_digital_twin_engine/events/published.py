"""Every subject digital-twin-engine is permitted to publish -- docs/design/
phase-2d/06-personal-companion.md Sec7.1. See ADR-004
(docs/architecture/00-overview-and-decisions.md).

Deliberately empty this phase. `personality.memory.update` (Sec7.3) and
`communication.intent.deliver.request` (Sec10.2, Fork D) are both approved
capabilities this engine will eventually publish, but neither has a real
production call site yet: `personality.memory.update` awaits an approved
evidence source for `CommunicationProfile`'s learned fields (Fork F,
`domain/models.py`'s own module docstring); `communication.intent.deliver.
request` is Step 9's own scope. Mirrors personality-engine's own precedent
for `personality.memory.update` in Phase 2D-A: "the subject is defined in
nova-contracts now, per ADR-024 versioning discipline, but no handler
exists ... until" a real caller does.
"""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset()
