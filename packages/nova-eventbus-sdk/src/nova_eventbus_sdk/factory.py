"""Backend selection for `EventBus` -- ADR-006: one configuration value, never a
code change. Kafka and RabbitMQ backends will register here (see
docs/architecture/09-event-bus-architecture.md §3) as `packages/nova-eventbus-sdk/
src/nova_eventbus_sdk/backends/kafka.py` / `.../rabbitmq.py` are added.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from nova_eventbus_sdk.interface import EventBus

_BackendFactory = Callable[[], EventBus]

_BACKEND_FACTORIES: dict[str, _BackendFactory] = {}


def register_backend(name: str) -> Callable[[_BackendFactory], _BackendFactory]:
    """Register a factory function under `EVENT_BUS_BACKEND=<name>`."""

    def _decorator(factory: _BackendFactory) -> _BackendFactory:
        _BACKEND_FACTORIES[name] = factory
        return factory

    return _decorator


def _build_in_memory() -> EventBus:
    from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus

    return InMemoryEventBus()


def _build_nats() -> EventBus:
    from nova_eventbus_sdk.backends.nats import NatsEventBus

    servers = os.environ.get("NATS_URL", "nats://localhost:4222")
    name = os.environ.get("NOVA_ENGINE_NAME")
    return NatsEventBus(servers=servers, name=name)


register_backend("in_memory")(_build_in_memory)
register_backend("nats")(_build_nats)


def get_event_bus(backend: str | None = None) -> EventBus:
    """Return an unconnected `EventBus` instance for the requested backend.

    `backend` defaults to the `EVENT_BUS_BACKEND` environment variable, which
    defaults to `"nats"` -- the local-first default (docs/architecture/01 §5).
    Callers are responsible for calling `await bus.connect()`.
    """
    resolved = backend or os.environ.get("EVENT_BUS_BACKEND", "nats")
    try:
        factory = _BACKEND_FACTORIES[resolved]
    except KeyError as exc:
        available = ", ".join(sorted(_BACKEND_FACTORIES)) or "(none registered)"
        raise ValueError(
            f"Unknown EVENT_BUS_BACKEND {resolved!r}. Available backends: {available}."
        ) from exc
    return factory()
