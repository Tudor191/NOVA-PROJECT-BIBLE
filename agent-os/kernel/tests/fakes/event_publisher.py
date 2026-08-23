"""In-memory `EventPublisher` fake -- records every published `EventEnvelope`
for assertions, mirrors `capability-engine`'s/`action-engine`'s own
`tests/fakes/event_publisher.py` convention."""

from __future__ import annotations

from nova_contracts import EventEnvelope

__all__ = ["FakeEventPublisher"]


class FakeEventPublisher:
    def __init__(self) -> None:
        self.published: list[EventEnvelope] = []

    async def publish(self, envelope: EventEnvelope) -> None:
        self.published.append(envelope)
