"""`WorldModelClient` -- `domain.ports.WorldModelPort` implementation,
calling `world_model.context.request` (design doc Sec8.7) -- the same
subject/payload every other engine has called since Phase 1. A timeout or
`degraded=True` reply both resolve to a `None`/`degraded` snapshot, never an
exception -- session creation proceeds without situational grounding rather
than failing.
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts import ContextReplyPayload, ContextRequestPayload

from nova_communication_engine.domain.ports import EventPublisher, WorldModelSnapshot

__all__ = ["WorldModelClient"]

SOURCE_ENGINE = "communication-engine"


class WorldModelClient:
    def __init__(self, event_publisher: EventPublisher, *, timeout_ms: int = 2000) -> None:
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
            degraded=parsed.degraded,
            present_identities=parsed.present_identities,
        )
