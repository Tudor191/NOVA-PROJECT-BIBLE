"""Every subject World Model Engine is permitted to publish -- docs/design/
phase-1/03-world-model-engine.md §13. See ADR-004
(docs/architecture/00-overview-and-decisions.md).

World Model initiates no outbound RPC calls in Phase 1 (it only *serves*
`world_model.context.request`, per `subscribed.py`) -- every subject here is an
event this engine is the sole producer of.
"""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "world_model.object.created",
        "world_model.object.updated",
        "world_model.object.deleted",
        "world_model.context.changed",
        "world_model.attention.shifted",
        "world_model.prediction.generated",
    }
)
