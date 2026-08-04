"""`FakeEventPublisher` -- an in-memory `domain.ports.EventPublisher` for testing
`domain/relationship.py` without a real Knowledge Engine (which doesn't exist yet
-- docs/design/phase-1/04-cross-engine-integration.md)."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

from nova_contracts import EventEnvelope
from pydantic import BaseModel


class FakeEventPublisher:
    """Routes `request()` calls to a per-subject canned handler. A subject with no
    registered handler raises `TimeoutError`, matching a real `EventBus.request()`
    against a subject nobody is serving -- exactly the "Knowledge Engine doesn't
    exist yet" case this fake exists to simulate.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[BaseModel], BaseModel]] = {}
        self.calls: list[tuple[str, BaseModel]] = []

    def register(self, subject: str, handler: Callable[[BaseModel], BaseModel]) -> None:
        self._handlers[subject] = handler

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope:
        self.calls.append((subject, payload))
        handler = self._handlers.get(subject)
        if handler is None:
            raise TimeoutError(f"No handler registered for {subject!r} (fake: nothing serving it)")
        reply_payload = handler(payload)
        return EventEnvelope(
            subject=f"{subject}.reply",
            source_engine="fake-knowledge-engine",
            correlation_id=correlation_id or uuid4(),
            payload=reply_payload.model_dump(mode="json"),
        )
