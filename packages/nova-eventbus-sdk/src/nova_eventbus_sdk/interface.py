"""The `EventBus` interface -- ADR-006 (docs/architecture/00-overview-and-decisions.md).

Every engine, agent, and gateway in NOVA depends on this Protocol and never on a
broker's native client library. It is deliberately scoped to the intersection of what
NATS JetStream, Kafka, and RabbitMQ can all provide: publish, subscribe, request/reply,
durable replayable streams, and consumer/queue groups.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import UUID

from nova_contracts import EventEnvelope
from pydantic import BaseModel

EventHandler = Callable[[EventEnvelope], Awaitable[None]]
"""An async callback invoked once per matching event delivered to a subscription."""

RequestHandler = Callable[[EventEnvelope], Awaitable[BaseModel]]
"""An async callback invoked once per request envelope delivered to a `serve()`
subscription. Returns the reply payload; the backend delivers it back to the
original `request()` caller using its own native reply mechanism -- the handler
never constructs a reply envelope or subject itself."""


class ReplayPolicy(StrEnum):
    """How a durable stream should be replayed when opened (docs/architecture/09 §5)."""

    ALL = "all"
    """Replay every event still retained by the stream, oldest first."""
    NEW = "new"
    """Only deliver events published after the stream is opened."""
    LAST = "last"
    """Deliver only the most recent event per subject, then new events."""


class BusHealth(BaseModel):
    """Point-in-time health snapshot for an `EventBus` connection."""

    connected: bool
    backend: str
    latency_ms: float | None = None
    error: str | None = None


@runtime_checkable
class Subscription(Protocol):
    """A handle returned by `EventBus.subscribe`, used to stop receiving events."""

    async def unsubscribe(self) -> None: ...


@runtime_checkable
class EventStream(Protocol):
    """An async-iterable handle over a durable, replayable stream of events."""

    def __aiter__(self) -> EventStream: ...

    async def __anext__(self) -> EventEnvelope: ...

    async def close(self) -> None: ...


@runtime_checkable
class EventBus(Protocol):
    """The only interface any NOVA code may depend on to talk to the Event Bus.

    Concrete backends (NATS by default; Kafka/RabbitMQ as alternates, see
    `nova_eventbus_sdk.backends`) implement this Protocol. Selecting a backend is a
    configuration decision (`nova_eventbus_sdk.factory.get_event_bus`), never an
    import decision -- no engine ever imports `nats`, `aiokafka`, or `aio_pika`
    directly.
    """

    async def connect(self) -> None:
        """Establish the underlying connection. Idempotent."""
        ...

    async def close(self) -> None:
        """Tear down the underlying connection. Idempotent."""
        ...

    async def publish(self, envelope: EventEnvelope) -> None:
        """Publish `envelope` on `envelope.subject`."""
        ...

    async def subscribe(
        self,
        subject_pattern: str,
        handler: EventHandler,
        *,
        queue_group: str | None = None,
    ) -> Subscription:
        """Invoke `handler` for every event matching `subject_pattern`.

        `queue_group`, when set, load-balances delivery across every subscriber
        sharing the same group name -- used to scale multiple instances of the same
        engine horizontally (docs/architecture/19 §2).
        """
        ...

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope:
        """Synchronous cross-engine RPC without violating ADR-004: publish `payload`
        to `subject` and wait up to `timeout_ms` for a single reply envelope.
        """
        ...

    async def serve(
        self,
        subject_pattern: str,
        handler: RequestHandler,
        *,
        source_engine: str,
        queue_group: str | None = None,
    ) -> Subscription:
        """The server side of `request()` (docs/architecture/10-inter-engine-
        communication.md §3): subscribe to `subject_pattern` and reply to every
        matching request with whatever `handler` returns. Every backend routes the
        reply back to the original caller using its own native mechanism (a NATS
        reply-to inbox; the in-memory backend's pending-request table) -- this is
        precisely the part that varies by backend and that a hand-rolled `publish()`
        of a reply envelope inside engine code would get wrong for at least one of
        them, which is why this exists as its own Protocol method rather than being
        left as "just call publish() with the right causation_id".
        """
        ...

    async def open_stream(
        self,
        subject_pattern: str,
        *,
        durable_name: str,
        replay: ReplayPolicy = ReplayPolicy.NEW,
    ) -> EventStream:
        """Open a durable, replayable stream over events matching `subject_pattern`."""
        ...

    async def health(self) -> BusHealth:
        """Report the current connection health."""
        ...
