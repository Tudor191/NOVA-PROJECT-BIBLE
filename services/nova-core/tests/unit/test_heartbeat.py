import asyncio

from nova_contracts import EventEnvelope
from nova_core.domain.boot import NovaHost
from nova_core.domain.heartbeat import HeartbeatPublisher
from nova_core.domain.registry import ModuleRegistry
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus
from nova_testkit import wait_until


async def test_beat_once_publishes_a_heartbeat(event_bus: InMemoryEventBus) -> None:
    host = NovaHost(event_bus=event_bus, registry=ModuleRegistry())
    await host.boot()

    received: list[EventEnvelope] = []

    async def handler(envelope: EventEnvelope) -> None:
        received.append(envelope)

    await event_bus.subscribe("nova.heartbeat", handler)
    publisher = HeartbeatPublisher(event_bus=event_bus, host=host, interval_s=100)
    await publisher.beat_once()

    assert len(received) == 1
    assert received[0].payload["module"] == "nova-core"
    assert received[0].payload["status"] == "healthy"


async def test_start_runs_the_loop_until_stop_is_called(event_bus: InMemoryEventBus) -> None:
    host = NovaHost(event_bus=event_bus, registry=ModuleRegistry())
    await host.boot()

    received: list[EventEnvelope] = []

    async def handler(envelope: EventEnvelope) -> None:
        received.append(envelope)

    await event_bus.subscribe("nova.heartbeat", handler)
    publisher = HeartbeatPublisher(event_bus=event_bus, host=host, interval_s=0.01)
    publisher.start()

    await wait_until(lambda: len(received) >= 2, timeout_s=1.0)
    await publisher.stop()

    count_after_stop = len(received)
    await asyncio.sleep(0.05)
    assert len(received) == count_after_stop


async def test_start_is_idempotent(event_bus: InMemoryEventBus) -> None:
    host = NovaHost(event_bus=event_bus, registry=ModuleRegistry())
    await host.boot()
    publisher = HeartbeatPublisher(event_bus=event_bus, host=host, interval_s=100)

    publisher.start()
    first_task = publisher._task  # noqa: SLF001
    publisher.start()

    assert publisher._task is first_task  # noqa: SLF001
    await publisher.stop()
