"""NATS JetStream `EventBus` backend -- the default implementation (ADR-006).

Core NATS pub/sub backs `publish`/`subscribe` (fast, at-most-once, no pre-provisioned
stream required). JetStream backs `open_stream` (durable, replayable) and `request`
uses core NATS request/reply. See docs/architecture/09-event-bus-architecture.md.

This module lazily imports `nats` inside each method (not at module scope) so that
importing `nova_eventbus_sdk` never requires a NATS server to be reachable, and so
`nats-py` stays an implementation detail behind the `EventBus` Protocol rather than a
dependency every engine's code needs to know about.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from nova_contracts import EventEnvelope
from pydantic import BaseModel

from nova_eventbus_sdk.interface import BusHealth, EventHandler, ReplayPolicy, RequestHandler

if TYPE_CHECKING:
    from nats.aio.client import Client as NatsClient
    from nats.aio.subscription import Subscription as NatsSubscription
    from nats.js.client import JetStreamContext


def _stream_name_for(subject_pattern: str) -> str:
    """NATS stream names may not contain '.', '*', '>', or spaces."""
    sanitized = re.sub(r"[.\*>\s]+", "_", subject_pattern).strip("_")
    return f"NOVA_{sanitized.upper()}"


class _NatsSubscription:
    def __init__(self, subscription: NatsSubscription) -> None:
        self._subscription = subscription

    async def unsubscribe(self) -> None:
        await self._subscription.unsubscribe()


class _NatsStreamHandle:
    def __init__(self, subscription: NatsSubscription) -> None:
        self._subscription = subscription

    def __aiter__(self) -> _NatsStreamHandle:
        return self

    async def __anext__(self) -> EventEnvelope:
        msg = await self._subscription.next_msg()
        await msg.ack()
        return EventEnvelope.model_validate_json(msg.data)

    async def close(self) -> None:
        await self._subscription.unsubscribe()


class NatsEventBus:
    """`EventBus` implementation backed by NATS + JetStream."""

    def __init__(
        self, servers: str | list[str] = "nats://localhost:4222", *, name: str | None = None
    ) -> None:
        self._servers = servers
        self._name = name
        self._nc: NatsClient | None = None
        self._js: JetStreamContext | None = None

    async def connect(self) -> None:
        import nats

        self._nc = await nats.connect(self._servers, name=self._name)
        self._js = self._nc.jetstream()

    async def close(self) -> None:
        if self._nc is not None:
            await self._nc.close()
            self._nc = None
            self._js = None

    async def publish(self, envelope: EventEnvelope) -> None:
        nc = self._require_connected()
        await nc.publish(envelope.subject, envelope.model_dump_json().encode())

    async def subscribe(
        self,
        subject_pattern: str,
        handler: EventHandler,
        *,
        queue_group: str | None = None,
    ) -> _NatsSubscription:
        nc = self._require_connected()

        async def _callback(msg: object) -> None:
            envelope = EventEnvelope.model_validate_json(msg.data)  # type: ignore[attr-defined]
            await handler(envelope)

        sub = await nc.subscribe(subject_pattern, queue=queue_group or "", cb=_callback)
        return _NatsSubscription(sub)

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope:
        import nats.errors

        nc = self._require_connected()
        envelope = EventEnvelope(
            subject=subject,
            source_engine=source_engine,
            correlation_id=correlation_id or uuid4(),
            payload=payload.model_dump(mode="json"),
        )
        try:
            msg = await nc.request(
                subject, envelope.model_dump_json().encode(), timeout=timeout_ms / 1000
            )
        except nats.errors.TimeoutError as exc:
            raise TimeoutError(f"No reply on {subject!r} within {timeout_ms}ms") from exc
        return EventEnvelope.model_validate_json(msg.data)

    async def serve(
        self,
        subject_pattern: str,
        handler: RequestHandler,
        *,
        source_engine: str,
        queue_group: str | None = None,
    ) -> _NatsSubscription:
        nc = self._require_connected()

        async def _callback(msg: object) -> None:
            # `msg.reply` is the ephemeral inbox subject NATS generates for
            # `nc.request()` calls; publishing there -- not to `subject_pattern` --
            # is what actually routes the reply back to that specific caller. A
            # message with no `.reply` was published via plain `publish()`, not
            # `request()`, and has nothing to respond to.
            envelope = EventEnvelope.model_validate_json(msg.data)  # type: ignore[attr-defined]
            reply_payload = await handler(envelope)
            reply_to = msg.reply  # type: ignore[attr-defined]
            if reply_to:
                reply_envelope = EventEnvelope(
                    subject=reply_to,
                    source_engine=source_engine,
                    correlation_id=envelope.correlation_id,
                    causation_id=envelope.event_id,
                    payload=reply_payload.model_dump(mode="json"),
                )
                await nc.publish(reply_to, reply_envelope.model_dump_json().encode())

        sub = await nc.subscribe(subject_pattern, queue=queue_group or "", cb=_callback)
        return _NatsSubscription(sub)

    async def open_stream(
        self,
        subject_pattern: str,
        *,
        durable_name: str,
        replay: ReplayPolicy = ReplayPolicy.NEW,
    ) -> _NatsStreamHandle:
        import contextlib

        from nats.js.api import ConsumerConfig, DeliverPolicy, StreamConfig
        from nats.js.errors import BadRequestError

        js = self._require_jetstream()
        stream_name = _stream_name_for(subject_pattern)
        # BadRequestError here means the stream already exists -- add_stream is not
        # idempotent, so this is the expected path whenever open_stream() is called
        # again for the same subject pattern.
        with contextlib.suppress(BadRequestError):
            await js.add_stream(StreamConfig(name=stream_name, subjects=[subject_pattern]))

        deliver_policy = {
            ReplayPolicy.ALL: DeliverPolicy.ALL,
            ReplayPolicy.NEW: DeliverPolicy.NEW,
            ReplayPolicy.LAST: DeliverPolicy.LAST,
        }[replay]
        # No `cb` -- this returns a pull-able Subscription (`.next_msg()`), which is
        # what `_NatsStreamHandle.__anext__` consumes one message at a time.
        sub = await js.subscribe(
            subject_pattern,
            durable=durable_name,
            config=ConsumerConfig(deliver_policy=deliver_policy),
            manual_ack=True,
        )
        return _NatsStreamHandle(sub)

    async def health(self) -> BusHealth:
        if self._nc is None:
            return BusHealth(connected=False, backend="nats")
        try:
            rtt = await self._nc.rtt()
            return BusHealth(connected=self._nc.is_connected, backend="nats", latency_ms=rtt * 1000)
        except Exception as exc:  # noqa: BLE001 -- health checks must never raise
            return BusHealth(connected=False, backend="nats", error=str(exc))

    def _require_connected(self) -> NatsClient:
        if self._nc is None:
            raise RuntimeError("NatsEventBus.connect() must be called before use.")
        return self._nc

    def _require_jetstream(self) -> JetStreamContext:
        if self._js is None:
            raise RuntimeError("NatsEventBus.connect() must be called before use.")
        return self._js
