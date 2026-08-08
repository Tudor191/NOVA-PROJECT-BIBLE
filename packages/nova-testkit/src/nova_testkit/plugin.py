"""pytest plugin exposing NOVA's shared test fixtures.

Registered via the `pytest11` entry point in pyproject.toml -- any package that
depends on `nova-testkit` gets these fixtures automatically, with no conftest.py
wiring required (docs/architecture/16-testing-strategy.md §3).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus

from nova_testkit.model_gateway import FakeModelGateway


@pytest.fixture
async def event_bus() -> AsyncIterator[InMemoryEventBus]:
    """A connected, isolated `InMemoryEventBus` for a single test.

    Use this instead of hand-rolling a fake bus, and instead of a real NATS
    connection, in unit/integration tests (docs/architecture/16 §3): it implements
    the exact same `EventBus` Protocol NATS does, so tests exercise real pub/sub,
    queue-group, and request/reply behavior without any external process.
    """
    bus = InMemoryEventBus()
    await bus.connect()
    yield bus
    await bus.close()


@pytest.fixture
async def fake_model_gateway(event_bus: InMemoryEventBus) -> AsyncIterator[FakeModelGateway]:
    """A `FakeModelGateway` (`model_gateway.py`) already `start()`-ed against
    this test's `event_bus` -- serves every `ai_model.*.request` subject with
    deterministic replies. Depends on `event_bus`, not a second, independent
    bus: any code under test that also receives `event_bus` (or a component
    built from it) can reach this gateway over the same in-memory connection.
    """
    gateway = FakeModelGateway()
    await gateway.start(event_bus)
    yield gateway
    await gateway.stop()
