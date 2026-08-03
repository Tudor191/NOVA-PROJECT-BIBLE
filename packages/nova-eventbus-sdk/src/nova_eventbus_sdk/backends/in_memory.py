"""In-process EventBus backend: no external broker, used for unit/integration tests
(see `nova-testkit`) and as a dependency-free default for local development before
NATS is running. Not durable -- `open_stream` only supports `ReplayPolicy.NEW`.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from uuid import UUID, uuid4

from nova_contracts import EventEnvelope
from pydantic import BaseModel

from nova_eventbus_sdk.interface import BusHealth, EventHandler, ReplayPolicy


@dataclass
class _Subscription:
    bus: InMemoryEventBus
    subject_pattern: str
    handler: EventHandler
    queue_group: str | None = None
    _active: bool = field(default=True, init=False)

    async def unsubscribe(self) -> None:
        if self._active:
            self._active = False
            self.bus._remove_subscription(self)  # noqa: SLF001


class _StreamHandle:
    """`EventStream` implementation backed by an `asyncio.Queue`."""

    def __init__(self, subscription: _Subscription, queue: asyncio.Queue[EventEnvelope]) -> None:
        self._subscription = subscription
        self._queue = queue

    def __aiter__(self) -> _StreamHandle:
        return self

    async def __anext__(self) -> EventEnvelope:
        return await self._queue.get()

    async def close(self) -> None:
        await self._subscription.unsubscribe()


class InMemoryEventBus:
    """Reference `EventBus` implementation with no external dependencies."""

    def __init__(self) -> None:
        self._connected = False
        self._subscriptions: list[_Subscription] = []
        # One "next subscriber" cursor per queue_group, for round-robin load balancing.
        self._queue_group_cursor: dict[str, int] = defaultdict(int)
        self._pending_requests: dict[UUID, asyncio.Future[EventEnvelope]] = {}

    async def connect(self) -> None:
        self._connected = True

    async def close(self) -> None:
        self._connected = False
        self._subscriptions.clear()

    def _remove_subscription(self, subscription: _Subscription) -> None:
        if subscription in self._subscriptions:
            self._subscriptions.remove(subscription)

    async def publish(self, envelope: EventEnvelope) -> None:
        self._require_connected()

        matching = [
            s for s in self._subscriptions if fnmatchcase(envelope.subject, s.subject_pattern)
        ]
        grouped: dict[str, list[_Subscription]] = defaultdict(list)
        ungrouped: list[_Subscription] = []
        for sub in matching:
            if sub.queue_group:
                grouped[sub.queue_group].append(sub)
            else:
                ungrouped.append(sub)

        targets: list[_Subscription] = list(ungrouped)
        for group_name, members in grouped.items():
            index = self._queue_group_cursor[group_name] % len(members)
            self._queue_group_cursor[group_name] += 1
            targets.append(members[index])

        for sub in targets:
            await sub.handler(envelope)

        # If this event is a reply to a pending request, resolve it.
        if envelope.causation_id is not None:
            future = self._pending_requests.pop(envelope.causation_id, None)
            if future is not None and not future.done():
                future.set_result(envelope)

    async def subscribe(
        self,
        subject_pattern: str,
        handler: EventHandler,
        *,
        queue_group: str | None = None,
    ) -> _Subscription:
        self._require_connected()
        subscription = _Subscription(
            bus=self, subject_pattern=subject_pattern, handler=handler, queue_group=queue_group
        )
        self._subscriptions.append(subscription)
        return subscription

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope:
        self._require_connected()
        request_envelope = EventEnvelope(
            subject=subject,
            source_engine=source_engine,
            correlation_id=correlation_id or uuid4(),
            payload=payload.model_dump(mode="json"),
        )
        loop = asyncio.get_running_loop()
        future: asyncio.Future[EventEnvelope] = loop.create_future()
        self._pending_requests[request_envelope.event_id] = future
        await self.publish(request_envelope)
        try:
            return await asyncio.wait_for(future, timeout=timeout_ms / 1000)
        except TimeoutError:
            self._pending_requests.pop(request_envelope.event_id, None)
            raise

    async def reply(self, *, to: EventEnvelope, payload: BaseModel, source_engine: str) -> None:
        """Send a reply to a request previously received via `subscribe`."""
        reply_envelope = EventEnvelope(
            subject=f"{to.subject}.reply",
            source_engine=source_engine,
            correlation_id=to.correlation_id,
            causation_id=to.event_id,
            payload=payload.model_dump(mode="json"),
        )
        future = self._pending_requests.get(to.event_id)
        if future is not None and not future.done():
            future.set_result(reply_envelope)
            self._pending_requests.pop(to.event_id, None)

    async def open_stream(
        self,
        subject_pattern: str,
        *,
        durable_name: str,
        replay: ReplayPolicy = ReplayPolicy.NEW,
    ) -> _StreamHandle:
        self._require_connected()
        if replay is not ReplayPolicy.NEW:
            raise NotImplementedError(
                f"InMemoryEventBus only supports ReplayPolicy.NEW (no durable storage); "
                f"got {replay!r}. Use the NATS backend for durable replay."
            )
        queue: asyncio.Queue[EventEnvelope] = asyncio.Queue()

        async def _forward(envelope: EventEnvelope) -> None:
            await queue.put(envelope)

        subscription = await self.subscribe(subject_pattern, _forward)
        return _StreamHandle(subscription, queue)

    async def health(self) -> BusHealth:
        start = time.perf_counter()
        connected = self._connected
        latency_ms = (time.perf_counter() - start) * 1000
        return BusHealth(connected=connected, backend="in_memory", latency_ms=latency_ms)

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("InMemoryEventBus.connect() must be called before use.")
