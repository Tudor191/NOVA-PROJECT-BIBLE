# 19 — Scalability Strategy for Future Enterprise Deployment

## 1. Scaling dimensions the Bible explicitly names

| Dimension | Bible source | Target this architecture supports |
|---|---|---|
| Number of concurrent agents | Part 4 "Future Scalability" | 10 → 100 → 1,000 → 10,000 micro-agents "without redesigning the core orchestration system" |
| Knowledge graph size | Part 10 "Performance Targets" | "Millions of interconnected knowledge objects without significant degradation" |
| World Model object count | Part 18 "Performance Targets" | "Relationship queries should scale to millions of objects" |
| Concurrent conversation sessions | Part 13 "Performance Targets" | "Thousands of concurrent conversation sessions in enterprise deployments" |
| Queued actions | Part 12 "Performance Targets" | "Thousands of queued actions while maintaining stable performance" |
| Installed capabilities | Part 15 "Performance Targets" | "Thousands of installed capabilities while maintaining fast search and execution" |

Every one of these is satisfiable *because* of ADR-001: each engine scales
independently, on the axis that actually matters for it, without the others needing to
change.

## 2. Per-engine scaling levers

| Engine | Bottleneck as load grows | Lever |
|---|---|---|
| `reasoning-engine` | Model inference latency/throughput | Horizontal pod scaling + GPU node pool autoscaling; request queue with priority (Executive Cognition's Cognitive Priority Matrix) |
| `agent-os-kernel` (NAOS) | Concurrent agent instances, distribution across machines | Purpose-built for this axis from day one (ADR-008): the kernel schedules agent instances onto pluggable execution backends — in-process (v1 default) → subprocess → container (Kubernetes Job/pod-per-instance) → remote `agent-os-worker` nodes — as concurrency grows toward Part 4's 10,000 micro-agents target, with zero change to agent implementations or the kernel's own scheduling logic. See [12](12-agent-architecture.md) for the execution-backend interface. |
| `memory-engine` / `knowledge-engine` | Vector search QPS, embedding volume | Swap `VectorStore` adapter from pgvector to **Qdrant** (sharded) — interface unchanged ([07 §3](07-database-architecture.md#3-vector-storage-pgvector)); read replicas for Postgres |
| `world-model-engine` / `knowledge-engine` (Neo4j) | Graph traversal depth/volume at millions of nodes | Neo4j causal clustering (read replicas); query result caching in Redis for hot traversal paths; graph partitioning by project/tenant for enterprise multi-tenancy |
| `event-bus` | Message throughput, consumer lag | NATS JetStream cluster scale-out; per-subject stream sharding (e.g., `perception.*` on its own high-throughput, low-durability stream separate from `planning.*`) |
| `communication-engine` / `ws-gateway` | Concurrent live sessions | Stateless horizontal scaling behind a sticky-session-aware load balancer; presence state in Redis Cluster, not in-process |
| `capability-engine` | Registry search over thousands of entries | Search index (Postgres full-text initially, OpenSearch if catalog size demands it later) — same adapter-swap pattern as vector storage |

## 3. Multi-tenancy model (enterprise)

- **Isolation level:** schema-per-tenant in Postgres, label/property-scoped
  (`tenant_id`) partitioning in Neo4j, and bucket-prefix isolation in object storage —
  chosen over fully separate database instances per tenant for operational simplicity
  at small-to-mid tenant counts, with a documented graduation path to instance-per-tenant
  for large/regulated customers who require it.
- **Noisy-neighbor protection:** per-tenant rate limits at the API Gateway
  ([11 §5](11-api-architecture.md#5-rate-limiting--quotas)) and per-tenant resource
  quotas in Kubernetes (`ResourceQuota`/`LimitRange` per namespace).
- **Cross-tenant guarantee:** every query path validated in integration tests to prove
  tenant A's Reasoning Engine call cannot retrieve tenant B's Memory/Knowledge, even
  under the shared-schema model.

## 4. Horizontal scale-out is opt-in complexity

Directly following Part 1's "whenever a conflict exists between simplicity and
scalability, scalability always wins" — but applied precisely: the *architecture* is
always scalable (every engine is independently deployable and horizontally
replicable by construction), while the *default deployment* stays as simple as
possible (single Postgres, single Neo4j, embedded NATS) until a real load signal
justifies turning a lever on. This avoids the Bible's other stated principle — never
implement shortcuts, but also never add complexity the current stage doesn't need —
being read as "run a 15-node cluster on day one," which the Bible does not ask for
(its own "Initial Zero Budget Strategy," Part 7, explicitly asks for the opposite at
launch).

## 5. Capacity planning signals

Each engine publishes standard load metrics (queue depth, p99 latency, error rate,
resource saturation) via OpenTelemetry ([01](01-technology-stack.md)); Grafana
dashboards define explicit scale-up thresholds per engine (e.g., `reasoning-engine`
scales out at sustained p99 queue wait > 2s), so scaling decisions in production are
signal-driven, matching Part 20's "Self Optimization" ("reduce latency... balance GPU
workloads") as an operational practice, not just an aspiration.

## 6. Future platform scale-out (beyond enterprise SaaS)

The Bible's "Future Evolution" sections (Parts 4, 11, 12, 18, 19, 20) describe
robotics fleets, planet-scale distributed AI, and swarm intelligence. This
architecture does not attempt to solve those today; it ensures they remain *reachable*
without a rewrite:

- New physical Perception/Action targets integrate as new Companion-style
  implementations of the same `Sensor`/`Actuator` traits ([05](05-desktop-architecture.md)) —
  a humanoid robot's sensor suite is architecturally the same shape as a laptop's.
- New Event Bus topology tiers (edge device → regional hub → global) are a NATS
  supercluster configuration, not an application change, because engines already only
  know about "the bus," never about network topology ([09 §7](09-event-bus-architecture.md#7-local-first-vs-enterprise-topology)).
- This is the concrete payoff of ADR-001 and ADR-004 held consistently through every
  other document in this SAD: scalability is not a phase bolted on at the end, it is
  the reason every module boundary was drawn the way it was drawn from Part 0 forward.
