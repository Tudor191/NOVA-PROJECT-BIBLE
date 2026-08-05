"""`WorldModelClient` -- `domain.ports.WorldModelPort` implementation, calling
`world_model.context.request` (docs/design/phase-2b/00-reasoning-engine.md
§7.2) -- the same subject/payload every other engine has called since
Phase 1. A timeout or `degraded=True` reply both resolve to a `None`/
`degraded` snapshot, never an exception -- the pipeline proceeds with
reduced confidence (§10) rather than failing.
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts import ContextReplyPayload, ContextRequestPayload

from nova_reasoning_engine.domain.models import WorldModelSnapshot
from nova_reasoning_engine.domain.ports import EventPublisher

__all__ = ["WorldModelClient"]

SOURCE_ENGINE = "reasoning-engine"
DEFAULT_TIMEOUT_MS = 2000


class WorldModelClient:
    def __init__(
        self, event_publisher: EventPublisher, *, timeout_ms: int = DEFAULT_TIMEOUT_MS
    ) -> None:
        self._event_publisher = event_publisher
        self._timeout_ms = timeout_ms

    async def get_context(
        self, *, user_id: UUID, scope: str | None = None, correlation_id: UUID | None = None
    ) -> WorldModelSnapshot | None:
        try:
            reply = await self._event_publisher.request(
                "world_model.context.request",
                ContextRequestPayload(user_id=user_id, scope=scope),
                source_engine=SOURCE_ENGINE,
                correlation_id=correlation_id,
                timeout_ms=self._timeout_ms,
            )
        except TimeoutError:
            return None
        parsed = ContextReplyPayload.model_validate(reply.payload)
        return WorldModelSnapshot(
            user_id=parsed.user_id,
            objective=parsed.objective,
            project_id=parsed.project_id,
            device=parsed.device,
            task=parsed.task,
            activity=parsed.activity,
            confidence=parsed.confidence,
            degraded=parsed.degraded,
        )
