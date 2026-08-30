# NOVA Engineering Roadmap

Status: **Draft v2.0 — companion document to the [Software Architecture Document](../architecture/00-overview-and-decisions.md). Technology stack, Event Bus (ADR-006), Graph Store (ADR-007), Agent Architecture (ADR-008), Embedding Provider (ADR-009), and the standardized embedding model (ADR-010) approved. Phase 0 is implemented. Phase 1 is implemented and Gate-Reviewed (Go). Phase 2A — AI Model Orchestration Layer — is implemented and Gate-Reviewed (Go), approved by the user. Phase 2B — Reasoning Engine — is implemented and Gate-Reviewed (Go), approved by the user. Phase 2C — Executive Cognition (minimal) — is implemented and Gate-Reviewed (Go), approved by the user.** `ai-model-orchestration-engine` built at production-grade per the [Phase 2A design package](../design/phase-2a/README.md), with the [Architecture Review Report](architecture-reviews/phase-2a-ai-model-orchestration.md), the canonical [AI Model Orchestration Philosophy](../architecture/21-ai-model-orchestration-philosophy.md), structured ADRs (ADR-020 through ADR-026, [index](../architecture/adr/README.md)), and the formal [Phase 2A Gate Review](architecture-reviews/phase-2a-gate-review.md) filed. `reasoning-engine` built at production-grade per the [Phase 2B design package](../design/phase-2b/README.md), with the [Architecture Review Report](architecture-reviews/phase-2b-reasoning-engine.md) and the formal [Phase 2B Gate Review](architecture-reviews/phase-2b-gate-review.md) filed. `executive-cognition-engine` built at production-grade per the [Phase 2C design package](../design/phase-2c/README.md), with the [Architecture Review Report](architecture-reviews/phase-2c-executive-cognition-engine.md) and the formal [Phase 2C Gate Review](architecture-reviews/phase-2c-gate-review.md) filed — including the discovery and fix of a cross-engine Alembic version-table collision affecting all six engines built to date, found during this phase's own real-Postgres verification. **[ADR-025](../architecture/adr/ADR-025-personal-edition-is-the-flagship.md) establishes the Personal Edition as NOVA's permanent flagship and reference implementation, binding on every phase from here forward. [ADR-026](../architecture/adr/ADR-026-reasoning-engine-cognitive-bridge-not-isolated.md) establishes the Reasoning Engine's boundary ahead of its own design work. [ADR-027](../architecture/adr/ADR-027-executive-cognition-coordinates-never-owns-intelligence.md) establishes the Executive Cognition Engine's boundary ahead of its own design work; [ADR-028](../architecture/adr/ADR-028-executive-cognition-defers-to-specialized-engine-authority.md) and [ADR-029](../architecture/adr/ADR-029-executive-cognition-optimizes-long-term-user-objectives.md) add two further permanent principles (epistemic deference to specialized engines; long-term-objective optimization as a Personal Edition default), both implemented and verified this phase. Phase 2D — originally scoped as a single, undifferentiated "Give NOVA a Voice" milestone — has been expanded into a full pre-implementation architectural blueprint at the user's direction and restructured into four sub-phases (2D-A Voice & Communication Foundation, 2D-B Identity & Presence, 2D-C Conversation Intelligence, 2D-D Personal Companion): see the [Phase 2D Master Architectural Blueprint](../design/phase-2d/00-master-blueprint.md), [NOVA Human Interaction Principles](../architecture/22-nova-human-interaction-principles.md), and [NOVA Personality Specification](../architecture/23-nova-personality-specification.md). **All three approved.** **Phase 2D-A — Voice & Communication Foundation — is implemented and Gate-Reviewed (Go), approved by the user; the real-Postgres-verification recommendation is not a blocker but remains an explicitly open, tracked item, to be closed as soon as a Docker-capable environment is available.** `personality-engine` and `communication-engine` built at production-grade per the [Phase 2D-A Technical Design Documents](../design/phase-2d/README.md) (01 Communication Engine, 02 Personality Engine), with the [Architecture Review Report](architecture-reviews/phase-2d-a-voice-communication-foundation.md) and the formal [Phase 2D-A Gate Review](architecture-reviews/phase-2d-a-gate-review.md) filed — including the required, additive AI Model Orchestration Engine speech extension (`transcribe`/`synthesize`, `WhisperConnector`/`PiperConnector`), two new ADRs, [ADR-030](../architecture/adr/ADR-030-personality-stores-digital-twin-learns.md) (Personality stores, Digital Twin learns) and [ADR-031](../architecture/adr/ADR-031-subjective-experience-quality-is-a-first-class-requirement.md) (subjective experience quality as a NOVA-wide standing tiebreaker), and a post-Gate-Review API-consistency correction normalizing both engines' REST routes to the project-wide `/v1/<domain>/...` convention. **Phase 2D-B — Identity & Presence — is implemented and Gate-Reviewed (Go), pending the user's final approval.** `perception-engine` built at production-grade per the [Phase 2D-B Technical Design Document](../design/phase-2d/03-perception-engine.md), with the [Architecture Review Report](architecture-reviews/phase-2d-b-identity-presence.md) and the formal [Phase 2D-B Gate Review](architecture-reviews/phase-2d-b-gate-review.md) filed — including the required, additive AI Model Orchestration Engine biometric/wake-signal extension (`detect_wake_phrase`/`embed_voice`/`embed_face`/`estimate_gaze`) and World Model Engine's `ActiveContext.present_identities` extension, [ADR-032](../architecture/adr/ADR-032-identity-confidence-is-also-an-authorization-signal.md) (identity confidence is also an authorization signal, a NOVA-wide permanent principle), and a new permanent standing rule ("always verify the implementation before trusting the documentation," [15-development-workflow.md §9.0](../architecture/15-development-workflow.md)). **Cumulative Production SLOC crossed the 30,000 Project Health Review reminder threshold this phase (31,610 SLOC), flagged explicitly per the standing instruction — the user elected to perform the full Project Health Review before continuing.** The first [Project Health Review](architecture-reviews/project-health-review-2026-08.md) is complete: covers overall architecture assessment, SOLID/Clean Architecture/DDD boundary validation, ADR/Bible/documentation consistency, cross-engine dependency analysis, Event Bus/API/database/repository review, domain purity, error handling/logging/observability/configuration, security/privacy, CI/build pipeline, testing quality/coverage, complexity/duplication, and a dedicated Architectural Opportunities section — concluding **the architecture is healthy, no blocking issues found, recommend proceeding to Phase 2D-C** after a short, low-risk cleanup pass. The single most significant finding: `docs/architecture/16-testing-strategy.md` describes `testcontainers`-backed real-infrastructure test fixtures and an 85%-coverage CI gate that were never actually built in `nova-testkit` — the true root cause behind the real-Postgres-verification recommendation's repeated deferral, tracked now as its own named architectural opportunity rather than folded into the generic "Docker unavailable" explanation. Feature development is paused pending the user's review and approval of this report. The real-Postgres-verification recommendation itself remains open, now understood to require building `nova-testkit`'s missing fixtures first, not only a Docker-capable environment.

## How this roadmap is organized

Every phase builds strictly on the previous one's deliverables (no phase assumes an
engine that a later phase introduces). Phases are scoped so that **every phase ends
with a runnable, demonstrable increase in NOVA's capability** — never a phase that only
produces internal scaffolding with nothing observable at the end, per Part 9's
"Milestone System": "each milestone represents measurable progress."

**Standing requirement, established mid-Phase-2A (per [ADR-025](../architecture/adr/ADR-025-personal-edition-is-the-flagship.md)):**
NOVA's Personal Edition — built for one trusted user — is the permanent flagship and
reference implementation; Phases 7 and 8 below build a Commercial/Enterprise Edition
as a strictly *additive* deployment mode of the same codebase, never a redesign and
never at the Personal Edition's expense. Wherever a phase has latitude in what to
build first, the resolution order is **Personal Intelligence > Long-Term Memory >
Personal Automation > Natural Interaction** (ADR-025's permanent development-priority
order), not breadth of generic configurability.

**Standing requirement, established at the Phase 1 Gate Review:** every phase, on
completion, gets a formal Architecture Gate Review (architecture assessment, risk/debt/
scalability/security/reliability analysis, consistency reviews, dependency and SOLID/
DDD/Bible compliance verification, and a final Go/No-Go) before the next phase begins,
plus the full [engineering metrics](architecture-reviews/METRICS_TEMPLATE.md) set
(Production/total SLOC and percentage toward the 30,000/50,000 SLOC milestones,
module/service/engine/API/Event-Bus-subject/database-table counts, test counts and
coverage, ADR count, complexity and dependency metrics, ruff/mypy/import-linter
status — measured, never estimated). Filed in
`docs/roadmap/architecture-reviews/phase-N-gate-review.md`, alongside that phase's own
Architecture Review Report.

**Standing requirement, established at the Phase 2D-A checkpoint (per
[SAD 15 §8](../architecture/15-development-workflow.md#8-the-permanent-subsystem-lifecycle)):**
no subsystem's implementation ever begins immediately after a roadmap milestone.
Every engine, subsystem, or major architectural component follows the same fixed
sequence — Roadmap → Blueprint (if required) → Human/philosophical documents (if
required) → Technical Design Document → the user's explicit approval →
Implementation, layer by layer, each layer tested before the next begins →
Architecture Review → Gate Review → Engineering Metrics → the user's final approval
→ only then the next subsystem. Every TDD is structured per
[SAD 15 §9.0](../architecture/15-development-workflow.md#90-required-technical-design-document-contents)'s
required contents. Whenever multiple implementations satisfy a requirement equally,
[ADR-031](../architecture/adr/ADR-031-subjective-experience-quality-is-a-first-class-requirement.md)
requires preferring the one that produces the most natural, responsive, and
consistent user experience, without deviating from the approved architecture.

Complexity is rated Low / Medium / High / Very High, reflecting engineering effort and
architectural risk combined, not calendar time (calendar time depends on team size,
which is not yet decided).

| Phase | Name | Complexity | Producible outcome at the end |
|---|---|---|---|
| 0 | Platform Bootstrap | Medium | Empty-but-real monorepo; `nova-host` boots, does nothing yet, but boots correctly |
| 1 | Data & Memory Substrate | Very High | NOVA can store and retrieve memories, knowledge, and world objects, on a production-grade foundation every later engine builds on |
| 2A | AI Model Orchestration Layer | High | A single, provider-agnostic gateway can route a request to any local or cloud model, stream the response, call tools, and track cost — with zero UI, proven at the API level |
| 2B | Reasoning Engine | High | Given an objective, NOVA runs a real 13-step reasoning pipeline (Levels 1–2) and produces a confidence-scored result, calling models only through 2A |
| 2C | Executive Cognition (minimal) | Medium | Competing requests between the Orchestration and Reasoning engines are arbitrated by a real priority mechanism, not first-come-first-served |
| 2D | Give NOVA a Voice — 2D-A Voice & Communication Foundation, 2D-B Identity & Presence, 2D-C Conversation Intelligence, 2D-D Personal Companion | Very High | You can talk to NOVA by voice or text; it recognizes who's speaking, distinguishes being addressed from being mentioned, reasons before answering, stays personality-consistent across models, adapts to how you specifically like to communicate, and responds through a real (if minimal) web UI |
| 3 | Planning & the NOVA Agent Operating System | Very High | NOVA can take a real objective, plan it, delegate it through NAOS to agents, and execute real actions |
| 4 | Perception, Autonomy & Digital Twin | High | NOVA notices what you're doing on your machine and proactively assists, within trust boundaries you control |
| 5 | Desktop App & Living Interface | High | The actual JARVIS-like command center exists, on your desktop, visually alive |
| 6 | Executive Cognition & Full Orchestration | Very High | NOVA coordinates all engines as one coherent mind, not a pipeline of parts |
| 7 | Security, Governance & Enterprise Readiness | High | NOVA is safe to run for other people, not just its own builder |
| 8 | Scale-Out & Cloud/Enterprise Deployment | Very High | NOVA runs as a multi-tenant, horizontally scaled platform |

---

## Phase 0 — Platform Bootstrap

**Objectives**
- Stand up the monorepo exactly as specified in [02](../architecture/02-repository-and-folder-structure.md).
- Get `nova-core`'s boot sequence ([03](../architecture/03-backend-architecture.md)) running end-to-end with zero real engines behind it — proving the orchestration skeleton before any intelligence is built on top of it.
- Stand up the Event Bus, observability stack, and CI/CD pipeline so every subsequent phase inherits working infrastructure instead of building it ad hoc.

**Deliverables**
- Monorepo scaffold: `apps/`, `services/`, `agents/`, `companion/`, `packages/`, `infra/`, `tools/`, `docs/` as specified.
- `packages/nova-contracts` with the `EventEnvelope` schema and codegen pipeline (Python + TS) working.
- `packages/nova-eventbus-sdk` (Python) and `nova-eventbus-sdk-ts` wrapping embedded NATS JetStream.
- `services/nova-core` implementing the 7-phase boot sequence ([Part 20](../bible/part-20-nova-core.md)) against an empty module registry (phases 2–4 are no-ops until later phases populate them).
- `infra/docker/docker-compose.local.yml` bringing up Postgres, Neo4j, Redis, MinIO, NATS, Ollama.
- CI: `pr-checks.yml`, `build-and-scan.yml` functioning per [17](../architecture/17-cicd-pipeline.md), even with only `nova-core` to lint/test/build.
- Observability: OpenTelemetry wired through `nova-core`; a Grafana dashboard showing the heartbeat.
- `tools/scaffold-engine.py` producing a compliant empty engine from the template.

**Dependencies:** None — this is the first phase.

**Estimated complexity:** Medium (mostly known-quantity DevOps/scaffolding work; the one genuinely novel piece is the import-boundary linter enforcing ADR-004 from day one).

**Implementation order**
1. Repo scaffold + monorepo tooling (Turborepo, uv workspace, pnpm workspace, Cargo workspace).
2. `nova-contracts` + codegen.
3. `nova-eventbus-sdk` (embedded NATS wrapper) + import-boundary linter.
4. `nova-core` boot sequence skeleton + heartbeat.
5. `docker-compose.local.yml` for all backing stores.
6. CI/CD pipelines.
7. Observability skeleton (OTel + Grafana + Loki + Tempo, all self-hosted).

**Testing strategy**
- Unit tests for the boot-sequence state machine (phase ordering, failure handling).
- An integration test that boots `nova-host` against the full Compose stack and asserts a healthy heartbeat within N seconds.
- CI pipeline itself is the deliverable being tested — validated by intentionally breaking a lint rule / import boundary in a throwaway branch and confirming CI catches it.

**Acceptance criteria**
- `git clone` → `turbo run bootstrap` → `docker compose up` → `turbo run dev` results in a running `nova-host` reporting "System Ready" (Part 20 Phase 7) with zero errors, on a clean machine, with no API keys configured.
- A PR that imports one (placeholder) engine's internals directly from another fails CI via the import-boundary check.
- `tools/scaffold-engine.py demo-engine` produces a new engine that passes CI unmodified.

---

## Phase 1 — Data & Memory Substrate

Status: **Implemented, Gate Review passed (Go), phase closed.** See the
[Phase 1 Gate Review](architecture-reviews/phase-1-gate-review.md) — a formal
verification, run before Phase 2 began, that the foundation is strong enough to
support the rest of NOVA (20 sections: architecture assessment, risk/debt/scalability/
security/reliability analysis, API/Event-Bus/database/ADR consistency, dependency and
circular-dependency verification, SOLID/Clean-Architecture/DDD compliance, Bible
compliance, and a final Go/No-Go), plus the phase's
[engineering metrics](architecture-reviews/phase-1-gate-review.md#21-engineering-metrics)
(SLOC, module/API/test counts, coverage, ADR count, static analysis, dependency graph
— every completed phase reports these from Phase 1 onward, per
[METRICS_TEMPLATE.md](architecture-reviews/METRICS_TEMPLATE.md)). Three real gaps found
during the Gate Review were fixed as part of it (the three engines are now wired into
`infra/docker/docker-compose.local.yml` and into `build-and-scan.yml`'s CI matrix; test
coverage tooling was added) — see the Gate Review's §4 and §19 for detail. Memory,
Knowledge, and World Model Engines are the
foundation almost every later engine reads from or writes into — a design mistake
here is systemic, not local — so this phase was scoped and built as production-grade
throughout, not a lighter "storage and retrieval" pass. The full technical design
package ([docs/design/phase-1/](../design/phase-1/README.md): 00 — Shared Foundations
introducing ADR-009/010 and three new shared packages; 01 — Memory Engine; 02 —
Knowledge Engine; 03 — World Model Engine; 04 — Cross-Engine Integration) was approved
before implementation began and no design deviation occurred during the build beyond
one schema-supported repository method addition, recorded in the
[Architecture Review Report](architecture-reviews/phase-1-data-memory-substrate.md).
244 tests passing across the three engines, `ruff`/`mypy` clean, import-linter
contracts enforced. **One listed deliverable below (the internal CLI/admin API) was
not built** — see the Architecture Review Report's Known Limitations for why and
when to pick it up; every other listed deliverable is complete. See also the
[Memory/Knowledge/World Model boundary reference](../architecture/20-engine-responsibility-boundaries.md)
(now canonical for every future subsystem) and
[ADR-011 through ADR-019](../architecture/adr/README.md) for every significant
decision made during this phase's implementation.

**Objectives**
- Implement `memory-engine`, `knowledge-engine`, and `world-model-engine` as
  production-grade foundations, not minimal CRUD services — the cognitive intelligence
  (reasoning over this data) comes in Phase 2, but the data model, lifecycle, retrieval
  pipeline, and failure-recovery behavior built here must not need a redesign once
  Phase 2 through Phase 8 engines start depending on it.
- Prove the polyglot persistence strategy ([07](../architecture/07-database-architecture.md))
  end-to-end: relational, vector, and graph stores all working together behind their
  owning engines, including the cross-datastore consistency problem (Postgres + Neo4j,
  no shared transaction) solved once via a transactional-outbox-backed saga pattern and
  reused by both Knowledge and World Model Engines.
- Close two abstraction gaps the SAD didn't yet cover: embedding generation
  (ADR-009 — `EmbeddingProvider` interface, Ollama default) and a standardized
  system-wide embedding model (ADR-010 — `nomic-embed-text`, 768 dimensions).

**Deliverables**
- Three new shared packages, built first: `nova-vectorstore-sdk` (`VectorStore`
  interface, pgvector/HNSW default), `nova-graphstore-sdk` (`GraphStore` interface per
  ADR-007, Neo4j default), `nova-embeddings-sdk` (`EmbeddingProvider` interface per
  ADR-009, Ollama default) — see
  [00 §New shared packages](../design/phase-1/00-shared-foundations.md#new-shared-packages-this-design-requires).
- `memory-engine`: sensory intake → working → short-term → long-term pipeline; all 9
  memory type modules per [08](../architecture/08-memory-architecture.md) and
  [01](../design/phase-1/01-memory-engine.md), unified `memory_record` schema
  (discriminated by `memory_type`), CRUD + semantic/timeline search, consolidation
  worker, transactional outbox, no graph of its own (delegates relationships to
  Knowledge Engine — see [01 §5](../design/phase-1/01-memory-engine.md#5-graph-model)).
- `knowledge-engine`: Knowledge Graph in Neo4j, node/relationship CRUD, source
  attribution, confidence scoring, structural contradiction detection, full
  Raw→...→Strategic evolution state machine, node version history, Postgres-then-graph
  saga (see [02](../design/phase-1/02-knowledge-engine.md)).
- `world-model-engine`: object/relationship graph (merged Part 5 + Part 18 spec per
  ADR-002), event-driven object state updates, Redis-primary Active Context with a
  sub-20ms p95 context-request budget, World Simulation shipped as a stub interface
  only (see [03](../design/phase-1/03-world-model-engine.md)).
- The one real Phase 1 cross-engine integration (Memory ↔ Knowledge, fully tested) plus
  a synthetic event harness in `nova-testkit` so Perception-dependent code paths are
  fully tested before Phase 4's real Perception Engine exists (see
  [04](../design/phase-1/04-cross-engine-integration.md)).
- Event contracts for all `memory.*`, `knowledge.*`, `world_model.*` subjects
  registered in `nova-contracts`.
- A minimal internal CLI/admin API for manually inspecting memory/knowledge/world state
  (used through Phase 2 before the real UI exists). **Not yet built** — see the
  Architecture Review Report's Known Limitations and Future Improvements; each
  engine's own FastAPI `/docs` covers ad hoc per-engine inspection in the meantime.
- The full per-subsystem deliverable checklist
  ([SAD 15 §9](../architecture/15-development-workflow.md#9-per-subsystem-deliverable-checklist))
  satisfied for all three engines and all three new shared packages: architecture docs,
  sequence diagrams, component diagrams, API docs, unit tests, integration tests,
  performance benchmarks, failure-scenario tests, logging strategy, observability
  metrics — delivered as part of the implementation, not after it.
- An [Architecture Review Report](../roadmap/architecture-reviews/TEMPLATE.md) filed at
  `docs/roadmap/architecture-reviews/phase-1-data-memory-substrate.md`, required for
  this phase to be considered complete.

**Dependencies:** Phase 0 (Event Bus, `nova-core`, CI/CD, `nova-contracts`).

**Estimated complexity:** Very High — revised up from the original Medium rating.
Production-grade design across three foundational engines, a cross-datastore saga
pattern used by two of them, an embedding abstraction with a system-wide model
standardization decision, and the newly-mandatory full deliverable checklist (docs,
diagrams, benchmarks, failure-scenario tests, observability) for every subsystem
together represent materially more engineering and architectural risk than the
original CRUD-plus-search scope.

**Implementation order** (design package's own build order — followed as planned;
all steps below are complete)
1. `nova-vectorstore-sdk`, `nova-graphstore-sdk`, `nova-embeddings-sdk` — interfaces and
   default implementations, before any engine that depends on them.
2. Postgres schemas + Alembic migrations for all three engines (per-engine schema, per
   [07 §1](../architecture/07-database-architecture.md#1-store-to-engine-ownership-map)).
3. `memory-engine`: working/short-term (Redis + Postgres) first, since nothing
   downstream needs long-term yet.
4. `memory-engine`: long-term + pgvector search + consolidation worker + outbox.
5. `knowledge-engine`: Neo4j graph CRUD + semantic search + Postgres-then-graph saga.
6. `world-model-engine`: object graph + Active Context + event ingestion from the
   synthetic event harness (real Perception Engine input arrives in Phase 4).
7. Memory ↔ Knowledge integration, contract-tested end-to-end.
8. Contradiction detection (structural).

**Testing strategy**
- Unit tests per memory type module (retention rules, importance scoring) and per
  domain module in Knowledge/World Model.
- Integration tests against real Postgres/Neo4j/Redis via `nova-testkit` testcontainers,
  per [16 §3](../architecture/16-testing-strategy.md#3-integration-testing).
- Contract tests for every `memory.*`/`knowledge.*`/`world_model.*` event, and
  specifically for the Memory↔Knowledge integration loop
  ([04 §1](../design/phase-1/04-cross-engine-integration.md#1-memory--knowledge-integration-real-phase-1)).
- Failure-scenario tests for every documented failure mode (§17 of each engine's design
  doc): process crash mid-consolidation, process crash between the Postgres and Neo4j
  halves of the saga (assert exactly-once, not lost or duplicated), VectorStore/GraphStore
  unavailability, Redis unavailability for World Model's Active Context (fails fast, by
  design).
- Performance benchmarks asserting each engine's §15 targets, not just prose claims.
- A scripted scenario test: write 500 synthetic memories with controlled importance/recency, run the consolidation worker, assert the expected lifecycle-stage distribution.

**Acceptance criteria**
- A memory written via the admin API is retrievable by semantic search with reasonable relevance ranking within 200ms (p95) on a 100k-memory dataset (per [01 §15](../design/phase-1/01-memory-engine.md#15-performance-considerations)).
- A knowledge contradiction (two conflicting facts about the same node) is detected and flagged, not silently overwritten (Part 10).
- Killing and restarting `memory-engine` mid-consolidation, or killing the outbox dispatcher between the Postgres and Neo4j halves of a Knowledge/World Model write, resumes without data loss or duplicate application (Part 6 "Cognitive Memory"; [02 §17](../design/phase-1/02-knowledge-engine.md#17-failure-recovery)).
- Project Memory scoping works: retrieving `project_id=X` context returns only that project's memories.
- World Model's `world_model.context.request` responds within 20ms p95.
- The full per-subsystem deliverable checklist ([SAD 15 §9](../architecture/15-development-workflow.md#9-per-subsystem-deliverable-checklist)) is satisfied for all three engines and the three new shared packages, verified in the phase's Architecture Review Report.

---

## Phase 2 — AI Core

Per explicit user directive on approving the Phase 1 Gate Review: **AI Core is no
longer one implementation effort.** It is four sequential sub-phases — 2A, 2B, 2C,
2D — each gets its own Architecture Review Report, Gate Review, ADRs, and Project
Metrics (the same standing requirements established at Phase 1), and each is closed
before the next begins. This ordering was chosen specifically to **reduce coupling
between cognitive systems**: the AI Model Orchestration Layer (2A) is built and
proven as a pure intelligence-provider gateway *before* anything that reasons or
plans exists to depend on it, so that dependency can never accidentally run the other
way.

**New permanent engineering rule, effective from 2A onward (see
[ADR-020](../architecture/adr/ADR-020-sole-legal-llm-provider-channel.md)): no
subsystem may ever depend directly on an LLM/AI provider.** Every interaction with
any AI model — text generation, embeddings, vision, speech, anything — passes
exclusively through `ai-model-orchestration-engine`. No exceptions, and no
grandfathering: Memory Engine's and Knowledge Engine's existing direct Ollama
embedding calls (via `nova-embeddings-sdk`, built under ADR-009 before this engine
existed) are recorded as tracked migration debt in ADR-020, not silently exempted.

### Phase 2A — AI Model Orchestration Layer

**Objectives**
- Build the single, provider-agnostic gateway between NOVA and every intelligence
  provider (Bible Part 7) — and nothing else. Per Part 7's own "Architectural
  Requirements": this engine **must remain completely independent from Memory,
  Planning, Knowledge, Personality, World Model, Executive Cognition, Action, and
  Capabilities.** It serves only as the intelligence provider layer.
- Full design in [docs/design/phase-2a/](../design/phase-2a/README.md).

**Deliverables** — `ai-model-orchestration-engine`:
- Model Registry (name, version, provider, capabilities, context window, latency,
  cost, health — Part 7).
- Provider Abstraction (`ModelConnector` protocol: generate/stream/tool_call/embed),
  Ollama connector (default, zero-budget), one cloud connector (Anthropic) as proof
  the abstraction holds.
- Prompt Pipeline & Context Builder — a *provider-formatting* mechanism (fit
  pre-assembled, named context components into a chosen model's token budget and
  request format), explicitly **not** a context-*sourcing* mechanism (deciding what's
  relevant is Reasoning Engine's job, Phase 2B) — see the design doc's boundary
  section for the full reasoning.
- Tool Calling & Function Registry — a provider-agnostic tool-schema translation
  layer (register a tool's schema once, get it correctly formatted for whichever
  provider's tool-calling convention is in use); registering what a tool *does* is a
  future Capability Engine concern (Phase 3), not this engine's.
- Model Router (capability × historical success / (latency, cost) scoring, per
  [06 §1](../architecture/06-ai-layer-architecture.md#1-model-gateway-ai-model-orchestration-engine)),
  Local vs. Cloud execution policy, Fallback Strategy (Part 7).
- Streaming, Token Management, Cost Tracking (Part 7 "Cost Management"),
  Observability (per every prior engine's pattern).

**Dependencies:** Phase 1 infra (Postgres for the registry/cost-tracking tables),
Phase 0 (Event Bus, `nova-core`).

**Estimated complexity:** High — thirteen distinct capability areas in one engine,
and the independence boundary (§ above) is easy to erode by convenience if not
actively defended, the same discipline the World Model boundary required in Phase 1.

**Testing strategy**
- `FakeModelConnector`-driven integration tests for deterministic CI runs; a small,
  separate "live model smoke test" job (manually triggered, not on every PR) against
  real Ollama.
- A contract test proving connector-swap independence (`test_connector_swap.py`, per
  [06 §6](../architecture/06-ai-layer-architecture.md#6-independence-from-any-single-provider-verification)) —
  every domain behavior passes against a fake connector with zero code path touching
  a real provider SDK outside `connectors/*_connector.py`.

**Acceptance criteria**
- A scripted request completes correctly through both the Ollama and Anthropic
  connectors, verified at the API level — no UI required.
- Killing the preferred model mid-request triggers the documented fallback chain
  automatically (Part 7 "Fallback Strategy").
- Token/cost tracking for a completed request is queryable via API immediately after
  the request finishes.
- The import-linter contract set gains a fourth rule: no engine other than
  `ai-model-orchestration-engine` imports an LLM/embedding provider SDK directly
  (mirrors ADR-006/007's existing broker/graph-client rules).

### Phase 2B — Reasoning Engine

**Objectives**
- Implement Levels 1–2 of the 13-step reasoning pipeline
  ([06 §2](../architecture/06-ai-layer-architecture.md#2-reasoning-engine)),
  consuming Memory/Knowledge/World Model Engine context (Phase 1) and calling models
  *exclusively* through `ai-model-orchestration-engine` (ADR-020 — this is the first
  engine built under that rule with something to prove it against).

**Deliverables:** `reasoning-engine` — full pipeline for Levels 1–2, confidence
scoring (`{value, tier, evidence}`), Reasoning Memory writes to `memory-engine`.

**Dependencies:** Phase 2A (every model call routes through it), Phase 1 (Memory/
Knowledge/World Model to retrieve from).

**Estimated complexity:** High.

**Testing strategy:** Golden-scenario tests per
[16 §5](../architecture/16-testing-strategy.md#5-multi-agent--orchestration-testing)
(assert pipeline stage completion and confidence presence, not exact text); the
whole suite also runs against 2A's `FakeModelConnector` to keep CI deterministic.

**Acceptance criteria**
- Given a scripted objective via API, the pipeline runs end-to-end and produces a
  confidence-scored reasoning result, inspectable via API/logs and traceable by
  `correlation_id` — no UI required yet.
- Zero direct imports of any provider SDK anywhere in `reasoning-engine` (import-linter
  enforced, per 2A's new contract).

### Phase 2C — Executive Cognition (minimal)

**Objectives**
- The minimal viable slice of Part 19 needed once two AI-layer engines exist:
  arbitrate attention/priority between `ai-model-orchestration-engine` and
  `reasoning-engine` when both want resources simultaneously. **This is not** the
  full `executive-cognition-engine` of
  [Phase 6](#phase-6--executive-cognition--full-orchestration) (Goal Hierarchy,
  Delegation Engine, Meta Reasoning, cross-engine conflict resolution) — Phase 6
  *extends* the service this phase starts, once Planning, Autonomy, Personality, and
  Communication also exist to coordinate.

**Deliverables:** `executive-cognition-engine` (initial version) — Cognitive
Priority Matrix (urgency × importance × risk × learning value × resource cost, Part
6) applied to exactly two contending engines.

**Dependencies:** Phase 2A, Phase 2B.

**Estimated complexity:** Medium — small in scope by design; the point is standing
the service up correctly, not building its full feature set yet.

**Acceptance criteria**
- Two concurrent, competing requests from simulated callers are arbitrated
  correctly by the Priority Matrix (verifiable via test), never resolved by simple
  first-come-first-served ordering.

### Phase 2D — Give NOVA a Voice

Status: **Master architectural blueprint, [NOVA Human Interaction
Principles](../architecture/22-nova-human-interaction-principles.md), and [NOVA
Personality Specification](../architecture/23-nova-personality-specification.md)
all approved — see [`docs/design/phase-2d/`](../design/phase-2d/README.md).**
**2D-A (Voice & Communication Foundation)**'s two Technical Design Documents
([01 — Communication Engine](../design/phase-2d/01-communication-engine.md),
[02 — Personality Engine](../design/phase-2d/02-personality-engine.md)) are
approved, implemented, and Gate-Reviewed (Go) — see the top status line above
for the full 2D-A/2D-B/Project-Health-Review history. Per direct user instruction, this phase's original single-milestone
scope ("make NOVA's intelligence actually reachable by a person") was expanded and
restructured into four sub-phases, with two permanent governing documents filed
alongside it, before any Technical Design Document or implementation work began —
the same validate-the-architecture-first discipline Phase 2B and 2C were held to,
applied here to an entire phase's worth of engines at once.

**Objectives**
- What remains of the original "first conversation" milestone once the cognitively-
  pure engines above are built and proven independently: make NOVA's intelligence
  actually reachable by a person — and, per the expanded scope, make that first
  reachability already personal: NOVA recognizes who it's talking to, knows the
  difference between being addressed and being mentioned, and begins adapting to
  how this specific user likes to communicate from the very first sessions.

**Sub-phases** (full detail in the
[Master Blueprint](../design/phase-2d/00-master-blueprint.md)):

- **Phase 2D-A — Voice & Communication Foundation.** Builds `communication-engine`
  (conversation session model, text *and* voice channels, streaming, transport-level
  interruption handling, multilingual input capture) and `personality-engine`
  (core identity/values as a behavioral constraint layer, not a system prompt
  string, with consistency validation).
- **Phase 2D-B — Identity & Presence.** Builds `perception-engine` in deliberately
  minimal form — voice and camera-based presence/identity sensing only (speaker
  recognition, face recognition, presence/attention/gaze detection, wake logic,
  identity confidence) — implementing Bible Part 11's full Sensor Abstraction
  Layer lifecycle contract so Phase 4 can extend it with desktop sensors without a
  redesign.
- **Phase 2D-C — Conversation Intelligence.** Extends `communication-engine` with
  the behavioral/policy layer: silence and interruption policy, response-length
  adaptation, the Clarification Engine, emotional tone selection, session-scoped
  conversation memory, multilingual understanding with English-first response
  policy, and the addressee-detection decision (talking TO NOVA vs. talking ABOUT
  NOVA) that fuses 2D-B's raw signals into an actual judgment.
- **Phase 2D-D — Personal Companion.** Builds `digital-twin-engine` in deliberately
  minimal form — the Communication Profile domain and a conversation-scoped slice
  of Preference Evolution/Habit Detection only (of Bible Part 16's eleven eventual
  domains) — plus trust-development tracking and a user-configurable
  proactive-**communication** boundary (never proactive action, which stays
  Autonomy Engine's, Phase 4).

**Deliverables**
- `personality-engine`: core identity/values as a behavioral constraint layer (not a
  system prompt string), with consistency validation.
- `communication-engine`: conversation session model, text **and voice** channels,
  response streaming, silence/interruption/clarification policy, addressee
  detection.
- `perception-engine` (minimal — voice + face/presence modalities): Sensor
  Abstraction Layer, Identity Registry, wake/presence/attention signal publishing.
- `digital-twin-engine` (minimal — Communication Profile + conversation-scoped
  Preferences): preference learning from real session evidence, trust-development
  metric, proactive-communication boundary policy.
- `api-gateway` + `ws-gateway` minimal implementation ([11](../architecture/11-api-architecture.md)).
- `apps/web-client`: conversation panel (voice + text) plus a presence/identity
  indicator — other panels remain stubs — the first real UI.
- Prompt Orchestration assembly ([06 §4](../architecture/06-ai-layer-architecture.md#4-prompt-orchestration))
  pulling from Memory/Knowledge/World Model/Personality/Digital Twin, formatted for
  the chosen model via 2A's Context Builder.

**Dependencies:** Phases 2A + 2B + 2C complete.

**Estimated complexity:** Very High — revised up from the original High rating now
that this phase stands up two additional stateful engines (`perception-engine`,
`digital-twin-engine`) ahead of their originally-planned Phase 4 slot, on top of the
original "many independent engines must feel like one mind" challenge at the
user-facing surface.

**Testing strategy**
- Contract + integration tests as in Phase 1, extended to the four new/expanded
  engines.
- Addressee-detection accuracy tests: scripted scenarios distinguishing genuine
  address from mention-in-passing, tracking both false-positive and
  false-negative rates separately (per the Master Blueprint §11's asymmetric-cost
  risk).
- Preference-evolution discipline tests: a single contradicting data point must
  never flip a stored Communication Profile preference (Bible Part 16, enforced
  per the Master Blueprint §4.4).
- Degraded-mode failure tests: `personality-engine` or `digital-twin-engine`
  unavailable mid-response must fall back to safe defaults, never silence (Master
  Blueprint §11.7).
- E2E: "first-run onboarding → first successful conversation with memory recall"
  (the first golden path from
  [16 §6](../architecture/16-testing-strategy.md#6-end-to-end-testing)), now
  exercised over both text and voice.

**Acceptance criteria**
- A fresh install, zero API keys, can hold a coherent multi-turn conversation by
  voice or text using only local models.
- Asking about something mentioned three turns ago (or in a previous session) is
  answered correctly via memory retrieval (Part 3's "memory first principle"
  demonstrated, not just claimed).
- Personality stays recognizably consistent across at least two different underlying
  models (Ollama vs. Anthropic) for the same query style — the concrete test of Part
  17's core promise.
- Saying NOVA's name in a sentence not directed at it does not trigger a response;
  a genuine address, even without a wake word, is correctly recognized with
  reasonable confidence — the concrete test of the talking-TO-vs-ABOUT-NOVA
  principle.
- A returning user is recognized (voice or face) with an explicit confidence value,
  never a silent binary assumption.
- Every response is traceable via `correlation_id` through the full event chain in
  the observability stack.

---

## Phase 3 — Planning & the NOVA Agent Operating System (NAOS)

Status (as of 2026-08-18, see `docs/project-health/project-health-master.md`
§1 and each sub-phase's own Gate Review for full detail — not repeated
here):
- **3A** (`reasoning-engine` Multi-step recursion trigger) — Complete. [Gate Review](architecture-reviews/phase-3a-gate-review.md).
- **3B — Domain Foundation** (`planning-engine` Task Graph model, PR #2) — Complete, merged. [Gate Review](architecture-reviews/phase-3b-domain-foundation-gate-review.md).
- **3B — Decomposition Orchestration** (PR #7) — Complete, merged. [Gate Review](architecture-reviews/phase-3b-decomposition-orchestration-gate-review.md).
- **3B — Planning Persistence** (Postgres persistence, `GET`/`POST /v1/plans` API, `planning.task_graph.created`/`planning.decompose.request`, PR #18) — Complete, **merged into canonical `phase-3b-planning-domain` 2026-08-20** (squash commit `a72bd83f69354fa8d262b9c0d68a7cd9125dc8ce`), fully verified locally and via real GitHub Actions (24/24 checks green, including `real-infra (planning-engine)`: 10/10 real-Postgres tests passed). This closes TDD 3B's approved scope entirely except §6.1's `agent_os.task.completed` subscription, correctly deferred to Phase 3E. [Gate Review](architecture-reviews/phase-3b-planning-persistence-gate-review.md).
- **3C** (`capability-engine`) — Complete, merged (PR #8). [Gate Review](architecture-reviews/phase-3c-capability-engine-gate-review.md).
- **3D** (`action-engine`) — Implementation complete against all 7 of 7 acceptance criteria, CI green, PR #13 **merged into `phase-3b-planning-domain`** 2026-08-18 (squash commit `ac285bc3533fb24d0434d7675b8fc3af2db1d079`). [Gate Review](architecture-reviews/phase-3d-action-engine-gate-review.md).
- **3E** (`agent-os` + first agents + supervisor) — **Implementation complete on branch `phase-3e-agent-os` (head `60934ac`), not merged, no PR open, no CI run yet.** Gate verdict **CONDITIONAL-GO** (2026-08-29). Delivered: `agent-os/{kernel,registry,supervisors,sdk/python}`, all five Agent Packages under `agents/`, the `engineering` Supervisor, the `GoalsPort` real-RPC migration in both calling engines, and TDD 3B §6.1's `agent_os.task.completed` subscription (which this entry previously recorded as deferred to 3E — now built). Acceptance criteria: **3 of 5 Met** (#1 real-path E2E, #4 `GoalsPort` transparency, #5 manifest validation), **2 Met with disclosed narrowing** (#2 restart-resume and #3 hot-load are proven at unit + integration + real-Postgres level, not by a full-path E2E; #3 is version *pinning*, not concurrent execution of two bytecode versions — see [`16-3e-hot-load-design-decision.md`](../design/phase-3/16-3e-hot-load-design-decision.md)). The architectural decision pass (2026-08-19) that preceded implementation stands unchanged: all four forks (3E-1 through 3E-4) **approved**, plus two additional open items (`nova-auth`/`PermissionGrant` scope, `priority`'s critical-path-position formula) **resolved** — [`14-3e-agent-os-research.md`](../design/phase-3/14-3e-agent-os-research.md) and `08-tdd-3e-agent-os.md` §11 carry the full record. **Closure pass 2026-08-29: five of the six Gate Review conditions are closed; one remains.** Closed: `agents/*` now have a CI gate (`pr-checks.yml` runs `ruff check agents/` plus a per-package `mypy src && pytest tests` loop — per-package isolation is required because all five expose a module named `handler`); `agent-os` deployment is **ratified as a deferred obligation** (no Dockerfile, matrix entry or compose service is introduced by 3E — TDD 3E §15 shows criterion by criterion that none of §14's five requires one); all six TDD deviations are **ratified as explicit Phase 3E narrowings**; the ~30k SLOC [Project Health Review](architecture-reviews/project-health-review-2026-08-29.md) is conducted (**HEALTHY**; it does not discharge the 50k gate); and decisions D1–D4/D10–D12 are **verified absent** by a second independent search rather than invented. **Still open — the sole barrier to GO: no GitHub Actions run has ever executed against any Phase 3E commit**, because all three workflows trigger only on `pull_request`/`push: main` and no PR is open. [Gate Review](architecture-reviews/phase-3e-agent-os-gate-review.md) · [Project Health](../project-health/phase-3e.md).
- The gateway/web-client prerequisite (`docs/design/phase-3/03-gateway-web-prerequisite.md`) and `apps/web-client`'s Planning/Agent Activity panels remain **design-only**, no production code authorized yet.

**Objectives**
- Implement `planning-engine`, the **NOVA Agent Operating System** ([12](../architecture/12-agent-architecture.md), ADR-008) — Agent Kernel, Agent Registry, Agent SDK, and the `inprocess` execution backend — plus the first concrete agents, `action-engine`, and `capability-engine`. This is the point at which NOVA moves from "answers questions" to "does work," and where NAOS ships as a real but intentionally minimal instance of the full architecture in [12 §15](../architecture/12-agent-architecture.md#15-what-ships-in-phase-3-vs-what-the-architecture-already-supports).

**Deliverables**
- `planning-engine`: objective decomposition, Work Breakdown Structure, Task Graph data model + dependency/critical-path analysis, per [06 §3](../architecture/06-ai-layer-architecture.md#3-planning-engine).
- `agent-os/kernel`: process/instance management, Kernel Scheduler, health monitoring, the `inprocess` execution backend (only backend enabled this phase).
- `agent-os/sdk/python`: the `AgentHandler` Protocol, `AgentContext`, `AgentMessage` types — published in `nova-contracts`.
- `agent-os/registry`: filesystem-based discovery/install pipeline, versioning, Agent Package manifest validation.
- `agent-os/supervisors`: one supervisor (`engineering`) implemented to prove hierarchical supervision, peer review, and conflict-resolution escalation end-to-end before more supervisors are added in later phases.
- First agent set (as Agent Packages under `agents/`): `research-agent`, `coding-agent`, `qa-agent`, `architect-agent`, `documentation-agent` — five of the Part 4 categories, enough to prove the pattern before building the rest.
- `action-engine`: Action Object Model, validation/risk pipeline, terminal + filesystem + git adapters, rollback for reversible actions, Action Queue.
- `capability-engine`: registry, installation pipeline (sandboxed), and a first batch of built-in capabilities (git, filesystem, terminal, HTTP) that agents declare and consume.
- `reasoning-engine` extended to Levels 3–4 (now that Planning/NAOS exist to delegate to).
- `apps/web-client`: Planning + Agent Activity panels added.

**Dependencies:** Phases 2A–2D complete (`reasoning-engine` from 2B must exist to feed
Planning; `communication-engine` from 2D to report progress/results).

**Estimated complexity:** Very High — this phase implements the most bespoke, least off-the-shelf part of the entire system (a purpose-built agent operating system, not a wrapper around an existing agent framework — see ADR-008) and integrates the most engines simultaneously. Building NAOS's kernel/registry/SDK/supervision structure correctly here, even in its minimal Phase-3 form, is what avoids a redesign later per the 10x Test ([00](../architecture/00-overview-and-decisions.md#the-10x-test)) — this phase deliberately spends more design care than its immediate feature scope would otherwise justify.

**Implementation order**
1. `planning-engine` Task Graph model + decomposition (no agents yet — output inspected manually).
2. `capability-engine` registry + sandboxing + the four foundational capabilities.
3. `action-engine` (depends on capabilities existing to execute against).
4. `agent-os/sdk` + `agent-os/kernel` (inprocess backend only) + `agent-os/registry`, validated with a single trivial agent (`research-agent`) to prove the full loop before adding more.
5. Remaining four agents.
6. `engineering` Supervisor: peer review + conflict resolution (escalating to Reasoning Engine only when the Supervisor can't resolve it itself).
7. `reasoning-engine` Levels 3–4.

**Testing strategy**
- Structural assertions on generated Task Graphs (no cycles, expected dependency shape) for scripted objectives, per [16 §5](../architecture/16-testing-strategy.md#5-multi-agent--orchestration-testing).
- Sandboxed capability execution tests proving no capability can escape its declared permission scope.
- Agent SDK contract tests: every shipped agent's manifest and handler validated against the `AgentHandler` Protocol before it can be registered.
- Integration test: a real, scripted end-to-end objective ("add a health-check endpoint to a sample repo") flows through Reasoning → Planning → NAOS (Kernel → Engineering Supervisor → agent instances, including a peer-review round) → Action Engine → a real git commit in a throwaway repo.
- Rollback test: force an action to fail mid-execution, assert the rollback strategy restores prior state.
- Supervision test: force an agent instance to crash mid-task, assert the Engineering Supervisor applies the configured restart strategy (`one_for_one` by default) correctly.

**Acceptance criteria**
- A non-trivial multi-step coding objective, given to NOVA, produces a correct Task Graph, executes via at least two agent instances working in parallel where dependencies allow, includes at least one real peer-review round (e.g., `architect-agent` reviewing `coding-agent`'s output), and produces a verifiable result (e.g., a passing test suite in the target repo).
- A deliberately risky action (e.g., deleting a file) is blocked pending approval per its risk classification, and proceeds only after approval — end-to-end proof of Part 12's Safety Layers, ahead of the full Autonomy Engine (Phase 4) providing the policy layer around it.
- Killing `agent-os-kernel` mid-execution and restarting resumes in-flight Task Graph work rather than restarting it from scratch.
- Installing a new version of an existing agent package (e.g., `coding-agent@1.1.0` → `1.2.0`) hot-loads without a kernel restart and without dropping in-flight instances of the old version — proving [12 §6](../architecture/12-agent-architecture.md#6-agent-registry--discovery-install-versioning-hot-loadunload)'s hot-swap claim in the simplest case, ahead of the fuller registry (git/HTTP discovery, marketplace) built in Phase 8.

---

## Phase 4 — Perception, Autonomy & Digital Twin

Status note: **`perception-engine` and `digital-twin-engine` are no longer created
in this phase.** Per the [Phase 2D Master
Blueprint](../design/phase-2d/00-master-blueprint.md) (§9.1, §9.3), both are stood
up earlier, in Phase 2D, in deliberately minimal form (voice + face/presence
sensing only; Communication Profile + conversation-scoped preferences only). This
phase **extends** both — additive, not a rewrite, the same pattern already used for
`executive-cognition-engine` between Phase 2C and Phase 6 — rather than building
either from scratch.

**Objectives**
- Extend NOVA's senses beyond voice and presence to the desktop itself
  (`perception-engine` + `nova-companion`) and give it disciplined initiative
  (`autonomy-engine`), extend the user model beyond conversation into the full
  Digital Twin (`digital-twin-engine`), and begin NOVA's own internal attention
  independent of any single conversation (`cognitive-state-engine`).

**Deliverables**
- `nova-companion` (Rust): desktop/window-focus, clipboard, filesystem, and process/system-health sensors; terminal and window-control actuators — per [05](../architecture/05-desktop-architecture.md). Registers as new sensors behind Phase 2D-B's already-built Sensor Abstraction Layer, per that layer's full lifecycle contract.
- `perception-engine` **extension**: event normalization, context enrichment, multi-modal fusion across the now-larger sensor set (the "meeting begins" scenario from [10 §2 row 9](../architecture/10-inter-engine-communication.md#2-canonical-event-flow-table) becomes real) — additive to the voice/face sensing already shipped in Phase 2D-B.
- `autonomy-engine`: Autonomy Levels 0–2 (Observation Only → Suggestive → Assisted), Trust Engine, Policy Engine, Permission Matrix wired into `nova-auth` ([13](../architecture/13-auth-and-security.md)). The Trust Engine consumes Phase 2D-D's conversational trust-development signal as one input to its own execution-trust model (Master Blueprint §3.2, §10) rather than re-deriving an unrelated one.
- `digital-twin-engine` **extension**: the remaining nine of Bible Part 16's eleven domains (goal model, project model, software/hardware environment, skill model, knowledge profile, productivity patterns, learning progress) — populated from real Perception + Memory data for the first time — added to the Communication Profile domain already shipped in Phase 2D-D.
- `cognitive-state-engine`: Active Thoughts, Focus System, Attention Layers — NOVA's continuous internal thinking, independent of any active conversation session, explicitly distinct from Phase 2D-C's session-scoped conversation memory (Master Blueprint §9.4).
- `apps/web-client`: Autonomy + Digital Twin panels.

**Dependencies:** Phase 3 (Autonomy gates Action Engine executions; Digital Twin consumes Memory/World Model data already flowing); Phase 2D (`perception-engine` and `digital-twin-engine` already exist and are being extended, not created).

**Estimated complexity:** High — OS-level sensor engineering (Rust, per-platform) is a genuinely different discipline from the rest of the stack and carries real platform-compatibility risk (Windows/macOS/Linux each need their own sensor implementations behind the shared trait).

**Implementation order**
1. `nova-companion` sensors (start with filesystem + process monitor — lowest OS-permission friction).
2. `perception-engine` normalization + World Model integration.
3. `autonomy-engine` Levels 0–1 (observe/suggest only — no auto-execution risk yet).
4. `nova-companion` actuators + Action Engine integration, gated by Autonomy Level 2.
5. `digital-twin-engine`.
6. `cognitive-state-engine`.
7. Multi-modal fusion scenario (meeting-detection) as an integration milestone.

**Testing strategy**
- Per-platform sensor integration tests (Windows/macOS/Linux CI runners) validating the `Sensor`/`Actuator` trait contract.
- Permission-boundary tests: a sensor without a granted OS permission must fail closed, never silently degrade to reading data anyway.
- Autonomy-level gating tests: identical action requests produce different outcomes (block/suggest/auto-execute) purely based on configured Autonomy Level and Trust score.
- Golden-scenario replay of the "meeting begins" fusion scenario from [10](../architecture/10-inter-engine-communication.md).

**Acceptance criteria**
- Opening a known project in the IDE is detected and reflected in the World Model within one second, with no user action required.
- An autonomous suggestion at Level 1 is proposed, not executed, and executing it requires explicit user approval; the same action category at Level 2 for a low-risk case executes automatically per policy.
- Digital Twin's project model correctly reconstructs "what was I doing on Project X" after a simulated multi-week gap in a test scenario.
- Revoking a sensor's OS permission immediately stops that perception stream, visibly, in the (still-minimal) UI.

---

## Phase 5 — Desktop App & Living Interface

**Objectives**
- Build the actual product experience the Bible's Part 1 describes: the Tauri desktop shell, the full Command Center UI across all panels, voice I/O, and the "living interface" visual language.

Status note: **the voice channel itself (Whisper/Piper integration, streaming,
wake-word activation) is no longer built in this phase.** Per the [Phase 2D Master
Blueprint](../design/phase-2d/00-master-blueprint.md) (§10), the core audio
pipeline and wake logic already exist from Phase 2D-A/2D-B. This phase's remaining
voice-related scope narrows to the *visual* presentation of an already-working
channel — waveform/listening indicators, wake-word UX polish in the desktop shell —
not the channel's first implementation.

**Deliverables**
- `apps/desktop-client` (Tauri): system tray, window management, `nova-companion` supervision, signed installers for Windows/macOS/Linux.
- Full `apps/web-client` panel set: Reasoning, Planning, Memory Timeline, Knowledge Graph, World Model, Agents, Autonomy, Digital Twin, Personality, Executive (stubbed until Phase 6), System — per [04](../architecture/04-frontend-architecture.md).
- Voice UI polish for the `communication-engine` channel already shipped in Phase 2D-A/2D-B: waveform/listening/speaking indicators, wake-word UX, presence/identity indicator promoted from the Phase 2D web-client stub to a full panel.
- `@nova/ui` design system finalized: idle-state animations driven by real telemetry, System Pulse component.
- Native OS-level packaging for zero-Docker installs (Windows Service / launchd / systemd user unit wrapping `nova-host`), per [14 §2](../architecture/14-deployment-architecture.md#2-local-first-topology).

**Dependencies:** Phases 1–4 (every panel visualizes an engine built in a prior phase; nothing new is invented here except presentation) plus Phase 2D (voice channel already exists; this phase only visualizes it).

**Estimated complexity:** High — less architectural risk than Phases 3/4, but very high polish and integration surface (D3 visualizations, animation performance, cross-platform packaging). Voice *latency* risk, previously carried here, moved to Phase 2D where the channel is actually built.

**Implementation order**
1. Desktop shell wrapping the existing web-client (functional parity first, polish after).
2. Remaining panels, in Bible part order (Memory Timeline, Knowledge Graph, World Model first — they have the richest existing data from Phases 1 & 4).
3. Voice UI polish (waveform/listening indicators, wake-word UX) on top of the already-working Phase 2D channel.
4. Living-interface animation pass across all panels.
5. Native packaging / signed installers.

**Testing strategy**
- Playwright E2E across the full panel set (not just conversation) — extending [16 §6](../architecture/16-testing-strategy.md#6-end-to-end-testing).
- Voice UI responsiveness checks (indicator state matches actual `ConversationSession` state with no perceptible lag) — the underlying round-trip latency itself is verified in Phase 2D's own acceptance criteria, not re-verified here.
- `axe-core` accessibility pass on every panel.
- Cross-platform installer smoke tests (install → launch → boot to "System Ready") on Windows, macOS, Linux CI runners.

**Acceptance criteria**
- A new user can install the desktop app (no Docker, no CLI) and reach a working conversation with voice in under five minutes.
- Every panel reflects live backend state with no fabricated/decorative animation (spot-checked against [16 §6](../architecture/16-testing-strategy.md) and Part 6's explicit "never generate fake animations" rule).
- The first-ten-seconds experience is validated against Part 1's "Wow Factor" criterion via structured user testing (qualitative acceptance, tracked as a checklist item, not just automated tests).

---

## Phase 6 — Executive Cognition & Full Orchestration

**Objectives**
- Extend `executive-cognition-engine` — first stood up in
  [Phase 2C](#phase-2c--executive-cognition-minimal) as a minimal two-engine
  arbitrator — into its full form: attention allocation, goal hierarchy, and
  conflict resolution across every engine built so far, plus hardening `nova-core`'s
  recovery/hot-reload capabilities — the phase where NOVA stops being "a pipeline of
  engines" and becomes "one coordinated mind," per Part 19 and Part 20. This is
  additive to 2C's existing service, not a rewrite.

**Deliverables**
- `executive-cognition-engine`: Goal Hierarchy, Priority Engine (extends 2C's
  Cognitive Priority Matrix from two contending engines to every engine),
  Cognitive Load Management, Delegation Engine, Meta Reasoning, Explainability APIs
  — per [06 §5](../architecture/06-ai-layer-architecture.md#5-executive-cognition-engine--coordination-layer).
- `nova-core` hardening: hot reload for capabilities/agents/models, full Recovery Engine (task/module/engine/session/full-system recovery levels), Version Management, Dependency Graph enforcement — per [Part 20](../bible/part-20-nova-core.md).
- Cross-engine conflict resolution generalized (Phase 3 built it for agents specifically; this phase extends it to any two engines disagreeing, e.g., Planning vs. Autonomy).
- Executive dashboard panel completed in the UI.
- `autonomy-engine` extended to Levels 3–4 (Supervised, Highly Autonomous) now that Executive Cognition can safely arbitrate broader initiative.

**Dependencies:** Phases 2–5 (Executive Cognition coordinates engines that must already exist and be individually correct before their *coordination* can be meaningfully tested).

**Estimated complexity:** Very High — this is the phase where subtle cross-engine interaction bugs surface; correctness here is behavioral/emergent, not unit-testable in isolation, and requires the golden-scenario/chaos testing infrastructure from earlier phases to actually validate.

**Implementation order**
1. Goal Hierarchy + Priority Engine (read-only coordination first — observes and scores, doesn't yet override).
2. Cognitive Load Management + Delegation Engine (now actively shaping NAOS Kernel Scheduler dispatch).
3. Generalized conflict resolution.
4. `nova-core` Recovery Engine levels.
5. Hot reload.
6. Autonomy Levels 3–4, now safe to enable because Executive Cognition can supervise them.

**Testing strategy**
- Chaos tests ([16 §7](../architecture/16-testing-strategy.md#7-non-functional-testing)): kill arbitrary engines mid-pipeline, assert graceful degradation and correct recovery level selection.
- Multi-goal contention scenarios: two competing objectives of different priority injected simultaneously, assert Executive Cognition allocates attention correctly and neither goal is silently dropped.
- Full regression of every golden scenario from Phases 2–5 to confirm Executive Cognition's introduction doesn't change observable behavior for the worse (it should only make coordination *better*, never *different in an unintended way*).

**Acceptance criteria**
- A hot-reloaded capability/model swap causes zero dropped in-flight tasks.
- Simulated engine crash-and-recovery completes within the RTO targets set in [14 §6](../architecture/14-deployment-architecture.md#6-disaster-recovery) for local-first mode.
- Given two simultaneous, resource-competing objectives, the system's prioritization decision is explainable on demand (Part 19 "Explainability") via the Executive dashboard.
- Autonomy Level 4 (Highly Autonomous) correctly executes a multi-day-scale objective with only milestone-level user check-ins, per Part 14's "Highly Autonomous" definition.

---

## Phase 7 — Security, Governance & Enterprise Readiness

**Objectives**
- Move NOVA from "safe for its own builder to run" to "safe to hand to other people," implementing the full auth/authorization model, multi-tenancy groundwork, and compliance-relevant controls.

**Deliverables**
- Full `nova-auth`: OIDC enterprise flow (in addition to the local-first device identity from Phase 0/2), RBAC + attribute-based policy per [13](../architecture/13-auth-and-security.md).
- Multi-tenant data isolation (schema-per-tenant Postgres, tenant-scoped Neo4j, bucket-prefix S3) per [19 §3](../architecture/19-scalability-strategy.md#3-multi-tenancy-model-enterprise).
- Secrets management upgraded from local SOPS/age to pluggable cloud KMS/Vault.
- Full audit logging + Autonomy/Action decision ledger exposed as a compliance-ready export.
- Security hardening pass: mTLS between engines, capability code signing enforcement, sandboxing promoted from "new capabilities" to "all capabilities below a trust threshold."
- Third-party security review (penetration test) of the API Gateway, auth flows, and sandboxing.

**Dependencies:** Phase 6 (a system must be behaviorally complete before its security boundary can be meaningfully audited) and Phase 4's Autonomy/Permission Matrix (this phase generalizes it to multi-user).

**Estimated complexity:** High — mostly well-understood enterprise security engineering, but with real consequences for mistakes, so verification (including external review) dominates the effort, not raw feature count.

**Implementation order**
1. OIDC flow + RBAC/ABAC (additive to existing local-device auth, not a replacement).
2. Multi-tenant data isolation.
3. mTLS + secrets management upgrade.
4. Audit log compliance export.
5. Sandboxing/code-signing hardening.
6. External penetration test + remediation.

**Testing strategy**
- Automated cross-tenant isolation tests (attempt and fail every cross-tenant read/write path) as a required, non-skippable CI suite once multi-tenancy lands.
- Full OWASP-aligned security test pass (ZAP scan, auth bypass attempts, injection tests) against the API Gateway.
- Audit log completeness test: every Critical/High-risk action in a scripted scenario produces exactly one corresponding, correctly-attributed log entry.

**Acceptance criteria**
- Independent penetration test finds no critical/high findings unresolved at phase close.
- A scripted multi-tenant scenario proves zero cross-tenant data leakage across every engine's query paths.
- Revoking a user's enterprise IdP account immediately (within the JWT's short expiry window) removes their access — no lingering session risk.
- Per [ADR-025](../architecture/adr/ADR-025-personal-edition-is-the-flagship.md): the full Personal Edition test suite (every phase's existing unit/integration/contract tests) passes unmodified with enterprise mode compiled in but disabled — proving OIDC/RBAC/multi-tenancy landed as additive layers, not changes to the single-user code path.

---

## Phase 8 — Scale-Out & Cloud/Enterprise Deployment

**Objectives**
- Deploy NOVA as a horizontally scaled, multi-tenant Kubernetes platform, exercising every scaling lever designed into the architecture since Phase 0 but not yet turned on.

**Deliverables**
- Helm charts for every NOVA-authored deployable unit in the [Service Inventory](../architecture/00-overview-and-decisions.md#canonical-service-inventory) + umbrella chart, per [14 §3](../architecture/14-deployment-architecture.md#3-enterprisecloud-topology).
- Terraform stacks for AWS and GCP.
- `VectorStore` adapter swap to Qdrant; `GraphStore` adapter validated against a second backend (e.g., Memgraph) to prove ADR-007 holds under real use, not just in contract tests; NATS JetStream clustering (or the Kafka/RabbitMQ `EventBus` backend, per ADR-006, if a launch customer requires it); Redis Cluster.
- NAOS `container` and `remote` execution backends activated ([12 §8](../architecture/12-agent-architecture.md#8-execution-backends--how-distributed-from-day-one-actually-works)); `agent-os-worker` node type shipped for distributed/multi-machine agent execution.
- `nova-sync-service` for multi-device/cloud sync per [18](../architecture/18-local-first-and-cloud-sync.md).
- Autoscaling policies per engine, tied to the metrics/thresholds defined in [19 §5](../architecture/19-scalability-strategy.md#5-capacity-planning-signals).
- Load-tested SLAs published (latency/throughput targets per engine, matching each Bible Part's stated "Performance Targets").
- Multi-region groundwork: cross-region NATS mirroring, Postgres read replicas (full active-active explicitly deferred, per [19 §4](../architecture/19-scalability-strategy.md#4-horizontal-scale-out-is-opt-in-complexity)).

**Dependencies:** Phase 7 (enterprise security posture must exist before enterprise scale is exposed to real multi-tenant traffic).

**Estimated complexity:** Very High — this phase validates every architectural bet made since Phase 0 (ADR-001 and ADR-008 in particular) under real load; discovering that a boundary was drawn wrong is expensive here, which is exactly why the earlier phases were structured to keep every engine's and NAOS's contract clean from the start.

**Implementation order**
1. Helm charts + Terraform for a single-region deployment (functional parity with Compose first).
2. Load testing against the Bible's stated performance targets, per engine, including NAOS's `inprocess` backend at increasing agent concurrency.
3. Turn on scaling levers only where load testing shows the current default insufficient (per [19 §4](../architecture/19-scalability-strategy.md#4-horizontal-scale-out-is-opt-in-complexity) — no premature complexity) — this includes activating NAOS's `container`/`remote` execution backends only once `inprocess` concurrency actually becomes the bottleneck under test, not preemptively.
4. `nova-sync-service` for cross-device/cloud sync.
5. Multi-region groundwork.

**Testing strategy**
- `k6` load tests against every Bible-stated Performance Target, per engine, as a pass/fail gate (not just observational).
- Chaos testing at cluster scale (node loss, AZ failure simulation).
- Sync conflict-resolution tests across simulated multi-device scenarios (offline edits on two devices, reconnect, verify correct merge per [18 §3](../architecture/18-local-first-and-cloud-sync.md#3-sync-architecture-opt-in)).

**Acceptance criteria**
- Every Bible-stated Performance Target ([Parts 3, 7–20] "Performance Targets" sections) is met under load test, with results published in the SAD as a living benchmark record.
- A simulated single-AZ failure causes no data loss and recovers within the documented RTO.
- A multi-device sync conflict resolves correctly and explainably in 100% of a scripted test matrix covering the documented conflict-resolution rules.
- The platform sustains the Part 4 "Future Scalability" target of at least 1,000 concurrent agents in a load test without orchestration-layer redesign (10,000 remains a stretch target validated directionally, not a hard Phase 8 gate).
- Per [ADR-025](../architecture/adr/ADR-025-personal-edition-is-the-flagship.md): a single-user, single-region Compose deployment (the Personal Edition's own default topology) is re-verified against the full test suite after this phase's scale-out work lands, confirming the Helm/Terraform/clustering additions changed nothing about running NOVA for one person on one machine.

---

## Cross-phase notes

- **Nothing in this roadmap contradicts the SAD** — every deliverable cites the
  architecture document and Bible part it implements, and no phase introduces a
  technology or pattern not already decided in [00–19](../architecture/00-overview-and-decisions.md).
- **Re-planning is expected.** Per Part 9's own "Dynamic Replanning" principle, this
  roadmap should be revised as each phase completes and reveals what the next one
  actually needs — it is a living plan, not a contract frozen on day one.
- **Approved.** The technology stack, Event Bus (ADR-006), Graph Store (ADR-007), and
  Agent Architecture/NAOS (ADR-008) decisions are approved, with the conditions from
  that approval incorporated throughout the SAD and this roadmap. Phase 0 is cleared
  to begin. (Phase 0 was added here as the necessary bootstrap step beneath the user's
  originally requested "Phase 1"; the numbering has been kept as-is since it was not
  flagged for change.)
- **The 10x Test applies to every future addition to this roadmap**, per
  [00](../architecture/00-overview-and-decisions.md#the-10x-test): any new deliverable
  proposed in a later phase must be checked against "will this still be correct at
  10x scale in five years" before it is added, not after.
