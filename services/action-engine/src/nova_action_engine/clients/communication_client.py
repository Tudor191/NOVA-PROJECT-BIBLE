"""`CommunicationClient` -- `domain.ports.CommunicationPort` implementation,
calling `communication.session.lookup_by_user.request` and the existing
`communication.intent.deliver.request` (TDD 3D §4, the same Fork D
precedent `capability-engine`'s own `clients/communication_client.py`
already implements -- this module mirrors that one's structure exactly,
the closest, most recent precedent in this codebase).

`TimeoutError` propagates uncaught -- `domain/pipeline.py`'s approval loop
is the one place that catches it, treating a timeout the same as the
disclosure not being delivered right now (best-effort human notification,
distinct from the approval *timeout* itself, which is enforced separately
by `_await_decision`).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_action_engine.domain.ports import EventPublisher
from nova_contracts import (
    CommunicationIntentDeliverReplyPayload,
    CommunicationIntentDeliverRequestPayload,
    CommunicationSessionLookupByUserReplyPayload,
    CommunicationSessionLookupByUserRequestPayload,
)

__all__ = ["CommunicationClient"]

SOURCE_ENGINE = "action-engine"


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
