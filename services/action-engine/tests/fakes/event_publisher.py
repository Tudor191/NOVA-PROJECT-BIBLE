"""`FakeEventPublisher` -- an in-memory `domain.ports.EventPublisher`,
recording every `publish()` call (`.request()` is unused by
`domain/pipeline.py` directly -- only `clients/*.py` call it, and those are
exercised through the real `CapabilityPort`/`CommunicationPort`/
`IdentityPort` fakes instead) -- lets a unit test assert on
`action.approval.requested`/`action.approval.decided` without a real Event
Bus."""

from __future__ import annotations

from uuid import UUID

from nova_contracts import EventEnvelope
from pydantic import BaseModel


class FakeEventPublisher:
    def __init__(self) -> None:
        self.published: list[EventEnvelope] = []

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope:
        raise NotImplementedError("FakeEventPublisher.request() is not used by domain/pipeline.py")

    async def publish(self, envelope: EventEnvelope) -> None:
        self.published.append(envelope)
