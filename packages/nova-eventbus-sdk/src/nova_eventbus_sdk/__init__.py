"""nova-eventbus-sdk: the EventBus interface (ADR-006) and its backends.

No engine, agent, or gateway may import a broker's native client library (`nats`,
`aiokafka`, `aio_pika`, ...) directly -- only this package's `EventBus` Protocol and
`get_event_bus()` factory.
"""

from nova_eventbus_sdk.boundary import BoundEventBus, SubjectNotAllowedError
from nova_eventbus_sdk.factory import get_event_bus, register_backend
from nova_eventbus_sdk.interface import (
    BusHealth,
    EventBus,
    EventHandler,
    EventStream,
    ReplayPolicy,
    RequestHandler,
    Subscription,
)

__all__ = [
    "BoundEventBus",
    "BusHealth",
    "EventBus",
    "EventHandler",
    "EventStream",
    "ReplayPolicy",
    "RequestHandler",
    "SubjectNotAllowedError",
    "Subscription",
    "get_event_bus",
    "register_backend",
]
