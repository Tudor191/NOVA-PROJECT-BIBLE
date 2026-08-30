"""In-memory `EventPublisher` fake -- records every published `EventEnvelope`
for assertions, mirrors `capability-engine`'s/`action-engine`'s own
`tests/fakes/event_publisher.py` convention.

`request()` is a structural stub only -- `domain/scheduler.py` never calls
it directly (only `RegistryClient`/`SupervisorClient`/`ModelGatewayClient`
do, each exercised against its own purpose-built fake Port in Scheduler
unit tests), but `EventPublisher` now declares both methods (disclosed
addition, `domain/ports.py`), so this fake must satisfy the full Protocol
shape."""

from __future__ import annotations

from uuid import UUID

from nova_contracts import EventEnvelope
from pydantic import BaseModel

__all__ = ["FakeEventPublisher"]


class FakeEventPublisher:
    def __init__(self) -> None:
        self.published: list[EventEnvelope] = []

    async def publish(self, envelope: EventEnvelope) -> None:
        self.published.append(envelope)

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope:
        raise NotImplementedError(
            "FakeEventPublisher.request() is not exercised by scheduler tests"
        )
