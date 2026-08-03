"""Runtime enforcement of an engine's declared publish/subscribe allow-lists.

docs/architecture/09-event-bus-architecture.md §6: "An engine cannot publish an
undeclared subject even by accident." `BoundEventBus` wraps any `EventBus`
implementation and makes that a runtime guarantee, not just a CI convention -- every
engine's `events/published.py` / `subscribed.py` declares its allow-lists and passes
them here once, at startup.
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from uuid import UUID

from nova_contracts import EventEnvelope
from pydantic import BaseModel

from nova_eventbus_sdk.interface import (
    BusHealth,
    EventHandler,
    EventStream,
    ReplayPolicy,
    Subscription,
)


class SubjectNotAllowedError(PermissionError):
    """Raised when an engine attempts to publish or subscribe outside its declared
    allow-list."""


def _matches_any(subject: str, patterns: frozenset[str]) -> bool:
    return any(fnmatchcase(subject, pattern) for pattern in patterns)


class BoundEventBus:
    """An `EventBus` wrapper that only permits declared subjects through.

    `publishable_subjects` and `subscribable_subjects` accept glob patterns
    (`fnmatch` semantics, e.g. `"memory.*.created"`) so an engine can declare a
    family of subjects without enumerating every concrete one.
    """

    def __init__(
        self,
        bus: object,
        *,
        engine_name: str,
        publishable_subjects: frozenset[str],
        subscribable_subjects: frozenset[str],
    ) -> None:
        self._bus = bus
        self._engine_name = engine_name
        self._publishable = publishable_subjects
        self._subscribable = subscribable_subjects

    async def connect(self) -> None:
        await self._bus.connect()  # type: ignore[attr-defined]

    async def close(self) -> None:
        await self._bus.close()  # type: ignore[attr-defined]

    async def publish(self, envelope: EventEnvelope) -> None:
        if not _matches_any(envelope.subject, self._publishable):
            raise SubjectNotAllowedError(
                f"{self._engine_name!r} is not permitted to publish on "
                f"{envelope.subject!r}. Declare it in this engine's "
                f"events/published.py first."
            )
        await self._bus.publish(envelope)  # type: ignore[attr-defined]

    async def subscribe(
        self,
        subject_pattern: str,
        handler: EventHandler,
        *,
        queue_group: str | None = None,
    ) -> Subscription:
        if not _matches_any(subject_pattern, self._subscribable):
            raise SubjectNotAllowedError(
                f"{self._engine_name!r} is not permitted to subscribe to "
                f"{subject_pattern!r}. Declare it in this engine's "
                f"events/subscribed.py first."
            )
        return await self._bus.subscribe(  # type: ignore[attr-defined]
            subject_pattern, handler, queue_group=queue_group
        )

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope:
        if not _matches_any(subject, self._publishable):
            raise SubjectNotAllowedError(
                f"{self._engine_name!r} is not permitted to request on {subject!r}."
            )
        return await self._bus.request(  # type: ignore[attr-defined]
            subject,
            payload,
            source_engine=source_engine,
            correlation_id=correlation_id,
            timeout_ms=timeout_ms,
        )

    async def open_stream(
        self,
        subject_pattern: str,
        *,
        durable_name: str,
        replay: ReplayPolicy = ReplayPolicy.NEW,
    ) -> EventStream:
        if not _matches_any(subject_pattern, self._subscribable):
            raise SubjectNotAllowedError(
                f"{self._engine_name!r} is not permitted to stream {subject_pattern!r}."
            )
        return await self._bus.open_stream(  # type: ignore[attr-defined]
            subject_pattern, durable_name=durable_name, replay=replay
        )

    async def health(self) -> BusHealth:
        return await self._bus.health()  # type: ignore[attr-defined]
