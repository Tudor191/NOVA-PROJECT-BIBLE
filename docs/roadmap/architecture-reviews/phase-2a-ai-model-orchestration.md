# Architecture Review Report — Phase 2A: AI Model Orchestration Engine

**Phase:** 2A — AI Model Orchestration Layer
**Completed:** 2026-08-05
**Design document(s):** [docs/design/phase-2a/](../../design/phase-2a/README.md) (00 AI Model
Orchestration Engine), plus the new canonical
[AI Model Orchestration Philosophy](../../architecture/21-ai-model-orchestration-philosophy.md)
**Author:** Claude (Anthropic), AI-assisted implementation under direct human
architectural direction and review throughout — every design deviation, boundary
decision, and deferral recorded in this report was either explicitly instructed by
the user or self-identified and flagged for the reasoning shown below, never
silently decided.

## 1. What was implemented

One independently deployable engine — a full FastAPI service + Arq worker process
pair — plus the `nova-contracts` additions and one shared-package reuse Phase 2A
required.

**AI Model Orchestration Engine** (`services/ai-model-orchestration-engine/`) —
Bible Part 7. The sole legal channel to any LLM/AI provider in NOVA (ADR-020). Owns
the `model_orchestration.*` Postgres schema (`model_registry`,
`model_health_snapshot`, `usage_record`, `budget`, `outbox_event`) and no graph, no
Redis domain state, and no cache beyond an in-process registry snapshot (ADR-022).

- **Domain layer**: `router.py` (the nine-step Orchestration Principle pipeline,
  split into a pure `plan_routing`/impure `route_and_execute` per ADR-021, plus
  `execute_and_record`/`embed_and_record` wrapping both with mandatory,
  always-on structured telemetry), `capability_matrix.py` (Part 7's twelve
  capability dimensions), `privacy_classifier.py` (hard privacy-tier gate, no
  override), `fallback.py`, `cost_tracker.py`, `context_builder.py` (Prompt
  Pipeline — formatting only), `tool_schema.py` (Function Registry — schema
  translation only), `health.py`, `benchmark.py`.
- **Connectors**: `FakeConnector` (deterministic, for tests), `OllamaConnector`
  (the default, zero-budget connector; reuses Phase 1's `nova-embeddings-sdk`
  for embedding rather than duplicating an Ollama HTTP client), `AnthropicConnector`
  (proves the abstraction holds against a real cloud provider), and
  `connectors/factory.py` (registry entry → live, cached connector instance).
- **Repository layer**: `PostgresModelRegistryRepository`,
  `PostgresUsageRepository` (including budget CRUD and the simpler,
  no-graph-shaped transactional outbox), a hand-written initial Alembic
  migration matching the design doc's schema exactly.
- **API**: `POST /v1/models/generate`(`/stream`), `POST /v1/models/embed`,
  `GET/POST /v1/models`, `GET /v1/models/{id}`, `DELETE /v1/models/{id}`,
  `POST /v1/models/{id}/benchmark`, `GET /v1/models/select` (Part 7's "Select
  Model" dry-run API), `GET /v1/usage` (filterable by model, requesting engine,
  and time range). 12 route handlers total, 8 with an explicit `response_model`
  (the remaining 4 — `DELETE`'s 204, the SSE stream, and the two internal
  health/readiness endpoints — are each individually justified, not a gap).
- **Events**: publishes `ai_model.request.completed`/`.failed`,
  `ai_model.model.registered`/`.deregistered`/`.health_changed`,
  `ai_model.budget.exceeded`; serves `ai_model.generate.request` and
  `ai_model.embed.request` as Event Bus RPCs sharing the exact same
  `execute_and_record`/`embed_and_record` pipeline the HTTP routes call — no
  duplicated routing logic between transports. Streaming is deliberately not an
  Event Bus contract (HTTP/SSE only).
- **Workers**: `outbox_worker.py` (the simpler, no-graph-saga outbox dispatch,
  every 10s), `health_monitor_worker.py` (periodic connector probes, publishing
  `ai_model.model.health_changed` only on an actual status transition — a real
  gap caught and fixed during this phase's own review, see §2),
  `benchmark_worker.py` (a small, fixed evaluation set, scored structurally —
  never semantically — feeding `avg_latency_ms`/`avg_quality_score` back into
  `capability_matrix.py`).
- **`nova-contracts` additions**: the full `ai_model_orchestration` event-payload
  family (10 registered subjects), the first payloads written under ADR-024 —
  every class carries `schema_version: int = 1` from its first commit, no
  retrofit needed the way Phase 1's payloads would eventually require one.

**95 tests** (60 unit, 15 integration, 20 ADR-023 connector-compliance), all
passing; `ruff check` and `mypy` clean across the engine's `src/` and `tests/`;
the root `import-linter`'s fourth contract (ADR-020: only this engine may import
`anthropic`/`ollama`/`openai`/`cohere`/`mistralai`) passing with zero violations,
alongside the three Phase 1 contracts, which remain unbroken.

No design changed from what
[docs/design/phase-2a/00-ai-model-orchestration-engine.md](../../design/phase-2a/00-ai-model-orchestration-engine.md)
specified. Several additions went beyond the design doc's literal text, each
schema-supported or protocol-consistent rather than a new architectural decision:
`domain/health.py` and `domain/benchmark.py` (both named in the design doc's
directory tree but not elaborated, built to the responsibilities that tree already
assigned them), `router.py`'s embedding-routing functions
(`plan_embedding_routing`/`route_and_embed`/`embed_and_record`, extending the same
routing/fallback shape §10 already specified for `POST /v1/models/embed`),
`connectors/factory.py` (not named in the design doc, but a direct, mechanical
consequence of `route_and_execute`'s existing `get_connector: Callable[...]`
parameter needing a real implementation somewhere), and `UsageRepository`'s budget
CRUD plus `list_usage`'s `since`/`until` filters (the design doc's §14 already
promised `GET /v1/usage` "filterable by time range," which the originally-specified
repository port did not yet support — closed during implementation, not deferred).

## 2. Why each architectural decision was made

Every non-obvious implementation-time decision is now filed as a structured ADR in
[`docs/architecture/adr/`](../../architecture/adr/README.md) (ADR-020 through
ADR-025), per the standing requirement established at the Phase 1 Gate Review.
Summary list:

- **ADR-020** — The AI Model Orchestration Engine is the only legal channel to any
  LLM/AI provider, enforced by a dedicated import-linter contract, not just
  documentation.
- **ADR-021** — Deterministic, explainable model routing with mandatory structured
  telemetry on every request, success or failure.
- **ADR-022** — The engine is a stateless cognitive gateway; the only permitted
  in-process state is the disposable registry/capability-matrix cache.
- **ADR-023** — Every provider connector passes one identical compliance test
  suite; adding a provider never requires touching anything outside its own
  connector module.
- **ADR-024** — Every public interface (event payload and HTTP API) is versioned
  from the beginning; this engine's payloads are the first written under this
  rule.
- **ADR-025** — Established mid-phase, NOVA-wide: the Personal Edition is the
  permanent flagship; commercial/enterprise capability is strictly additive,
  never at the Personal Edition's expense. Does not change anything already
  built in this engine (it is provider-agnostic infrastructure equally needed
  by both editions), but now governs every future tradeoff in every engine that
  follows, starting with Reasoning Engine.

One decision made and corrected within this phase, not deferred to an ADR because
it was a bug fix rather than a design choice: the domain model was originally
named/reasoned as `min_privacy_tier` (a floor), which combined with a
`PrivacyLevel.PUBLIC` default would have let cloud models serve highly-sensitive
requests by default — caught while writing `capability_matrix.py`'s eligibility
filter, corrected to `max_privacy_tier` (a ceiling) with the comparison operator
flipped to match, before any code shipped depending on the wrong semantics.

One real gap was found and fixed during this report's own review, not before:
`health_monitor_worker.py` called `ModelRegistryRepository.update_health()` on
every probe but never constructed the `ai_model.model.health_changed` outbox event
the engine is declared to publish — the event existed in `published.py`, had a
registered payload schema, and had a metrics counter, but nothing actually enqueued
it. Fixed by threading an optional `outbox_event` parameter through `update_health`
(mirroring `register`/`deregister`'s existing shape) and having the worker
construct one only when a probe's resulting status genuinely differs from the
model's previously-recorded one.

## 3. Tradeoffs considered

- **No read-through cache beyond the in-process registry snapshot.** Every other
  read (usage history, budget lookups) hits Postgres directly. The registry
  snapshot itself *is* a deliberate exception to Phase 1's "no cache" precedent —
  justified explicitly in the design doc (§9) because Part 7's own performance
  target ("model selection should complete within milliseconds") makes a
  Postgres round-trip on the routing hot path the wrong choice from the start,
  not a premature optimization.
- **Structural, non-ML heuristics throughout**, maintained deliberately as the
  same honesty precedent Knowledge Engine's `summarization.py` and World Model's
  `prediction.py` set in Phase 1: complexity estimation (`router.py`), health
  status thresholding (`health.py`), and benchmark quality scoring
  (`benchmark.py`, average `structural_confidence` and success rate, never
  semantic correctness) are all fixed formulas over structural signals, never
  another model call judging the request or the response. Classifying a
  request's complexity or a response's quality by calling a model would be
  circular for the former and out of scope for the latter (semantic quality is
  explicitly Reasoning Engine's concern, Phase 2B).
- **Budget enforcement built but not wired into routing.** `cost_tracker.
  budget_status` and the full budget CRUD exist and are unit-tested, and
  `ai_model.budget.exceeded` is a declared, contract-tested subject — but
  nothing in `router.py` or the API layer yet calls `spend_this_period` +
  `budget_status` together to restrict routing when a budget is exceeded, or to
  publish the event. Deliberately deferred rather than guessed at: which budget
  scope (global/provider/model) applies to a given request is a real design
  decision Part 7 doesn't fully specify, and inventing a resolution order would
  have been exactly the speculative behavior this project's standing
  instructions rule out.
- **Streaming does not walk the fallback chain.** `POST /v1/models/generate/
  stream` plans a route once and calls that connector's `stream()` directly; a
  mid-stream failure is recorded as a failed request, not silently retried on a
  second model. No precedent in Part 7's fallback description covers a
  partially-streamed response, and switching models mid-response isn't a
  meaningful recovery once tokens have already reached the caller.
- **Anthropic's connector is the only real cloud provider built this phase.**
  Sufficient to prove ADR-023's compliance-suite abstraction holds against a
  genuinely different wire format and tool-calling convention (the concrete
  goal §1 of the design doc states for it), without needing every possible
  provider built before the abstraction can be trusted.

## 4. Known limitations

The engine's own README carries the full list under "Known limitations (Phase
2A)." Restated here for a reader who doesn't cross-reference:

- **Budget enforcement not wired into routing** (§3) — deliberately deferred,
  with a named trigger condition (a real scope-resolution design decision) for
  revisiting.
- **Streaming has no fallback** (§3) — deliberately scoped, with the reasoning
  for why stated plainly rather than left implicit.
- **No vision/speech connectors.** `Modality` covers `text_generation`/
  `streaming`/`embedding`/`tool_calling` only; vision/speech are a named future
  extension point (design doc §20), not a claimed capability.
- **No Google/Gemini connector yet.** ADR-020's import-linter contract
  deliberately omits `google.generativeai`/`google.genai` — import-linter
  rejects subpackages of external packages as invalid `forbidden_modules`
  entries — tracked for whenever a Google connector is actually built, not
  silently exempted from the rule.
- **No automated model integrity/signature verification** (design doc §18) — an
  honestly-scoped gap (no such mechanism is specified for Ollama-distributed
  models), not a claimed guarantee.
- **Memory Engine and Knowledge Engine still call `nova-embeddings-sdk`'s
  `OllamaEmbeddingProvider` directly**, not through this engine's `POST
  /v1/models/embed`. ADR-020 names this explicitly as tracked migration debt,
  predating this engine's existence and out of Phase 2A's own scope.
- **No read-through cache beyond the registry snapshot** (§3), mirroring every
  Phase 1 engine's same accepted gap.
- **`GET /v1/models` has no pagination or limit**, unlike `GET /v1/usage` (which
  has a bounded `limit`, though still no offset/cursor). This is the same
  unbounded-list gap Phase 1's Gate Review flagged across all three of its
  engines, now also present here — not a regression, but not yet closed either.
  See §6.
- **Untestable in this environment, not untested in principle:** the
  Postgres-specific repository code (`PostgresModelRegistryRepository`,
  `PostgresUsageRepository`) and the real Ollama/Anthropic connectors' live-network
  paths are exercised by the fake/mock-transport substitution pattern in unit,
  integration, and contract tests, but never against real infrastructure — the
  same accepted gap already established at Phase 0 and carried through Phase 1,
  since this development environment has no Docker daemon.

## 5. Technical debt introduced, if any

None accepted as debt in the traditional sense. The closest candidates were
evaluated and are recorded here as deliberate scope decisions, not shortcuts that
will need unwinding:

- **`connectors/factory.py`** was not named in the design doc's directory tree,
  but is a direct, mechanical consequence of `route_and_execute`'s already-specified
  `get_connector` parameter needing a concrete implementation — not a workaround,
  not a new architectural surface.
- **`embed_and_record`'s `estimated_complexity: float = 0.0`** for embedding
  requests is not a real complexity estimate (embedding has no task-type/tool-count
  shape to estimate from) — explicitly documented in the field's own docstring as
  "not applicable," rather than a fabricated number dressed up as real. The same
  honesty standard as `router.py`'s complexity heuristic itself, applied to the
  one request shape that heuristic doesn't fit.
- **`approximate_token_count`'s characters-per-token heuristic** (used only where
  no caller-supplied token estimate exists — `embed_and_record` and the
  streaming path's output-token count) is an explicitly-labeled approximation, not
  a claimed precise count. This engine owns no tokenizer (§0's formatting-only
  boundary means it never measures content, only fits already-declared sizes),
  so an approximation with its assumptions stated is the honest choice, not debt.

## 6. Future improvements

- **Wire budget enforcement into routing** once a scope-resolution design decision
  is made (§3, §4) — restrict candidates to zero-cost/local models when a budget
  is exceeded, and publish `ai_model.budget.exceeded` for real.
- **Decide and implement a pagination convention** for `GET /v1/models` (§4) —
  the same open item Phase 1's Gate Review already recommended system-wide;
  this engine should adopt whatever convention that recommendation produces
  rather than inventing its own.
- **Build a Google/Gemini connector** once ADR-020's import-linter contract is
  extended with the real top-level package name for Google's SDK (§4).
- **Migrate Memory Engine and Knowledge Engine's direct `OllamaEmbeddingProvider`
  usage to call this engine's `POST /v1/models/embed`** instead (ADR-020's named
  migration debt) — closes the one remaining place in NOVA where a non-orchestration
  engine still touches a model-adjacent SDK, even indirectly.
- **Run the health-check and benchmark cadences against real traffic data** once
  Reasoning Engine (Phase 2B) becomes a real caller, to validate
  `Settings.health_check_interval_seconds`/`benchmark_interval_hours`'s fixed
  intervals against an actual load pattern rather than a design-time guess.
- **Extend vision/speech connector support** once a concrete Bible-driven need
  exists (design doc §20) — not before, per the project's standing
  evidence-driven-optimization instruction.

## 7. Risks

- **Operational:** `main.py`/`workers/` have not been booted against real
  Postgres/Ollama/Anthropic in this environment (no Docker daemon available
  here, the same accepted limitation as every Phase 1 engine). The fake/mock
  substitution test suite gives strong confidence in domain logic, connector
  wire-format correctness (ADR-023), and wiring correctness, but
  first-boot-against-real-infra issues remain unverified until a Docker Compose
  run happens.
- **Architectural:** the Prompt Pipeline/Context Builder boundary (design doc
  §0) depends on every future caller respecting "supply already-assembled
  context, never expect this engine to fetch it." Nothing currently enforces
  this at the code level beyond the Protocol shape of `GenerateRequest` itself
  (which structurally has no way to ask this engine to go fetch memory) — low
  risk today (Reasoning Engine, the first real caller, doesn't exist yet),
  worth an explicit code-review checklist item when Phase 2B's first caller
  lands, the same recommendation Phase 1's Gate Review made for the World
  Model/Knowledge Engine boundary.
- **Scale:** Part 7's stated performance target ("model selection should
  complete within milliseconds") has not been load-tested; it is a design-time
  target, not a measured result, the same unmeasured-until-Docker status every
  Phase 1 performance target carries.
- **Provider-specific:** only one real cloud provider (Anthropic) has been
  built and compliance-tested. The abstraction's actual robustness against a
  *third*, differently-shaped provider (not just "two is enough to prove a
  Protocol") remains unproven until one is built — low likelihood of a real
  problem (the Protocol was designed against Part 7's abstraction requirement,
  not fitted to Anthropic's shape after the fact), but genuinely unverified
  beyond two data points.

## 8. Compatibility with the NOVA Project Bible

- **AI Model Orchestration Engine (Bible Part 7):** implemented at full
  breadth for Phase 2A's stated scope — Model Registry, Provider Abstraction,
  Prompt Pipeline, Context Builder, Tool Calling, Function Registry, Model
  Router, Local vs. Cloud execution, Streaming, Token Management, Cost
  Tracking, Fallback Strategies, Observability — the exact thirteen focus
  areas the user specified when opening Phase 2A. Vision/speech modalities and
  a Google connector are named, honest, out-of-scope extension points (§20),
  not silent gaps.
- **ADR-025's Personal Edition principle**, established mid-phase, required no
  retrofit to anything already built: this engine is provider-agnostic
  infrastructure equally necessary for a single-user Personal Edition and any
  future derived commercial edition, and carries no multi-tenant assumption
  either way (single-user by default, per ADR-025's own consequence #1) — the
  first phase evaluated against ADR-025's priority order, and it required no
  changes to pass that evaluation.
- **ADR-026's Reasoning Engine boundary**, also established at this phase's
  close, is forward-looking and does not constrain anything already built here
  — it exists so Phase 2B's design doc is written correctly the first time,
  the same sequencing ADR-017 followed for World Model Engine in Phase 1.
- All Known Limitations (§4) are, per the user's standing instruction carried
  forward from Phase 1, deliberately preferred over any speculative
  implementation of behavior the design doc did not specify.

## Sign-off

- [x] All items in the engine's design-doc review checklist
      ([docs/design/phase-2a/README.md](../../design/phase-2a/README.md)) are
      satisfied — the design was approved before implementation began and no
      deviation occurred beyond the schema-supported/protocol-consistent
      additions noted in §1.
- [x] The phase's Definition of Done
      ([SAD 15 §4](../../architecture/15-development-workflow.md#4-definition-of-done-per-pr))
      was met: implementation, tests, observability, and documentation
      delivered together, not as follow-up work.
- [x] The per-subsystem deliverable checklist
      ([SAD 15 §9](../../architecture/15-development-workflow.md#9-per-subsystem-deliverable-checklist))
      was met for the engine built this phase.
