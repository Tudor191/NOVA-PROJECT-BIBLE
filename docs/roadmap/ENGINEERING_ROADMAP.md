# NOVA Engineering Roadmap

Status: **Draft v1 — companion document to the [Software Architecture Document](../architecture/00-overview-and-decisions.md). Pending approval before Phase 0 begins.**

## How this roadmap is organized

Every phase builds strictly on the previous one's deliverables (no phase assumes an
engine that a later phase introduces). Phases are scoped so that **every phase ends
with a runnable, demonstrable increase in NOVA's capability** — never a phase that only
produces internal scaffolding with nothing observable at the end, per Part 9's
"Milestone System": "each milestone represents measurable progress."

Complexity is rated Low / Medium / High / Very High, reflecting engineering effort and
architectural risk combined, not calendar time (calendar time depends on team size,
which is not yet decided).

| Phase | Name | Complexity | Producible outcome at the end |
|---|---|---|---|
| 0 | Platform Bootstrap | Medium | Empty-but-real monorepo; `nova-host` boots, does nothing yet, but boots correctly |
| 1 | Data & Memory Substrate | Medium | NOVA can store and retrieve memories, knowledge, and world objects |
| 2 | AI Core: Model Orchestration & Reasoning | High | You can talk to NOVA; it remembers you, reasons before answering, and picks models intelligently |
| 3 | Planning & Multi-Agent Execution | Very High | NOVA can take a real objective, plan it, delegate it to agents, and execute real actions |
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

**Objectives**
- Implement `memory-engine`, `knowledge-engine`, and `world-model-engine` at a *storage and retrieval* level — the cognitive intelligence (reasoning over this data) comes in Phase 2; this phase proves the data model and lifecycle are correct.
- Prove the polyglot persistence strategy ([07](../architecture/07-database-architecture.md)) end-to-end: relational, vector, and graph stores all working together behind their owning engines.

**Deliverables**
- `memory-engine`: sensory intake → working → short-term → long-term pipeline; all 9 memory type modules per [08](../architecture/08-memory-architecture.md), CRUD + semantic/timeline search working; consolidation worker (merge duplicates, decay lifecycle stages) running on a schedule.
- `knowledge-engine`: Knowledge Graph in Neo4j, node/relationship CRUD, source attribution, confidence scoring, contradiction detection (structural — flags conflicting edges, doesn't yet resolve them intelligently, which needs Reasoning Engine).
- `world-model-engine`: object/relationship graph (merged Part 5 + Part 18 spec per ADR-002), event-driven object state updates, basic World View query API.
- Event contracts for all `memory.*`, `knowledge.*`, `world_model.*` subjects registered in `nova-contracts`.
- A minimal internal CLI/admin API for manually inspecting memory/knowledge/world state (used through Phase 2 before the real UI exists).

**Dependencies:** Phase 0 (Event Bus, `nova-core`, CI/CD, `nova-contracts`).

**Estimated complexity:** Medium — mostly well-understood CRUD-plus-search engineering; the one non-trivial piece is the consolidation worker's duplicate-merge/promotion logic.

**Implementation order**
1. Postgres schemas + Alembic migrations for all three engines (per-engine schema, per [07 §1](../architecture/07-database-architecture.md#1-store-to-engine-ownership-map)).
2. `memory-engine`: working/short-term (Redis + Postgres) first, since nothing downstream needs long-term yet.
3. `memory-engine`: long-term + pgvector search.
4. `knowledge-engine`: Neo4j graph CRUD + semantic search over knowledge text.
5. `world-model-engine`: object graph + event ingestion from a synthetic event generator (real Perception Engine input arrives in Phase 4).
6. Memory consolidation worker.
7. Contradiction detection (structural).

**Testing strategy**
- Unit tests per memory type module (retention rules, importance scoring).
- Integration tests against real Postgres/Neo4j/Redis via `nova-testkit` testcontainers, per [16 §3](../architecture/16-testing-strategy.md#3-integration-testing).
- Contract tests for every `memory.*`/`knowledge.*`/`world_model.*` event.
- A scripted scenario test: write 500 synthetic memories with controlled importance/recency, run the consolidation worker, assert the expected lifecycle-stage distribution.

**Acceptance criteria**
- A memory written via the admin API is retrievable by semantic search with reasonable relevance ranking within 100ms (p95) on a 10k-memory dataset.
- A knowledge contradiction (two conflicting facts about the same node) is detected and flagged, not silently overwritten (Part 10).
- Killing and restarting `memory-engine` mid-consolidation resumes without data loss (Part 6 "Cognitive Memory").
- Project Memory scoping works: retrieving `project_id=X` context returns only that project's memories.

---

## Phase 2 — AI Core: Model Orchestration & Reasoning

**Objectives**
- Deliver the first genuinely intelligent, user-facing slice of NOVA: a conversational interface backed by memory, multi-model routing, and structured reasoning — not a bare LLM wrapper.
- Implement `ai-model-orchestration-engine`, `reasoning-engine` (Levels 1–2 only; 3–4 need Planning/Agents from Phase 3), `personality-engine`, and `communication-engine` (text channel only).
- Ship a minimal web chat UI as the first observable "you can talk to NOVA" milestone.

**Deliverables**
- `ai-model-orchestration-engine`: Model Registry, Ollama connector (default, zero-budget), one cloud connector (Anthropic) as proof the abstraction holds, routing algorithm per [06 §1](../architecture/06-ai-layer-architecture.md#1-model-gateway-ai-model-orchestration-engine).
- `reasoning-engine`: full 13-step pipeline for Levels 1–2, confidence scoring, Reasoning Memory writes to `memory-engine`.
- `personality-engine`: core identity/values encoded as a behavioral constraint layer (not a system prompt string) with consistency validation.
- `communication-engine`: conversation session model, text channel, response streaming.
- `api-gateway` + `ws-gateway` minimal implementation ([11](../architecture/11-api-architecture.md)).
- `apps/web-client`: conversation panel only (other panels are stubs) — the first real UI.
- Prompt Orchestration assembly ([06 §4](../architecture/06-ai-layer-architecture.md#4-prompt-orchestration)) pulling from Memory/Knowledge/World Model/Personality.

**Dependencies:** Phase 1 (Memory/Knowledge/World Model must exist for the Thinking Pipeline to retrieve from), Phase 0 infra.

**Estimated complexity:** High — this is where the "many independent engines must feel like one mind" requirement first gets tested for real, and where prompt orchestration and confidence scoring need genuine design iteration, not just plumbing.

**Implementation order**
1. `ai-model-orchestration-engine` with Ollama connector only — get local inference working first (zero-budget default, Part 7).
2. `reasoning-engine` Level 1 (instant reasoning) — simplest path end-to-end.
3. `communication-engine` text channel + `ws-gateway` streaming.
4. `personality-engine` + consistency validation wired into the response path.
5. `reasoning-engine` Level 2 (hypothesis generation, evidence collection, Decision Memory writes).
6. Anthropic connector + routing algorithm (proves multi-model abstraction).
7. `apps/web-client` conversation panel.

**Testing strategy**
- Contract + integration tests as in Phase 1, extended to the new engines.
- Golden-scenario tests per [16 §5](../architecture/16-testing-strategy.md#5-multi-agent--orchestration-testing): assert pipeline stage completion and confidence presence, not exact text.
- `FakeModelGateway`-driven integration tests for deterministic CI runs; a small, separate "live model smoke test" job (manually triggered, not on every PR) against real Ollama to catch integration drift.
- E2E: "first-run onboarding → first successful conversation with memory recall" (the first golden path from [16 §6](../architecture/16-testing-strategy.md#6-end-to-end-testing)).

**Acceptance criteria**
- A fresh install, zero API keys, can hold a coherent multi-turn conversation using only local models.
- Asking about something mentioned three turns ago (or in a previous session) is answered correctly via memory retrieval (Part 3's "memory first principle" demonstrated, not just claimed).
- Personality stays recognizably consistent across at least two different underlying models (Ollama vs. Anthropic) for the same query style — the concrete test of Part 17's core promise.
- Every response is traceable via `correlation_id` through the full event chain in the observability stack.

---

## Phase 3 — Planning & Multi-Agent Execution

**Objectives**
- Implement `planning-engine`, `agent-orchestrator`, and the first concrete agents, plus `action-engine` and `capability-engine` — the point at which NOVA moves from "answers questions" to "does work."

**Deliverables**
- `planning-engine`: objective decomposition, Work Breakdown Structure, Task Graph data model + dependency/critical-path analysis, per [06 §3](../architecture/06-ai-layer-architecture.md#3-planning-engine).
- `agent-orchestrator`: full lifecycle state machine ([12](../architecture/12-agent-architecture.md)), Agent Registry, parallel dispatch, peer review, conflict resolution (escalating to Reasoning Engine).
- First agent set: `research-agent`, `coding-agent`, `qa-agent`, `architect-agent`, `documentation-agent` (five of the Part 4 categories — enough to prove the pattern before building all ~20).
- `action-engine`: Action Object Model, validation/risk pipeline, terminal + filesystem + git adapters, rollback for reversible actions, Action Queue.
- `capability-engine`: registry, installation pipeline (sandboxed), and a first batch of built-in capabilities (git, filesystem, terminal, HTTP) that agents declare and consume.
- `reasoning-engine` extended to Levels 3–4 (now that Planning/Agents exist to delegate to).
- `apps/web-client`: Planning + Agent Activity panels added.

**Dependencies:** Phase 2 (Reasoning Engine must exist to feed Planning; Communication Engine to report progress/results).

**Estimated complexity:** Very High — this phase implements the most bespoke, least off-the-shelf part of the entire system (custom agent runtime, peer review, conflict resolution) and integrates the most engines simultaneously.

**Implementation order**
1. `planning-engine` Task Graph model + decomposition (no agents yet — output inspected manually).
2. `capability-engine` registry + sandboxing + the four foundational capabilities.
3. `action-engine` (depends on capabilities existing to execute against).
4. `agent-orchestrator` lifecycle + Agent Registry, with a single trivial agent first (e.g., `research-agent`) to validate the full loop.
5. Remaining four agents.
6. Peer review + conflict resolution.
7. `reasoning-engine` Levels 3–4.

**Testing strategy**
- Structural assertions on generated Task Graphs (no cycles, expected dependency shape) for scripted objectives, per [16 §5](../architecture/16-testing-strategy.md#5-multi-agent--orchestration-testing).
- Sandboxed capability execution tests proving no capability can escape its declared permission scope.
- Integration test: a real, scripted end-to-end objective ("add a health-check endpoint to a sample repo") flows through Reasoning → Planning → Agent Orchestrator → Action Engine → a real git commit in a throwaway repo.
- Rollback test: force an action to fail mid-execution, assert the rollback strategy restores prior state.

**Acceptance criteria**
- A non-trivial multi-step coding objective, given to NOVA, produces a correct Task Graph, executes via at least two agents working in parallel where dependencies allow, and produces a verifiable result (e.g., a passing test suite in the target repo).
- A deliberately risky action (e.g., deleting a file) is blocked pending approval per its risk classification, and proceeds only after approval — end-to-end proof of Part 12's Safety Layers, ahead of the full Autonomy Engine (Phase 4) providing the policy layer around it.
- Killing `agent-orchestrator` mid-execution and restarting resumes the in-flight Task Graph rather than restarting it from scratch.

---

## Phase 4 — Perception, Autonomy & Digital Twin

**Objectives**
- Give NOVA senses (`perception-engine` + `nova-companion`) and disciplined initiative (`autonomy-engine`), and begin modeling the user (`digital-twin-engine`) and NOVA's own internal attention (`cognitive-state-engine`).

**Deliverables**
- `nova-companion` (Rust): desktop/window-focus, clipboard, filesystem, and process/system-health sensors; terminal and window-control actuators — per [05](../architecture/05-desktop-architecture.md).
- `perception-engine`: Sensor Abstraction Layer, event normalization, context enrichment, multi-modal fusion (the "meeting begins" scenario from [10 §2 row 9](../architecture/10-inter-engine-communication.md#2-canonical-event-flow-table) becomes real).
- `autonomy-engine`: Autonomy Levels 0–2 (Observation Only → Suggestive → Assisted), Trust Engine, Policy Engine, Permission Matrix wired into `nova-auth` ([13](../architecture/13-auth-and-security.md)).
- `digital-twin-engine`: user profile, goal model, project model, skill model, preference evolution — populated from real Perception + Memory data for the first time.
- `cognitive-state-engine`: Active Thoughts, Focus System, Attention Layers.
- `apps/web-client`: Autonomy + Digital Twin panels.

**Dependencies:** Phase 3 (Autonomy gates Action Engine executions; Digital Twin consumes Memory/World Model data already flowing).

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

**Deliverables**
- `apps/desktop-client` (Tauri): system tray, window management, `nova-companion` supervision, signed installers for Windows/macOS/Linux.
- Full `apps/web-client` panel set: Reasoning, Planning, Memory Timeline, Knowledge Graph, World Model, Agents, Autonomy, Digital Twin, Personality, Executive (stubbed until Phase 6), System — per [04](../architecture/04-frontend-architecture.md).
- Voice channel in `communication-engine`: Whisper (STT) + Piper (TTS) integration, wake-word activation.
- `@nova/ui` design system finalized: idle-state animations driven by real telemetry, System Pulse component.
- Native OS-level packaging for zero-Docker installs (Windows Service / launchd / systemd user unit wrapping `nova-host`), per [14 §2](../architecture/14-deployment-architecture.md#2-local-first-topology).

**Dependencies:** Phases 1–4 (every panel visualizes an engine built in a prior phase; nothing new is invented here except presentation and voice).

**Estimated complexity:** High — less architectural risk than Phases 3/4, but very high polish and integration surface (D3 visualizations, animation performance, cross-platform packaging, voice latency).

**Implementation order**
1. Desktop shell wrapping the existing web-client (functional parity first, polish after).
2. Remaining panels, in Bible part order (Memory Timeline, Knowledge Graph, World Model first — they have the richest existing data from Phases 1 & 4).
3. Voice channel (Whisper/Piper) — highest latency-sensitivity, benefits from being built once other panels reveal real usage patterns.
4. Living-interface animation pass across all panels.
5. Native packaging / signed installers.

**Testing strategy**
- Playwright E2E across the full panel set (not just conversation) — extending [16 §6](../architecture/16-testing-strategy.md#6-end-to-end-testing).
- Voice round-trip latency benchmarks against the Part 13 "Performance Targets" (minimal latency).
- `axe-core` accessibility pass on every panel.
- Cross-platform installer smoke tests (install → launch → boot to "System Ready") on Windows, macOS, Linux CI runners.

**Acceptance criteria**
- A new user can install the desktop app (no Docker, no CLI) and reach a working conversation with voice in under five minutes.
- Every panel reflects live backend state with no fabricated/decorative animation (spot-checked against [16 §6](../architecture/16-testing-strategy.md) and Part 6's explicit "never generate fake animations" rule).
- The first-ten-seconds experience is validated against Part 1's "Wow Factor" criterion via structured user testing (qualitative acceptance, tracked as a checklist item, not just automated tests).

---

## Phase 6 — Executive Cognition & Full Orchestration

**Objectives**
- Implement `executive-cognition-engine`, wiring attention allocation, goal hierarchy, and conflict resolution across every engine built so far, and harden `nova-core`'s recovery/hot-reload capabilities — the phase where NOVA stops being "a pipeline of engines" and becomes "one coordinated mind," per Part 19 and Part 20.

**Deliverables**
- `executive-cognition-engine`: Goal Hierarchy, Priority Engine, Cognitive Load Management, Delegation Engine, Meta Reasoning, Explainability APIs — per [06 §5](../architecture/06-ai-layer-architecture.md#5-executive-cognition-engine--coordination-layer).
- `nova-core` hardening: hot reload for capabilities/agents/models, full Recovery Engine (task/module/engine/session/full-system recovery levels), Version Management, Dependency Graph enforcement — per [Part 20](../bible/part-20-nova-core.md).
- Cross-engine conflict resolution generalized (Phase 3 built it for agents specifically; this phase extends it to any two engines disagreeing, e.g., Planning vs. Autonomy).
- Executive dashboard panel completed in the UI.
- `autonomy-engine` extended to Levels 3–4 (Supervised, Highly Autonomous) now that Executive Cognition can safely arbitrate broader initiative.

**Dependencies:** Phases 2–5 (Executive Cognition coordinates engines that must already exist and be individually correct before their *coordination* can be meaningfully tested).

**Estimated complexity:** Very High — this is the phase where subtle cross-engine interaction bugs surface; correctness here is behavioral/emergent, not unit-testable in isolation, and requires the golden-scenario/chaos testing infrastructure from earlier phases to actually validate.

**Implementation order**
1. Goal Hierarchy + Priority Engine (read-only coordination first — observes and scores, doesn't yet override).
2. Cognitive Load Management + Delegation Engine (now actively shaping Agent Orchestrator dispatch).
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

---

## Phase 8 — Scale-Out & Cloud/Enterprise Deployment

**Objectives**
- Deploy NOVA as a horizontally scaled, multi-tenant Kubernetes platform, exercising every scaling lever designed into the architecture since Phase 0 but not yet turned on.

**Deliverables**
- Helm charts for all 19 deployable units + umbrella chart, per [14 §3](../architecture/14-deployment-architecture.md#3-enterprisecloud-topology).
- Terraform stacks for AWS and GCP.
- `VectorStore` adapter swap to Qdrant; Neo4j causal clustering; NATS JetStream clustering; Redis Cluster.
- `nova-sync-service` for multi-device/cloud sync per [18](../architecture/18-local-first-and-cloud-sync.md).
- Autoscaling policies per engine, tied to the metrics/thresholds defined in [19 §5](../architecture/19-scalability-strategy.md#5-capacity-planning-signals).
- Load-tested SLAs published (latency/throughput targets per engine, matching each Bible Part's stated "Performance Targets").
- Multi-region groundwork: cross-region NATS mirroring, Postgres read replicas (full active-active explicitly deferred, per [19 §4](../architecture/19-scalability-strategy.md#4-horizontal-scale-out-is-opt-in-complexity)).

**Dependencies:** Phase 7 (enterprise security posture must exist before enterprise scale is exposed to real multi-tenant traffic).

**Estimated complexity:** Very High — this phase validates every architectural bet made since Phase 0 (ADR-001 in particular) under real load; discovering that a boundary was drawn wrong is expensive here, which is exactly why the earlier phases were structured to keep every engine's contract clean from the start.

**Implementation order**
1. Helm charts + Terraform for a single-region deployment (functional parity with Compose first).
2. Load testing against the Bible's stated performance targets, per engine.
3. Turn on scaling levers only where load testing shows the current default insufficient (per [19 §4](../architecture/19-scalability-strategy.md#4-horizontal-scale-out-is-opt-in-complexity) — no premature complexity).
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

---

## Cross-phase notes

- **Nothing in this roadmap contradicts the SAD** — every deliverable cites the
  architecture document and Bible part it implements, and no phase introduces a
  technology or pattern not already decided in [00–19](../architecture/00-overview-and-decisions.md).
- **Re-planning is expected.** Per Part 9's own "Dynamic Replanning" principle, this
  roadmap should be revised as each phase completes and reveals what the next one
  actually needs — it is a living plan, not a contract frozen on day one.
- **Phase 0 does not start until this document and the SAD are explicitly approved**,
  per the user's original request: "once the architecture is finalized and approved,
  we will begin implementation starting with Phase 1" (Phase 0 was added here as the
  necessary bootstrap step beneath the user's "Phase 1"; renumber on approval if the
  user prefers Phase 0 to be folded into Phase 1).
