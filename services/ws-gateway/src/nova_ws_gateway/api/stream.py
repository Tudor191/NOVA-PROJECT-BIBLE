"""`GET /v1/stream` -- the only path from a browser to the Event Bus.

Doc 09 §6 makes `ws-gateway` the sole component permitted to bridge bus
subjects to a client. This endpoint implements that, and the properties it
must hold are the ones Phase 4 **AC-2** turns on:

- an unauthenticated handshake is rejected before any subscription exists;
- a client can only name a topic from `PUBLIC_TOPICS`;
- the session credential is never passed to the bus;
- a malformed message or an unauthorised topic is answered with an error
  frame and the connection continues, rather than silently ignored.

The bridge subscribes to the bus **once per connection, per allowed topic**,
through `BoundEventBus`, which independently refuses any subject absent from
`events/subscribed.py`. Two allow-lists therefore guard the boundary: the
public one a browser may name, and the bus-side one this service may reach.
"""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from nova_contracts import EventEnvelope
from nova_eventbus_sdk import SubjectNotAllowedError
from nova_observability import get_logger

from nova_ws_gateway.domain.protocol import (
    ControlFrame,
    MalformedClientMessage,
    error_frame,
    parse_client_message,
    partition_topics,
    ready_frame,
    to_event_frame,
)
from nova_ws_gateway.domain.session import extract_presented_token

logger = get_logger("ws-gateway")

router = APIRouter(tags=["stream"])

#: Close codes. 1008 is "policy violation" -- the correct signal for an
#: authentication failure on a WebSocket, which has no 401.
WS_POLICY_VIOLATION = 1008
WS_INTERNAL_ERROR = 1011


class ConnectionBridge:
    """One browser connection's subscriptions and outbound queue."""

    def __init__(self, websocket: WebSocket, bus: object, max_queued: int) -> None:
        self._websocket = websocket
        self._bus = bus
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=max_queued)
        self._subscriptions: dict[str, object] = {}
        self.dropped_frames = 0

    @property
    def topics(self) -> list[str]:
        return list(self._subscriptions)

    async def _on_event(self, envelope: EventEnvelope) -> None:
        """Bus handler. Never raises into the bus."""
        try:
            # Serialisation belongs inside this guard, not after it. Projection
            # only copies the payload dict, so a value that cannot be encoded
            # fails at `model_dump_json`, and leaving that outside the try let
            # a single bad event escape into the bus handler and kill the
            # subscription for every later event on the topic.
            serialised = to_event_frame(envelope).model_dump_json()
        except Exception:
            # Dropped with a log: never forwarded half-formed, never allowed
            # to take the subscription down with it.
            logger.warning(
                "undeliverable event dropped", extra={"subject": envelope.subject}
            )
            return
        try:
            self._queue.put_nowait(serialised)
        except asyncio.QueueFull:
            # A client too slow to drain is dropped frame-wise rather than
            # allowed to grow this queue without bound.
            self.dropped_frames += 1
            logger.warning(
                "client too slow; frame dropped", extra={"topic": envelope.subject}
            )

    async def subscribe(self, topics: list[str]) -> list[str]:
        subscribed: list[str] = []
        for topic in topics:
            if topic in self._subscriptions:
                subscribed.append(topic)
                continue
            try:
                subscription = await self._bus.subscribe(topic, self._on_event)  # type: ignore[attr-defined]
            except SubjectNotAllowedError:
                # The public list and the bus-side list disagree. That is a
                # configuration bug in this service, not a client error, so
                # it is logged loudly rather than reported as the caller's
                # fault -- but the topic is still not subscribed.
                logger.error(
                    "public topic is not bus-subscribable; check "
                    "events/subscribed.py",
                    extra={"topic": topic},
                )
                continue
            self._subscriptions[topic] = subscription
            subscribed.append(topic)
        return subscribed

    async def unsubscribe(self, topics: list[str]) -> list[str]:
        removed: list[str] = []
        for topic in topics:
            subscription = self._subscriptions.pop(topic, None)
            if subscription is not None:
                await subscription.unsubscribe()  # type: ignore[attr-defined]
                removed.append(topic)
        return removed

    async def close(self) -> None:
        for topic in list(self._subscriptions):
            subscription = self._subscriptions.pop(topic)
            try:
                await subscription.unsubscribe()  # type: ignore[attr-defined]
            except Exception:
                # Teardown must not raise: the connection is going away and
                # a leaked log line is better than a lost cleanup pass over
                # the remaining subscriptions.
                logger.warning("failed to unsubscribe cleanly", extra={"topic": topic})

    async def next_frame(self) -> str:
        return await self._queue.get()


@router.websocket("/v1/stream")
async def stream(websocket: WebSocket) -> None:
    settings = websocket.app.state.settings
    validator = websocket.app.state.session_validator
    bus = websocket.app.state.bus

    presented = extract_presented_token(
        websocket.cookies.get(settings.session_cookie_name),
        websocket.headers.get("authorization"),
    )
    if not validator.is_valid(presented):
        # Rejected during the handshake: no subscription is ever created for
        # an unauthenticated caller, so it cannot observe bus activity at all.
        await websocket.close(code=WS_POLICY_VIOLATION, reason="unauthenticated")
        return

    await websocket.accept()
    bridge = ConnectionBridge(websocket, bus, settings.max_queued_frames)

    # One task owns the socket. Inbound client messages and outbound bus
    # frames are multiplexed by racing two awaitables rather than by running a
    # concurrent send pump: a second task writing while this one reads is a
    # deadlock against any transport that serialises access, and it bought
    # nothing the queue does not already provide.
    receive_task: asyncio.Task[str] = asyncio.create_task(websocket.receive_text())
    frame_task: asyncio.Task[str] = asyncio.create_task(bridge.next_frame())

    try:
        await websocket.send_text(ready_frame([]).model_dump_json())
        while True:
            done, _ = await asyncio.wait(
                {receive_task, frame_task}, return_when=asyncio.FIRST_COMPLETED
            )

            if frame_task in done:
                await websocket.send_text(frame_task.result())
                frame_task = asyncio.create_task(bridge.next_frame())
                if receive_task not in done:
                    continue

            if receive_task not in done:
                continue

            raw = receive_task.result()
            receive_task = asyncio.create_task(websocket.receive_text())
            try:
                message = parse_client_message(raw)
            except MalformedClientMessage as exc:
                await websocket.send_text(
                    error_frame("malformed_message", str(exc)[:300]).model_dump_json()
                )
                continue

            allowed, rejected = partition_topics(message.topics)
            if rejected:
                await websocket.send_text(
                    error_frame(
                        "topic_not_allowed",
                        f"Not subscribable: {', '.join(sorted(rejected))}",
                    ).model_dump_json()
                )

            if not allowed:
                continue

            if message.action == "subscribe":
                topics = await bridge.subscribe(allowed)
                ack = ControlFrame(type="subscribed", topics=sorted(topics))
            else:
                topics = await bridge.unsubscribe(allowed)
                ack = ControlFrame(type="unsubscribed", topics=sorted(topics))
            await websocket.send_text(ack.model_dump_json())

    except WebSocketDisconnect:
        # Normal client-side close. Not an error; the reconnect is the
        # browser's job and `realtime/` handles it with backoff.
        logger.info("client disconnected", extra={"topics": bridge.topics})
    except Exception:
        logger.exception("stream failed")
        # The socket may already be closed; there is nothing left to tell
        # the client either way.
        with contextlib.suppress(RuntimeError):
            await websocket.close(code=WS_INTERNAL_ERROR)
    finally:
        receive_task.cancel()
        frame_task.cancel()
        await bridge.close()
