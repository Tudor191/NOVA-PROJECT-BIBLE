# 09 — Event Bus Architecture

The Event Bus is the single most load-bearing piece of infrastructure in NOVA: ADR-004
makes it the *only* legal channel between engines, which means every requirement in
Parts 4, 11, 12, 13, 18, and 20 about "no module communicates directly" collapses to
"is the Event Bus correctly designed and enforced."

## 1. Technology

**NATS with JetStream**, run embedded (single binary, in-process) in local-first mode
and as a clustered deployment in enterprise mode — see [01](01-technology-stack.md) for
the comparison against Kafka. The same `nova-eventbus-sdk` client API is used in both
modes; only the connection URL and cluster topology differ.

| NATS core feature | Bible requirement it satisfies |
|---|---|
| Subject-based pub/sub | Part 20 "Event Bus... every subsystem publishes events, every subsystem subscribes to events" |
| Request/Reply | Synchronous cross-engine RPC (e.g., "retrieve relevant memories") without violating ADR-004 |
| JetStream (persistent streams) | Part 11 "Replay Events," Part 20 "replay missed events" on recovery |
| Consumer groups / queue subscriptions | Load-balanced processing across multiple instances of the same engine (enterprise scale-out, [19](19-scalability-strategy.md)) |
| Key-Value store (JetStream KV) | Lightweight alternative to Redis for small shared state, used sparingly |

## 2. Topic taxonomy

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

## 3. Delivery guarantees

| Category | Delivery mode | Rationale |
|---|---|---|
| Perception observations (high volume, low individual value) | At-most-once, non-durable subject | Part 11 "Event Filtering": most sensory events should never become permanent; durability here would be waste |
| Cognitive/planning/action events | At-least-once, JetStream durable stream, consumer acks | These drive state changes that must survive a crash (Part 20 "replay missed events") |
| User-facing communication events | At-least-once with idempotency key (`event_id`) | A duplicate delivery must never produce a duplicate message to the user |

## 4. Boundary enforcement

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

## 5. Local-first vs. enterprise topology

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

## 6. Observability

Every event is mirrored (sampled at 100% in development, configurable in production)
into the OpenTelemetry pipeline as a span event, giving the `nova.heartbeat`-driven
System dashboard (Part 20) a live, queryable event-throughput view without a bespoke
monitoring integration per engine.
