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
| 12 | [Agent Architecture](12-agent-architecture.md) | Agent architecture |
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

**Consequence.** The canonical service inventory has 17 cognitive/functional engines
(below), not 21. This is captured once here so no other document re-litigates it.

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

## Canonical Service Inventory

| Service | Bible Part(s) | Layer |
|---|---|---|
| `nova-core` | 20 | Orchestration / nervous system |
| `executive-cognition-engine` | 19 | Orchestration |
| `cognitive-state-engine` | 6 | Orchestration |
| `event-bus` (infra, not a Bible "engine" but required by all) | 4, 11–20 | Infrastructure |
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
| `agent-orchestrator` + agent runtimes | 4 | Multi-agent |
| `nova-companion` (Rust desktop sensor/actuator daemon) | 11, 12 | Sensing/Acting (desktop) |
| `web-client`, `desktop-client` | 1 | Presentation |

19 deployable units total. Each is described structurally in
[02](02-repository-and-folder-structure.md) and behaviorally in its corresponding
document above.
