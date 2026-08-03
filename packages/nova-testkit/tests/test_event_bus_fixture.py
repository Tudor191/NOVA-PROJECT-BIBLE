"""Verifies the `event_bus` fixture (registered via the pytest11 entry point in
plugin.py) is auto-discovered and usable without any local conftest.py -- this is
itself the proof that other packages will get it for free."""

from uuid import uuid4

from nova_contracts import EventEnvelope
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus


async def test_event_bus_fixture_is_connected_and_isolated(event_bus: InMemoryEventBus) -> None:
    received: list[EventEnvelope] = []

    async def handler(envelope: EventEnvelope) -> None:
        received.append(envelope)

    await event_bus.subscribe("a.b.c", handler)
    await event_bus.publish(
        EventEnvelope(subject="a.b.c", source_engine="test", correlation_id=uuid4())
    )

    assert len(received) == 1
