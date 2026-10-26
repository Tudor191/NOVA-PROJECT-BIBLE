"""SAD 15 §9.1 items 9 and 10 for `ws-gateway`.

Each decision on the stream -- handshake refused or accepted, message
malformed, topic refused, subscribed, frame queued, dropped or undeliverable
-- must be **counted** under a bounded label and **logged** with the
connection's `connection_id` (and, for an event, the event's own `event_id`
and `correlation_id`).

Metrics are read the way Prometheus reads them, from the process-global
registry `/internal/metrics` serves; every assertion is a delta.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from nova_contracts import EventEnvelope
from nova_eventbus_sdk import SubjectNotAllowedError
from nova_ws_gateway.api.stream import ConnectionBridge
from nova_ws_gateway.config import Settings
from nova_ws_gateway.domain.protocol import PUBLIC_TOPICS
from nova_ws_gateway.main import create_app
from nova_ws_gateway.observability import create_metrics
from prometheus_client import REGISTRY, generate_latest
from starlette.websockets import WebSocketDisconnect

TOKEN = "ws-observability-token"
TOPIC = "communication.turn.received"


@dataclass
class FakeSubscription:
    async def unsubscribe(self) -> None:
        return None


@dataclass
class FakeBus:
    allowed: set[str] = field(default_factory=lambda: set(PUBLIC_TOPICS))
    handlers: dict[str, Any] = field(default_factory=dict)

    async def subscribe(self, subject: str, handler: Any) -> FakeSubscription:
        if subject not in self.allowed:
            raise SubjectNotAllowedError(f"{subject} not allowed")
        self.handlers[subject] = handler
        return FakeSubscription()


class _Unserialisable:
    """A payload value `model_dump_json` cannot encode."""


def _envelope(subject: str = TOPIC, payload: dict[str, Any] | None = None) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid4(),
        subject=subject,
        occurred_at=datetime.now(UTC),
        source_engine="communication-engine",
        correlation_id=uuid4(),
        causation_id=uuid4(),
        payload=payload if payload is not None else {"text": "hi"},
    )


class _Records(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def records() -> Iterator[list[logging.LogRecord]]:
    """On the `ws-gateway` logger itself: `configure_logging` replaces the
    root handlers on first use, which would detach pytest's `caplog`."""
    handler = _Records()
    ws_logger = logging.getLogger("ws-gateway")
    ws_logger.addHandler(handler)
    previous = ws_logger.level
    ws_logger.setLevel(logging.DEBUG)
    try:
        yield handler.records
    finally:
        ws_logger.removeHandler(handler)
        ws_logger.setLevel(previous)


@pytest.fixture
def bus() -> FakeBus:
    return FakeBus()


@pytest.fixture
def client(bus: FakeBus) -> Iterator[TestClient]:
    app = create_app(Settings(session_token=TOKEN), bus=bus)  # type: ignore[arg-type]
    with TestClient(app) as test_client:
        yield test_client


_SAMPLE = re.compile(r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(\{(?P<labels>[^}]*)\})? (?P<value>\S+)$")


def _sample(name: str, **labels: str) -> float:
    total = 0.0
    for line in generate_latest(REGISTRY).decode().splitlines():
        match = _SAMPLE.match(line)
        if match is None or match["name"] != name:
            continue
        found = dict(re.findall(r'(\w+)="([^"]*)"', match["labels"] or ""))
        if all(found.get(k) == v for k, v in labels.items()):
            total += float(match["value"])
    return total


def _messages(records: list[logging.LogRecord], message: str) -> list[logging.LogRecord]:
    return [r for r in records if r.getMessage() == message]


# --- handshake ---------------------------------------------------------------


def test_an_unauthenticated_handshake_is_counted_and_logged(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    before = _sample("ws_gateway_connections_total", outcome="unauthenticated")
    with pytest.raises(WebSocketDisconnect) as closed:  # noqa: SIM117
        with client.websocket_connect("/v1/stream") as ws:
            ws.receive_text()
    assert closed.value.code == 1008
    assert _sample("ws_gateway_connections_total", outcome="unauthenticated") - before == 1
    [record] = _messages(records, "connection refused")
    assert record.reason == "unauthenticated"  # type: ignore[attr-defined]
    assert record.connection_id  # type: ignore[attr-defined]
    assert _messages(records, "client connected") == []


def test_an_accepted_connection_is_counted_and_closes_the_open_gauge(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    accepted = _sample("ws_gateway_connections_total", outcome="accepted")
    open_before = _sample("ws_gateway_open_connections")
    client.cookies.set("nova_session", TOKEN)
    with client.websocket_connect("/v1/stream") as ws:
        assert json.loads(ws.receive_text())["type"] == "ready"
        assert _sample("ws_gateway_open_connections") - open_before == 1
    assert _sample("ws_gateway_connections_total", outcome="accepted") - accepted == 1
    # The server-side `finally` runs as the socket closes; the gauge must
    # return to where it started, or a long-lived process would drift.
    assert _sample("ws_gateway_open_connections") == open_before
    [connected] = _messages(records, "client connected")
    [disconnected] = _messages(records, "client disconnected")
    assert connected.connection_id == disconnected.connection_id  # type: ignore[attr-defined]


# --- client messages ---------------------------------------------------------


def test_a_malformed_message_is_counted_and_logged_on_the_same_connection(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    before = _sample("ws_gateway_client_messages_total", outcome="malformed")
    client.cookies.set("nova_session", TOKEN)
    with client.websocket_connect("/v1/stream") as ws:
        ws.receive_text()
        ws.send_text("{not json")
        assert json.loads(ws.receive_text())["error"]["code"] == "malformed_message"
    assert _sample("ws_gateway_client_messages_total", outcome="malformed") - before == 1
    [connected] = _messages(records, "client connected")
    [rejected] = _messages(records, "client message rejected")
    assert rejected.connection_id == connected.connection_id  # type: ignore[attr-defined]


def test_refused_topics_are_counted_logged_capped_and_never_a_label(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    before = _sample("ws_gateway_client_messages_total", outcome="topic_not_allowed")
    bogus = [f"secret.internal.subject.{i:02d}." + "x" * 300 for i in range(15)]
    client.cookies.set("nova_session", TOKEN)
    with client.websocket_connect("/v1/stream") as ws:
        ws.receive_text()
        ws.send_text(json.dumps({"action": "subscribe", "topics": bogus}))
        assert json.loads(ws.receive_text())["error"]["code"] == "topic_not_allowed"

    assert (
        _sample("ws_gateway_client_messages_total", outcome="topic_not_allowed") - before == 1
    )
    [record] = _messages(records, "subscription refused")
    assert record.rejected_count == 15  # type: ignore[attr-defined]
    logged: list[str] = record.rejected  # type: ignore[attr-defined]
    assert len(logged) == 10
    assert all(len(name) <= 120 for name in logged)
    assert "secret.internal" not in generate_latest(REGISTRY).decode()


def test_a_subscription_is_counted_and_logged_with_its_topics(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    before = _sample("ws_gateway_client_messages_total", outcome="subscribe")
    client.cookies.set("nova_session", TOKEN)
    with client.websocket_connect("/v1/stream") as ws:
        ws.receive_text()
        ws.send_text(json.dumps({"action": "subscribe", "topics": [TOPIC]}))
        assert json.loads(ws.receive_text())["type"] == "subscribed"
    assert _sample("ws_gateway_client_messages_total", outcome="subscribe") - before == 1
    [record] = _messages(records, "subscribed")
    assert record.topics == [TOPIC]  # type: ignore[attr-defined]


# --- frames ------------------------------------------------------------------


async def test_frames_are_counted_queued_dropped_and_undeliverable_by_topic(
    records: list[logging.LogRecord],
) -> None:
    """Driven through the bridge directly so the queue can be filled
    without a consumer racing to drain it."""
    bridge = ConnectionBridge(
        websocket=None,  # type: ignore[arg-type]
        bus=FakeBus(),
        max_queued=1,
        connection_id="conn-under-test",
        metrics=create_metrics(),
    )
    labels = {"topic": TOPIC}
    queued = _sample("ws_gateway_frames_total", outcome="queued", **labels)
    dropped = _sample("ws_gateway_frames_total", outcome="dropped_slow_client", **labels)
    undeliverable = _sample("ws_gateway_frames_total", outcome="undeliverable", **labels)

    first, second = _envelope(), _envelope()
    await bridge._on_event(first)
    await bridge._on_event(second)  # the queue holds one: this is dropped
    await bridge._on_event(_envelope(payload={"bad": _Unserialisable()}))

    assert _sample("ws_gateway_frames_total", outcome="queued", **labels) - queued == 1
    assert (
        _sample("ws_gateway_frames_total", outcome="dropped_slow_client", **labels) - dropped
        == 1
    )
    assert (
        _sample("ws_gateway_frames_total", outcome="undeliverable", **labels) - undeliverable
        == 1
    )
    [drop] = _messages(records, "client too slow; frame dropped")
    assert drop.connection_id == "conn-under-test"  # type: ignore[attr-defined]
    assert drop.event_id == str(second.event_id)  # type: ignore[attr-defined]
    assert UUID(drop.correlation_id) == second.correlation_id  # type: ignore[attr-defined]
    [bad] = _messages(records, "undeliverable event dropped")
    assert bad.connection_id == "conn-under-test"  # type: ignore[attr-defined]


async def test_a_topic_outside_the_public_list_is_labeled_other() -> None:
    bridge = ConnectionBridge(
        websocket=None,  # type: ignore[arg-type]
        bus=FakeBus(),
        max_queued=10,
        metrics=create_metrics(),
    )
    before = _sample("ws_gateway_frames_total", topic="other", outcome="queued")
    await bridge._on_event(_envelope(subject="internal.never.public"))
    assert _sample("ws_gateway_frames_total", topic="other", outcome="queued") - before == 1
    assert 'topic="internal.never.public"' not in generate_latest(REGISTRY).decode()


async def test_a_public_topic_the_bus_refuses_is_counted_as_a_configuration_bug(
    records: list[logging.LogRecord],
) -> None:
    bus = FakeBus(allowed=set())
    bridge = ConnectionBridge(
        websocket=None,  # type: ignore[arg-type]
        bus=bus,
        max_queued=10,
        connection_id="conn-cfg",
        metrics=create_metrics(),
    )
    before = _sample("ws_gateway_bus_subscribe_refused_total", topic=TOPIC)
    assert await bridge.subscribe([TOPIC]) == []
    assert _sample("ws_gateway_bus_subscribe_refused_total", topic=TOPIC) - before == 1
    [record] = _messages(
        records, "public topic is not bus-subscribable; check events/subscribed.py"
    )
    assert record.levelno == logging.ERROR
    assert record.connection_id == "conn-cfg"  # type: ignore[attr-defined]
