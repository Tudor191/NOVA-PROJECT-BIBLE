# nova-eventbus-sdk

The `EventBus` interface (ADR-006, docs/architecture/00-overview-and-decisions.md)
and its backend implementations. **No engine, agent, or gateway may import a broker's
native client library directly** -- only this package.

- `interface.py` -- the `EventBus` Protocol every caller depends on.
- `factory.py` -- `get_event_bus()`, resolving the `EVENT_BUS_BACKEND` environment
  variable (`nats` by default) to a concrete backend.
- `boundary.py` -- `BoundEventBus`, which wraps any backend and enforces an engine's
  declared publish/subscribe allow-lists at runtime (ADR-004).
- `backends/in_memory.py` -- dependency-free backend for tests and local dev
  (`nova-testkit` builds on this).
- `backends/nats.py` -- the default production backend (NATS + JetStream).

## Adding a new backend (e.g. Kafka, RabbitMQ)

1. Create `backends/<name>.py` implementing every method on `EventBus`.
2. Register it in `factory.py`: `register_backend("<name>")(_build_<name>)`.
3. Add the shared contract test suite (once it exists, docs/architecture/16 §4)
   against the new backend to prove behavioral equivalence with `nats`.

No other package needs to change -- this is what ADR-006 exists to guarantee.

## Usage

```python
from nova_eventbus_sdk import get_event_bus, BoundEventBus
from nova_contracts import EventEnvelope

bus = get_event_bus()  # reads EVENT_BUS_BACKEND, defaults to "nats"
await bus.connect()

bound = BoundEventBus(
    bus,
    engine_name="memory-engine",
    publishable_subjects=frozenset({"memory.*.created", "memory.consolidation.completed"}),
    subscribable_subjects=frozenset({"perception.*.observed"}),
)
```
