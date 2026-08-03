# 01 — Technology Stack

Every choice below follows the Decision Matrix method the Bible itself mandates for
NOVA's own Reasoning Engine (Part 8): accuracy, complexity, maintainability,
scalability, security, cost, and future compatibility. Where two options were close,
the reasoning is written out explicitly rather than asserted.

## 1. Languages & Runtimes

| Concern | Choice | Reasoning |
|---|---|---|
| Cognitive engines, agents, orchestration | **Python 3.12** | Unmatched ecosystem for LLM orchestration, embeddings, graph/vector tooling, data science. `asyncio` + structural pattern matching + typed generics make it viable for production services, not just prototyping. Every engine in Parts 3–20 is fundamentally an information-processing/AI workload — Python is the only language where the required libraries (tokenizers, ML runtimes, graph clients) are first-class. |
| Desktop Companion (OS-level Perception/Action sensors) | **Rust** | Part 11/12 require low-level, continuous OS observation (windows, clipboard, processes, filesystem) and safe execution of desktop actions. Rust gives memory safety without a GC pause (important for a process that must run silently, forever, in the background — Part 1 "Living Interface"), plus first-class OS APIs via `windows-rs` / `objc2` / `x11rb`. |
| Desktop application shell | **Rust (Tauri) + TypeScript (React)** | See ADR-003 and [05](05-desktop-architecture.md). Rejected Electron: ships a full Chromium + Node runtime per app (200MB+), weaker OS sandboxing, and no natural home for the Rust Companion — Tauri lets the same Rust workspace host both the shell and the sensor/actuator daemon. |
| Web command center | **TypeScript + React 18 + Vite** | Team-standard, largest talent pool, best real-time UI ecosystem (WebSocket/SSE, canvas/WebGL for the "living interface" visualizations in Part 1 and the graph/timeline views in Parts 3, 10, 18). |
| Infra/tooling scripts | Python or TypeScript, matching the owning package | No third scripting language introduced purely for glue. |

## 2. Backend Framework

| Concern | Choice | Reasoning |
|---|---|---|
| HTTP/WebSocket API surface per engine | **FastAPI** | Async-native, Pydantic v2 request/response validation doubles as the engine's typed contract (feeds `nova-contracts` codegen), automatic OpenAPI generation satisfies "every subsystem must expose clean APIs" (Part 1) with zero hand-written spec drift. |
| Internal (non-HTTP) service contracts | **Pydantic v2 models + Protocols**, versioned in `packages/nova-contracts` | Bible Part 20: "every subsystem registers itself... supported APIs." A single schema source generates both the Python types and the TS client, so a breaking change is a compile-time error in every consumer, not a runtime surprise. |
| Background job / long-running task execution | **Arq** (Redis-backed async task queue) | The Action Engine (Part 12) and Autonomy Engine (Part 14) need a durable, async-native queue with retries, priorities, and scheduling; Arq is asyncio-native (fits the rest of the stack) versus Celery's heavier, sync-first worker model. |
| Agent process runtime | Custom `nova-agent-runtime` on top of the Event Bus (see [12](12-agent-architecture.md)) | Part 4 defines a bespoke agent lifecycle (Idle → Assigned → Context Loading → ... → Learning → Idle) and structured inter-agent messages with confidence/priority/dependencies that do not map cleanly onto any off-the-shelf agent framework's assumptions. Building it natively keeps NOVA's orchestration semantics (peer review, conflict resolution, chief-executive delegation) first-class instead of working around a framework's opinions. |

## 3. Data Stores

| Store | Technology | Owning engines | Reasoning |
|---|---|---|---|
| System of record (relational) | **PostgreSQL 16** | nova-core, capability-engine, autonomy-engine, agent-orchestrator, planning-engine | ACID guarantees for permissions, capability registry, action ledger, plans, audit logs. Best-in-class open-source RDBMS; enterprise-proven. |
| Vector search | **pgvector** (Postgres extension), abstracted behind a `VectorStore` interface | memory-engine, knowledge-engine | Co-locating vectors with their relational metadata avoids a second store for v1 ("zero budget," Part 7) while the `VectorStore` interface (ADR-001) allows swapping to Qdrant/Milvus when scale demands a dedicated ANN index — see [19](19-scalability-strategy.md). |
| Knowledge / relationship graph | **Neo4j Community** (self-hosted) | knowledge-engine, world-model-engine | Parts 10 and 18 describe genuinely graph-shaped data (nodes, typed relationships, multi-hop traversal, contradiction detection across paths). Modeling this relationally would require recursive CTEs that don't scale; a native graph engine is the correct tool. |
| Working / short-term memory, cache, pub-sub side channel | **Redis 7** | memory-engine, cognitive-state-engine, event-bus (JetStream KV alt.), rate limiting | Sub-millisecond TTL-based storage matches Part 3's Working Memory ("extremely fast... leave automatically once the task finishes") and Part 6's Active Thoughts almost exactly. |
| Object / blob storage | **MinIO (self-hosted, S3-compatible)** locally, **AWS S3** in cloud mode | memory-engine (attachments), knowledge-engine (documents), backups | Same API in both deployment modes (local-first and cloud) — satisfies [18](18-local-first-and-cloud-sync.md) without a code fork. |
| Time-series / telemetry (Phase 2+) | **TimescaleDB** (Postgres extension) | world-model-engine (system health), nova-core (observability) | Avoids a fourth database engine for v1; graduates to a dedicated TSDB only if enterprise telemetry volume requires it (Part 19). |

## 4. AI / Model Layer

| Concern | Choice | Reasoning |
|---|---|---|
| Unified model access | **LiteLLM-style internal `ModelGateway`** implementing Part 7's "AI Model Abstraction" (`generate`, `reason`, `embed`, `stream`, `tool_call`) | One interface, N providers. Built as our own thin package (not a hard dependency on the LiteLLM project) so NOVA's confidence-scoring and cost/privacy metadata (Part 7 "Cost Management", "Privacy Management") are first-class fields, not bolted on. |
| Local inference runtime | **Ollama** (wraps llama.cpp) | Explicitly named in Part 7 ("Ollama becomes the default runtime"). Zero-cost, offline, GPU-accelerated where available. |
| Local model families | Llama, Qwen, Mistral, DeepSeek, Gemma, Phi (as named in Part 7) | Directly specified by the Bible. |
| Cloud model connectors | Anthropic, OpenAI, Google, Mistral AI, DeepSeek Cloud — each a thin `ModelConnector` plugin | Part 7 "Cloud Integrations": "adding a provider should require only a connector implementation." |
| Speech-to-text | **Whisper** (local, via faster-whisper) | Named explicitly in Part 7. |
| Text-to-speech | **Piper** (local) | Named explicitly in Part 7 ("offline speech synthesis"). |
| Embeddings | Local sentence-transformer models by default (e.g., BGE/E5 family) via Ollama/ONNX runtime; cloud embedding APIs as an optional connector | Keeps Knowledge/Memory embedding generation inside the local-first, zero-cost default. |

## 5. Event Bus / Messaging

| Concern | Choice | Reasoning |
|---|---|---|
| Local-first mode | **NATS (embedded server) with JetStream** | Single static binary, <20MB footprint, runs embedded in `nova-host` with no external ops burden — critical for "zero budget," single-machine local-first (Part 7, Part 18). Supports pub/sub, request/reply, and durable streams (needed for Part 11's "replay events," Part 20's "replay missed events" on recovery) out of the box. |
| Enterprise/cloud mode | **NATS JetStream cluster** (default) with a documented migration path to **Kafka/Redpanda** for organizations with existing Kafka infrastructure | Same client API in both deployment modes (see [09](09-event-bus-architecture.md)); Kafka is offered as an alternative backend behind the same `EventBus` interface, not a rewrite. |

## 6. Frontend Stack

| Concern | Choice | Reasoning |
|---|---|---|
| Framework | **React 18** + **TypeScript 5** | Concurrent rendering suits a UI that must stay live/animated (Part 1) while streaming dozens of independent real-time widgets (Parts 6, 9, 12–19 dashboards). |
| Build tool | **Vite** | Fast HMR needed for a UI this visually iterative. |
| State/data layer | **TanStack Query** (server state) + **Zustand** (UI/local state) | Clear separation between "state that mirrors the World Model / Event Bus" (Query, with WebSocket-driven cache invalidation) and ephemeral UI state (Zustand) — avoids the over-engineering of a global Redux store for data that is really just a live mirror of backend state. |
| Real-time transport | **WebSocket** (primary) with **SSE** fallback, both fed by a `ws-gateway` service that bridges the Event Bus to the browser | Browsers cannot subscribe to NATS directly in a security-safe way; the gateway is the one place browser auth and event-bus trust boundaries meet (see [13](13-auth-and-security.md)). |
| Visualization | **D3.js** for graphs/timelines (knowledge graph, world model, memory timeline — Parts 3, 10, 18), **Framer Motion** for the living/idle animations (Part 1) | Purpose-built tools for exactly the two categories of visualization the Bible repeatedly demands. |
| Design system | Internal `@nova/ui` package, Tailwind CSS + CSS variables for theming | Keeps every dashboard (11 separate "Live X Dashboard" widgets across Parts 6–20) visually and behaviorally consistent — reinforcing "one coherent intelligence" (Part 20) at the pixel level. |

## 7. Infrastructure & Platform

| Concern | Choice | Reasoning |
|---|---|---|
| Containerization | **Docker** | Universal baseline for both `docker compose` (local-first/self-hosted) and Kubernetes (enterprise). |
| Local orchestration | **Docker Compose** | Zero-ops single-machine deployment target for the default NOVA installation. |
| Enterprise orchestration | **Kubernetes** + **Helm** | Standard for the horizontal scale-out described in Part 19. |
| Infrastructure as Code | **Terraform** (cloud provisioning), **Ansible** (optional bare-metal/home-server provisioning) | Terraform is the de facto standard for reproducible cloud infra; Ansible covers the "home server" deployment target explicitly named in Part 1. |
| Secrets management | **SOPS + age** locally, **cloud KMS** (AWS/GCP) in enterprise mode, both behind one `SecretsProvider` interface | Zero-cost local default, upgrade path without code change. |
| Observability | **OpenTelemetry** (traces/metrics/logs) → **Prometheus** + **Grafana** (metrics/dashboards) → **Loki** (logs) → **Tempo** (traces) | Fully open-source, self-hostable stack that satisfies Part 20's "Observability" requirement ("metrics, logs, tracing, events... nothing important should become invisible") without vendor lock-in; managed equivalents (Grafana Cloud, Datadog) can be swapped in for enterprise customers via the same OTel exporters. |
| CI/CD | **GitHub Actions** | Repository is already GitHub-hosted; native integration with branch protection, environments, and the GitHub MCP tooling already used for this project. |
| Package registry | **GitHub Container Registry (GHCR)** for images, **GitHub Packages** for internal Python/npm packages | Avoids a third-party account dependency for a project still in the "zero budget" phase. |

## 8. Monorepo Tooling

| Concern | Choice | Reasoning |
|---|---|---|
| Task orchestration across Python + Rust + TS | **Turborepo** | Lightweight, fast remote-cacheable task graph; unlike Nx, it doesn't assume a single-language plugin ecosystem — it happily shells out to `uv run pytest`, `cargo test`, and `pnpm test` from one `turbo.json` pipeline. Chosen over Nx for lower configuration overhead given the project's polyglot-by-layer (not per-package) structure (ADR-003). |
| Python dependency/workspace management | **uv** (Astral) with a `uv.workspace` covering all `services/*` packages | Fastest resolver available, native workspace support (analogous to pnpm/Cargo workspaces), single lockfile for the whole Python surface. |
| TypeScript package management | **pnpm workspaces** | Disk-efficient, strict dependency isolation (prevents phantom cross-package imports — reinforcing ADR-001's module boundaries). |
| Rust workspace | **Cargo workspace** (`companion/`, `desktop-shell/`) | Standard. |

## 9. Summary Decision Table (at a glance)

| Layer | Primary Technology |
|---|---|
| Cognitive engines | Python 3.12 / FastAPI / Pydantic v2 |
| Agent runtime | Custom, on Event Bus |
| Relational data | PostgreSQL 16 |
| Vector search | pgvector → Qdrant (scale) |
| Graph data | Neo4j |
| Cache / working memory | Redis 7 |
| Object storage | MinIO → S3 |
| Event bus | NATS JetStream (embedded → clustered) |
| Local inference | Ollama (Llama/Qwen/Mistral/DeepSeek/Gemma/Phi) |
| Speech | Whisper (STT) / Piper (TTS) |
| Web frontend | React 18 / TypeScript / Vite |
| Desktop shell | Tauri (Rust + React) |
| Desktop sensors/actuators | Rust (`nova-companion`) |
| Containers | Docker / Compose / Kubernetes |
| IaC | Terraform / Ansible |
| Observability | OpenTelemetry / Prometheus / Grafana / Loki / Tempo |
| CI/CD | GitHub Actions |
| Monorepo | Turborepo + uv workspaces + pnpm workspaces + Cargo workspace |
