"""`CommunicationClient` -- `domain.ports.CommunicationPort` implementation,
calling `communication.session.lookup_by_user.request` and the existing
`communication.intent.deliver.request` (Phase 2D-D docs/design/phase-2d/
06-personal-companion.md Sec10.2, Fork D) -- this engine's first
synchronous upstream RPC caller. Mirrors `communication-engine`'s own
`clients/personality_client.py` structure exactly.

`TimeoutError` propagates uncaught -- `proactive_delivery.
attempt_proactive_delivery` is the one place that catches it, mirroring
every other client's documented convention in this project.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_contracts import (
    CommunicationIntentDeliverReplyPayload,
    CommunicationIntentDeliverRequestPayload,
    CommunicationSessionLookupByUserReplyPayload,
    CommunicationSessionLookupByUserRequestPayload,
)

from nova_digital_twin_engine.domain.ports import EventPublisher

__all__ = ["CommunicationClient"]

SOURCE_ENGINE = "digital-twin-engine"


class CommunicationClient:
    def __init__(self, event_publisher: EventPublisher, *, timeout_ms: int = 2000) -> None:
        self._event_publisher = event_publisher
        self._timeout_ms = timeout_ms

    async def get_connected_session(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> UUID | None:
        reply = await self._event_publisher.request(
            "communication.session.lookup_by_user.request",
            CommunicationSessionLookupByUserRequestPayload(user_id=user_id),
            source_engine=SOURCE_ENGINE,
            correlation_id=correlation_id,
            timeout_ms=self._timeout_ms,
        )
        parsed = CommunicationSessionLookupByUserReplyPayload.model_validate(reply.payload)
        return parsed.session_id

    async def deliver_intent(
        self, *, session_id: UUID, content: str, correlation_id: UUID | None = None
    ) -> bool:
        reply = await self._event_publisher.request(
            "communication.intent.deliver.request",
            CommunicationIntentDeliverRequestPayload(
                session_id=session_id,
                content=content,
                requesting_engine=SOURCE_ENGINE,
                correlation_id=correlation_id or uuid4(),
            ),
            source_engine=SOURCE_ENGINE,
            correlation_id=correlation_id,
            timeout_ms=self._timeout_ms,
        )
        parsed = CommunicationIntentDeliverReplyPayload.model_validate(reply.payload)
        return parsed.delivered
