"""pytest plugin exposing NOVA's shared test fixtures.

Registered via the `pytest11` entry point in pyproject.toml -- any package that
depends on `nova-testkit` gets these fixtures automatically, with no conftest.py
wiring required (docs/architecture/16-testing-strategy.md §3).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus


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
