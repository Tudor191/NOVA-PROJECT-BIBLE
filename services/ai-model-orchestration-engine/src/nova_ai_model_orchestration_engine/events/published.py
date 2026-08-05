"""Every subject AI Model Orchestration Engine is permitted to publish -- docs/
design/phase-2a/00-ai-model-orchestration-engine.md §13. See ADR-004
(docs/architecture/00-overview-and-decisions.md).

`ai_model.generate.reply` / `ai_model.embed.reply` are not here -- reply
payloads are returned directly from a `BoundEventBus.serve()` handler, never
published (the same convention as World Model's `world_model.context.reply`).
"""

from __future__ import annotations

PUBLISHABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "ai_model.request.completed",
        "ai_model.request.failed",
        "ai_model.model.registered",
        "ai_model.model.deregistered",
        "ai_model.model.health_changed",
        "ai_model.budget.exceeded",
    }
)
