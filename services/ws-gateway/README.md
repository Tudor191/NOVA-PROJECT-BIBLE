# ws-gateway

The only component permitted to bridge Event Bus subjects to a browser
([09](../../docs/architecture/09-event-bus-architecture.md) §6, ADR-006). It holds
one WebSocket per client, validates the session cookie the `api-gateway` issued,
and forwards frames for an explicitly allow-listed set of subjects — nothing else.
The browser never connects to NATS, and an end-to-end test asserts that a direct
socket to the bus port is refused.

It implements no Bible Part of its own; it is the realtime half of the transport
boundary, the counterpart to `api-gateway`'s request/response half.

**The allow-list is a fixed list, not a pattern language.** A client cannot
subscribe to `>`, to `*`, or to an internal RPC subject, because those strings are
not in the set. Full permission-derived allow-lists depend on Phase 7's
`nova-auth` and are an explicit Phase 4 non-goal.

Frames carry the topic, the payload, and [11](../../docs/architecture/11-api-architecture.md)
§4's `meta` — and nothing else. `causation_id` (internal event chaining) and
`source_engine` (internal topology) stay off the wire.

**Subscriptions are NATS core, so there is no replay**: a browser that joins late
does not receive frames published before it connected.

## Owned events

Publishes nothing. Subscribes to the bus on the browser's behalf; the 17 subjects
a client may name are `PUBLIC_TOPICS` in `domain/protocol.py`, with the matching
bus-side declarations in `events/subscribed.py`.

| Consumer | Subjects |
|---|---|
| Conversation panel | `communication.turn.received`, `communication.intent.delivered`, `communication.session.created`, `communication.session.state_changed`, `communication.session.completed` |
| Presence/identity indicator | `perception.identity.observed`, `perception.presence.observed` |
| System Pulse | `nova.heartbeat` |
| Planning panel | `planning.task_graph.created` |
| Reasoning Trace panel | `reasoning.process.completed`, `reasoning.process.failed`, `reasoning.human_override.applied` |
| Approvals panel | `action.approval.requested`, `action.approval.decided` |
| Health panel | `nova.module.status_changed`, `ai_model.model.health_changed`, `perception.sensor.health_changed` |

Two guards keep this list honest, and both are load-bearing:
`test_every_public_topic_is_actually_published` asserts each entry is a subject
some engine's own `events/published.py` really declares — a client subscribing to
a dead topic succeeds and then waits forever — and
`test_every_public_topic_is_reachable_on_the_bus` asserts each is covered by
`events/subscribed.py`, matching with `fnmatchcase` because that is what
`BoundEventBus` itself uses.

**The Capabilities panel has no entry on purpose:** `capability-engine` publishes
no domain events at all, only outbound RPC requests, so that panel is REST-only.

## Owned APIs

- `WS /v1/stream` — the single realtime endpoint
- `GET /internal/health`
- `GET /internal/readiness`
- `GET /internal/metrics` — the Prometheus scrape endpoint, mounted as a
  sub-application in `main.py` rather than declared in `api/health.py`.

## Testing

```bash
uv run --package ws-gateway pytest services/ws-gateway/tests
```
