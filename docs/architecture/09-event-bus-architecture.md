# 09 — Event Bus Architecture

The Event Bus is the single most load-bearing piece of infrastructure in NOVA: ADR-004
makes it the *only* legal channel between engines, which means every requirement in
Parts 4, 11, 12, 13, 18, and 20 about "no module communicates directly" collapses to
"is the Event Bus correctly designed and enforced." Per **ADR-006**, the bus itself is
also required to be replaceable — this document leads with that contract, then
describes the default implementation.

## 1. The `EventBus` interface (the contract, not the technology)

Every engine, agent, and gateway in NOVA depends on this Protocol, defined once in
`packages/nova-eventbus-sdk`, and **never** on a broker's native client library:

```python
class EventBus(Protocol):
    async def publish(self, envelope: EventEnvelope) -> None: ...

    async def subscribe(self, subject_pattern: str, handler: EventHandler,
                         *, queue_group: str | None = None) -> Subscription: ...

    async def request(self, subject: str, payload: BaseModel,
                       *, timeout_ms: int) -> EventEnvelope: ...

    async def open_stream(self, subject_pattern: str, *, durable_name: str,
                           replay: ReplayPolicy) -> EventStream: ...

    async def health(self) -> BusHealth: ...
```

This interface was deliberately scoped to the *intersection* of what NATS JetStream,
Kafka, and RabbitMQ can all provide — pub/sub, request/reply, durable replayable
streams, consumer/queue groups — rather than to any one broker's unique extensions.
Backend selection is one configuration value:

```
EVENT_BUS_BACKEND=nats      # default — see §2
EVENT_BUS_BACKEND=kafka     # packages/nova-eventbus-sdk/backends/kafka.py
EVENT_BUS_BACKEND=rabbitmq  # packages/nova-eventbus-sdk/backends/rabbitmq.py
```

resolved by a small backend registry at SDK startup — the same adapter pattern used
for `ModelConnector` ([06](06-ai-layer-architecture.md)) and `VectorStore`/`GraphStore`
([07](07-database-architecture.md)). A new backend is a bounded, isolated
implementation task: satisfy the Protocol above, pass the shared contract-test suite
([16 §4](16-testing-strategy.md#4-contract-testing)), done — never a cross-cutting
rewrite of engine code, which is exactly what the user's approval condition on this
component requires.

## 2. Default implementation: NATS JetStream

**NATS with JetStream**, run embedded (single binary, in-process) in local-first mode
and as a clustered deployment in enterprise mode — see [01](01-technology-stack.md) for
the comparison against Kafka. This is the `nats` backend behind the `EventBus`
interface above; only the connection URL and cluster topology differ between
local-first and enterprise deployment, and neither is visible to callers.

| NATS core feature | `EventBus` method it backs | Bible requirement it satisfies |
|---|---|---|
| Subject-based pub/sub | `publish` / `subscribe` | Part 20 "Event Bus... every subsystem publishes events, every subsystem subscribes to events" |
| Request/Reply | `request` | Synchronous cross-engine RPC (e.g., "retrieve relevant memories") without violating ADR-004 |
| JetStream (persistent streams) | `open_stream` | Part 11 "Replay Events," Part 20 "replay missed events" on recovery |
| Consumer groups / queue subscriptions | `subscribe(..., queue_group=...)` | Load-balanced processing across multiple instances of the same engine (enterprise scale-out, [19](19-scalability-strategy.md)) |
| Key-Value store (JetStream KV) | (implementation detail, not exposed on the interface) | Lightweight alternative to Redis for small shared state, used sparingly |

## 3. Alternative backends: when to switch

| Trigger | Recommended backend | Why |
|---|---|---|
| Default — local-first, self-hosted, small-to-mid enterprise | NATS JetStream | Lowest operational overhead, embeds for zero-ops local mode ([01](01-technology-stack.md)) |
| Customer already operates a Kafka platform / needs Kafka-native tooling (Kafka Connect, ksqlDB, existing SRE runbooks) for compliance or integration reasons | Kafka (via `packages/nova-eventbus-sdk/backends/kafka.py`) | Satisfies enterprise procurement/compliance requirements without forking engine code |
| Customer standardized on AMQP / RabbitMQ for existing service-mesh tooling | RabbitMQ (via `.../backends/rabbitmq.py`) | Same principle — organizational fit, not a NOVA technical need |
| Sustained message throughput exceeds what a well-tuned NATS JetStream cluster serves at acceptable latency | Kafka | Kafka's log-structured storage and partitioning model outperforms NATS at extreme sustained throughput; this is a capacity decision, evaluated against the signals in [19 §5](19-scalability-strategy.md#5-capacity-planning-signals) |

No backend switch requires touching a single engine's `domain/` or `events/` code —
this is the entire point of ADR-006, verified by running the full engine test suite
against each backend implementation in CI ([16](16-testing-strategy.md),
[17](17-cicd-pipeline.md)).

## 4. Topic taxonomy

Subjects are dot-namespaced `<engine>.<entity>.<action>`, always matching a schema
defined in `packages/nova-contracts/schemas/events/`:

```
perception.<source>.observed              # perception.desktop.observed, perception.voice.observed
world_model.object.created|updated|deleted
world_model.context.changed
memory.<type>.created|updated|decayed      # memory.episodic.created
memory.consolidation.completed
knowledge.node.created|updated
knowledge.contradiction.detected
reasoning.session.started|step.completed|result
planning.task_graph.created|updated|completed
agent.<agent_id>.assigned|started|completed|failed
action.execute|result|rollback
capability.installed|updated|health_changed
communication.intent.received|response.ready
autonomy.decision.made|approval.requested
digital_twin.profile.updated
executive.priority.changed|attention.shifted
nova.heartbeat|nova.mode.changed|nova.module.status_changed
```

Every published event carries a common envelope (defined once in `nova-contracts`):

```python
class EventEnvelope(BaseModel):
    event_id: UUID
    subject: str
    occurred_at: datetime
    source_engine: str
    correlation_id: UUID        # ties an entire request lifecycle together end-to-end
    causation_id: UUID | None   # the event that directly caused this one
    confidence: float | None
    payload: dict               # validated against the subject's registered schema
```

`correlation_id`/`causation_id` give every pipeline (e.g., the sequence diagram in
[03 §3](03-backend-architecture.md#3-request-lifecycle-the-thinking-pipeline-concretely))
a reconstructable causal chain — this is what powers the Reasoning/Executive
"Explainability" panels (Parts 8, 14, 19) without bolting on separate tracing logic.

## 5. Delivery guarantees

| Category | Delivery mode | Rationale |
|---|---|---|
| Perception observations (high volume, low individual value) | At-most-once, non-durable subject | Part 11 "Event Filtering": most sensory events should never become permanent; durability here would be waste |
| Cognitive/planning/action events | At-least-once, JetStream durable stream, consumer acks | These drive state changes that must survive a crash (Part 20 "replay missed events") |
| User-facing communication events | At-least-once with idempotency key (`event_id`) | A duplicate delivery must never produce a duplicate message to the user |

## 6. Boundary enforcement

- Every engine connects to the bus only through `nova-eventbus-sdk`, which requires a
  declared **publish allow-list** and **subscribe allow-list** per engine (declared in
  that engine's `events/published.py` / `subscribed.py` and checked against
  `nova-contracts` at CI time). An engine cannot publish an undeclared subject even by
  accident.
- The `ws-gateway` service is the **only** component allowed to bridge bus subjects to
  a browser/desktop client, and it does so through a per-connection subscription
  allow-list derived from the authenticated user's permissions ([13](13-auth-and-security.md))
  — this is what keeps ADR-005 ("NOVA never speaks except through the Communication
  Engine") true even though the frontend is, mechanically, "subscribed to the bus": it
  only ever receives already-finalized `communication.*` events plus read-only
  telemetry, never raw internal engine chatter.

## 7. Local-first vs. enterprise topology

```mermaid
flowchart TB
    subgraph Local-first (single machine)
    NH[nova-host process] --- EB1[(Embedded NATS + JetStream)]
    end
    subgraph Enterprise / cloud
    E1[memory-engine pod] --- EB2[(NATS JetStream cluster)]
    E2[knowledge-engine pod] --- EB2
    E3[... every engine pod] --- EB2
    EB2 --- EB2b[(Cross-region mirror, optional)]
    end
```

Both topologies speak the identical wire protocol and subject taxonomy; the only thing
that changes between them is the JetStream cluster size and the presence of a
cross-region mirror (see [19](19-scalability-strategy.md)) — no engine code is aware of
which topology it is running in.

## 8. Observability

Every event is mirrored (sampled at 100% in development, configurable in production)
into the OpenTelemetry pipeline as a span event, giving the `nova.heartbeat`-driven
System dashboard (Part 20) a live, queryable event-throughput view without a bespoke
monitoring integration per engine.
