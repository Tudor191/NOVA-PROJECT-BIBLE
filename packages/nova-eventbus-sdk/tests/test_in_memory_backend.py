import asyncio
from uuid import uuid4

import pytest
from nova_contracts import EventEnvelope
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus
from nova_eventbus_sdk.interface import EventHandler, ReplayPolicy
from pydantic import BaseModel


class _Ping(BaseModel):
    message: str


async def _bus() -> InMemoryEventBus:
    bus = InMemoryEventBus()
    await bus.connect()
    return bus


async def test_publish_delivers_to_matching_subscriber() -> None:
    bus = await _bus()
    received: list[EventEnvelope] = []

    async def handler(envelope: EventEnvelope) -> None:
        received.append(envelope)

    await bus.subscribe("memory.episodic.created", handler)
    await bus.publish(
        EventEnvelope(
            subject="memory.episodic.created",
            source_engine="memory-engine",
            correlation_id=uuid4(),
        )
    )
    assert len(received) == 1
    assert received[0].subject == "memory.episodic.created"


async def test_publish_respects_glob_subject_patterns() -> None:
    bus = await _bus()
    received: list[EventEnvelope] = []

    async def handler(envelope: EventEnvelope) -> None:
        received.append(envelope)

    await bus.subscribe("memory.*.created", handler)
    await bus.publish(
        EventEnvelope(subject="memory.episodic.created", source_engine="x", correlation_id=uuid4())
    )
    await bus.publish(
        EventEnvelope(subject="knowledge.node.created", source_engine="x", correlation_id=uuid4())
    )
    assert len(received) == 1


async def test_publish_before_connect_raises() -> None:
    bus = InMemoryEventBus()
    with pytest.raises(RuntimeError, match="connect"):
        await bus.publish(
            EventEnvelope(subject="a.b.c", source_engine="x", correlation_id=uuid4())
        )


async def test_unsubscribe_stops_delivery() -> None:
    bus = await _bus()
    received: list[EventEnvelope] = []

    async def handler(envelope: EventEnvelope) -> None:
        received.append(envelope)

    sub = await bus.subscribe("a.b.c", handler)
    await sub.unsubscribe()
    await bus.publish(EventEnvelope(subject="a.b.c", source_engine="x", correlation_id=uuid4()))
    assert received == []


async def test_queue_group_round_robins_across_subscribers() -> None:
    bus = await _bus()
    counts = {"one": 0, "two": 0}

    def make_handler(name: str) -> EventHandler:
        async def handler(envelope: EventEnvelope) -> None:
            counts[name] += 1

        return handler

    await bus.subscribe("work.*", make_handler("one"), queue_group="workers")
    await bus.subscribe("work.*", make_handler("two"), queue_group="workers")

    for _ in range(4):
        await bus.publish(
            EventEnvelope(subject="work.item", source_engine="x", correlation_id=uuid4())
        )

    assert counts["one"] == 2
    assert counts["two"] == 2


async def test_request_reply_round_trip() -> None:
    bus = await _bus()

    async def handler(envelope: EventEnvelope) -> None:
        await bus.reply(to=envelope, payload=_Ping(message="pong"), source_engine="responder")

    await bus.subscribe("ping", handler)
    reply = await bus.request(
        "ping", _Ping(message="ping"), source_engine="requester", timeout_ms=500
    )
    assert reply.payload["message"] == "pong"
    assert reply.subject == "ping.reply"


async def test_request_times_out_when_nobody_replies() -> None:
    bus = await _bus()
    with pytest.raises(asyncio.TimeoutError):
        await bus.request(
            "nobody.listening", _Ping(message="hello"), source_engine="x", timeout_ms=50
        )


async def test_open_stream_delivers_new_events_only() -> None:
    bus = await _bus()
    stream = await bus.open_stream("nova.heartbeat", durable_name="test-consumer")

    await bus.publish(
        EventEnvelope(subject="nova.heartbeat", source_engine="nova-core", correlation_id=uuid4())
    )
    envelope = await stream.__anext__()
    assert envelope.subject == "nova.heartbeat"
    await stream.close()


async def test_open_stream_rejects_durable_replay_policies() -> None:
    bus = await _bus()
    with pytest.raises(NotImplementedError):
        await bus.open_stream("a.b.c", durable_name="d", replay=ReplayPolicy.ALL)


async def test_health_reports_connection_state() -> None:
    bus = InMemoryEventBus()
    disconnected = await bus.health()
    assert disconnected.connected is False
    await bus.connect()
    connected = await bus.health()
    assert connected.connected is True
    assert connected.backend == "in_memory"
