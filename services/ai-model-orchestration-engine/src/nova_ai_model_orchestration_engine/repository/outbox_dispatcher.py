"""Thin wrapper binding this engine's `source_engine` default onto the shared
transactional-outbox dispatch loop (Project Health Review, August 2026;
`docs/design/nova-service-kit/boilerplate-extraction-proposal.md`
Extraction C) -- the loop itself now lives once in `nova_service_kit.outbox`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nova_service_kit import dispatch_ready_events as _dispatch_ready_events

from nova_ai_model_orchestration_engine.domain.ports import UsageRepository

if TYPE_CHECKING:
    from nova_eventbus_sdk import EventBus

    from nova_ai_model_orchestration_engine.observability import AiModelOrchestrationEngineMetrics

DEFAULT_BATCH_SIZE = 100


async def dispatch_ready_events(
    repository: UsageRepository,
    bus: EventBus,
    *,
    source_engine: str = "ai-model-orchestration-engine",
    batch_size: int = DEFAULT_BATCH_SIZE,
    metrics: AiModelOrchestrationEngineMetrics | None = None,
) -> int:
    """Returns the number of rows dispatched."""
    return await _dispatch_ready_events(
        repository, bus, source_engine=source_engine, batch_size=batch_size, metrics=metrics
    )
