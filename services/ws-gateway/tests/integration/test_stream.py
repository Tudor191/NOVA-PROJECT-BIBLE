"""Integration tests over a real WebSocket through a real `create_app()`.

The Event Bus is replaced with a recording fake, so these exercise the whole
bridge -- handshake auth, allow-list, subscription bookkeeping, envelope
projection, teardown -- without NATS. `nova-eventbus-sdk`'s own boundary is
covered separately by its package tests; what matters here is that this
service never reaches the bus except through it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from nova_contracts import EventEnvelope
from nova_eventbus_sdk import SubjectNotAllowedError
from nova_ws_gateway.api.stream import ConnectionBridge
from nova_ws_gateway.config import Settings
from nova_ws_gateway.domain.protocol import PUBLIC_TOPICS
from nova_ws_gateway.main import create_app

TOKEN = "ws-test-token"


@dataclass
class FakeSubscription:
    subject: str
    unsubscribed: bool = False

    async def unsubscribe(self) -> None:
        self.unsubscribed = True


@dataclass
class FakeBus:
    """Records subscriptions and lets a test push an event to the handler."""

    # Derived from `PUBLIC_TOPICS` rather than restated. A hand-copied list
    # here drifted once already: it carried three topics no engine publishes,
    # and because the fake happily served them the integration suite stayed
    # green while the real bridge offered dead topics. Tests that need a
    # subject the bridge must *not* reach pass it explicitly instead.
    allowed: set[str] = field(default_factory=lambda: set(PUBLIC_TOPICS))
    handlers: dict[str, Any] = field(default_factory=dict)
    subscriptions: list[FakeSubscription] = field(default_factory=list)
    credentials_seen: list[Any] = field(default_factory=list)

    async def subscribe(self, subject: str, handler: Any) -> FakeSubscription:
        if subject not in self.allowed:
            raise SubjectNotAllowedError(f"{subject} not allowed")
        self.handlers[subject] = handler
        subscription = FakeSubscription(subject)
        self.subscriptions.append(subscription)
        return subscription

    async def emit(self, subject: str, **overrides: Any) -> None:
        envelope = EventEnvelope(
            event_id=uuid4(),
            subject=subject,
            occurred_at=overrides.get("occurred_at", datetime.now(UTC)),
            source_engine="communication-engine",
            correlation_id=overrides.get("correlation_id", uuid4()),
            causation_id=uuid4(),
            confidence=overrides.get("confidence"),
            payload=overrides.get("payload", {"text": "hi"}),
        )
        await self.handlers[subject](envelope)


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {"session_token": TOKEN}
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def bus() -> FakeBus:
    return FakeBus()


@pytest.fixture
def client(bus: FakeBus):  # type: ignore[no-untyped-def]
    app = create_app(_settings(), bus=bus)  # type: ignore[arg-type]
    with TestClient(app) as test_client:
        test_client.cookies.set("nova_session", TOKEN)
        yield test_client


def _drain_ready(ws: Any) -> None:
    assert json.loads(ws.receive_text())["type"] == "ready"


# --- authentication -------------------------------------------------------


def test_unauthenticated_connection_is_rejected(bus: FakeBus) -> None:
    app = create_app(_settings(), bus=bus)  # type: ignore[arg-type]
    with (
        TestClient(app) as anon,
        pytest.raises(Exception),  # noqa: B017
        anon.websocket_connect("/v1/stream"),
    ):
        pass
    # No subscription may exist for an unauthenticated caller.
    assert bus.subscriptions == []


def test_wrong_token_is_rejected(bus: FakeBus) -> None:
    app = create_app(_settings(), bus=bus)  # type: ignore[arg-type]
    with TestClient(app) as wrong:
        wrong.cookies.set("nova_session", "not-the-token")
        with pytest.raises(Exception), wrong.websocket_connect("/v1/stream"):  # noqa: B017
            pass
    assert bus.subscriptions == []


def test_unconfigured_gateway_refuses_everyone(bus: FakeBus) -> None:
    app = create_app(_settings(session_token=""), bus=bus)  # type: ignore[arg-type]
    with TestClient(app) as unconfigured:
        unconfigured.cookies.set("nova_session", "")
        with pytest.raises(Exception), unconfigured.websocket_connect("/v1/stream"):  # noqa: B017
            pass


def test_authenticated_connection_is_accepted(client: TestClient) -> None:
    with client.websocket_connect("/v1/stream") as ws:
        _drain_ready(ws)


# --- subscription and the allow-list --------------------------------------


def test_allowed_topic_subscribes_on_the_bus(
    client: TestClient, bus: FakeBus
) -> None:
    with client.websocket_connect("/v1/stream") as ws:
        _drain_ready(ws)
        ws.send_text(json.dumps({"action": "subscribe", "topics": ["nova.heartbeat"]}))
        ack = json.loads(ws.receive_text())
        assert ack["type"] == "subscribed"
        assert ack["topics"] == ["nova.heartbeat"]
    assert [s.subject for s in bus.subscriptions] == ["nova.heartbeat"]


@pytest.mark.parametrize("topic", [">", "*", "communication.*", "secret.internal"])
def test_unauthorized_topic_is_refused_and_never_reaches_the_bus(
    topic: str, client: TestClient, bus: FakeBus
) -> None:
    with client.websocket_connect("/v1/stream") as ws:
        _drain_ready(ws)
        ws.send_text(json.dumps({"action": "subscribe", "topics": [topic]}))
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "error"
        assert frame["error"]["code"] == "topic_not_allowed"
    assert bus.subscriptions == []


def test_mixed_request_subscribes_the_allowed_and_reports_the_rest(
    client: TestClient, bus: FakeBus
) -> None:
    with client.websocket_connect("/v1/stream") as ws:
        _drain_ready(ws)
        ws.send_text(
            json.dumps(
                {"action": "subscribe", "topics": ["nova.heartbeat", "forbidden.topic"]}
            )
        )
        error = json.loads(ws.receive_text())
        assert error["error"]["code"] == "topic_not_allowed"
        ack = json.loads(ws.receive_text())
        assert ack["topics"] == ["nova.heartbeat"]
    assert [s.subject for s in bus.subscriptions] == ["nova.heartbeat"]


def test_unsubscribe_releases_the_bus_subscription(
    client: TestClient, bus: FakeBus
) -> None:
    with client.websocket_connect("/v1/stream") as ws:
        _drain_ready(ws)
        ws.send_text(json.dumps({"action": "subscribe", "topics": ["nova.heartbeat"]}))
        json.loads(ws.receive_text())
        ws.send_text(json.dumps({"action": "unsubscribe", "topics": ["nova.heartbeat"]}))
        ack = json.loads(ws.receive_text())
        assert ack["type"] == "unsubscribed"
    assert bus.subscriptions[0].unsubscribed is True


def test_duplicate_subscribe_does_not_create_a_second_bus_subscription(
    client: TestClient, bus: FakeBus
) -> None:
    with client.websocket_connect("/v1/stream") as ws:
        _drain_ready(ws)
        for _ in range(3):
            ws.send_text(
                json.dumps({"action": "subscribe", "topics": ["nova.heartbeat"]})
            )
            json.loads(ws.receive_text())
    assert len(bus.subscriptions) == 1


# --- malformed input ------------------------------------------------------


@pytest.mark.parametrize(
    "raw", ["nonsense", "{}", '{"action":"nope","topics":["x"]}', "[]"]
)
def test_malformed_message_yields_an_error_frame_and_keeps_the_connection(
    raw: str, client: TestClient
) -> None:
    with client.websocket_connect("/v1/stream") as ws:
        _drain_ready(ws)
        ws.send_text(raw)
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "error"
        assert frame["error"]["code"] == "malformed_message"
        # Still usable afterwards.
        ws.send_text(json.dumps({"action": "subscribe", "topics": ["nova.heartbeat"]}))
        assert json.loads(ws.receive_text())["type"] == "subscribed"


# --- event forwarding -----------------------------------------------------


@pytest.mark.asyncio
async def test_bus_event_is_forwarded_with_the_envelope_preserved() -> None:
    """Drive the bridge directly rather than through the socket.

    `TestClient`'s WebSocket runs the app on a background portal, so pushing
    a bus event from the test thread mid-connection deadlocks against the
    bridge's own send pump. Exercising `ConnectionBridge` gives the same
    coverage of projection and queueing without racing the transport; the
    socket-level tests above already prove the transport itself works.
    """
    bus = FakeBus()
    bridge = ConnectionBridge(websocket=None, bus=bus, max_queued=8)  # type: ignore[arg-type]
    await bridge.subscribe(["communication.turn.received"])

    correlation = uuid4()
    occurred = datetime(2026, 9, 1, 7, 0, tzinfo=UTC)
    await bus.emit(
        "communication.turn.received",
        correlation_id=correlation,
        occurred_at=occurred,
        payload={"text": "hello"},
        confidence=0.75,
    )

    frame = json.loads(bridge._queue.get_nowait())
    assert frame["type"] == "event"
    assert frame["topic"] == "communication.turn.received"
    assert frame["data"] == {"text": "hello"}
    assert frame["meta"]["correlation_id"] == str(correlation)
    assert frame["meta"]["generated_at"].startswith("2026-09-01T07:00:00")
    assert frame["meta"]["confidence"] == 0.75
    assert frame["error"] is None


@pytest.mark.asyncio
async def test_forwarded_frame_contains_no_credential_or_bus_internals() -> None:
    bus = FakeBus()
    bridge = ConnectionBridge(websocket=None, bus=bus, max_queued=8)  # type: ignore[arg-type]
    await bridge.subscribe(["nova.heartbeat"])
    await bus.emit("nova.heartbeat", payload={"module": "nova-core"})

    raw = bridge._queue.get_nowait()
    assert TOKEN not in raw
    assert "causation_id" not in raw
    assert "source_engine" not in raw
    assert "event_id" not in raw


@pytest.mark.asyncio
async def test_slow_client_drops_frames_rather_than_growing_without_bound() -> None:
    bus = FakeBus()
    bridge = ConnectionBridge(websocket=None, bus=bus, max_queued=2)  # type: ignore[arg-type]
    await bridge.subscribe(["nova.heartbeat"])
    for _ in range(5):
        await bus.emit("nova.heartbeat", payload={"n": 1})
    assert bridge._queue.qsize() == 2
    assert bridge.dropped_frames == 3


@pytest.mark.asyncio
async def test_undeliverable_payload_is_dropped_not_forwarded_half_formed() -> None:
    """A projection failure must not kill the subscription or emit a partial frame."""
    bus = FakeBus()
    bridge = ConnectionBridge(websocket=None, bus=bus, max_queued=8)  # type: ignore[arg-type]
    await bridge.subscribe(["nova.heartbeat"])

    class Unserialisable:
        pass

    await bus.emit("nova.heartbeat", payload={"bad": Unserialisable()})
    assert bridge._queue.empty()
    # The subscription survives; a good event still arrives.
    await bus.emit("nova.heartbeat", payload={"ok": True})
    assert json.loads(bridge._queue.get_nowait())["data"] == {"ok": True}


def test_session_credential_is_never_passed_to_the_bus(
    client: TestClient, bus: FakeBus
) -> None:
    with client.websocket_connect("/v1/stream") as ws:
        _drain_ready(ws)
        ws.send_text(json.dumps({"action": "subscribe", "topics": ["nova.heartbeat"]}))
        json.loads(ws.receive_text())
    # subscribe() is called with (subject, handler) only -- no credential.
    assert bus.credentials_seen == []


# --- disconnect / teardown ------------------------------------------------


def test_disconnect_releases_every_subscription(
    client: TestClient, bus: FakeBus
) -> None:
    with client.websocket_connect("/v1/stream") as ws:
        _drain_ready(ws)
        ws.send_text(
            json.dumps(
                {
                    "action": "subscribe",
                    "topics": ["nova.heartbeat", "communication.turn.received"],
                }
            )
        )
        json.loads(ws.receive_text())
    assert len(bus.subscriptions) == 2
    assert all(s.unsubscribed for s in bus.subscriptions)


def test_reconnect_starts_from_a_clean_subscription_set(
    client: TestClient, bus: FakeBus
) -> None:
    for _ in range(2):
        with client.websocket_connect("/v1/stream") as ws:
            _drain_ready(ws)
            ws.send_text(
                json.dumps({"action": "subscribe", "topics": ["nova.heartbeat"]})
            )
            json.loads(ws.receive_text())
    # Two connections, two independent subscriptions, both released.
    assert len(bus.subscriptions) == 2
    assert all(s.unsubscribed for s in bus.subscriptions)


# --- upstream bus failure -------------------------------------------------


def test_bus_refusal_does_not_kill_the_connection(
    client: TestClient, bus: FakeBus
) -> None:
    """A public topic the bus refuses is a config bug, not a client error.

    The topic is simply not subscribed; the connection stays usable so the
    rest of the UI keeps working rather than going dark.
    """
    bus.allowed.discard("nova.heartbeat")
    with client.websocket_connect("/v1/stream") as ws:
        _drain_ready(ws)
        ws.send_text(json.dumps({"action": "subscribe", "topics": ["nova.heartbeat"]}))
        ack = json.loads(ws.receive_text())
        assert ack["type"] == "subscribed"
        assert ack["topics"] == []
        ws.send_text(
            json.dumps({"action": "subscribe", "topics": ["communication.turn.received"]})
        )
        assert json.loads(ws.receive_text())["topics"] == [
            "communication.turn.received"
        ]
