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

*(Corrected 2026-10-16. The sentence above and the table below are preserved
as written, but both are stale against `domain/protocol.py`: `PUBLIC_TOPICS`
has **18** subjects, and the table omits `agent_os.task.completed`, which
Phase 4C.2 added for the Agents panel. The row is added below, marked.)*

| Consumer | Subjects |
|---|---|
| Conversation panel | `communication.turn.received`, `communication.intent.delivered`, `communication.session.created`, `communication.session.state_changed`, `communication.session.completed` |
| Presence/identity indicator | `perception.identity.observed`, `perception.presence.observed` |
| System Pulse | `nova.heartbeat` |
| Planning panel | `planning.task_graph.created` |
| Reasoning Trace panel | `reasoning.process.completed`, `reasoning.process.failed`, `reasoning.human_override.applied` |
| Approvals panel | `action.approval.requested`, `action.approval.decided` |
| Health panel | `nova.module.status_changed`, `ai_model.model.health_changed`, `perception.sensor.health_changed` |
| Agents panel *(row added 2026-10-16)* | `agent_os.task.completed` |

**The bus-side patterns are narrower than they once were, and two are still
broad** *(added 2026-10-16; ledger row L-8).*

- **`perception.*` was narrowed in Phase 4F.2** to the three subjects the panels
  read: `perception.presence.observed`, `perception.identity.observed` and
  `perception.sensor.health_changed`. `*` spans dots under `fnmatchcase`, so the
  old pattern let this process receive `perception.workspace.observed`, which
  carries raw workspace-sensor provenance. A browser could never *name* it, but
  the process should not receive it at all (doc 09 §6).
  `test_4f2_no_raw_perception_subject_is_subscribable` keeps it out.
- **`communication.*` and `personality.*` are still patterns** (carried since
  Phase 4C.2, Gate Review §13.1). They match six internal RPC request subjects,
  so this process may receive traffic it never forwards. Narrowing them is open.

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

## Internal structure

*(Added 2026-10-16, SAD 15 §9.1 item 3. Drawn from `src/` at this commit.)*

```
src/nova_ws_gateway/
├── main.py             create_app(): settings, BoundEventBus (NATS), session
│                       validator, metrics, routers, /internal/metrics mount
├── config.py           Settings (env prefix WS_GATEWAY_)
├── observability.py    WsGatewayMetrics: the five instruments below
├── api/
│   ├── stream.py       WS /v1/stream and ConnectionBridge (one per connection)
│   └── health.py       /internal/health, /internal/readiness
├── domain/             no I/O
│   ├── protocol.py     PUBLIC_TOPICS, client messages, event/control frames
│   └── session.py      LocalTokenSessionValidator, cookie/bearer extraction
├── events/
│   ├── published.py    empty: publishes nothing
│   └── subscribed.py   the bus-side allow-list
├── models/             scaffold package; empty
└── repository/         scaffold package; empty (owns no data)
```

Shared packages: `nova-eventbus-sdk` (`BoundEventBus`, NATS), `nova-contracts`
(`EventEnvelope`), `nova-observability` (logging, metrics).

## Observability

*(Added 2026-10-16, SAD 15 §9.1 items 9 and 10.)*

**Metrics**, scraped from `/internal/metrics`. A topic a client merely *names*
is never a label; a topic is labeled only once it is in `PUBLIC_TOPICS`, and
anything else is `other`.

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `ws_gateway_connections_total` | counter | `outcome` | `accepted` or `unauthenticated` handshakes |
| `ws_gateway_open_connections` | gauge | — | Connections open now |
| `ws_gateway_client_messages_total` | counter | `outcome` | `subscribe`, `unsubscribe`, `malformed`, `topic_not_allowed` |
| `ws_gateway_frames_total` | counter | `topic`, `outcome` | `queued`, `dropped_slow_client`, `undeliverable` |
| `ws_gateway_bus_subscribe_refused_total` | counter | `topic` | A public topic the bus-side list refused: a configuration bug |

**Logs** (JSON, via `nova-observability`). Every line about a connection
carries its `connection_id`; every line about an event also carries the
event's `event_id` and `correlation_id`.

| Message | Level | When |
|---|---|---|
| `connection refused` | info | Handshake without a valid session; nothing was subscribed |
| `client connected` / `client disconnected` | info | Lifecycle; the latter carries `topics` and `dropped_frames` |
| `client message rejected` | info | Malformed client message |
| `subscription refused` | info | Topics outside `PUBLIC_TOPICS`; at most 10 names, 120 characters each, are repeated |
| `subscribed` / `unsubscribed` | info | Carries the topics acknowledged |
| `client too slow; frame dropped` | warning | The connection's queue was full |
| `undeliverable event dropped` | warning | The envelope could not be encoded |
| `public topic is not bus-subscribable; check events/subscribed.py` | error | The two allow-lists disagree |

**Not built: traces.** No span is created and no trace context crosses the
bus. SAD 15 §9.1 item 10 asks for both; propagation across the Event Bus
envelope is a contract decision, recorded as open in the Phase 4 closure
matrix.

## Testing

```bash
uv run --package ws-gateway pytest services/ws-gateway/tests          # default tier
uv run --package ws-gateway pytest services/ws-gateway -m real_infra  # real NATS
```

The default tier replaces the bus with a recording fake.
`tests/integration/test_stream_real_nats.py` (`real_infra`, added 2026-10-16)
runs a real uvicorn server and a real WebSocket client against a real NATS:
delivery, the public allow-list and unsubscribe are all decided at the broker.
It is in `real-infra-checks.yml`'s matrix.
