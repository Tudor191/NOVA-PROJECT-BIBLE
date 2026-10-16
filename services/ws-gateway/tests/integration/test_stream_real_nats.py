"""`ws-gateway` against a **real NATS** (SAD 15 §9.1 item 6; protocol §10.1).

Every other test of this service replaces the Event Bus with a fake. That
proves the bridge's bookkeeping, but not the property the service exists
for: that an event published on the real broker reaches a subscribed
browser, that a subject outside `PUBLIC_TOPICS` never does, and that an
unsubscribe actually stops delivery at the broker.

So nothing here is a double. `create_app()` builds its bus from
`NATS_URL`, exactly as in the composed stack, and its lifespan connects it;
a real uvicorn server serves it on a free port; a real WebSocket client
connects with the session cookie; a separate real NATS client publishes.
Each wait is bounded, so a regression fails rather than hangs.

Delivery is retried, not assumed instant: a core-NATS `SUB` sent by the
gateway's connection and a `PUB` sent by the publisher's are ordered only
per connection, so the first publish may legitimately precede the
subscription's registration at the broker.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
import uvicorn
from nova_contracts import EventEnvelope
from nova_eventbus_sdk.backends.nats import NatsEventBus
from nova_ws_gateway.config import Settings
from nova_ws_gateway.main import create_app
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import InvalidStatus

pytestmark = pytest.mark.real_infra

TOKEN = "ws-real-nats-token"
PUBLIC = "communication.turn.received"
#: Matched by `events/subscribed.py`'s `communication.*` pattern, so the bus
#: side would allow it -- but it is not in `PUBLIC_TOPICS`, so no browser
#: may name it. Only the public allow-list stands between it and a client.
INTERNAL = "communication.intent.deliver.request"

_RECV_TIMEOUT_S = 0.5
_DELIVERY_ATTEMPTS = 20


class _Server:
    def __init__(self, app: Any) -> None:
        config = uvicorn.Config(
            app, host="127.0.0.1", port=0, lifespan="on", log_config=None, ws="websockets"
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self.port = 0

    def start(self) -> None:
        self._thread.start()
        deadline = time.monotonic() + 20
        while not self._server.started:
            if time.monotonic() > deadline or not self._thread.is_alive():
                raise RuntimeError("ws-gateway did not start against real NATS")
            time.sleep(0.05)
        self.port = self._server.servers[0].sockets[0].getsockname()[1]

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=20)


@pytest.fixture
def gateway(nats_container, monkeypatch: pytest.MonkeyPatch) -> Iterator[_Server]:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "nats")
    monkeypatch.setenv("NATS_URL", nats_container.nats_uri())
    server = _Server(create_app(Settings(session_token=TOKEN)))
    server.start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
async def publisher(nats_container) -> AsyncIterator[NatsEventBus]:  # type: ignore[no-untyped-def]
    bus = NatsEventBus(servers=nats_container.nats_uri())
    await bus.connect()
    try:
        yield bus
    finally:
        await bus.close()


def _envelope(subject: str) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid4(),
        subject=subject,
        occurred_at=datetime.now(UTC),
        source_engine="communication-engine",
        correlation_id=uuid4(),
        causation_id=uuid4(),
        payload={"text": f"real-nats {subject}", "marker": uuid4().hex},
    )


def _url(server: _Server) -> str:
    return f"ws://127.0.0.1:{server.port}/v1/stream"


def _cookie() -> dict[str, str]:
    return {"Cookie": f"nova_session={TOKEN}"}


async def _recv(ws: ClientConnection, timeout: float = 5.0) -> dict[str, Any]:
    return json.loads(await asyncio.wait_for(ws.recv(), timeout))


async def _command(ws: ClientConnection, action: str, topics: list[str]) -> dict[str, Any]:
    await ws.send(json.dumps({"action": action, "topics": topics}))
    return await _recv(ws)


async def _deliver(
    publisher: NatsEventBus, ws: ClientConnection, envelope: EventEnvelope
) -> dict[str, Any]:
    """Publish until a frame arrives; return the first event frame."""
    for _ in range(_DELIVERY_ATTEMPTS):
        await publisher.publish(envelope)
        try:
            frame = await _recv(ws, _RECV_TIMEOUT_S)
        except TimeoutError:
            continue
        if frame.get("type") == "event":
            return frame
    raise AssertionError(f"no event frame for {envelope.subject} after {_DELIVERY_ATTEMPTS} tries")


async def _frames_within(ws: ClientConnection, seconds: float) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    deadline = time.monotonic() + seconds
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            frames.append(await _recv(ws, remaining))
        except TimeoutError:
            break
    return frames


async def test_an_event_published_on_real_nats_reaches_a_subscribed_browser(
    gateway: _Server, publisher: NatsEventBus
) -> None:
    async with connect(_url(gateway), additional_headers=_cookie()) as ws:
        assert (await _recv(ws))["type"] == "ready"
        ack = await _command(ws, "subscribe", [PUBLIC])
        assert ack["type"] == "subscribed" and ack["topics"] == [PUBLIC]

        envelope = _envelope(PUBLIC)
        frame = await _deliver(publisher, ws, envelope)

    assert frame["topic"] == PUBLIC
    assert frame["data"] == envelope.payload
    assert frame["meta"]["correlation_id"] == str(envelope.correlation_id)


async def test_an_internal_subject_never_reaches_the_browser_even_when_published(
    gateway: _Server, publisher: NatsEventBus
) -> None:
    async with connect(_url(gateway), additional_headers=_cookie()) as ws:
        await _recv(ws)
        refused = await _command(ws, "subscribe", [INTERNAL])
        assert refused["type"] == "error"
        assert refused["error"]["code"] == "topic_not_allowed"

        # A positive control on the same connection: delivery works, so the
        # absence below is the allow-list, not a dead subscription.
        await _command(ws, "subscribe", [PUBLIC])
        for _ in range(5):
            await publisher.publish(_envelope(INTERNAL))
        delivered = await _deliver(publisher, ws, _envelope(PUBLIC))
        later = await _frames_within(ws, 1.0)

    seen = [delivered, *later]
    assert all(f.get("topic") != INTERNAL for f in seen)
    assert delivered["topic"] == PUBLIC


async def test_unsubscribing_stops_delivery_at_the_broker(
    gateway: _Server, publisher: NatsEventBus
) -> None:
    async with connect(_url(gateway), additional_headers=_cookie()) as ws:
        await _recv(ws)
        await _command(ws, "subscribe", [PUBLIC])
        await _deliver(publisher, ws, _envelope(PUBLIC))
        await _frames_within(ws, 0.3)  # drain retries' duplicates

        ack = await _command(ws, "unsubscribe", [PUBLIC])
        assert ack["type"] == "unsubscribed" and ack["topics"] == [PUBLIC]
        for _ in range(5):
            await publisher.publish(_envelope(PUBLIC))
        after = await _frames_within(ws, 1.0)

    assert [f for f in after if f.get("type") == "event"] == []


async def test_an_unauthenticated_handshake_is_refused_before_any_subscription(
    gateway: _Server, publisher: NatsEventBus
) -> None:
    with pytest.raises(InvalidStatus) as refused:
        async with connect(_url(gateway)):
            pass  # pragma: no cover - the handshake must not succeed
    assert refused.value.response.status_code == 403
