"""Every subject Planning Engine is permitted to publish. See ADR-004
(docs/architecture/00-overview-and-decisions.md).

`ai_model.generate.request` is a request/reply RPC call, not a wire event
this engine owns -- listed here because `BoundEventBus.request()` enforces
this same allow-list for outbound RPC subjects, identically to how
`reasoning-engine`'s own `events/published.py` lists it (ADR-020).

`planning.task_graph.created` is enqueued via the transactional outbox
(TDD 3B §4/§6.2, `phase-3b-planning-persistence` precursor) and actually
published by `workers/outbox_worker.py`, not directly by this engine's own
FastAPI process -- listed here because `nova_service_kit.dispatch_ready_events`
calls the same `BoundEventBus.publish()` allow-list check."""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "ai_model.generate.request",
        "planning.task_graph.created",
    }
)
