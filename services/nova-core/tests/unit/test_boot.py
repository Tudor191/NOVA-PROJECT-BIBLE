import pytest
from nova_contracts import EventEnvelope, ModuleStatus
from nova_core.domain.boot import BootError, NovaHost
from nova_core.domain.registry import BootPhase, ModuleDescriptor, ModuleRegistry
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus


async def test_boot_progresses_through_all_seven_phases(event_bus: InMemoryEventBus) -> None:
    host = NovaHost(event_bus=event_bus, registry=ModuleRegistry())

    assert host.current_phase is None
    await host.boot()

    assert host.current_phase is BootPhase.READY
    assert host.status is ModuleStatus.HEALTHY
    assert host.is_ready is True


async def test_boot_starts_registered_modules_in_their_declared_phase(
    event_bus: InMemoryEventBus,
) -> None:
    started: list[str] = []

    async def start_memory() -> None:
        started.append("memory-engine")

    async def health_ok() -> bool:
        return True

    registry = ModuleRegistry()
    registry.register(
        ModuleDescriptor(
            name="memory-engine",
            phase=BootPhase.DATA_ENGINES,
            start=start_memory,
            health_check=health_ok,
        )
    )
    host = NovaHost(event_bus=event_bus, registry=registry)

    await host.boot()

    assert started == ["memory-engine"]


async def test_boot_raises_and_reports_degraded_when_a_module_fails_health_check(
    event_bus: InMemoryEventBus,
) -> None:
    async def start_noop() -> None:
        return None

    async def unhealthy() -> bool:
        return False

    registry = ModuleRegistry()
    registry.register(
        ModuleDescriptor(
            name="broken-engine",
            phase=BootPhase.COGNITIVE_ENGINES,
            start=start_noop,
            health_check=unhealthy,
        )
    )
    host = NovaHost(event_bus=event_bus, registry=registry)

    with pytest.raises(BootError, match="broken-engine"):
        await host.boot()

    assert host.status is ModuleStatus.DEGRADED
    assert host.current_phase is BootPhase.HEALTH_CHECKS


async def test_boot_publishes_module_status_changed_events_ending_in_healthy(
    event_bus: InMemoryEventBus,
) -> None:
    received: list[EventEnvelope] = []

    async def handler(envelope: EventEnvelope) -> None:
        received.append(envelope)

    await event_bus.subscribe("nova.module.status_changed", handler)

    host = NovaHost(event_bus=event_bus, registry=ModuleRegistry())
    await host.boot()

    assert received, "expected at least one status_changed event during boot"
    assert received[-1].payload["status"] == "healthy"
    assert all(e.source_engine == "nova-core" for e in received)


async def test_heartbeat_payload_reflects_current_state(event_bus: InMemoryEventBus) -> None:
    host = NovaHost(event_bus=event_bus, registry=ModuleRegistry())
    await host.boot()

    payload = host.heartbeat_payload()

    assert payload.module == "nova-core"
    assert payload.status is ModuleStatus.HEALTHY
    assert payload.boot_phase == int(BootPhase.READY)
    assert payload.uptime_seconds >= 0.0


async def test_shutdown_publishes_down_status_and_closes_bus(event_bus: InMemoryEventBus) -> None:
    host = NovaHost(event_bus=event_bus, registry=ModuleRegistry())
    await host.boot()

    await host.shutdown()

    assert host.status is ModuleStatus.DOWN
    health = await event_bus.health()
    assert health.connected is False


def test_registering_duplicate_module_name_in_same_phase_raises() -> None:
    async def noop() -> None:
        return None

    async def ok() -> bool:
        return True

    registry = ModuleRegistry()
    descriptor = ModuleDescriptor(
        name="dup", phase=BootPhase.DATA_ENGINES, start=noop, health_check=ok
    )
    registry.register(descriptor)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(descriptor)
