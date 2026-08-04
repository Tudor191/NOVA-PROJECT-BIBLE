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
    subscribable_subjects=frozenset({"perception.*.observed", "memory.retrieve.request"}),
)
```

## Request/reply: `request()` (caller) vs. `serve()` (server)

`request()` is the caller side: publish a payload and wait for a single reply
envelope. `serve()` is the server side: subscribe to a subject and reply to every
request `handler` receives, using whichever mechanism the backend actually needs
(NATS: publish to the ephemeral reply-to inbox NATS attaches to the message; the
in-memory backend: resolve the caller's pending future directly). Handling this
inside `serve()` -- instead of leaving each engine to reconstruct a reply envelope
and `publish()` it -- is what makes the reply path actually work against NATS: a
hand-rolled `publish()` of a "reply" has no NATS inbox to deliver to and the caller's
`request()` would simply time out.

```python
from pydantic import BaseModel

class Reply(BaseModel):
    ok: bool

async def handle_ping(envelope):
    return Reply(ok=True)

await bound.serve("memory.retrieve.request", handle_ping, source_engine="memory-engine")
```
