"""Every subject Knowledge Engine is permitted to publish -- docs/design/phase-1/
02-knowledge-engine.md §13. See ADR-004 (docs/architecture/00-overview-and-decisions.md).

Unlike Memory Engine, Knowledge Engine initiates no outbound RPC calls in Phase 1
(it only *serves* `knowledge.retrieve.request`/`.traverse.request`/`.link.request`,
per `subscribed.py`) -- every subject here is an event this engine is the sole
producer of.
"""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "knowledge.node.created",
        "knowledge.node.updated",
        "knowledge.edge.created",
        "knowledge.contradiction.detected",
        "knowledge.contradiction.resolved",
        "knowledge.layer.advanced",
    }
)
