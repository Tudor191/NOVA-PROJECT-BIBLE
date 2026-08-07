# NOVA Project Health Review — August 2026

**Trigger:** The 30,000 SLOC Project Health Review reminder ([SAD 15 §10](../../architecture/15-development-workflow.md#10-project-metrics--the-sloc-milestone-gate)), crossed at the Phase 2D-B Gate Review (cumulative Production SLOC 31,610). Per direct user instruction, feature development is paused and this review is performed before Phase 2D-C begins.

**Scope:** All 10 engines (`memory-engine`, `knowledge-engine`, `world-model-engine`, `ai-model-orchestration-engine`, `reasoning-engine`, `executive-cognition-engine`, `personality-engine`, `communication-engine`, `perception-engine`, `nova-core`) and all 7 shared packages (`nova-contracts`, `nova-eventbus-sdk`, `nova-observability`, `nova-testkit`, `nova-vectorstore-sdk`, `nova-graphstore-sdk`, `nova-embeddings-sdk`).

**Method:** Direct repository inspection this session (`scc`, `radon cc`, `grimp`, `pytest --cov`, `lint-imports`, `ruff`, `mypy`, direct file reads) plus four parallel deep-read audits covering SOLID/DDD/domain-purity, repository/database/migrations, error-handling/logging/observability/configuration, and API/Event-Bus/code-duplication/naming across all 10 engines. Every finding below is cited with a file path (and line number where practical) and was verified by reading the actual code, not inferred from documentation claims — the explicit "verify before trusting documentation" standing rule applied recursively to this review itself, which is itself a piece of documentation until it's been checked against the code one more time.

**This review is not a pass/fail gate.** Per the user's own framing, it identifies strengths worth codifying as permanent standards alongside problems worth fixing, and closes with an honest recommendation on what (if anything) should change before Phase 2D-C begins.

## Contents

0. [Executive summary](#0-executive-summary)
1. [Overall architecture assessment](#1-overall-architecture-assessment)
2. [Recurring patterns worth making permanent standards](#2-recurring-patterns-worth-making-permanent-standards)
3. [Engine responsibility, SOLID, Clean Architecture, DDD boundary validation](#3-engine-responsibility-solid-clean-architecture-ddd-boundary-validation)
4. [ADR consistency](#4-adr-consistency)
5. [Bible consistency](#5-bible-consistency)
6. [Documentation consistency](#6-documentation-consistency)
7. [Cross-engine dependency / import graph / circular dependency analysis](#7-cross-engine-dependency--import-graph--circular-dependency-analysis)
8. [Event Bus architecture review](#8-event-bus-architecture-review)
9. [API consistency review](#9-api-consistency-review)
10. [Database schema, migration, and repository layer review](#10-database-schema-migration-and-repository-layer-review)
11. [Domain purity review](#11-domain-purity-review)
12. [Error handling, logging, and observability consistency](#12-error-handling-logging-and-observability-consistency)
13. [Configuration consistency](#13-configuration-consistency)
14. [Security review](#14-security-review)
15. [Privacy review](#15-privacy-review)
16. [Build pipeline and CI review](#16-build-pipeline-and-ci-review)
17. [Testing quality and coverage](#17-testing-quality-and-coverage)
18. [Complexity and code duplication analysis](#18-complexity-and-code-duplication-analysis)
19. [Performance analysis](#19-performance-analysis)
20. [Maintainability assessment](#20-maintainability-assessment)
21. [Scalability assessment](#21-scalability-assessment)
22. [Technical debt assessment](#22-technical-debt-assessment)
23. [Long-term risks](#23-long-term-risks)
24. [Recommended refactorings](#24-recommended-refactorings)
25. [Recommended simplifications](#25-recommended-simplifications)
26. [Architectural improvements](#26-architectural-improvements)
27. [**Architectural Opportunities**](#27-architectural-opportunities)
28. [Engineering metrics](#28-engineering-metrics)
29. [Final recommendation](#29-final-recommendation)

---

## 0. Executive summary

The architecture is healthy. Ten engines built across five phases (31,610 cumulative Production SLOC) hold to a consistent, largely self-reinforcing set of conventions: zero circular dependencies, zero cross-engine coupling, a domain-purity rule violated in only 2 of 10 engines, a repository-transaction discipline followed without exception across 18 files, an identical outbox/transactional-dispatch pattern in 8 of 8 engines that have one, and a genuine, repeated DDD anti-corruption-layer pattern for every piece of cross-engine data since the very first engine. These are real strengths, each independently verified this session, not carried forward from prior reports.

The problems found are real but narrow, and none of them are severe enough to block Phase 2D-C. The single most significant finding is that `docs/architecture/16-testing-strategy.md` — a canonical architecture document, not a phase-specific TDD — describes real-infrastructure test fixtures (`testcontainers`-backed Postgres/Neo4j/Redis/NATS, a `FakeModelGateway`, an 85%-coverage CI gate) that were never built; none of it exists in `nova-testkit` today. This explains, more precisely than "no Docker daemon available," why real-Postgres verification has now been deferred across three consecutive Gate Reviews: even once Docker is available, there is currently nothing built to point it at. Two concrete code bugs were found (`ai-model-orchestration-engine`'s `model_registry.updated_at` never updates after INSERT; `perception-engine`'s `identity_observation` table has a real FK in its migration but not in its ORM model), one tooling function has been silently broken since the second engine was ever scaffolded (`tools/scaffold-engine.py`'s `_update_root_pyproject`), and a modest, precisely-quantified pile of structural boilerplate duplication (~700 lines across `api/health.py`/`repository/db.py`/`repository/outbox_dispatcher.py`/`workers/__init__.py`) is ready for low-risk extraction into a shared package.

**Recommendation: proceed to Phase 2D-C**, after a short, dedicated cleanup pass applying the low-risk, high-confidence fixes this review identifies (§24 items 1-6 and 10, §25 items 1-3) — none of them are feature work, all of them are corrections to things already broken or already stale. The larger opportunities (§26, §27) are genuine but not urgent, and should be sequenced deliberately across upcoming phases; §27.1 (building the real-infrastructure test fixtures this project's own documentation already claims exist) deserves to be scheduled as its own piece of work the moment a Docker-capable environment is confirmed available.

## 1. Overall architecture assessment

Every dimension the user asked this review to cover was checked directly against the code, not inferred from prior reports or documentation claims — including, deliberately, this project's own canonical architecture documentation (§6.1's finding is the clearest example of why that discipline matters even when it's uncomfortable). The architecture holds up under that scrutiny:

- **Structural integrity**: zero circular dependencies and zero cross-engine coupling across 17 first-party packages, verified by a from-scratch dependency graph, not merely inferred from `import-linter`'s 4 passing contracts (§7).
- **Layering discipline**: domain purity holds in 8 of 10 engines with zero violations, and the 2 partial exceptions (`nova-core`, `knowledge-engine`) are narrow, well-understood, and traced to a specific, nameable root cause each (§3.3).
- **Cross-engine data modeling**: the single most consistently-repeated architectural pattern in the codebase — every piece of cross-engine data is a narrow, ID+summary-only local value object, never a duplicated aggregate — held from the very first engine (Phase 1) through the most recent one (`perception-engine`, this phase) without exception (§3.4).
- **Persistence discipline**: schema namespacing, PK/timestamp conventions, transaction boundaries, and the transactional outbox pattern are all applied with a level of consistency across 9 independently-built engines that is genuinely unusual for a codebase this size — the deviations found (§10) are two concrete bugs and some naming drift, not architectural disagreement.
- **The one real crack**: this project's own testing-strategy documentation has been describing infrastructure that doesn't exist since at least Phase 1, and this was never caught until this review specifically went looking for it (§6.1). This is not a structural problem with the architecture itself — it's a process gap in how this project verifies its own documentation stays true — but it is the most consequential single finding here, because it has been quietly shaping every prior phase's "we'll verify against real Postgres once Docker is available" plan without anyone checking whether "once Docker is available" was actually sufficient.

Nothing found in this review suggests the architecture needs a different foundational shape. Every recommendation in §24-27 is an extension or correction within the existing architecture, not a proposal to replace any part of it.

## 2. Recurring patterns worth making permanent standards

The user explicitly asked this review not to focus only on problems. These are the patterns that have proven themselves — independently re-derived or consistently re-applied across 5 phases and 10 engines built at different times by the same iterative process — and are recommended as explicit, permanent, documented engineering standards going forward (most already function as de facto standards; the recommendation is to make them load-bearing and written down, not to invent something new):

1. **The narrow, ID+summary-only cross-engine value object** (§3.4) — every single instance of cross-engine data modeling in this codebase follows this pattern, with zero counterexamples found. This is this project's strongest architectural property and should be stated explicitly in `docs/architecture/00-overview-and-decisions.md` or a dedicated ADR, not left as an emergent convention every engine happens to have converged on independently.
2. **The transactional outbox pattern, byte-identical table shape and dispatch cadence across 8 engines** (§10) — `DEFAULT_BATCH_SIZE = 100`, the 10-second Arq cron, the `id/subject/payload/correlation_id/causation_id/created_at/dispatched_at` shape. Zero deviation found beyond the one deliberately-scoped graph-write extension. Ready to be declared a hard, mechanically-checkable standard (a future contract test could assert every new engine's outbox table matches this shape).
3. **Repository transaction discipline** (§10) — write methods always `.begin()`, read methods never do. Zero exceptions across 18 files. Worth codifying in a written repository-layer style guide, since it's exactly the kind of subtle rule that's easy to violate by accident on engine #11 without an explicit statement to check against.
4. **The `domain/ports.py` Protocol + narrow, single-purpose cross-engine consumer port** (§3.2 ISP) — every cross-engine client Protocol in the codebase is 1-2 methods, purpose-built for exactly what the consuming engine needs, never a copy of the producing engine's full interface. This is the concrete mechanism that makes the DDD boundary discipline (#1 above) actually enforceable in code, not just true in prose.
5. **The `Fake<PortOrRepoName>` test-double naming convention and the `create_app(repository=..., <port>=...)` dependency-injection-for-tests pattern** — fully consistent, zero exceptions, across all 10 engines. Makes every engine's test suite legible to a reader already familiar with any other engine's.
6. **Zero circular dependencies, verified fresh every phase, never once requiring a cycle-breaking intervention** (§7) — worth continuing exactly as-is: a fresh `grimp` graph at every Gate Review, not just trusting that yesterday's zero-cycles result still holds.
7. **The `<engine>.<entity>.<action>` event-subject naming convention and the "outbound RPC subjects live in `published.py`, not `subscribed.py`" rule** (§8) — followed correctly in every single outbound RPC call site checked this session, a real, load-bearing convention, not just a docstring claim.
8. **Scope-boundary honesty in engine READMEs and design docs** — perception-engine's explicit enumeration of what it does *not* yet sense (desktop/browser/filesystem/IoT/wearables, deferred to Phase 4), world-model-engine's explicit "no vector store" claim (verified true), personality-engine's and executive-cognition-engine's explicit "no model-orchestration port" claims (verified true) — every spot-checked scope claim in this review turned out to be accurate. This is a genuinely rare property for a fast-growing codebase and is worth naming explicitly as a standard to protect: never claim a capability, or a non-capability, without verifying it against the code first.

---

## 3. Engine responsibility, SOLID, Clean Architecture, DDD boundary validation

*(Full audit performed by a dedicated deep-read pass across all 10 engines' `domain/` trees, `domain/ports.py` vs. `tests/fakes/`, `repository/models.py` vs. `domain/models.py`, and every README's claims vs. actual code.)*

### 3.1 Engine responsibility validation

Every shipped engine's actual code responsibilities were checked against its own README/design-doc claims, and — with one cosmetic exception — **every spot-checked claim verified true**: world-model-engine's "no vector/embeddings dependency" (confirmed: only `nova-graphstore-sdk` in its `pyproject.toml`), ai-model-orchestration-engine's "connectors/ is the sole LLM-SDK import site" (confirmed), executive-cognition-engine's and personality-engine's "no model-orchestration port" claims (confirmed: neither `domain/ports.py` declares one), reasoning-engine's "no local system of record for any of its six inputs" (confirmed: every foreign concept is a 1-2-method Protocol). This level of README-to-code fidelity, across 9 independently-built engines, is itself a strength worth naming (§2).

One drift found: `memory-engine/README.md:20` describes the forgetting lifecycle as `active → dormant → archived → ...`, but the shipped enum (`packages/nova-contracts/src/nova_contracts/events/memory.py:46-50`, consumed by `domain/lifecycle.py`) names the state `WEAK`, not "dormant" — cosmetic, but a real terminology mismatch a new reader would trip over.

### 3.2 SOLID compliance

- **Single Responsibility** — mostly strong (state machines like `memory-engine/domain/lifecycle.py` and `communication-engine/domain/state_machine.py` are exemplary, single-purpose, zero I/O). One real outlier: `ai-model-orchestration-engine/domain/router.py` is **1,498 lines** — 5.7× the next-largest file in that engine — structurally nine repeated `plan_X_routing`/`route_and_X`/`X_and_record` triplets, one per modality. Each individual function is narrow; the *file* has taken on too much by accretion across three phases of modality extensions (text/embed in Phase 2A, speech in 2D-A, biometric/wake in 2D-B). This is the same file the Phase 2D-B Gate Review already flagged as "the single largest file in the codebase" — now confirmed as a genuine SRP-at-the-module-level concern, not just a line-count curiosity.
- **Open/Closed** — strong: every engine except `nova-core` defines `domain/ports.py` Protocols as its extension seam; new backends/connectors are added by implementing a Protocol, never by modifying domain code. `nova-core` is the one engine with no `ports.py` at all — see Domain Purity below.
- **Liskov Substitution** — verified directly for 3 engines (memory: 17/17 methods match; knowledge: 19/19; world-model: 19/19 across two Protocols) — every checked fake is a true drop-in substitute. The one real gap: no fake declares nominal Protocol conformance (`class Fake(Protocol)`) and no runtime `isinstance` check exists anywhere, so this is enforced only by mypy — see §12 for the important correction that mypy *does* run in CI, but scoped to `src/` only, never `tests/`, meaning a fake silently drifting out of Protocol conformance would not be caught by CI today.
- **Interface Segregation** — a genuinely repeated, strong pattern: every cross-engine consumer Protocol is deliberately narrow (`MemoryPort`/`WorldModelPort`/`PersonalContextPort`/`GoalsPort` = 1 method each; `KnowledgePort`/`ModelOrchestrationPort`/`PersonalityPort` = 1-2 methods). The one real violation: `ai-model-orchestration-engine/domain/ports.py:65-71`'s `ModelConnector` Protocol has 11 methods; its own docstring concedes every connector must `raise NotSupportedError` for whatever it doesn't implement, and `AnthropicConnector` does exactly that for 8 of 11 methods. ADR-023's compliance-suite mitigates the risk (every connector is tested against the full Protocol either way) but doesn't remove the fat-interface smell itself.
- **Dependency Inversion** — clean everywhere: zero instances of any `domain/` importing its own engine's `repository/`, `clients/`, or `api/` modules, across all 10 engines.

### 3.3 Domain purity (Clean Architecture layering)

Zero `fastapi`/`sqlalchemy`/`httpx`/LLM-SDK imports found anywhere in any of the 10 engines' `domain/` trees, and zero cross-engine internal imports — the core Clean Architecture promise holds. Two real, concrete leaks found:

- **`nova-core` is the only engine whose domain code imports live infrastructure directly**: `domain/heartbeat.py:21-23` imports `nova_eventbus_sdk.interface.EventBus`, `nova_observability.get_meter`, and raw `opentelemetry.metrics` types, and instruments an OTel counter/gauge inside `HeartbeatPublisher.__init__`. Every other engine avoids this via a local `EventPublisher` Protocol in its own `domain/ports.py`, explicitly documented as *"structurally identical to `nova_eventbus_sdk.interface.EventBus.request` so the real `BoundEventBus` satisfies it without an adapter"* (verified in `memory-engine/domain/ports.py:173-191`, `knowledge-engine/domain/ports.py:185-192`, `world-model-engine/domain/ports.py:190-194`). `nova-core` is also the **only engine with no `domain/ports.py` at all** — both gaps trace to the same root cause: nova-core predates the ports.py convention (it was the very first thing scaffolded, before the pattern had crystallized) and was never retrofitted.
- **`knowledge-engine/domain/retrieval.py:22-24` and `domain/graph_operations.py:21`** import `GraphStore`/`TraversalDirection`/`TraversalSpec`/`VectorQuery` directly from `nova_graphstore_sdk`/`nova_vectorstore_sdk`, bypassing the engine's own `ports.py` re-exports that exist for exactly this purpose; `retrieval.py:23,34` also imports and calls `nova_observability.get_logger` directly in domain. `memory-engine/domain/retrieval.py:18` has the same minor SDK-bypass pattern. This is defensible in *effect* (these SDK types are pure `BaseModel`/`StrEnum` value types, not concrete backend classes — confirmed by reading both SDKs' `interface.py`), but contradicts the literal rule each engine's own `ports.py` docstring states, and is inconsistent with those same files' own re-export convention.
- **The domain-purity rule itself is enforced only by prose and developer discipline, not by tooling.** `import-linter`'s 4 contracts (independence, no-broker, no-graph-client, no-LLM-SDK) don't include a "domain/ layer may not import repository/api/clients" contract — nothing in `pyproject.toml` would catch a `domain/` file importing `fastapi` tomorrow except a human reviewer or `grep`. Given how cleanly this rule already holds by discipline alone, formalizing it as a 5th import-linter contract (scoped per-engine: `<engine>.domain` forbidden from importing `<engine>.{api,repository,clients,sensors,channels,connectors}`) would be low-risk and would convert a currently-informal-but-real guarantee into a mechanically-enforced one.

### 3.4 DDD boundary validation

Every engine's bounded context is clear and well-separated (one-sentence ownership statements for all 10, verified against `domain/models.py`, given in §3.1's underlying audit). The strongest, most consistently-repeated pattern in the whole codebase is here: **cross-engine data is always modeled as a narrow, explicitly-documented, ID+summary-only local value object, never a duplicated aggregate** — `world-model-engine`'s `PresentIdentitySignal` (carries only `identity_id`/`confidence`/`modality_summary`, explicitly documented as *"a direct pass-through... never a re-interpretation"*, deliberately omitting perception-engine's own `template_ciphertext`/`per_modality_signals`/`observation_count`), `executive-cognition-engine`'s `MemoryReference`, `reasoning-engine`'s `KnowledgeReference` — all textbook anti-corruption-layer objects. This is a genuinely strong, repeated architectural discipline (§2).

One real drift-risk pattern, not a boundary violation: `Goal`, `MemoryReference`, `WorldModelSnapshot`, `PersonalContext`, and `HumanOverrideRequest` are each **hand-duplicated as separate, independently-typed classes** in both `executive-cognition-engine/domain/models.py` and `reasoning-engine/domain/models.py`, with no shared type in `nova_contracts` — correct DDD (each context translates a foreign concept into its own local shape) but with zero mechanism preventing the two hand-copies from drifting incompatibly over time (already visibly diverging: `executive-cognition-engine`'s `Goal` has an additive `goal_tier` field `reasoning-engine`'s copy lacks). A shared, versioned `nova_contracts` type for at least the ones that are identical today (not the ones already legitimately diverging) would remove this risk without violating ADR-004, since `nova_contracts` is explicitly the one shared vocabulary layer every engine already depends on.

A second minor finding: no pydantic model anywhere in the codebase uses `frozen=True` (grepped all 10 `domain/models.py`) — types explicitly documented as immutable snapshots (`WorldModelSnapshot`, `MemoryReference`, `KnowledgeReference`) are immutable by convention only, not by the type system. The `.model_copy(update=...)` functional-update pattern is used in places (`memory-engine/domain/long_term.py:97,144`) but not universally.

### 3.5 Anemic vs. rich domain model check

Overwhelmingly rich, not anemic: `memory-engine/domain/lifecycle.py`'s explicit `_VALID_TRANSITIONS` table and `communication-engine/domain/state_machine.py`'s dict-driven FSM are exemplary; every spot-checked `api/*.py` file (`memory-engine`, `executive-cognition-engine`, `personality-engine`, `knowledge-engine`, `reasoning-engine`) contains only `None`-checks and exception-to-`HTTPException` translation, no business logic.

One concrete, real anemic-model leak found: **`ai-model-orchestration-engine/api/generate.py`'s streaming handler (`generate_stream`, lines 74-164)** performs model-selection lookup, token-count aggregation, direct `cost_tracker.estimate_cost(...)` calls, and hand-builds `UsageRecord`/`OutboxEvent` objects entirely inline in the API layer — duplicating, rather than reusing, the `<x>_and_record` domain function every *other* modality in the same engine correctly uses (`execute_and_record`, `embed_and_record`, `transcribe_and_record`, etc. all live in `domain/router.py`). The same file's own non-streaming `generate` handler (lines 36-61) does this correctly, delegating to `routing.execute_and_record` — making the streaming path's leak a clear, fixable inconsistency within the same file, not an architectural disagreement. `reasoning-engine/api/reason.py`'s own streaming endpoint (`reason_stream`) shows the correct pattern already exists elsewhere in the codebase (`pipeline.run(..., on_stage=on_stage)`, no inline business logic) — this is a "backport the existing correct pattern," not a "invent a new one," fix.

`repository/models.py` vs. `domain/models.py` separation is clean across every spot-checked engine — ORM classes are consistently `...ORM`-suffixed, contain zero business-logic methods, and never leak into `domain/`.

---

## 4. ADR consistency

32 ADRs total (10 foundational, embedded in [00-overview-and-decisions.md](../../architecture/00-overview-and-decisions.md); 22 per-subsystem files, ADR-011 through ADR-032, in `docs/architecture/adr/`). Every ADR with a falsifiable, checkable claim was spot-checked against the actual code this session, not merely re-read.

**Honored, verified directly:**
- **ADR-004** (engine independence) — zero engine-to-engine internal imports, verified by a from-scratch `grimp` graph (§7).
- **ADR-006/007** (no direct broker/graph-DB client import) — `import-linter`'s forbidden-import contracts pass, 4/4, `nova_perception_engine` now included.
- **ADR-014** (Postgres-then-graph two-phase saga) — knowledge-engine and world-model-engine's outbox tables both carry the documented `graph_write`/`graph_applied_at` extension, confirmed identical in shape (§10).
- **ADR-020** (sole legal LLM/model provider channel) — zero direct provider-SDK imports outside `ai-model-orchestration-engine/connectors/`, verified by `import-linter`'s ADR-020 contract; `perception-engine` routes every biometric/wake call through it.
- **ADR-023** (uniform connector compliance suite) — `ai-model-orchestration-engine/tests/contract/test_connector_compliance.py` runs identical compliance tests against all 8 connectors, including the four newest (wake/voice/face/gaze).
- **ADR-024** (interface versioning from day one) — honored in full by every payload module written *since* its adoption (Phase 2A onward: `ai_model_orchestration.py`, `reasoning.py`, `executive_cognition.py`, `personality.py`, `communication.py`). **Not honored retroactively** — see §6.
- **ADR-032** (identity confidence is also an authorization signal) — perception-engine performs no gating of any kind anywhere in its own code (confirmed: zero authorization/threshold logic in `domain/`), and every identity-observed payload carries the full confidence float alongside its tier, mechanically tested (`test_identity_observed_carries_full_confidence_float_alongside_tier`).

**Re-examined, still correctly deferred:**
- **ADR-019** (idle-sweep worker deliberately deferred) — still genuinely unbuilt (`grep` for "idle"/"sweep" in `world-model-engine/workers/__init__.py` finds nothing beyond the pure `next_state_on_idle_timeout` transition function). Worth naming explicitly: ADR-019's own stated precondition ("no real Perception Engine producing events") is now *false* — perception-engine exists. This does not actually change the calculus for ADR-019's own target (generic `WorldObject` staleness for windows/files, still a Phase 4 `nova-companion` concern) — presence/identity staleness is handled by perception-engine's own explicit `present=False` signal, a cleaner mechanism than a timeout sweep for that specific case. ADR-019 remains correctly deferred, but its own "why not yet" reasoning should be refreshed to say so explicitly rather than silently still citing a precondition that's no longer accurate.

**New finding this review — ADR-024 compliance gap:**

`schema_version` is **missing from all ~33 registered payload classes in the four Phase-1-vintage contract modules** — `system.py` (`HeartbeatPayload`, `ModuleStatusChangedPayload`, `ModeChangedPayload`), `world_model.py` (`WorldObjectChangedPayload`, `ContextChangedPayload`, `AttentionShiftedPayload`, `PredictionPayload`, `ContextRequestPayload`, `ContextReplyPayload`), `memory.py` (9 payloads), `knowledge.py` (9 payloads) — verified directly (`grep` for `schema_version` inside every `@register_payload`-decorated class body; confirmed zero hits in these four files, and confirmed present in every payload class in `ai_model_orchestration.py`, `reasoning.py`, `executive_cognition.py`, `personality.py`, `communication.py`). These four modules predate ADR-024's adoption (Phase 1, before ADR-020 through -024 existed), so this isn't a regression — but it was never backfilled, including a fresh missed opportunity **this very session**: `world_model.py`'s `ContextChangedPayload` was extended with `present_identities` as part of the Phase 2D-B World Model extension, and `schema_version` was not added even though the file was already being edited. Recommendation: backfill `schema_version: int = 1` into all ~33 classes as a single, low-risk, mechanical PR — every consumer already treats an absent field as "version 1" implicitly, so this closes the gap without a behavior change.

---

## 5. Bible consistency

- **Part 5 vs. Part 18 (both titled "World Model Engine")** — a pre-existing duplicate-numbering quirk in the source Bible itself (Part 5 "The Digital Consciousness of NOVA," Part 18 "The Real Time Representation of Reality"). Already identified and reconciled during Phase 1 (`docs/architecture/20-engine-responsibility-boundaries.md`, `docs/architecture/00-overview-and-decisions.md`, and the Phase 1 Gate Review all cross-reference this explicitly) — confirmed still honored, not a fresh finding, called out here only because the review was asked to validate Bible consistency and this is the one place the Bible's own numbering needed reconciliation.
- Every shipped engine maps to exactly one Bible Part, with no engine's actual code responsibilities having drifted from its own claimed Part: memory-engine (Part 3), knowledge-engine (Part 10), world-model-engine (Parts 5/18, reconciled), ai-model-orchestration-engine (Part 7), reasoning-engine (Part 8), executive-cognition-engine (Part 19), personality-engine (Part 17), communication-engine (Part 13), perception-engine (Part 11, deliberately minimal slice — voice + camera only, explicitly documented as such rather than silently claiming full Part 11 coverage), nova-core (Part 20).
- Perception-engine's own scope narrowing is itself a positive Bible-consistency pattern worth naming: rather than claiming full Part 11 compliance, its TDD and README both explicitly enumerate what's *not* built yet (desktop/browser/filesystem/IoT/wearable sensing, deferred to Phase 4) — the same discipline Doc 23 §6 ("never claim a capability NOVA does not have") requires, applied to a Bible Part's own scope.

---

## 6. Documentation consistency

The single largest, most significant finding in this review is here.

### 6.1 `docs/architecture/16-testing-strategy.md` describes testing infrastructure that was never built

The canonical testing-strategy document explicitly claims, in its own words:

> "`nova-testkit` provides `testcontainers`-backed fixtures: real Postgres, Neo4j, Redis, and an embedded NATS JetStream instance spun up per test module, torn down after... `nova-testkit` also provides a `FakeModelGateway` implementing the same `ModelConnector` protocol as real providers... Enforced minimum coverage: 85% line coverage on `domain/`... checked in CI."

None of this is true today, verified directly:
- `packages/nova-testkit/src/nova_testkit/` contains exactly three files (`__init__.py`, `plugin.py`, `waiting.py`) totaling 35 SLOC — an in-memory Event Bus fixture and an async polling helper. **No** testcontainers dependency exists anywhere in the dependency tree (`grep -r testcontainers` across the whole repo finds only two aspirational docstring mentions, in `nova-vectorstore-sdk`/`nova-graphstore-sdk`'s own test files, themselves never acted on). **No** Postgres, Neo4j, Redis, or NATS JetStream fixture exists. **No** `FakeModelGateway` exists anywhere (zero grep hits).
- **No coverage enforcement exists in CI at all** — confirmed by reading `.github/workflows/pr-checks.yml` and every engine's `package.json`: the `test` script is a bare `uv run --package <name> pytest`, no `--cov` flag, no `--cov-fail-under`, anywhere. `communication-engine` currently sits at 65% *total* coverage (well below the claimed 85% domain threshold) and CI is green.

This is precisely the class of problem the project's own "verify before trusting documentation" standing rule (adopted at the Phase 2D-B Gate Review) exists to catch — applied here to the project's own canonical architecture documentation, not a phase-specific TDD.

**The honest, positive counterpoint**: the *outcome* this policy was meant to protect is largely being achieved anyway, through practiced discipline rather than tooling enforcement. A spot-check of `domain/`-only coverage this session (`pytest --cov=<pkg>.domain`) found memory-engine at 97%, communication-engine at 99%, perception-engine at 99% — all comfortably clearing the claimed 85% threshold in practice, just not by anything that would catch a regression automatically. This nuances the finding: the gap is between *what's promised in writing* and *what's mechanically enforced*, not between what's promised and what's actually true today.

**Recommendation**: either (a) build the `testcontainers`-backed fixtures and `--cov-fail-under=85 --cov=<pkg>.domain` CI gate the document already describes as if it exists, or (b) rewrite `16-testing-strategy.md §3` to describe what's actually built today (in-memory Event Bus fixture, manual per-Gate-Review coverage measurement) and track the testcontainers/coverage-gate work as an explicit, named future item rather than leaving it stated as present-tense fact. Given the "verify before trusting documentation" principle this project has now formally adopted, (b) at minimum should happen immediately regardless of whether (a) is scheduled.

### 6.2 Stale "pending approval" status lines

Four documents still say implementation "must not begin" or is "pending review" for engines that have been fully implemented, tested, Gate-Reviewed, and approved for one or more phases:
- `docs/design/phase-2b/README.md:10` — Reasoning Engine has been implemented and Gate-Reviewed (Go) since Phase 2B.
- `docs/design/phase-2d/01-communication-engine.md:18` and `docs/design/phase-2d/02-personality-engine.md:12` — both engines implemented and Gate-Reviewed (Go) since Phase 2D-A.
- `docs/roadmap/ENGINEERING_ROADMAP.md:396` (the Phase 2D narrative section, not the top status line, which is kept current) — same claim about the 2D-A TDDs.

This is not a systemic failure: Phase 2A's and Phase 2C's own design README status lines *were* correctly updated after approval (spot-checked directly), and this review's own Phase 2D-B updates (previous session) correctly updated the top-of-file roadmap status and the Phase 2D-B design doc's own status line. The gap is specifically: Phase 2B's README, and Phase 2D-A's two TDDs' own status lines, plus the roadmap's *per-phase narrative section* (separate from its top summary paragraph) were never revisited. **Root cause**: there is no checklist item at Gate Review time enforcing "update every design doc's own status line, not just the roadmap's top paragraph." Recommend adding this as an explicit Gate Review checklist step going forward, and fixing the four stale lines named above as a trivial, immediate cleanup.

### 6.3 `docs/architecture/20-engine-responsibility-boundaries.md`'s diagram is stale

Its interaction diagram (§5) still labels `Perception["Perception Engine\n(Phase 4)"]` in a dotted "not yet built" style, even though Perception Engine (a deliberately minimal Phase 2D-B slice) now exists and publishes exactly the `perception.*.observed` events this diagram shows. Lower severity than §6.1/§6.2 — this document's own title scopes it to Memory/Knowledge/World Model specifically, so the Perception label was accurate when written and has simply not been revisited as the roadmap evolved Perception from "Phase 4" to "Phase 2D-B." Worth a one-line fix in any documentation cleanup pass.

### 6.4 `tools/scaffold-engine.py`'s `_update_root_pyproject` has been silently broken since the second engine

This is a tooling-vs-documentation-claim gap, not a markdown-file gap, but belongs here for the same reason: the tool's own docstring claims it adds every new engine "to the workspace-wide import-boundary contracts... so it's enforced from its very first commit, exactly like every other engine" (`tools/scaffold-engine.py:91-95`). Reading the implementation shows this is done via four `str.replace(old, new, count=1)` calls where `old` is a literal string that only matches when `root_packages` (and each contract's `modules`/`source_modules` list) contains **exactly one entry** (`"nova_core"` alone) — true only for the very first engine scaffolded after `nova-core`. For every engine after that, the literal pattern no longer exists in the file, so `.replace()` silently returns the original text unchanged, with **no error, no warning**. Verified directly: running the same pattern-match against the current `pyproject.toml` confirms zero matches. This exactly explains why `nova_perception_engine` was found missing from all four import-linter contracts during this phase's own build (and had to be added manually) — and strongly suggests the same silent no-op happened for every engine scaffolded after the second one (`knowledge-engine` onward), each one presumably caught and fixed manually during that phase's own build, the same way this phase's was, without anyone naming the tool itself as the root cause until now.

**Recommendation**: fix `_update_root_pyproject` to parse and rewrite the TOML structurally (e.g. via `tomlkit`, which preserves formatting and comments, unlike `tomllib` which is read-only) rather than literal-string matching, so it's correct for the 11th engine as reliably as the 2nd. Low-risk, mechanical, and removes a recurring manual-verification burden every future engine's build has silently been paying.

---

## 7. Cross-engine dependency / import graph / circular dependency analysis

A from-scratch `grimp` graph was built this session (walking every module's own imports, not just each package's `__init__`) over all 17 first-party packages. Unchanged from the Phase 2D-B Gate Review since no code has changed:

- **39 package-to-package edges**, all of them an engine importing a shared package (`nova_contracts`, `nova_eventbus_sdk`, `nova_observability`, plus `nova_graphstore_sdk`/`nova_vectorstore_sdk`/`nova_embeddings_sdk` for the 3 engines that need them). **Zero engine-to-engine edges.**
- **Zero cycles**, verified by an explicit DFS over the edge set (not merely inferred from `import-linter`'s contracts passing, which check specific declared boundaries rather than the graph globally).
- Every engine's own minimal-footprint shape holds: `perception-engine` adds exactly 3 edges (`nova_contracts`, `nova_eventbus_sdk`, `nova_observability`) — the same shape every engine since `reasoning-engine` has established. No engine imports a graph/vector/embedding SDK it doesn't functionally need.

This is one of the strongest, most consistently-held architectural properties in the whole project — 10 engines built across 5 phases by the same iterative process, and the dependency graph has never once needed a cycle-breaking intervention. Worth naming as a permanent standard in §2, not just a passing check.

---

## 8. Event Bus architecture review

- **Outbound-RPC-declared-in-`published.py`-not-`subscribed.py` convention** — verified correctly applied without exception, across every client call site in every engine that makes an outbound RPC (reasoning-engine's five, perception-engine's four, executive-cognition-engine's two, communication-engine's five, memory-engine's two). Every corresponding server-side subject is correctly declared in the *serving* engine's own `subscribed.py`. This is a real, load-bearing, universally-applied convention — not just a docstring claim.
- **No double-subscription risk** — every `bus.subscribe`/`bus.serve` call site across all 10 `main.py` files registers each subject pattern exactly once per engine; legitimate multi-engine fan-out on the same wildcard (`perception.*.observed` subscribed by both `memory-engine` and `world-model-engine`) is expected, not a bug.
- **Subject-naming convention (`<domain>.<entity>.<action>`, 3 segments) is followed by 90 of 99 unique subjects.** The 9 outliers: `nova.heartbeat` and `action.result` (2 segments each, both pre-existing/Phase-1-vintage), and communication-engine's three served RPCs + one outbound RPC use 4 segments (`communication.session.create.request`, `communication.intent.deliver.request`, etc. — folding a verb into what's normally a single `<action>` segment). Cosmetic, not a functional risk, but worth normalizing if a "permanent standards" pass happens (§2/§25).
- **A real, concrete stale subscription**: `knowledge-engine/events/subscribed.py:21` and `memory-engine/events/subscribed.py:19` both subscribe to `reasoning.result`, live-wired in both engines' `main.py`. **`reasoning-engine` — a real, shipped engine — does not publish this subject.** Its actual completion events are `reasoning.process.completed`/`reasoning.process.failed`/`reasoning.human_override.applied` (`reasoning-engine/events/published.py:21-23`). Both subscribing files' own docstrings note "no real Phase 1 producer yet" — true when written, before reasoning-engine existed, but the producer that exists *today* publishes under different names entirely, so the subscription is now stale relative to reality rather than merely forward-declared. **This should be fixed as part of Phase 2D-C or sooner**: either wire `memory-engine`/`knowledge-engine` to the subjects reasoning-engine actually publishes, or remove the dead `reasoning.result` subscription and replace it with the real ones if the intended behavior is still wanted. (`action.result` has the same "subscribed with zero publisher" shape but is lower-risk — genuinely reserved for a not-yet-built future Action/Agent-OS engine, not a stale reference to one that already shipped under a different name.)

---

## 9. API consistency review

- **`/v1/<domain>/...` convention**: 41 of 44 `APIRouter` declarations use an explicit, correctly-namespaced prefix. Two real deviations: `memory-engine/api/decisions.py:12` uses a bare `/v1/decisions` prefix (should be `/v1/memory/decisions` or `/v1/memories/decisions` by the pattern every sibling engine follows) and `perception-engine/api/sensors.py:15` declares `APIRouter(tags=["sensors"])` with **no prefix at all**, hardcoding the full `/v1/perception/...` path on each route individually instead. Both land in the right place functionally; both are the only two files in the whole codebase that don't use the `prefix=` mechanism the other 42 routers rely on.
- **`api/health.py`**: exactly one per engine, and 9 of 10 are **byte-identical** (same MD5 hash, 27 lines) — `nova-core`'s is the sole, arguably-justified deviation (adds `uptime_seconds`/`boot_phase` since it's the boot orchestrator).
- **HTTP status codes**: POST-create is 100% consistently `201`, DELETE is a deliberate, well-documented split (`204` for true hard deletes vs. default `200`-with-body for state-transition "soft deletes" that leave a record behind) — not an inconsistency once the underlying semantic distinction is understood.
- **Request/Response Pydantic naming**: universal `<X>Request`/`<X>Response` suffix convention, 67 classes checked across all 10 engines, zero deviations at the top level.

---

## 10. Database schema, migration, and repository layer review

- **Schema namespacing, PK/timestamp conventions, JSONB usage**: fully consistent across all 9 database-owning engines (each has its own Postgres schema via `MetaData(schema=...)`; every timestamp is `TIMESTAMPTZ` with `server_default=func.now()`; every open/extensible field is `JSONB`, never plain `JSON`).
- **No cross-engine foreign keys** — verified across every `models.py`: every FK target is scoped to the same engine's own schema; cross-engine references are consistently plain, unconstrained UUID/Text columns. This is the correct microservice-per-engine boundary, applied without exception.
- **`version_table` Alembic namespacing** (the Phase 2C-era cross-engine collision fix) is now confirmed applied identically and correctly across **all 9** engines, both online and offline migration paths — the fix has fully propagated, no regression.
- **A real, confirmed bug**: `ai-model-orchestration-engine`'s `model_registry.updated_at` column has neither `onupdate=func.now()` nor is it ever set explicitly by `update_health()`/`update_benchmark()` — meaning **the column is set once at INSERT and never changes again**, even though `health_status`/`avg_latency_ms`/`avg_quality_score` are updated repeatedly without it. Since this column exists specifically to track staleness, this defeats its own purpose. Concrete, low-risk fix: add `onupdate=func.now()` to the column or pass `updated_at=func.now()` in both update paths.
- **A real, confirmed ORM/migration mismatch in perception-engine, this project's newest engine**: the migration creates a real FK (`identity_id UUID REFERENCES perception.enrolled_identity`), but the ORM model declares the same column with no `ForeignKey()` — every other engine's FK columns are declared consistently in both places. This directly contradicts the migration file's own docstring claim ("hand-written to match this file precisely") and should be fixed (add `ForeignKey("perception.enrolled_identity.identity_id")` to `repository/models.py`).
- **`model_health_snapshot.id` under-declared width**: migration says `BIGSERIAL` (8-byte); ORM declares `Mapped[int]` with no `BigInteger` type, defaulting to SQLAlchemy's 4-byte `INTEGER` mapping. Not currently exploitable (Postgres round-trips fine regardless of the Python-side declared width) but a real under-declaration `world-model-engine`'s structurally identical append-log table gets right (`BigInteger` explicitly imported and used).
- **Outbox pattern**: implemented with an essentially identical table shape across all 8 publishing engines (personality-engine's absence is deliberate and explicitly documented, not an oversight — it publishes nothing this phase). `DEFAULT_BATCH_SIZE = 100` and the 10-second Arq cron cadence are byte-identical across all 8. This is a strong, safe candidate for a **permanent, hard standard** (§2) — no deviation found beyond the deliberate, correctly-scoped graph-write extension in the two graph-owning engines.
- **Repository transaction discipline**: every single write method across all 9 repositories opens `.begin()`; every single read method does not — verified exhaustively, zero exceptions across 18 repository files. This is a real, strong, consistently-applied pattern worth calling a permanent standard.
- **`_x_to_domain(row) -> DomainType` translation-function convention**: applied everywhere, one function per ORM class, named consistently — the one exception (`ai-model-orchestration-engine`'s `_to_domain`, dropping the entity-name segment used everywhere else) is trivial.
- **Minor naming drift**: `db_session` vs. `session` as the transaction-context variable name splits 7-vs-2 across the 9 engines (communication-engine and perception-engine use `db_session`); `memory-engine` alone names its outbox dispatch function `dispatch_pending` instead of the `dispatch_ready_events` name all 7 other outbox-owning engines converged on, and implements it with raw SQLAlchemy directly against the ORM rather than the `repository.list_dispatch_ready()`/`mark_dispatched()` port-abstraction every later engine uses — a Phase-1-vintage implementation that was never retrofitted when the later convention crystallized.
- **`PrivacyLevel` enforcement inconsistency**: memory-engine and knowledge-engine enforce the shared `PrivacyLevel` enum as a native Postgres `ENUM` type (DB-level rejection of an invalid value); `ai-model-orchestration-engine` stores the identical concept as unconstrained `TEXT`, with no CHECK constraint — a typo'd privacy value would be silently accepted there but rejected in the two Phase-1 engines.

Full per-engine table inventory (46 tables total, 9 schemas, matching exactly between every engine's `models.py` and its own migration): memory (6), knowledge (6), world-model (5), ai-model-orchestration (5), reasoning (7), executive-cognition (5), communication (4), perception (5), personality (3, no outbox by design), nova-core (0, no database).

---

## 11. Domain purity review

Covered in full in §3.3. Summary: zero framework/LLM-SDK imports in any `domain/` tree across all 10 engines; two real leaks found (`nova-core`'s direct OTel/EventBus imports in `domain/heartbeat.py`, and `knowledge-engine`/`memory-engine`'s direct SDK-type imports bypassing their own `ports.py` re-exports); the rule itself is enforced by discipline and code review, not by `import-linter` tooling — a concrete, low-risk opportunity to close (§24).

---

## 12. Error handling, logging, and observability consistency

**Error handling**: exception naming is consistent (`<Adjective/Reason>Error`, PascalCase, subclassing a semantically-appropriate stdlib exception) across the 8 engines that define custom exceptions, and `api/*.py` consistently translates them via `try/except <DomainError> as exc: raise HTTPException(status_code=N, detail=str(exc)) from exc`, with sensible status-code mapping (not-found→404, state/version conflict→409, upstream unavailable→503, consent/auth→403). Two real gaps:
- **`personality-engine` and `executive-cognition-engine` define zero custom domain exception classes.** `executive-cognition-engine/repository/postgres_executive_repository.py:186` raises a bare, unclassed `LookupError` that `api/decisions.py:88-90` never catches (a pre-check at lines 70-72 duplicates the logic instead of catching the error) — if ever triggered by a race, this surfaces as an unhandled 500, unlike every other engine's mapped-to-4xx pattern.
- **`perception-engine/domain/sensor.py:77`'s `SensorError` is a Pydantic `BaseModel` DTO (a sensor-error *event*, not an exception)** — the only class in the codebase using the `...Error` naming convention for something that isn't a raisable exception, which fooled even this review's own automated `class.*Error` sweep. Recommend renaming to `SensorErrorReport` to remove the ambiguity.
- Broad `except Exception:` appears 29 times repo-wide; `ai-model-orchestration-engine` disciplines every instance with an inline rationale comment (though the `noqa: BLE001` markers suppress a ruff rule — `BLE` — that isn't actually enabled in `pyproject.toml`, so the self-documentation habit is good but currently untooled); `memory-engine`, `knowledge-engine`, `world-model-engine`, and `personality-engine` use the same broad-catch pattern for the same legitimate degraded-mode-fallback reason, but without the inline rationale.

**Logging**: main-app and sub-component logger naming is 100% consistent (`get_logger("<engine>")`, `get_logger("<engine>.<component>[.<subcomponent>]")`) with zero deviations across all 10 engines. Zero stray `print()` statements, zero f-string-interpolated log messages anywhere in `src/` — both genuinely clean, repo-wide. Two real gaps: the Arq worker-process logger uses a hyphen (`<engine>-worker`) instead of the dot convention (applied uniformly, so low-severity); only 4 of 9 event-driven engines (`memory`, `knowledge`, `world-model`, `perception`) instantiate a sub-logger inside `events/handlers.py` at all — the other 5 have the file but never log from it, meaning event-handling failures in those 5 engines are effectively unlogged at the handler layer. Structured `extra={}` usage is uneven — `personality-engine` never uses it once (every log line it emits is unstructured, an outlier against `memory`/`knowledge`/`world-model`'s "gold standard" structured-logging discipline).

**Observability**: `create_metrics()` returns `@dataclass(frozen=True)` in every one of the 9 engines that has an `observability.py`; metric naming is uniformly Prometheus-style (`<engine>_<thing>_total` for counters, `..._seconds` for histograms, correctly omitted for non-duration histograms like confidence scores); the `create_metrics()`-after-`configure_observability()` ordering is not just claimed in a comment but verified actually correct in all 9 `main.py` files. **`nova-core` has no `observability.py` at all** — it mounts `/internal/metrics` and calls `configure_observability`, but never calls `create_metrics()`, so its metrics endpoint scrapes successfully but returns only default OTel process metrics, none of its own (no boot-phase-duration histogram, no module-health counter, despite `domain/boot.py`'s `NovaHost` being exactly the kind of stateful orchestration that would benefit from one). This is the one clear outlier in an otherwise fully-uniform pattern — and, combined with §3.3's finding that `nova-core` is also the only engine with no `domain/ports.py`, points to the same root cause: it was scaffolded first, before several conventions had crystallized, and was never retrofitted as those conventions became universal across every engine built after it.

**Middleware/global error handling**: confirmed, repo-wide, zero uses of `add_middleware`, `exception_handler`, `CORSMiddleware`, or any request-ID propagation mechanism, in any engine. This is a uniform gap, not an inconsistency: no engine has a global unhandled-exception → structured-JSON-error-response handler (an unhandled exception falls through to FastAPI's default plain-text 500, inconsistent with the JSON-structured-everything-else philosophy this project otherwise enforces), and there's no HTTP-level request/correlation-ID propagation (domain-level `correlation_id` threading through outbox events is universal and solid, but it isn't generated or read at the HTTP boundary itself). A good, concrete candidate for a future shared middleware package (§27).

---

## 13. Configuration consistency

`env_prefix`, `env_file=".env.local"`, and `extra="ignore"` are 100% consistent across all 10 `Settings` classes; `http_port: int = 8000` and `log_level: str = "INFO"` are identical by name, type, and default in all 10; `postgres_dsn`/`redis_url` field names and dev-mode defaults are byte-identical across every engine that needs them. Two minor, real deviations: `nova-core`'s settings class is named `NovaCoreSettings` while all 9 others use the bare name `Settings` for the identical role; `personality-engine` has no `redis_url`/`workers/`/outbox files at all — a deliberate, self-consistent, but architecturally divergent design (it publishes via `BoundEventBus` directly rather than the outbox pattern every sibling uses), worth a reliability-guarantees discussion since it means personality-engine's published events have no transactional-delivery guarantee its 8 siblings all have.

**No hardcoded secrets found anywhere** — repo-wide grep for password/API-key/secret/token literal patterns across every `config.py`/`main.py` returned zero matches beyond the one legitimate secret-shaped field (`ai-model-orchestration-engine`'s `anthropic_api_key: str = ""`, empty-by-default, populated exclusively via env var, with an explicit docstring explaining why). The one literal credential-shaped string anywhere in the codebase is the shared dev-mode DSN password `nova_dev_password`, embedded identically across all 9 `postgres_dsn` defaults — a well-known, low-risk local-dev convenience, not a real secret, but worth a footnote.

---

## 14. Security review

- **Consent-as-gate**: perception-engine's `require_active_consent` is the one gate every capture-adjacent operation passes through, verified failing explicitly (never silently) when absent.
- **Encryption boundary**: perception-engine's template encryption/decryption is confined entirely to `domain/enrollment.py`/`domain/matching.py`; the repository layer never sees a plaintext embedding, verified directly and by dedicated tests.
- **Revocation is a real hard delete**, not a soft-delete flag, in every engine that supports it.
- **No engine performs authorization/gating based on identity confidence** (ADR-032) — a structural property, not a policy statement, since perception-engine's own code contains no gating logic to audit for bypass.
- **No hardcoded secrets anywhere** (§13).
- **No global exception handler exists in any engine** (§12) — the practical security implication is that an unhandled exception's default FastAPI 500 response could, in principle, leak a stack trace or internal detail to a caller in a misconfigured deployment (FastAPI's `debug=False` default protects against this locally, but there is no engine-level belt-and-suspenders handler enforcing a sanitized error response). Worth closing before this project has a public-facing deployment surface.
- **No global rate limiting, no authentication/authorization middleware, on any engine's own HTTP surface** — expected and correct at this phase (every engine's HTTP surface is presumed private-network/gateway-fronted, per the project's own architecture; there is no public API Gateway built yet for this to apply to), but named here explicitly so it's tracked as a real precondition for public deployment rather than silently assumed handled.
- **`pip-audit`/`pnpm audit`** run in CI (`build-and-scan.yml`) and Trivy container scanning (CRITICAL/HIGH, exit-code 1 on findings) runs on every service's built image — this is a real, currently-passing security gate, not aspirational.

## 15. Privacy review

- **Perception-engine's own privacy architecture** (already reviewed in depth at the Phase 2D-B Gate Review, re-confirmed unchanged this session): raw audio/camera frames are never persisted (only derived embeddings and fused observations reach Postgres); every identity judgment carries a `per_modality_signals` audit trail for trust-through-inspectability; consent is per-source and immediately revocable.
- **`PrivacyLevel` classification exists as a shared vocabulary** (`nova_contracts.events.memory`) used consistently by memory-engine, knowledge-engine, and ai-model-orchestration-engine — but DB-level enforcement is inconsistent (§10): memory/knowledge enforce it as a native Postgres ENUM (a typo'd value is rejected), ai-model-orchestration-engine stores it as unconstrained `TEXT` (a typo'd value is silently accepted). Worth closing as part of the same pass that fixes the other DDL-consistency findings.
- **No engine logs raw user content at `INFO`/`DEBUG` in a way that would leak into aggregated logs** — spot-checked across `memory-engine`, `communication-engine`, and `perception-engine`'s `extra={}` structured-log fields; none embed full memory/message content, only IDs, states, and counts.

---

## 16. Build pipeline and CI review

Two workflows: `pr-checks.yml` (lint, import-boundary check, tests, docker-compose config validation — via Turborepo's per-package `lint`/`test` scripts, so it needs no per-language special-casing as new packages are added) and `build-and-scan.yml` (Docker image build + Trivy vulnerability scan per service, plus `pip-audit`/`pnpm audit`).

**Correction to one research finding this review must flag explicitly**: one of this session's own research agents reported "mypy is not invoked in either CI workflow." This is **not accurate** — verified directly by reading `pr-checks.yml:54-55` (`pnpm turbo run lint`) and every engine's `package.json` (`"lint": "uv run --package <name> ruff check . && uv run --package <name> mypy src"`). **Mypy does run in CI**, on every package, via Turborepo's delegation to each package's own `lint` script — it's simply not a *named* "mypy" step in the workflow YAML itself, which is presumably what led the agent's grep to miss it. The real, narrower, still-valid version of the underlying concern: **mypy is scoped to `src/` only, never `tests/`**, in every engine's `lint` script — so a test fake silently drifting out of Protocol conformance with the interface it fakes (§3.2's LSP finding) would not be caught by CI's mypy invocation, since fakes live under `tests/fakes/`. This is a real, worth-fixing gap, just a different and smaller one than "no mypy at all."

**A second, larger, confirmed gap**: no CI step runs `pytest --cov` or enforces any coverage threshold. `docs/architecture/16-testing-strategy.md`'s own claim of "enforced minimum coverage: 85%... checked in CI" is not true today (§6.1) — `communication-engine` sits at 65% total coverage and CI is green. Coverage is currently measured manually, once per Gate Review, not continuously.

**Strengths**: the Turborepo-based dispatch means CI needs zero changes when a new engine is scaffolded (beyond the one still-manual `build-and-scan.yml` matrix line, §6.4); `docker compose config --quiet` validates the full compose file's YAML/schema correctness even without a live daemon; concurrency groups with `cancel-in-progress` avoid wasted runs; the Trivy/pip-audit/pnpm-audit security gates are real and currently passing, not aspirational.

---

## 17. Testing quality and coverage

951 tests pass across all 17 packages (unchanged since the Phase 2D-B Gate Review — no code has changed). Aggregate coverage over the 10 production services (`memory-engine` through `perception-engine`) is 78.7% (10,952 statements, 2,330 missed). Per-engine range: communication-engine lowest at 65% (concentrated in `clients/`/`repository/`/`workers/`/`channels/voice_adapter.py`, all real-infra-only code paths), perception-engine highest among the newest engines at 81%.

The most important nuance, already surfaced in §6.1: the claimed-but-unenforced 85% `domain/`-only coverage target is **actually being met in practice** — a fresh spot-check this session (`pytest --cov=<pkg>.domain`) found memory-engine at 97%, communication-engine at 99%, perception-engine at 99%, all well above the claimed threshold despite no CI gate enforcing it. This is a genuine positive: the engineering discipline that produced this project has consistently over-delivered against its own untooled aspiration, which is a healthier failure mode than the reverse, but it is still worth closing the enforcement gap (§16) so that discipline is guaranteed rather than merely observed.

**No real-Postgres integration testing exists anywhere in the project** — not because of the Docker-daemon unavailability alone (the proximate, repeatedly-cited blocker across the last two phases), but because `nova-testkit` itself has never been extended with the `testcontainers`-backed fixtures `16-testing-strategy.md` describes as already existing (§6.1). This is the single most consequential finding in this entire review, and is treated at length in §27 (Architectural Opportunities) given its scope.

No end-to-end tests exist (unchanged since every prior phase — expected at this project's current maturity, no live multi-service environment exists to run one against). No contract-test coverage gap found: perception-engine's `tests/contract/` and ai-model-orchestration-engine's existing connector-compliance suite both exercise real subject-matching/Protocol-conformance mechanically, not by convention.

---

## 18. Complexity and code duplication analysis

**Complexity** (via `radon cc` over `src/` across all 17 packages, this session's own ephemeral tool install — not yet a committed dev dependency, noted so a future session doesn't assume it's already available): 1,895 blocks analyzed, average complexity **A (1.87)** — very low, healthy. Two D-grade outliers, both pre-existing (Phase 2B and 2D-A respectively, not introduced this phase or found newly this review): `reasoning-engine/domain/pipeline.py`'s `run` (D, 27) and `communication-engine/api/websocket.py`'s `session_websocket` (D, 22). No `perception-engine` function appears in the top 10 most complex blocks in the codebase.

**Code duplication — structural (boilerplate), quantified precisely this session**:

| File pattern | Engines | Duplication | Recommendation |
|---|---|---|---|
| `api/health.py` | 9/10 byte-identical (MD5-verified) | ~216 duplicated lines (8 exact extra copies) | Highest ROI, near-zero risk — extract a `make_health_router()` factory |
| `repository/db.py` | 9/9 identical except docstring | ~136 duplicated lines | Highest ROI, near-zero risk — extract `create_engine_and_session_factory(dsn)` |
| `repository/outbox_dispatcher.py` core loop | 7/8 near-identical (memory-engine diverges, §10) | ~180-210 duplicated lines | Good ROI; fixes memory-engine's naming/implementation drift as a side effect |
| `workers/__init__.py` skeleton | 8 engines, ~20-25 line shared skeleton within 74-117 line files | ~160-200 duplicated lines (skeleton portion only) | Legitimate but lower priority — most of each file's bulk is justified per-engine wiring, not boilerplate |

None of this crosses ADR-004 (it's infrastructure/boilerplate, not domain logic) — a small, new shared package (or additions to `nova-observability`) is the natural home for the first three. This is treated as a formal recommendation in §24.

**Code duplication — domain logic**: no verbatim-copied business logic found anywhere (ADR-004 holds). One recurring *pattern* (not copy-paste) worth naming: "weighted composite score, then select/sort" recurs independently in `ai-model-orchestration-engine/domain/router.py` (`_score`), `reasoning-engine/domain/confidence.py` (`_weighted_composite`), and `memory-engine/domain/ranking.py` (`rank`) — each a reasonable, independent, ADR-004-compliant implementation, but each handles a *missing signal* differently (redistribute weight proportionally, treat as zero, or default to a fixed midpoint). Unifying these into a shared scorer utility would only be safe *after* deliberately reconciling which missing-data semantic is actually correct — attempting it now would silently change behavior in at least two of the three engines. A smaller, real drift risk: the `ConfidenceTier` vocabulary (`high`/`medium`/`low`/`unknown`) is independently represented three different ways (`nova_contracts`'s canonical `StrEnum`, personality-engine's own separate identically-valued `StrEnum`, perception-engine's bare `Literal` alias) — three representations of one 4-value vocabulary that must be kept in sync by hand if a 5th tier is ever added upstream.

**Naming consistency**: handler-factory naming (`make_<x>_handler`) and test-fake naming (`Fake<PortOrRepoName>`) are both **fully consistent, zero exceptions, across all 10 engines** — genuinely clean conventions worth calling permanent standards. The only naming drift found: memory-engine's `dispatch_pending` vs. the 7-engine `dispatch_ready_events` convention (§10, same root cause as its outbox-dispatcher implementation divergence), and the `session`/`db_session` variable-naming split (§10).

---

## 19. Performance analysis

No load testing has been performed at any phase of this project (no live infrastructure has ever been reachable in a review environment) — this remains true and is stated plainly rather than assumed. Static analysis this session found no obvious anti-patterns: zero query-in-loop (N+1) patterns detected across any repository layer (verified by scanning every `for` loop in every `postgres_*_repository.py` for a nested `.execute()` call); an initial concern about unbounded `select()` calls without `.limit()` was investigated and found to be a false positive of line-based grepping — closer inspection confirmed the actual queries either carry a `.limit()` a few lines later in the same statement, or are narrowly filtered by a single ID/user, or target genuinely small config-like tables (model registry, budgets). No unbounded-query risk was found. The `identity_fusion.fuse_window`/`smooth` functions (perception-engine) remain pure, allocation-light, small-input functions with no performance concern at the single-user-default scale this phase targets (ADR-025). The TDD-stated latency goals (e.g. wake-phrase p95 < 300ms) remain unmeasured, not assumed met, for the same reason as every prior phase: no real connector, no real audio, no live environment.

## 20. Maintainability assessment

Strong overall: low average cyclomatic complexity (1.87), consistent layering (domain purity holds with two minor exceptions), consistent naming (handler factories, test fakes, exception classes all converge cleanly), and a genuinely repeated anti-corruption-layer DDD pattern across every cross-engine boundary. The two real maintainability risks found this review: `ai-model-orchestration-engine/domain/router.py`'s continued growth (1,498 lines now, up from 1,384 at the last Gate Review's own measurement two modality-extensions ago — see engineering-metrics discrepancy note in §28) toward a point where a single reviewer can no longer hold the whole file in working memory; and the ~700 duplicated lines of pure boilerplate across `api/health.py`/`repository/db.py`/`repository/outbox_dispatcher.py`/`workers/__init__.py` (§18), which is not currently a correctness risk (all copies are functionally identical) but is a real maintenance-burden risk the moment any one of these patterns needs to change (e.g. adding OpenTelemetry trace-context propagation to every engine's outbox dispatch would today require 7-9 separate, easy-to-miss edits).

## 21. Scalability assessment

No change to the project's overall scalability posture this review — every engine remains stateless-per-request (the one intentional exception, `communication-engine`'s `session_registry.py`-style in-memory trackers, mirrored now in `perception-engine`'s `SessionActivityTracker`, is explicitly documented as safe-to-lose state, not a scaling constraint). No new stateful singleton, no new synchronous cross-engine call chain was introduced since the last review (none was introduced this review at all, since this review changes no code). The outbox-worker-per-engine pattern (§10) scales horizontally by design (each engine's own Arq worker is independently deployable/replicable). The one architecture-level scalability question worth naming for a future phase: as the number of engines grows past 10, the "every engine polls its own outbox every 10 seconds" pattern means outbox-dispatch latency stays flat per-engine (good), but the total number of independent Postgres polling connections grows linearly with engine count — worth revisiting if a future Engineering Review Milestone (50,000 SLOC) finds this material, not urgent today.

## 22. Technical debt assessment

Consolidated list of concrete debt items found this review (each already detailed in its own section above, cross-referenced here for a single inventory):

| Item | Section | Severity |
|---|---|---|
| `16-testing-strategy.md` describes testcontainers/coverage infrastructure that was never built | §6.1 | High — misleads anyone trusting the doc, and blocks real-Postgres verification even once Docker is available |
| `model_registry.updated_at` never updates after INSERT | §10 | Medium — silently defeats the column's own purpose |
| `identity_observation.identity_id` FK missing from perception-engine's ORM model | §10 | Medium — migration/ORM drift on the newest engine |
| `tools/scaffold-engine.py`'s `_update_root_pyproject` silently no-ops from the 3rd engine onward | §6.4 | Medium — recurring, silent, manual-verification burden every future engine pays |
| `reasoning.result` subscribed by 2 engines but never published under that name | §8 | Medium — dead subscription masquerading as a live one |
| Four stale "pending approval" doc status lines | §6.2 | Low — cosmetic, but erodes trust in status lines generally |
| ~692 lines of pure structural boilerplate duplication (`health.py`/`db.py`/`outbox_dispatcher.py`/`workers/__init__.py`) | §18 | Low-Medium — no correctness risk today, real maintenance-burden risk on next cross-cutting change |
| `ai-model-orchestration-engine/domain/router.py` at 1,498 SLOC, largest file in the codebase | §3.2 | Low-Medium — not yet unmanageable, trending toward it |
| `personality-engine`/`executive-cognition-engine` have no custom exception classes; one unhandled-`LookupError` path in executive-cognition-engine | §12 | Low-Medium |
| `nova-core` missing `domain/ports.py` and `observability.py`; its domain code imports infra directly | §3.3, §12 | Low — isolated to the one engine that predates both conventions |
| `PrivacyLevel` enforced as a Postgres ENUM in 2 engines, unconstrained TEXT in a 3rd | §10, §15 | Low |
| ADR-024 (`schema_version`) not backfilled into ~33 Phase-1-vintage payload classes | §4 | Low — no behavioral impact, but a real, growing documentation-vs-code gap |
| No global exception handler / no HTTP-level request-ID propagation, uniform across all engines | §12, §14 | Low today, real precondition for a public-facing deployment |

None of these are severe enough to block Phase 2D-C on their own. Collectively, they are exactly the kind of accumulating friction a Project Health Review exists to surface before a 100,000+ SLOC codebase makes each one individually more expensive to fix.

## 23. Long-term risks

- **The documentation-vs-reality gap found in `16-testing-strategy.md` (§6.1) is the review's single biggest long-term risk if left uncorrected.** Every future phase's Gate Review will keep citing "no real-Postgres verification, blocked on Docker availability" as if that's the only blocker, when the deeper blocker (no fixture exists to use *once* Docker is available) will keep silently deferring the same recommendation indefinitely unless someone builds the fixture. This has already happened once (three consecutive phases: 2D-A, 2D-B, and now this review, all citing the same open item without anyone tracing it to its root cause until this session).
- **`ai-model-orchestration-engine/domain/router.py`'s continued growth** — if a third or fourth modality family is added without restructuring, this file becomes a genuine single-point-of-maintainability-failure for the whole engine.
- **Structural boilerplate duplication (§18) compounds linearly with engine count** — at 10 engines it's ~700 lines; at 20 engines (a plausible eventual project size per the roadmap's own Phase 4/5+ scope) it would be ~1,400+ lines of pure copy-paste, each copy a place a future security or reliability fix could be applied to 9 of 10 places and missed in the 10th.
- **The hand-duplicated cross-engine value objects** (`Goal`/`MemoryReference`/`WorldModelSnapshot`, §3.4) risk silent incompatible drift the longer they're maintained by hand without a shared schema or contract test catching divergence.
- **No engine has authentication, rate limiting, or a public API Gateway yet** — expected and fine today (everything is presumed private-network), but this project's own roadmap (Phase 4/5+, desktop companion, eventual multi-user considerations per ADR-025's "Personal Edition is the flagship, not the only edition forever") means this precondition will eventually need to be addressed deliberately, not discovered as a gap under deadline pressure.

---

## 24. Recommended refactorings

Ranked by (value ÷ risk), highest first. The user has explicitly asked not to hesitate here — every item below is scoped precisely enough to execute directly, not left as a vague future intention.

1. **Fix `tools/scaffold-engine.py`'s `_update_root_pyproject`** (§6.4) — rewrite using `tomlkit` instead of literal-string `.replace()`. ~1-2 hours. Zero risk to existing engines (only affects future scaffolding). Removes a silent-failure mode that has already cost manual-fix time on at least one engine (perception-engine, this phase) and very likely several before it.
2. **Backfill `schema_version: int = 1` into the ~33 Phase-1-vintage payload classes** (§4) missing it (`system.py`, `world_model.py`, `memory.py`, `knowledge.py`). ~1-2 hours, purely additive (a field with a default), zero behavior change, zero migration needed (it's a Pydantic model field, not a DB column). Closes a real, growing ADR-024 compliance gap.
3. **Fix `model_registry.updated_at`** (§10) — add `onupdate=func.now()` or set it explicitly in both `update_health()`/`update_benchmark()`. Trivial, one-line-ish fix, restores the column's actual intended behavior.
4. **Fix perception-engine's `identity_observation.identity_id` ORM/migration mismatch** (§10) — add the missing `ForeignKey()` to `repository/models.py`. Trivial, brings the newest engine's own model file back in line with its own migration and its own docstring's claim.
5. **Extract `api/health.py` into a shared `make_health_router()` factory** (§18) — highest-ROI duplication removal in the codebase (216 duplicated lines, 9/10 engines byte-identical). Low risk: behavior is currently identical everywhere, so a shared factory changes nothing observable. `nova-core`'s deliberate deviation (extra `uptime_seconds`/`boot_phase` fields) becomes an explicit, visible override parameter rather than an unexplained one-off.
6. **Extract `repository/db.py` into a shared `create_engine_and_session_factory(dsn)` helper** (§18) — same profile as #5: ~136 duplicated lines, zero behavioral variation across all 9 copies, near-zero risk.
7. **Reconcile the `reasoning.result`/`action.result` stale subscriptions** (§8) — either wire `memory-engine`/`knowledge-engine` to reasoning-engine's real completion subjects (`reasoning.process.completed`/`.failed`/`.human_override.applied`) or explicitly remove the dead subscription. Requires a small design decision (which of reasoning-engine's three real events should trigger what memory/knowledge-engine were originally meant to do with a generic "result"?) before the mechanical fix — recommend deciding this as part of Phase 2D-C planning rather than blocking this review on it, since it's a real gap but not a regression.
8. **Move `ai-model-orchestration-engine/api/generate.py`'s streaming-path business logic into `domain/router.py`** (§3.5) — the non-streaming handler already shows the correct pattern in the same file; this is a "backport an existing pattern," not new design work. Medium effort (the streaming path's cost/usage-recording logic needs to become a proper `_and_record`-style domain function callable incrementally), low risk given the target pattern is proven elsewhere in the same engine.
9. **Split `ai-model-orchestration-engine/domain/router.py`** (§3.2, §21) — the file's own internal structure (9 repeated per-modality triplets) already suggests the natural split: one module per modality-family (e.g. `router_text.py`, `router_speech.py`, `router_biometric.py`) sharing the existing `_plan_perception_routing`/`_route_and_record_perception`-style helpers via a small shared `router_shared.py`. Higher effort (touches the largest file in the codebase; needs careful re-testing against the existing 172-test contract suite) — recommend doing this deliberately, not as a rushed pre-Phase-2D-C task, but before a third modality family is ever added.
10. **Rename `perception-engine/domain/sensor.py`'s `SensorError` to `SensorErrorReport`** (§12) — trivial, removes a genuine naming ambiguity with the codebase's real exception-class convention.

## 25. Recommended simplifications

1. **Fix the four stale "pending approval" documentation status lines** (§6.2) — `docs/design/phase-2b/README.md:10`, `docs/design/phase-2d/01-communication-engine.md:18`, `docs/design/phase-2d/02-personality-engine.md:12`, `docs/roadmap/ENGINEERING_ROADMAP.md:396`. Trivial text edits.
2. **Rewrite `docs/architecture/16-testing-strategy.md §3`** to describe what's actually built today (in-memory Event Bus fixture, manual per-Gate-Review coverage measurement), moving the testcontainers/`FakeModelGateway`/85%-CI-gate description into an explicitly-labeled future item rather than present-tense fact (§6.1, §27). This is the single most important documentation fix in this review.
3. **Fix `docs/architecture/20-engine-responsibility-boundaries.md`'s stale "Perception Engine (Phase 4)" diagram label** (§6.3) — one-line diagram edit.
4. **Add a Gate Review checklist item**: "update every touched design doc's own status line, not just the roadmap's top summary paragraph" (§6.2's own root-cause fix, preventing recurrence rather than only fixing the four instances found this time).
5. **Normalize the two API-prefix outliers** (`memory-engine/api/decisions.py`, `perception-engine/api/sensors.py`, §9) to use the standard `APIRouter(prefix="/v1/<domain>/...")` mechanism every other router uses.
6. **Normalize the outbox partial-index name** (`outbox_undispatched_idx` vs. `outbox_event_dispatch_ready_idx`, §10) and the `session`/`db_session` variable-naming split — purely cosmetic, but cheap to fix in the same pass as the other repository-layer cleanups.

## 26. Architectural improvements

1. **Add a fifth `import-linter` contract enforcing domain-layer purity mechanically** (§3.3, §11) — `<engine>.domain` forbidden from importing `<engine>.{api,repository,clients,sensors,channels,connectors}`, scoped per-engine. This converts a currently-informal-but-real guarantee (zero violations found this review, apart from the two named exceptions) into a tooling-enforced one, at low implementation cost given how close to 100% compliant the codebase already is.
2. **Retrofit `nova-core` with a `domain/ports.py` and `observability.py`** (§3.3, §12) — brings the one engine that predates both conventions in line with all 9 built after it. Low risk, mechanical, and removes the one remaining asymmetry in an otherwise fully-consistent architecture.
3. **Add `mypy` coverage of `tests/` (at least `tests/fakes/`), not just `src/`** (§16) — closes the real, narrower LSP/Protocol-conformance gap correctly identified this review (once the "mypy doesn't run in CI" mischaracterization is corrected to its accurate form). Low effort: extend each engine's `package.json` `lint` script from `mypy src` to `mypy src tests/fakes` (or the whole `tests/` tree, budget permitting).
4. **Add a `--cov-fail-under` gate to CI**, scoped to `domain/` at minimum, matching what the actual practiced discipline already achieves (97-99% domain coverage measured this session) — this converts an already-true outcome into a guaranteed one, and is the more tractable half of closing the `16-testing-strategy.md` gap (§6.1, §27 covers the harder half — real infrastructure fixtures).

---

## 27. Architectural Opportunities

*Improvements that are not required today but could provide measurable, long-term value over the next several phases. Nothing here is included because it is newer or more fashionable — each is justified by a specific, concrete cost this review found, or a specific, concrete future need already named in this project's own roadmap.*

### 27.1 Build the `nova-testkit` real-infrastructure fixtures `16-testing-strategy.md` already claims exist

This is the highest-value opportunity in this review. The project has now deferred "real-Postgres verification" across three consecutive Gate Reviews (2D-A, 2D-B, and this one), each time citing "no Docker-capable environment available" as the blocker — true, but incomplete: even with Docker available, **there is currently nothing to point it at**. Building `nova_testkit.postgres` (and, in a later increment, `nova_testkit.neo4j`/`nova_testkit.redis`/`nova_testkit.nats`) as `testcontainers`-backed pytest fixtures — spin up a real Postgres container per test module, run each engine's own Alembic migrations against it, yield a real session factory, tear down after — would let every engine's `PostgresXRepository` be tested against a real database the next time a Docker-capable environment is available, closing task #93's now three-engine-deep backlog in one pass rather than three separate ad hoc verifications. Concrete scope: one new module in `packages/nova-testkit/src/nova_testkit/`, a new `testcontainers` dependency, and (per §26.4) a coverage/CI wiring decision about whether these fixtures run in the standard `pr-checks.yml` (if a Docker-in-Docker runner is available) or a separate, explicitly-slower "integration" CI job. Sizing: this is a multi-day effort, not a quick fix — sequence it as its own dedicated piece of work, likely the first thing to schedule once a Docker-capable environment is confirmed available, rather than folding it into a feature phase.

### 27.2 A shared `nova-service-kit` package for the ~700 lines of proven-safe-to-extract boilerplate

§18/§24 already identify `api/health.py`, `repository/db.py`, and (with more care) `repository/outbox_dispatcher.py`'s core loop as near-zero-risk extraction candidates — each is functionally identical across every engine that has one, differing only in a docstring or an engine-name string. A single new lightweight shared package (not `nova-eventbus-sdk` or `nova-observability`, which have their own distinct, already-well-scoped responsibilities) would let each of the 9-10 affected engines delete 20-30 lines per file and import instead. The value compounds with engine count: at today's 10 engines this saves ~500 lines total; at a hypothetical 20 engines (a plausible Phase 4/5+ size per the roadmap) it would be closer to 1,000+ lines, and — more importantly than the line count — it means a future cross-cutting change (e.g. adding OpenTelemetry trace-context propagation to every outbox dispatch, or adding a readiness sub-check to every health endpoint) becomes a one-file edit instead of 9-10 independently-drifting ones.

### 27.3 A shared HTTP middleware layer: global exception handling + request-ID propagation

§12/§14/§23 all converge on the same finding from different angles: no engine has a global unhandled-exception handler or HTTP-level correlation-ID propagation. This isn't urgent today (no engine is publicly exposed, and domain-level `correlation_id` threading through the Event Bus is already solid), but it's exactly the kind of gap that's cheap to close now, uniformly, across 10 structurally-identical FastAPI apps, and expensive to retrofit once each engine has grown its own bespoke error-handling edge cases. A shared `nova_observability.middleware.install(app)` (or a new small package) providing a structured-JSON 500 handler and `X-Request-Id` generation/propagation would be a natural complement to the existing `configure_observability()`/`create_metrics()` pattern every engine already imports identically.

### 27.4 Formalize the "weighted composite scorer" pattern — after reconciling its three divergent missing-data semantics

§18 found the same conceptual algorithm (weighted-sum composite scoring, then select/sort) independently implemented three times, each with a different, undocumented-as-a-deliberate-choice answer to "what happens when an input signal is missing." This is *not* ready to unify today — doing so before deciding which missing-data semantic is actually correct would silently change reasoning-engine's, memory-engine's, or ai-model-orchestration-engine's real behavior. The opportunity is the sequencing: (1) a short, dedicated design discussion establishing one canonical missing-data policy for weighted composite scores project-wide, (2) then, and only then, extracting a shared, tested `weighted_composite_score()` utility. Worth scheduling deliberately rather than either ignoring the drift indefinitely or unifying it carelessly.

### 27.5 Consider a per-capability authorization framework now that ADR-032 exists, ahead of the engines that will need it

ADR-032 (this phase's own addition) establishes that identity confidence is an authorization *signal*, and that gating logic belongs to a future privileged-capability-owning engine, never to perception-engine itself. No such engine exists yet (Action Engine/Autonomy Engine are Phase 3/4 per the roadmap). The opportunity: when that engine is designed, it will need a genuinely reusable "per-capability, configurable confidence threshold" mechanism (per ADR-032's own text: "never a single hardcoded system-wide threshold") — worth designing that mechanism once, generically, rather than once per privileged capability as Phase 3/4 engines are added one at a time. This is explicitly *not* something to build now (there's nothing to gate yet), but naming it here means the eventual design doesn't have to rediscover ADR-032's own requirement from scratch.

### 27.6 A structural domain-purity import-linter contract, now, while it's nearly free

Already covered as a concrete recommendation in §26.1 — restated here specifically as a *strategic* opportunity because of its unusually good timing: the codebase is already ~98% compliant with its own domain-purity rule (verified this review, only 2 real exceptions found across 10 engines). Formalizing this now, while violations are rare and small, costs almost nothing; deferring it means every future engine that's scaffolded without this guardrail is one more chance for `domain/` to quietly pick up a `fastapi` or `sqlalchemy` import that nobody notices until a much larger and more expensive untangling is needed.

### Explicitly considered and *not* recommended

- **Migrating to a different ORM, web framework, or event-bus technology** — no evidence anywhere in this review that FastAPI, SQLAlchemy 2.0, or the NATS-backed `nova_eventbus_sdk` abstraction are causing any real friction; this would be change for its own sake, exactly what the user asked not to recommend.
- **Merging any two engines** — every engine's bounded context is clear and non-overlapping (§3.4); there is no evidence of an engine boundary that should be collapsed.
- **Introducing a service mesh, API gateway, or distributed tracing backend before Phase 2D-C** — real, eventual needs (§14, §23) but premature relative to this project's current single-user-default, no-live-deployment maturity (ADR-025); the cheaper, more targeted §27.3 middleware opportunity captures most of the near-term value without the operational overhead a full mesh/gateway would add today.

---

## 28. Engineering metrics

No code has changed since the Phase 2D-B Gate Review (this review is read-only analysis); Production SLOC is therefore identical, confirmed by a fresh measurement rather than assumed:

| Metric | Phase 2D-B Gate Review | This Review |
|---|---|---|
| **Production SLOC** (`src/` + Alembic `versions/` only) | 31,610 | **31,610** — unchanged, confirmed by fresh `scc` measurement |
| Total SLOC (all languages, all purposes) | 77,286 (before staging that report) | **77,939** (+653 — the two Phase 2D-B review documents, committed since) |
| Total files (git-tracked) | 932 | **934** |
| Total directories (git-tracked) | 193 | **193** |
| Repository size (git-tracked working tree) | ~4.36 MB | **~4.41 MB** (4,411,068 bytes) |
| `.git` history size | 12 MB | **12 MB** |
| Total tests | 951 | **951** — unchanged |
| Aggregate coverage (10 production services) | 78.7% | **78.7%** — unchanged |
| Ruff | PASS, 0 issues | **PASS**, 0 issues |
| MyPy | PASS, 413 `src/` files | **PASS**, 413 `src/` files (confirmed still scoped to `src/` only, §16) |
| Import-linter | PASS, 4/4, 395 files / 1,783 deps | **PASS**, 4/4, 395 files / 1,783 deps |
| Dependency graph | 39 edges, 0 cross-engine, 0 cycles | **39 edges, 0 cross-engine, 0 cycles** — re-verified fresh this session |

**Note on `ai-model-orchestration-engine/domain/router.py`'s size**: this review's own §3.2 cited 1,498 lines (raw `wc -l`, confirmed by direct re-measurement while finalizing this section: exactly 1,498) against the Phase 2D-B Gate Review's own 1,384 SLOC (via `scc`, which excludes blank lines and comments). Both are correct — they measure different things, not a real discrepancy. Resolved here rather than left as an open question: no code changed between the two reports, the file is genuinely both "1,498 total lines" and "1,384 lines of actual code," and §3.2/§24 item 9's recommendation to split it stands either way.

**50,000 SLOC milestone status: 31,610 / 50,000 ≈ 63.2%**, unchanged. **30,000 SLOC Project Health Review threshold: this review is that response.**

---

## 29. Final recommendation

**The architecture is healthy.** Ten engines built across five phases hold to a consistent, largely self-reinforcing set of conventions — zero circular dependencies, zero cross-engine coupling, a domain-purity rule violated in only 2 of 10 engines, a repository-transaction discipline followed without exception across 18 files, an outbox pattern implemented identically across 8 engines, and a DDD anti-corruption-layer pattern for cross-engine data that has held from the very first engine to the most recent one. These are genuine, load-bearing strengths, not aspirational claims — every one was verified against the actual code this session, not assumed from prior reports.

The problems found are real but narrow: two concrete bugs (`model_registry.updated_at`, perception-engine's missing FK declaration), one broken-since-early tooling function (`_update_root_pyproject`), one stale dead event subscription (`reasoning.result`), a modest and well-quantified pile of boilerplate duplication, and — the one finding that genuinely changes how a future reader should treat this project's own documentation — a canonical architecture document (`16-testing-strategy.md`) that describes testing infrastructure that was never built. None of these block Phase 2D-C's own architectural soundness; several of them (the mechanical fixes in §24 items 1-6, 10, and the doc fixes in §25) are small enough to do *before* Phase 2D-C begins without meaningfully delaying it, and doing so now — at 31,610 SLOC — is unambiguously cheaper than doing it later, exactly as the user's own framing for this review anticipated.

**Recommendation: proceed to Phase 2D-C**, having first applied the small, low-risk, high-confidence fixes in §24 (items 1-6, 10) and §25 (items 1-3) as a short, dedicated cleanup pass — none of them are feature work, all of them are corrections to things this review found to be already broken or already stale, and fixing them now costs less than carrying them forward. The larger items (§24.7-9, §26, §27) are genuine opportunities, not blockers, and should be sequenced deliberately across upcoming phases rather than done in a rush before 2D-C — §27.1 (real-Postgres test infrastructure) in particular deserves to be scheduled as its own piece of work the moment a Docker-capable environment is confirmed available, since it is the one item in this review with the largest gap between its stated importance across three consecutive Gate Reviews and the amount of actual progress made toward it.

This review stops here and awaits the user's approval before any further implementation, per the user's own explicit instruction.

