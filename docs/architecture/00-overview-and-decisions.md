# NOVA Software Architecture Document (SAD) — Overview & Architecture Decision Records

Status: **Draft v1 — pending approval before Phase 1 implementation begins.**

This document set is the official engineering blueprint for NOVA, derived strictly from
the [NOVA Project Bible](../bible/README.md) (20 parts + system instruction). Every
architectural choice below is traceable to a Bible requirement. Where the Bible is
ambiguous, redundant, or silent, this document makes an explicit decision and records
the reasoning as an Architecture Decision Record (ADR) rather than inventing behavior
silently.

## How to read this document set

| # | Document | Bible requirement item |
|---|----------|------------------------|
| 01 | [Technology Stack](01-technology-stack.md) | Stack + reasoning |
| 02 | [Repository & Folder Structure](02-repository-and-folder-structure.md) | Repo structure + folder hierarchy |
| 03 | [Backend Architecture](03-backend-architecture.md) | Backend architecture |
| 04 | [Frontend Architecture](04-frontend-architecture.md) | Frontend architecture |
| 05 | [Desktop Application Architecture](05-desktop-architecture.md) | Desktop app architecture |
| 06 | [AI Layer Architecture](06-ai-layer-architecture.md) | AI layer architecture |
| 07 | [Database Architecture](07-database-architecture.md) | Database architecture |
| 08 | [Memory Architecture](08-memory-architecture.md) | Memory architecture |
| 09 | [Event Bus Architecture](09-event-bus-architecture.md) | Event bus architecture |
| 10 | [Inter-Engine Communication Flows](10-inter-engine-communication.md) | Communication flow between every engine |
| 11 | [API Architecture](11-api-architecture.md) | API architecture |
| 12 | [Agent Architecture — NOVA Agent Operating System](12-agent-architecture.md) | Agent architecture |
| 13 | [Authentication & Security Architecture](13-auth-and-security.md) | Auth & security |
| 14 | [Deployment Architecture](14-deployment-architecture.md) | Deployment architecture |
| 15 | [Development Workflow](15-development-workflow.md) | Development workflow |
| 16 | [Testing Strategy](16-testing-strategy.md) | Testing strategy |
| 17 | [CI/CD Pipeline](17-cicd-pipeline.md) | CI/CD pipeline |
| 18 | [Local-First & Cloud Sync](18-local-first-and-cloud-sync.md) | Local-first with optional cloud sync |
| 19 | [Scalability Strategy](19-scalability-strategy.md) | Enterprise scalability strategy |
| — | [Engineering Roadmap](../roadmap/ENGINEERING_ROADMAP.md) | Phased implementation roadmap |

## Guiding constraints (non-negotiable, per the Bible)

1. **One mind, many organs.** The user must never perceive fragmentation (Part 1, Part
   20). Internally there can be dozens of engines; externally there is one NOVA.
2. **Every module is replaceable without redesigning the rest of the system** (Part 1,
   Part 20, and restated independently inside almost every engine's "Architectural
   Requirements" section). This is the single most repeated requirement in the entire
   Bible and it is the primary driver of the architecture below.
3. **Local-first, cloud optional.** NOVA must run at zero cost, fully offline, on a
   single user's machine, using local models (Part 7). Cloud and enterprise capability
   is an additive deployment mode, not a prerequisite.
4. **Model-agnostic.** No engine may hard-depend on a specific LLM provider (Part 7,
   Part 20 "AI Model Abstraction").
5. **Architecture over speed, scalability over simplicity** (Part 1, "First Principle").
6. **Everything is observable, explainable, and reversible** (Parts 8, 12, 14, 19).
7. **Design for 10x** (user directive, added after initial SAD approval — see below).

## The 10x Test

In addition to the six constraints above, every architectural decision in this
document set — existing or new — must satisfy one further question, per explicit
user instruction:

> "Will this still be the correct design if NOVA becomes ten times larger in five
> years? If the answer is no, redesign it before implementation."

This is stricter than ordinary "design for scale" advice: it is a mandatory
pre-implementation gate, not a background aspiration. Two concrete consequences
already reshape this document set as of this revision:

1. **Any interface an ADR relies on for future swappability must be an explicit,
   first-class contract with more than one intended implementation from day one** —
   never an implicit assumption that "it could probably be swapped later." ADR-006
   and ADR-007 exist because of this: the Event Bus and Graph Store were previously
   described only in prose as "swappable"; they are now promoted to named interfaces
   with a documented multi-backend contract.
2. **Any subsystem whose Bible specification names an explicit scale target must be
   designed against that target, not against initial load.** Part 4's "10,000
   micro-agents... without redesigning the core orchestration system" is the most
   extreme such target in the entire Bible. ADR-008 redesigns the Agent Orchestrator
   accordingly — as a standalone Agent Operating System, not an engine that happens to
   run agents.

Every ADR below has been re-reviewed against this test; ADR-006, 007, and 008 are the
result.

## Architecture Decision Records (ADRs)

### ADR-001 — Modular Monolith first, microservices-ready by construction

**Context.** The Bible demands both (a) that NOVA run entirely on a single personal
machine with zero infrastructure cost (Part 7 "Initial Zero Budget Strategy", Part 18
local-first), and (b) that the architecture scale to enterprise deployments with
"10,000 micro-agents" and services split across desktop, cloud, and robotics (Part 4
"Future Scalability", Part 19 "Scalability Strategy"). A pure microservices architecture
from day one would force every individual user to operate a Kubernetes cluster just to
talk to NOVA, which contradicts local-first. A pure monolith would contradict "every
subsystem must be replaceable."

**Decision.** Every engine (Memory, Knowledge, World Model, Reasoning, Planning, etc.)
is built as an independently versioned, independently testable **module** with a hard
boundary: it may only be called through its published interface (a Python protocol /
OpenAPI contract) and it may only communicate with other engines by publishing and
subscribing to events on the **Event Bus** (see [09](09-event-bus-architecture.md)) —
never through direct in-process imports of another engine's internals. In **local-first
mode**, all engine modules run inside a single host process (`nova-host`) with an
in-process event bus implementation. In **enterprise/cloud mode**, the exact same
modules are deployed as independent containers, and the event bus implementation is
swapped for a clustered broker — with zero changes to engine business logic. This
directly satisfies Part 20's requirement that "replacing any subsystem should not
require redesigning NOVA Core."

**Consequence.** Every engine's public interface must be defined as a versioned
contract (Protocol Buffers or Pydantic models shared via an internal `nova-contracts`
package) independent of whether the call happens in-process or over the network.

### ADR-002 — Engine consolidation (resolving Bible redundancy)

**Context.** The Bible defines the **World Model Engine** twice: Part 5 ("The Digital
Consciousness of NOVA") and Part 18 ("The Real Time Representation of Reality"). Part 18
is a strict superset — it repeats Part 5's concepts (digital environment graph, real
time sync, attention, situational awareness) and adds concrete object/state/relationship
modeling. Likewise, Part 2 ("AI Core & Cognitive Architecture") describes an executive
brain, thinking pipeline, and multi-model reasoning that Parts 7, 8, 9, and 19 later
formalize into four dedicated engines (AI Model Orchestration, Reasoning, Planning,
Executive Cognition).

**Decision.** This is treated as the Bible's own architecture *evolving on the page* —
earlier parts introduce a concept conceptually, later parts formalize it as a concrete
engine. The implementation targets the later, more concrete specification in every case,
and does not create duplicate services:

- **World Model Engine** = one service, implementing the union of Part 5 + Part 18.
- **"AI Core"** (Part 2) is realized as the *composition* of four concrete services:
  AI Model Orchestration Engine (Part 7), Reasoning Engine (Part 8), Planning Engine
  (Part 9), and Executive Cognition Engine (Part 19) — coordinated by NOVA Core (Part 20).
  There is no separate "ai-core" service; Part 2 is the narrative introduction to what
  Parts 7–20 build concretely.

**Consequence.** The canonical service inventory has 16 cognitive/functional engines
(below), not 21 — the Agent Orchestrator is additionally elevated out of this count
entirely by ADR-008, since NAOS is a standalone framework, not one more engine. This
is captured once here so no other document re-litigates it.

### ADR-003 — Polyglot by layer, not by engine

**Context.** Engines are AI/data-native (embeddings, graph traversal, LLM calls, agent
loops) — a domain where Python's ecosystem has no substitute. The desktop Companion that
performs OS-level perception (Part 11) and action (Part 12) needs low-level, safe,
performant system access. The Command Center UI (Part 1 "Visual Design Philosophy") must
render a continuously live, animated interface at 60fps.

**Decision.**
- **Cognitive engines & orchestration:** Python 3.12 (async-first, FastAPI, Pydantic v2).
- **Desktop Companion / OS sensors & actuators:** Rust, exposed to the rest of NOVA
  through the same Perception/Action event contracts as every other sensor.
- **Web & Desktop UI:** TypeScript, React, Tauri (Rust shell).
- **Infra glue (CI scripts, codegen):** TypeScript/Node or Python, whichever already owns
  the domain — never a third language introduced solely for tooling.

**Consequence.** Three toolchains must be unified under one monorepo task runner (see
[02](02-repository-and-folder-structure.md)); a shared `nova-contracts` package generates
typed clients for both Python and TypeScript from a single schema source of truth.

### ADR-004 — Event Bus is the only legal cross-engine channel

**Context.** Repeated verbatim across Parts 11, 12, 13, 18, and 20: "no module
communicates directly," "no subsystem communicates directly with sensors," "all
communication with knowledge passes through these interfaces."

**Decision.** Direct engine-to-engine calls are architecturally forbidden. All
cross-engine interaction is either (a) an asynchronous event on the bus, or (b) a
synchronous request/reply RPC routed *through* the bus's request/reply pattern (NATS
supports this natively), never a raw HTTP call from one engine's code straight into
another engine's module. This is enforced at the CI level via import-boundary linting
(see [15](15-development-workflow.md)).

### ADR-005 — NOVA never speaks except through the Communication Engine

**Context.** Part 4: "Departments never communicate directly with the user. Only NOVA
speaks to the user." Part 13 formalizes this as the Communication Engine.

**Decision.** No engine, agent, or capability may render user-facing output directly.
Every user-visible artifact (chat message, notification, HUD update, voice utterance) is
produced by emitting a structured `communication.intent` event that the Communication
Engine converts into channel-appropriate output, filtered through the Personality Engine
for tone/style consistency (Part 17). This is what guarantees "the illusion of a single
mind" (Part 1) at the architecture level, not just the prompt level.

### ADR-006 — Event Bus abstracted behind an explicit `EventBus` interface

**Context.** NATS JetStream was approved as the *initial* Event Bus implementation
(see [09](09-event-bus-architecture.md)), but per the user's explicit condition, it
must be "completely abstracted behind an internal interface so that it can later be
replaced with Kafka, RabbitMQ or another enterprise messaging platform without
affecting the rest of the system." ADR-004 already forbids direct engine-to-engine
calls; this ADR ensures the bus implementation itself, not just the pattern of using
it, is swappable.

**Decision.** `EventBus` is defined as an explicit Protocol in
`packages/nova-eventbus-sdk`, designed against the intersection of capabilities NATS,
Kafka, and RabbitMQ can all provide (publish, subscribe, request/reply, durable
replayable streams, consumer/queue groups) — never against a NATS-specific extension.
No engine, agent, or tool imports a broker's native client library directly; every
caller depends only on this Protocol:

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

**Consequence.** Backend selection becomes one configuration value
(`EVENT_BUS_BACKEND=nats|kafka|rabbitmq`), resolved by a small backend registry at
`nova-eventbus-sdk` startup — the same adapter pattern already used for
`ModelConnector` ([06](06-ai-layer-architecture.md)) and `VectorStore`
([07](07-database-architecture.md)). Writing a `KafkaEventBus` or `RabbitMQEventBus`
is a bounded, isolated task (implement the Protocol, pass the existing contract-test
suite per [16 §4](16-testing-strategy.md#4-contract-testing)) — never a cross-cutting
rewrite. See [09](09-event-bus-architecture.md) for the full interface and backend
comparison.

### ADR-007 — Graph persistence abstracted behind an explicit `GraphStore` interface

**Context.** Neo4j was approved as the *initial* graph database for the World Model
and Knowledge Graph, on the same condition: the persistence layer must stay
abstracted so alternative graph databases can be introduced later "without a
redesign."

**Decision.** `GraphStore` is defined as an explicit interface in a new shared
package, `packages/nova-graphstore-sdk`, promoted out of being an implicit detail of
`knowledge-engine`/`world-model-engine` — mirroring the `VectorStore` interface
already defined in [07 §3](07-database-architecture.md#3-vector-storage-pgvector):

```python
class GraphStore(Protocol):
    async def upsert_node(self, label: str, node_id: str, properties: dict) -> None: ...
    async def upsert_relationship(self, from_id: str, rel_type: str, to_id: str,
                                   properties: dict) -> None: ...
    async def query(self, query: GraphQuery) -> GraphResult: ...
    async def traverse(self, start_id: str, spec: TraversalSpec) -> GraphResult: ...
    async def delete_node(self, node_id: str) -> None: ...
```

`GraphQuery`/`TraversalSpec` are backend-agnostic builder types, not raw Cypher —
`knowledge-engine` and `world-model-engine` construct queries against these types, and
only the Neo4j adapter translates them to Cypher. This is what keeps the interface
honest: a query method that just accepted a raw Cypher string would silently couple
every caller to Neo4j regardless of what the Protocol claimed.

**Consequence.** Graph backend selection becomes one configuration value, and the
contract tests that validate `knowledge-engine`'s and `world-model-engine`'s graph
behavior run unchanged against any conformant `GraphStore` implementation (Memgraph,
ArangoDB, Amazon Neptune, or a future NOVA-specific engine). This directly answers the
10x Test for graph storage, whose Bible-stated target (Parts 10 & 18: "millions of
interconnected objects") is exactly the kind of requirement that may eventually demand
a different graph engine than the one that made sense at launch.

### ADR-008 — The Agent Orchestrator becomes the NOVA Agent Operating System (NAOS)

**Context.** Part 4 describes an "AI organization": a Chief-Executive-style
orchestrator, a standardized agent lifecycle, structured inter-agent messages, peer
review, conflict resolution, and an explicit scale target — "10 agents. 100 agents.
1,000 agents. 10,000 micro-agents... without redesigning the core orchestration
system." The original design in this SAD ([12 — Agent Architecture, v1](12-agent-architecture.md))
treated the orchestrator as one more `services/` engine running each agent as an
in-process asyncio task. Under the 10x Test, that design does not hold: it does not
survive a jump from tens of agents to hundreds or thousands, it provides no path to
distributed execution across machines (Part 20 "Distributed Execution": desktop,
cloud, home server, robot, vehicle), and it treats "agent" as a fixed set of
hand-authored Python classes rather than a genuinely pluggable, dynamically
loadable, versioned unit — the same mistake ADR-001 was written specifically to avoid
for engines.

**Decision.** The Agent Orchestrator is promoted from "one engine among seventeen" to
a standalone framework — the **NOVA Agent Operating System (NAOS)** — living in its
own top-level `agent-os/` directory, not `services/`, and designed explicitly as an
operating system for agents, not a task dispatcher. Full design in the rewritten
[12 — Agent Architecture](12-agent-architecture.md). In summary, NAOS has five parts:

- **Agent Kernel** — control plane only (process/instance management, scheduling,
  supervision trees, health monitoring). Contains no agent-specific logic, exactly as
  `nova-core` contains no engine-specific logic.
- **Agent SDK** — the standardized interface (lifecycle, capabilities, permissions,
  communication, metrics) every agent implements — the "syscall interface" of the
  Agent OS.
- **Agent Registry** — dynamic discovery, installation, versioning, hot load/unload,
  marketplace-ready, mirroring the Capability Engine's registry pattern (Part 15)
  applied to agents themselves.
- **Execution Backends** — pluggable strategies (in-process, subprocess, container,
  remote worker node) behind one `AgentExecutionBackend` interface, so scaling from
  10 to 10,000 agents, or distributing execution across machines, is a scheduling
  decision, never a rewrite.
- **Supervision Trees** — Erlang/OTP-style hierarchical supervision (domain
  supervisors overseeing leaf agents), giving Part 4's scale target a structural
  mechanism instead of a flat registry that would bottleneck at hundreds of agents.

**Consequence.** `services/agent-orchestrator` is removed from the Service Inventory
below; `agent-os/` becomes a new top-level pillar alongside `apps/`, `services/`,
`companion/` (see [02](02-repository-and-folder-structure.md)). The v1 (Phase 3)
implementation stays intentionally simple — in-process execution backend only, a flat
supervision tree, a filesystem-based registry — but every extension point needed to
reach the full design (subprocess/container/remote backends, multi-level supervision,
marketplace-style discovery) is an addition behind an existing interface, never a
redesign. This is the 10x Test applied to the one subsystem the Bible most explicitly
asks to scale by three orders of magnitude.

### ADR-009 — Embedding generation abstracted behind an explicit `EmbeddingProvider` interface

**Context.** Memory Engine and Knowledge Engine both need vector embeddings for
semantic search starting in Phase 1 ([Phase 1 design, 00 §New Architecture
Decisions](../design/phase-1/00-shared-foundations.md#new-architecture-decisions-this-design-introduces)).
The AI Model Orchestration Engine that will eventually route all model calls,
embeddings included, is a Phase 2 deliverable
([Roadmap](../roadmap/ENGINEERING_ROADMAP.md#phase-2--ai-core-model-orchestration--reasoning)).
Phase 1 cannot depend on a Phase 2 engine, and per the 10x Test, embedding generation
must not be hard-wired to one provider even temporarily — the same reasoning already
applied to the Event Bus (ADR-006) and Graph Store (ADR-007).

**Decision.** A new shared package, `packages/nova-embeddings-sdk`, defines an
`EmbeddingProvider` Protocol:

```python
class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> Embedding: ...
    async def embed_batch(self, texts: list[str]) -> list[Embedding]: ...
```

with a default `OllamaEmbeddingProvider` implementation — the same
interface-first-then-default-implementation pattern as ADR-006/007. Memory and
Knowledge Engines depend only on the Protocol, never on Ollama directly. When the AI
Model Orchestration Engine ships in Phase 2, it becomes a second `EmbeddingProvider`
implementation (routing through the Model Gateway for provider selection, cost
tracking, and privacy classification per
[06 §1](06-ai-layer-architecture.md#1-model-gateway-ai-model-orchestration-engine)),
swapped in via configuration — not a redesign of either engine.

**Consequence.** Embedding backend selection becomes one configuration value,
resolved by `nova-embeddings-sdk` at startup, exactly mirroring
`EVENT_BUS_BACKEND` (ADR-006) and the `GraphStore` backend selection (ADR-007).

### ADR-010 — One embedding model, standardized system-wide, for Phase 1

**Context.** Memory Engine, Knowledge Engine, and (transitively, via shared UUID
cross-referencing) World Model Engine all need embeddings. Running a different model
per engine would mean operating multiple local models simultaneously for no
architectural benefit, and would permanently forfeit the option of comparing
embeddings across engines directly (e.g., "does this memory relate to this knowledge
node" via vector similarity, not just a graph edge).

**Decision.** Phase 1 standardizes on a single embedding model, **`nomic-embed-text`
(768 dimensions)**, served locally via Ollama — chosen for strong open-benchmark
performance at its size, native Ollama support (zero-budget default per Part 7), and a
practical dimension count (768 keeps HNSW index memory and build time reasonable at
Phase 1's target row counts, versus 1536+-dimension alternatives). Every `VECTOR(...)`
column across Memory and Knowledge Engine schemas is `VECTOR(768)`. An
`embedding_model` column is present on every embedded table specifically so this
choice is changeable later without a migration disaster: a future model change is a
background re-embedding job, not a schema change.

**Consequence.** Any future change to the system-wide embedding model is an
operational migration (re-embed via the `EmbeddingProvider` interface, tracked per-row
via `embedding_model`), not an architectural one. Cross-engine embedding comparison
(Memory ↔ Knowledge) remains possible for as long as this standardization holds,
which is the explicit reason a single model was chosen over per-engine optimization.

**This log continues in [`adr/`](adr/README.md).** ADR-001 through ADR-010 above are
the foundational decisions made during design, before any code existed, and stay
recorded inline here. Starting with ADR-011, every significant architectural decision
made *during* a subsystem's implementation is filed as its own structured record
(Context/Problem/Alternatives considered/Decision/Consequences/Tradeoffs/Future
implications) in that directory — a standing requirement established on Phase 1's
completion, so that every major architectural decision in NOVA stays traceable years
from now regardless of format.

## Canonical Service Inventory

| Service / unit | Bible Part(s) | Layer |
|---|---|---|
| `nova-core` | 20 | Orchestration / nervous system |
| `executive-cognition-engine` | 19 | Orchestration |
| `cognitive-state-engine` | 6 | Orchestration |
| `ai-model-orchestration-engine` | 7 (realizes Part 2) | AI layer |
| `reasoning-engine` | 8 (realizes Part 2) | AI layer |
| `planning-engine` | 9 (realizes Part 2) | AI layer |
| `memory-engine` | 3 | Cognition / data |
| `knowledge-engine` | 10 | Cognition / data |
| `world-model-engine` | 5 + 18 | Cognition / data |
| `digital-twin-engine` | 16 | Cognition / data |
| `perception-engine` | 11 | Sensing |
| `action-engine` | 12 | Acting |
| `capability-engine` | 15 | Acting |
| `communication-engine` | 13 | Interaction |
| `personality-engine` | 17 | Interaction |
| `autonomy-engine` | 14 | Governance |
| `agent-os-kernel` (NAOS control plane — see ADR-008) | 4 | Multi-agent |
| `api-gateway` | 1 (implied — clean external APIs) | Presentation edge |
| `ws-gateway` | 1, 9, 13 | Presentation edge |
| `nova-companion` (Rust desktop sensor/actuator daemon) | 11, 12 | Sensing/Acting (desktop) |
| `web-client` | 1 | Presentation |
| `desktop-client` | 1 | Presentation |

22 NOVA-authored deployable units (excludes third-party infrastructure — NATS,
Postgres, Neo4j, Redis, MinIO — which are configured, not built). Enterprise/distributed
deployments additionally introduce `agent-os-worker` (remote execution backend nodes,
[12](12-agent-architecture.md)) and `nova-sync-service` ([18](18-local-first-and-cloud-sync.md))
as opt-in units, not part of the default local-first baseline. Each unit is described
structurally in [02](02-repository-and-folder-structure.md) and behaviorally in its
corresponding document above.
