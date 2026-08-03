# 02 — Repository Structure & Folder Hierarchy

## 1. Repository strategy: single monorepo

**Decision.** All deployable units from the [Service Inventory](00-overview-and-decisions.md#canonical-service-inventory)
live in one repository, `nova` (this repository will be renamed/expanded from
`NOVA-PROJECT-BIBLE`, or a sibling `NOVA` implementation repo will be created — a
decision for the user, noted in the Roadmap's Phase 0).

**Reasoning.** Part 1 states the codebase must "remain production ready at all times"
and support "thousands of developers eventually contributing." A monorepo:

- Makes ADR-004 (event-bus-only communication) enforceable by a single CI lint pass
  across every engine at once, instead of N separate repos with N separate lint configs
  that drift.
- Lets `nova-contracts` changes and their consumers land in one atomic PR (no
  cross-repo version-bump choreography).
- Matches how the Bible itself organizes the system: one architecture, many modules —
  a polyrepo would fight that model.

The tradeoff (large clone, coarser access control) is accepted: engine-level access
control, if ever required for enterprise contributors, is handled with `CODEOWNERS`,
not repo splitting.

## 2. Top-level layout

```
nova/
├── apps/                       # Deployable, user-facing applications
│   ├── web-client/             # React web command center
│   └── desktop-client/         # Tauri desktop shell (wraps web-client)
│
├── services/                   # Python cognitive engines — one package per engine
│   ├── nova-core/
│   ├── executive-cognition-engine/
│   ├── cognitive-state-engine/
│   ├── ai-model-orchestration-engine/
│   ├── reasoning-engine/
│   ├── planning-engine/
│   ├── memory-engine/
│   ├── knowledge-engine/
│   ├── world-model-engine/
│   ├── digital-twin-engine/
│   ├── perception-engine/
│   ├── action-engine/
│   ├── capability-engine/
│   ├── communication-engine/
│   ├── personality-engine/
│   ├── autonomy-engine/
│   ├── api-gateway/             # External REST surface (see 11)
│   └── ws-gateway/             # Browser <-> Event Bus bridge (see 04, 09, 13)
│
├── agent-os/                   # NOVA Agent Operating System (NAOS) — standalone
│   │                            # framework, a core architectural pillar (ADR-008),
│   │                            # not "one more engine." See 12.
│   ├── kernel/                  # Agent Kernel: process manager, scheduler,
│   │                            # supervision trees, health monitor — control plane only
│   ├── registry/                # Agent Registry: discovery, install pipeline,
│   │                            # versioning, hot load/unload
│   ├── sdk/
│   │   ├── python/              # nova-agent-sdk — the standardized Agent interface
│   │   └── rust/                # nova-agent-sdk-rs — for future performance-critical agents
│   ├── execution-backends/
│   │   ├── inprocess/           # v1 default — asyncio task in the kernel process
│   │   ├── subprocess/          # OS-process isolation
│   │   ├── container/           # Docker/Firecracker isolation
│   │   └── remote/              # Dispatches to an agent-os-worker node (distributed mode)
│   └── supervisors/              # Built-in domain supervisor agents (Engineering,
│                                  # Research, Operations, ...) — see 12 §9
│
├── agents/                     # Concrete agent packages (Part 4 categories), each built
│   │                            # against agent-os/sdk — see 12 §3 for the package format
│   ├── research-agent/
│   ├── architect-agent/
│   ├── backend-agent/
│   ├── frontend-agent/
│   ├── coding-agent/
│   ├── devops-agent/
│   ├── database-agent/
│   ├── security-agent/
│   ├── qa-agent/
│   ├── documentation-agent/
│   └── ...                     # one directory per Part 4 agent category, added incrementally
│
├── companion/                  # Rust OS-level perception/action daemon
│   ├── nova-companion/         # Cargo workspace root
│   ├── sensors/                # desktop, filesystem, clipboard, process, network sensors
│   └── actuators/               # mouse/keyboard/window/terminal actuators
│
├── packages/                   # Shared libraries, consumed by services/apps, never the reverse
│   ├── nova-contracts/         # Pydantic + generated TS types: the ONE schema source of truth
│   ├── nova-eventbus-sdk/      # EventBus interface (ADR-006) + default NATS implementation
│   ├── nova-eventbus-sdk-ts/   # TypeScript client for the same
│   ├── nova-graphstore-sdk/    # GraphStore interface (ADR-007) + default Neo4j implementation
│   ├── nova-vectorstore-sdk/   # VectorStore interface + default pgvector implementation
│   ├── nova-embeddings-sdk/    # EmbeddingProvider interface (ADR-009) + default Ollama implementation
│   ├── nova-observability/     # Shared OTel setup, structured logging, tracing decorators
│   ├── nova-auth/              # Shared auth/permission primitives (Python)
│   ├── nova-testkit/           # Shared test fixtures, event-bus test harness, fake model gateway
│   └── ui/                     # @nova/ui — design system (React components, Tailwind config)
│
├── infra/                      # Everything required to run NOVA anywhere
│   ├── docker/                 # Dockerfiles per service, docker-compose.local.yml
│   ├── k8s/                    # Helm charts, one per service + umbrella chart
│   ├── terraform/              # Cloud provisioning (per provider: aws/, gcp/)
│   ├── ansible/                # Bare-metal / home-server playbooks
│   └── observability/          # Grafana dashboards, Prometheus rules, Loki config
│
├── tools/                      # Dev tooling: codegen scripts, import-boundary linter, scaffolders
│
├── docs/
│   ├── bible/                  # The NOVA Project Bible (already committed)
│   ├── architecture/           # This SAD
│   └── roadmap/                # Engineering roadmap + phase tracking
│
├── .github/
│   └── workflows/              # CI/CD pipelines (see 17)
│
├── turbo.json                  # Monorepo task graph
├── pnpm-workspace.yaml
├── pyproject.toml              # uv workspace root
├── Cargo.toml                  # Rust workspace root
└── README.md
```

## 3. Anatomy of one engine (the repeatable unit)

Every entry under `services/` follows an identical internal structure — this
uniformity is what lets `tools/scaffold-engine.py` generate a new engine and what lets
CI apply identical lint/test/boundary rules to all of them without per-engine
configuration:

```
services/<engine-name>/
├── pyproject.toml
├── Dockerfile
├── README.md                   # Engine-specific docs: responsibility, owned events, owned APIs
├── src/
│   └── nova_<engine_name>/
│       ├── __init__.py
│       ├── main.py             # FastAPI app entrypoint (HTTP + lifespan-managed bus connection)
│       ├── api/                # HTTP route handlers (thin — delegate to domain/)
│       ├── domain/              # Core business logic — the actual engine intelligence
│       ├── events/
│       │   ├── published.py    # Every event type this engine emits (typed, from nova-contracts)
│       │   └── subscribed.py   # Every event type this engine consumes + handlers
│       ├── models/              # SQLAlchemy / Neo4j / Pydantic models owned by this engine
│       ├── repository/          # Data access layer (never imported outside this engine)
│       └── config.py
└── tests/
    ├── unit/
    ├── integration/             # Uses nova-testkit's in-memory event bus + test containers
    └── contract/                 # Validates published events against nova-contracts schemas
```

**Rule enforced in CI:** a file under `services/X/src` may only import from
`services/X/src/*`, `packages/*`, and standard/third-party libraries. It may never
import `services/Y/src/*` directly. Cross-engine interaction happens only via
`packages/nova-eventbus-sdk` (ADR-004). This is checked with an import-graph linter
(see [15](15-development-workflow.md)).

`agent-os/` and `agents/` are intentionally **not** instances of this template —
`agent-os/kernel` is control-plane infrastructure (see [12](12-agent-architecture.md)
for its internal shape) and `agents/<name>-agent` follows the Agent Package format
defined there, since an agent is a dynamically loadable unit, not an always-on FastAPI
service. The same import-boundary rule still applies at the framework level: nothing
under `agents/*` may import another agent's internals, and nothing outside
`agent-os/kernel` may import the kernel's internals — only its published API and the
Agent SDK.

## 4. `nova-contracts` — the schema source of truth

```
packages/nova-contracts/
├── schemas/
│   ├── events/                 # One file per event family (memory.*, world_model.*, ...)
│   ├── entities/                # Shared domain entities (Task, Agent, Memory, KnowledgeNode...)
│   └── api/                     # Cross-engine RPC request/response contracts
├── python/                      # Generated (or hand-authored) Pydantic models
├── typescript/                  # Generated TS types + zod schemas for the frontend
└── codegen/                     # Generation scripts run in CI to keep both in sync
```

Every event on the [Event Bus](09-event-bus-architecture.md) and every payload described
in [Inter-Engine Communication](10-inter-engine-communication.md) is defined exactly
once here.

## 5. Naming conventions

| Item | Convention | Example |
|---|---|---|
| Service directory | kebab-case, `<domain>-engine` suffix for cognitive engines | `memory-engine` |
| Python package | snake_case, `nova_` prefix | `nova_memory_engine` |
| Event topic | dot-namespaced, `<engine>.<entity>.<action>` | `memory.episodic.created` |
| TS package | `@nova/<name>` | `@nova/ui`, `@nova/eventbus-sdk` |
| Docker image | `ghcr.io/<org>/nova-<service>` | `ghcr.io/nova/nova-memory-engine` |
| Helm release | matches Docker image short name | `memory-engine` |
| Agent package | kebab-case, `<category>-agent` | `coding-agent` |
| Agent OS component | kebab-case under `agent-os/` | `agent-os/kernel`, `agent-os/registry` |

This structure is stable from Phase 0 through the enterprise scale-out phase — engines
move from `docker-compose.local.yml` to individual `k8s/` Helm releases with **no
change to their internal directory layout**, which is the concrete, filesystem-level
expression of ADR-001. `agent-os/` follows the same rule for a different axis of
scale: the number and distribution of *agents*, not engines — see
[12](12-agent-architecture.md) and [19](19-scalability-strategy.md) for how it scales
from a handful of in-process agents to hundreds of distributed ones without moving out
of this directory layout.
