"""Verifies `nova_testkit.nats`'s fixtures against a real NATS JetStream
container -- real publish/subscribe, real request/reply, and real durable
-stream retention (implementation plan §13's verification bar: specifically
the one behavior `event_bus`'s `InMemoryEventBus` cannot represent, since it
has no persistence at all).

`@pytest.mark.real_infra`: excluded from the default `pytest`/`turbo run test`
invocation (ADR-033) -- requires Docker. **Not executed in the environment
this file was written in** (no reachable Docker daemon there); see `nats.py`'s
own module docstring.
"""

from uuid import uuid4

import pytest
from nova_contracts import EventEnvelope
from nova_eventbus_sdk import ReplayPolicy
from nova_eventbus_sdk.backends.nats import NatsEventBus
from nova_testkit import wait_until

pytestmark = pytest.mark.real_infra


async def test_real_publish_and_subscribe(nats_event_bus: NatsEventBus) -> None:
    received: list[EventEnvelope] = []

    async def handler(envelope: EventEnvelope) -> None:
        received.append(envelope)

    subscription = await nats_event_bus.subscribe("testkit.pubsub.widget", handler)
    await nats_event_bus.publish(
        EventEnvelope(
            subject="testkit.pubsub.widget",
            source_engine="test",
            correlation_id=uuid4(),
            payload={"name": "gizmo"},
        )
    )

    # subscribe()'s callback is invoked by the nats-py client's own background
    # task, not synchronously with publish() -- poll instead of asserting
    # immediately, the same "eventually consistent" pattern every other
    # engine's event-driven integration tests already use this helper for.
    await wait_until(lambda: len(received) == 1, timeout_s=2.0)
    assert received[0].payload == {"name": "gizmo"}
    await subscription.unsubscribe()


async def test_real_request_reply(nats_event_bus: NatsEventBus) -> None:
    async def handler(envelope: EventEnvelope) -> EventEnvelope:
        return envelope

    subscription = await nats_event_bus.serve(
        "testkit.rpc.echo", handler, source_engine="test-server"
    )
    reply = await nats_event_bus.request(
        "testkit.rpc.echo",
        EventEnvelope(
            subject="testkit.rpc.echo",
            source_engine="test-client",
            correlation_id=uuid4(),
            payload={"question": "ping"},
        ),
        source_engine="test-client",
        timeout_ms=2000,
    )

    assert reply.payload == {"question": "ping"}
    await subscription.unsubscribe()


async def test_durable_stream_retains_messages_until_pulled(
    nats_event_bus: NatsEventBus,
) -> None:
    """The behavior `InMemoryEventBus` cannot represent at all: JetStream
    retains a message published to an open stream even before anything
    actively pulls it -- confirmed by publishing before the first
    `__anext__()` call, not publish-then-immediately-consume."""
    stream = await nats_event_bus.open_stream(
        "testkit.durable.>", durable_name="testkit-durable", replay=ReplayPolicy.ALL
    )
    await nats_event_bus.publish(
        EventEnvelope(
            subject="testkit.durable.widget",
            source_engine="test",
            correlation_id=uuid4(),
            payload={"name": "gizmo"},
        )
    )

    received = await stream.__anext__()

    assert received.subject == "testkit.durable.widget"
    assert received.payload == {"name": "gizmo"}
    await stream.close()
