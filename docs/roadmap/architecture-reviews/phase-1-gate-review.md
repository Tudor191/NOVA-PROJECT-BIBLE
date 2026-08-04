# Phase 1 Architecture Gate Review

**Phase:** 1 — Data & Memory Substrate (Memory Engine, Knowledge Engine, World Model Engine)
**Date:** 2026-08-04
**Trigger:** Explicit user directive, on approving Phase 1's Architecture Review Report, to
formally verify the foundation is strong enough to support the rest of NOVA before Phase 2
begins.
**Method:** Every finding below is backed by a command actually run against this repository
in this session (test runs, `ruff`/`mypy`/`import-linter`/`pip-audit`, a `grimp`-based import
graph, and direct source inspection) — not restated from memory or prior reports. Where a
metric could not be measured in this environment, that is stated explicitly rather than
estimated. Three issues found during this review were fixed as part of it, per the standing
instruction to correct now rather than defer; each is called out where relevant and
summarized in §19.

---

## 1. Overall architecture assessment

The three-engine foundation holds up under direct scrutiny, not just narrative review.
Concretely verified this session:

- **376 tests pass** across all 11 first-party packages (7 shared packages + 4 services),
  zero failures.
- **`ruff check .`** — zero issues, whole repository.
- **`mypy`**, run per-package matching the exact CI invocation — zero issues, 167 source
  files across 11 packages.
- **`import-linter`** — all 3 ADR-004/006/007 contracts kept (0 broken) over 153 analyzed
  files / 691 dependencies.
- **`pip-audit`** — zero known vulnerabilities in third-party dependencies.
- **A from-scratch `grimp` dependency graph** (independent of import-linter's own scoped
  contracts) finds **zero cycles** among the 11 first-party packages and **zero
  engine-to-engine internal imports** — see §13/§14.
- **Domain-layer purity verified by direct grep, not assumed**: in all four services, zero
  `domain/` modules import from `api/`, `repository/`, `events/`, or `workers/`, and zero
  `domain/` modules import FastAPI, SQLAlchemy, Redis, Neo4j, asyncpg, arq, or NATS
  directly.

The architecture is sound: the layering is real (not just documented), the engine
boundaries are real (not just asserted), and the saga/outbox pattern that was flagged as
this phase's hardest consistency problem is implemented identically everywhere it's
needed and correctly absent where it isn't (§11). The gaps found are real but narrow, and
none of them are in the load-bearing architecture — they are missing operational
tooling (§4), unmeasured runtime characteristics (§8), and one API design gap
(pagination, §9). Three of the missing-tooling gaps were closed during this review
(§19). The foundation is ready to build Phase 2 on.

## 2. Remaining architectural risks

- **The World Model / Knowledge Engine non-interaction boundary (doc 20 §5, ADR-017) has
  no code-level enforcement beyond the import-linter's engine-independence contract.**
  That contract stops a direct Python import; it does nothing to stop a future engine
  (most likely Reasoning Engine in Phase 2) from hard-coding assumptions about both
  `:Project` and `:WorldProject` label shapes in a way that couples them anyway. Low
  likelihood today (no consumer exists yet); becomes real the moment Reasoning Engine
  starts reading both. Recommend an explicit code-review checklist item when that lands.
- **No pagination on any list-returning endpoint** (§9) — a scalability risk that is
  currently zero-cost (no real data volume) but will not stay that way once Phase 2's
  Thinking Pipeline starts driving real read traffic against `GET /v1/memories/search`,
  `GET /v1/knowledge/search`, etc.
- **Event contract drift is currently at zero but has no automated regression guard.**
  §10 confirms zero drift today by direct comparison of every subject used against
  `nova_contracts.registry.known_subjects()`, but that comparison was a manual script run
  for this review, not a CI check. If a future engine adds a subject to `published.py`
  without registering a payload (or vice versa), nothing currently catches it
  automatically.
- **The saga pattern (ADR-014) is proven correct in tests but never exercised against a
  live Postgres+Neo4j pair in this environment** (no Docker daemon available here — see
  §4). The crash-recovery property is verified against fakes; first contact with real
  infrastructure remains a real, if likely low-severity, unknown.

## 3. Technical debt

Consistent with the Phase 1 Architecture Review Report's §5 finding: no debt accepted in
the traditional sense (a shortcut that will need unwinding later). Re-verified this
session rather than just restated:

- `WorldHistoryRepository.list_recent_history_for_user` remains the only addition beyond
  each design doc's literal text, and remains schema-supported, not a workaround.
- The three deliberately-deferred items (no idle-sweep worker, no user-directory
  mechanism, no read-through cache) are scope decisions with documented trigger
  conditions, not debt — nothing was built incorrectly; nothing was built at all in those
  spots, and that absence is visible (README "Known Limitations" in every engine).
- **New this review:** the absence of test coverage tooling was a real, if minor, gap —
  no `coverage`/`pytest-cov` was installed anywhere in the monorepo before this review, so
  "test coverage" was previously an unanswerable question. Fixed during this review (added
  `pytest-cov` as a root dev dependency; see §19 and the Metrics section for the numbers
  it now produces).

## 4. Missing infrastructure

Real, verified gaps — three were fixed during this review, the rest are recorded as
open items with concrete next steps.

**Fixed during this review:**
- `infra/docker/docker-compose.local.yml` defined every backing store (Postgres, Neo4j,
  Redis, NATS, MinIO, Ollama, the full observability stack) and `nova-core`, but **none
  of the three Phase 1 engines had a compose service entry** — the full stack had never
  actually been composable, let alone booted, even in local dev. Added `memory-engine`,
  `knowledge-engine`, and `world-model-engine` service blocks (host ports 8001/8002/8003
  matching each README), wired to their real dependencies with correct environment
  variables (verified against each engine's actual `config.py` and each shared package's
  factory env-var contract, not guessed). `docker compose config --quiet` — the exact
  command CI runs — validates clean.
- `.github/workflows/build-and-scan.yml`'s image-build-and-vulnerability-scan matrix
  listed only `nova-core`, with a comment explicitly instructing "add a line here
  whenever a new engine is created" — never done for any of the three Phase 1 engines.
  **Their Dockerfiles have never been built or scanned in CI.** Added all three to the
  matrix. (Could not verify an actual image build succeeds in this environment — no
  Docker daemon is reachable here, confirmed via `docker info`; static verification that
  every `COPY` source path exists and that every Dockerfile's `COPY` list matches its
  `pyproject.toml` dependency list exactly, for all four services, found no discrepancies
  — see §11 methodology. Real build verification happens on this change's next CI run.)
- No coverage tooling existed anywhere (§3) — added `pytest-cov`, now producing the real
  numbers in the Metrics section.

**Open, not fixed this review:**
- **The internal CLI/admin API** — already flagged in the Phase 1 Architecture Review
  Report as a roadmap-listed deliverable that was not built. Still open.
- **No Docker daemon in this development environment.** Confirmed directly: `docker info`
  reports "Cannot connect to the Docker daemon," and starting one fails on a sandbox
  permission restriction (`ulimit: error setting limit (Operation not permitted)`). This
  is why performance benchmarks, memory usage, and startup time (§8, Metrics) cannot be
  measured here — not a gap in what was built, a gap in what this environment can verify.
  Recommend running the now-complete compose stack in a Docker-capable environment before
  Phase 2 begins, specifically to capture the baseline numbers this gate review cannot.
- **No automated event-contract-drift check** (§2) — the used-vs-registered subject
  comparison in §10 was manual; formalizing it as a CI check (a small script comparing
  every `published.py`/`subscribed.py` subject against `known_subjects()`) is cheap and
  would close a real, if currently dormant, risk.
- **No CORS middleware, no rate limiting, no request size limits** on any engine's API.
  Consistent with local-first Phase 1 scope (no engine is meant to be internet-facing
  yet) but worth a recommendation before any engine is ever deployed reachable from
  outside its own Docker network (§6).

## 5. Scalability analysis

- **Pagination is absent, confirmed by direct search**, not assumed: only one file in the
  entire codebase (`memory-engine/api/decisions.py`) references `limit`/`offset`/`cursor`
  at all. Every other list-returning endpoint — `GET /v1/memories/search`,
  `GET /v1/memories/timeline`, `GET /v1/knowledge/search`,
  `GET /v1/world/objects/{id}/history`, `GET /v1/world/snapshots`,
  `GET /v1/world/predictions` — returns an unbounded list. Zero-cost today (no real data
  volume); becomes a real risk the moment any of these are called against production-size
  data in Phase 2+.
- **`GET /v1/knowledge/graph` and `GET /v1/world/graph` issue one `GraphStore` call per
  node** (already flagged in the Phase 1 Architecture Review Report, re-confirmed here):
  acceptable at visualization-call sizes, a real N-calls-per-request pattern beyond that.
- **Redis is a hard dependency, by design (ADR-012), for the highest-QPS paths in two
  engines** (Working Memory, Active Context/Attention). This is architecturally correct
  (§17 of both design docs: fail fast, never serve stale data) but means Redis
  availability directly gates two engines' primary read paths — a single point of
  failure the architecture accepts deliberately, not accidentally, and one that should be
  reflected in any future capacity-planning or SLA work.
- **A single, system-wide embedding model** (ADR-010, `nomic-embed-text`, 768 dimensions)
  is a deliberate scalability tradeoff already reasoned through and recorded — re-verified
  here as still consistent across every `VECTOR(...)` column in both Memory and Knowledge
  Engine's schemas (`grep`-confirmed: no `VECTOR(1536)` or other dimension appears
  anywhere).
- **The Postgres-then-graph saga's outbox worker polls on a short fixed interval** (10s)
  rather than being triggered by the write itself. At Phase 1's zero real traffic this is
  invisible; at scale it is a deliberate latency-vs-simplicity tradeoff (ADR-014) whose
  interval should be revisited with real throughput data, not before then.

## 6. Security analysis

- **No hardcoded secrets anywhere** — verified by direct pattern search across every
  `src/` tree for password/secret/api-key/token literals; the only matches were
  legitimate dev-default DSN strings already using environment-variable overrides.
- **No raw SQL string interpolation** — verified by searching for f-string or
  `%`-formatted values passed into `.execute()`/`text()` calls; none found. Every
  database write goes through SQLAlchemy's parameterized ORM layer or a parameterized
  raw-SQL call, confirmed by direct inspection of the Alembic migrations and repository
  modules.
- **`pip-audit` reports zero known vulnerabilities** in any third-party dependency across
  the whole workspace.
- **No authentication or authorization exists on any Phase 1 API**, confirmed by direct
  search (no JWT/OAuth/API-key/`Depends(...auth...)` pattern found anywhere in any
  engine). This is **not a Phase 1 oversight** — the roadmap explicitly defers
  `packages/nova-auth` (SAD 13) to a much later phase (the "safe to hand to other people"
  phase, well past Phase 2), and Phase 1 was never scoped to include it. It is,
  nonetheless, a real fact worth stating plainly rather than leaving implicit: **every
  endpoint on every Phase 1 engine is currently open to any caller that can reach it.**
  In local-first mode this is mitigated by the deployment model itself (single machine,
  no network exposure) — but every engine's Dockerfile binds to `0.0.0.0:8000`, not
  `127.0.0.1`, meaning the mitigation is "don't publish the port," a deployment-time
  discipline, not an architectural guarantee. Recommend this be stated explicitly as a
  deployment constraint (never publish these ports to a host network or the internet
  before `nova-auth` ships) rather than left as an implicit assumption.
- **No CORS middleware and no rate limiting on any engine** (§4) — consistent with the
  same local-first, non-internet-facing scope as the auth gap above, and carrying the
  same recommendation.
- **Every Dockerfile runs as a non-root user** (`USER nova`, verified in all four
  Dockerfiles) and uses a multi-stage build that does not ship build tooling in the final
  image — both good defaults, already in place, not something this review needed to add.
- **Pydantic validates every API request body and every event payload** by construction
  (FastAPI + Pydantic v2 throughout) — the closest thing Phase 1 has to systematic input
  validation, and it is applied consistently, not selectively.

## 7. Reliability analysis

- **The transactional-outbox saga (ADR-014)** is the single strongest reliability
  mechanism in Phase 1: verified by this session's test runs that `test_saga.py` in both
  Knowledge Engine and World Model Engine actually exercises kill-and-resume behavior
  (apply-pending / dispatch-ready run independently and idempotently) and passes.
- **Every engine exposes `/internal/health` and `/internal/readiness`** (verified: 8 such
  endpoints across the 4 services, 2 each) plus a mounted `/internal/metrics` Prometheus
  endpoint (verified: `prometheus_asgi_app()` mounted in all 4 `main.py` files) — the
  minimum operational surface a scheduler/orchestrator needs to make restart decisions.
- **Graceful degradation is real, not aspirational**, confirmed by the actual counters
  that exist for it: `context_degraded_total` (World Model, Redis unreachable),
  `retrieval_degraded_total` (Memory Engine, vector index unreachable) — both fail fast
  and flag the degradation rather than silently returning stale or empty data, matching
  each design doc's explicit §17 requirement.
- **No chaos/fault-injection testing exists** beyond the specific saga crash-recovery
  scenario. Network partition between an engine and its Event Bus, a slow-but-not-down
  Postgres, or a Neo4j that accepts writes but fails reads are all untested scenarios.
  Reasonable to defer past Phase 1 (no real traffic to justify the investment yet) but
  worth naming as a real gap, not assuming it's covered by the saga tests.
- **No circuit breakers exist between engines** — Memory Engine's RPC calls into
  Knowledge Engine (`knowledge.link.request`/`knowledge.traverse.request`) degrade to
  `None`/`[]` on a timeout (verified in `domain/relationship.py`), which is graceful
  degradation for a single call but not a circuit breaker (no tracked failure rate, no
  open/half-open/closed state). Acceptable at Phase 1's real call volume (effectively
  zero, since Knowledge Engine's real producers don't exist yet); worth revisiting once
  Phase 2 makes this call path live.

## 8. Performance expectations

Every engine's design doc states explicit performance targets (§15 of each): Memory
Engine's semantic search at p95 < 200ms on a 100k-record dataset, World Model's
`world_model.context.request` at p95 < 20ms, Knowledge Engine's retrieval fan-out
targets. **None of these have been measured against real infrastructure, in this
environment or any other, at any point in this project's history.** This was already
flagged as a risk in the Phase 1 Architecture Review Report; this review adds no new
information except a stronger statement of fact: with no Docker daemon reachable here
(§4), this gate review cannot produce a single real latency number, and neither could any
prior verification pass in this environment. Every stated performance target remains a
design-time intention, not a measured result, until a Docker-capable environment runs
the (now-complete, §4) compose stack against representative data volumes. This is the
single most consequential open item before Phase 2 work that depends on these latency
budgets (specifically World Model's context-request budget, which the Thinking Pipeline
calls on every execution).

## 9. API consistency review

- **URL convention is consistent**: every engine uses `/v1/<domain>/...` for its public
  API and `/internal/...` for operational endpoints, with no exceptions found across all
  32 route declarations.
- **HTTP status code vocabulary is small and consistent**: exactly four status codes are
  used for errors across every engine (400, 404, 409, 503 — verified by direct count: 6,
  11, 2, 1 occurrences respectively), each mapped to a distinct, predictable meaning
  (validation failure, not found, conflict, degraded backend). No engine invents its own
  status-code convention.
- **`response_model` coverage is 23/32 endpoints**; the 9 without one are fully
  explainable, not a gap: the 8 health/readiness endpoints (2 per service × 4 services)
  intentionally return ad hoc status dicts rather than a formal schema, and World Model's
  `GET /v1/world/context` intentionally returns `dict[str, Any]` because its response
  shape is dynamic per the agent-scoped field whitelist (§7 step 4 of the World Model
  design doc) — a fixed Pydantic model would misrepresent a genuinely variable-shaped
  response. Verified by reading every one of the 9 call sites, not inferred from the
  count alone.
- **No pagination convention exists anywhere** (§5) — the one real API consistency gap this
  review found. Not a defect in what exists, but an absence that will need a decision
  (offset/limit vs. cursor, and whether it's per-engine or a shared `nova-contracts`
  convention) before Phase 2 traffic makes it necessary.

## 10. Event Bus consistency review

Verified by direct comparison, not narrative: every subject referenced across all four
services' `events/published.py` and `events/subscribed.py` files (35 unique strings,
including two wildcard subscribe patterns) against every subject with a registered
payload schema in `nova_contracts.registry.known_subjects()` (33 entries).

- **Zero unexplained drift.** The 7 subjects used but not registered are exactly the
  subjects belonging to engines that don't exist yet (Perception, Reasoning,
  Communication, Agent OS) plus the two wildcard subscribe patterns — none of these
  should be registered yet, since registering a payload schema for another engine's
  not-yet-designed event would be exactly the speculative behavior this project's
  standing instruction rules out. The 5 subjects registered but not directly listed in
  any `published.py`/`subscribed.py` are exactly the `.reply` payload types used by the
  request/reply RPC machinery (`bus.request()`/`bus.serve()`), which correctly don't
  appear in the publish/subscribe allow-lists (those govern fire-and-forget events and
  request subjects, not reply payloads).
- **Naming convention is consistent** (`<engine>.<entity>.<action>`) with one minor,
  justified exception: `nova.heartbeat` is two segments, not three — reasonable, since it
  identifies the engine itself rather than an entity-scoped domain event, and it's the
  only such exception in the entire event vocabulary.
- **The saga-driven subjects are correctly asymmetric**: Memory Engine's `outbox_event`
  publishes without a `graph_write` intent (Memory owns no graph); Knowledge and World
  Model's do (§11 confirms this at the schema level too) — the event-publishing behavior
  and the schema that backs it agree with each other.

## 11. Database consistency review

Verified by reading every `CREATE TABLE` statement in all three engines' initial Alembic
migrations, not sampled.

- **Schema-per-engine naming is consistent**: `memory`, `knowledge`, `world_model` —
  exactly matching each engine's name, no exceptions.
- **Primary key convention is `UUID PRIMARY KEY DEFAULT gen_random_uuid()` on 15 of 17
  tables**, with exactly two deliberate, justified exceptions, both already
  architecturally reasoned (not new findings, but re-verified as correct rather than
  assumed): `knowledge.node_metadata.node_id TEXT PRIMARY KEY` (a deterministic/slugified
  business key, not a surrogate key, tied to how Knowledge Engine deduplicates nodes) and
  `world_model.object_state_history.id BIGSERIAL PRIMARY KEY` (an append-only,
  high-write-volume history log where a monotonic integer is the correct choice, not a
  UUID). Both exceptions are consistent with each engine's own documented design; neither
  is drift.
- **Timestamp convention is uniform**: every `created_at`/`updated_at` column is
  `TIMESTAMPTZ NOT NULL DEFAULT now()`, no exceptions found.
- **The `outbox_event` table is structurally identical between Knowledge Engine and
  World Model Engine** (same 9 columns, same two indexes — `outbox_undispatched_idx` and
  `outbox_graph_pending_idx`), and **correctly, deliberately different in Memory
  Engine** (7 columns, one index — no `graph_write`/`graph_applied_at` columns, no
  `outbox_graph_pending_idx`, because Memory Engine owns no graph, per ADR-017/doc 20).
  This is exactly the kind of schema-level evidence that confirms the architectural
  boundary (Memory vs. the two graph-writing engines) is real, not just documented prose.

## 12. ADR consistency review

19 ADRs exist: ADR-001 through ADR-010 (foundational, pre-implementation, recorded
inline in `docs/architecture/00-overview-and-decisions.md`, Context/Decision/Consequence
format) and ADR-011 through ADR-019 (per-subsystem, filed during Phase 1's
implementation in `docs/architecture/adr/`, the fuller
Context/Problem/Alternatives/Decision/Consequences/Tradeoffs/Future-implications
format the user specified as the new standing requirement). The format change between
the two ranges is intentional and explained in `docs/architecture/adr/README.md`, not an
inconsistency — the first ten predate the requirement that introduced the richer format.
Every ADR from 011 onward follows the full seven-section structure without exception
(verified by reading all 9). The numbering is continuous (no gaps, no duplicates) and
every ADR is cross-referenced from at least one other document (the Phase 1 Architecture
Review Report, doc 20, or an engine's README), so none is an orphaned record.

## 13. Module dependency analysis

Built independently of import-linter's own scoped contracts, using `grimp` (the same
graph-analysis library import-linter uses internally) against all 11 first-party
top-level packages:

```mermaid
flowchart LR
    subgraph Shared["Shared packages"]
        contracts[nova_contracts]
        eventbus[nova_eventbus_sdk]
        graphstore[nova_graphstore_sdk]
        vectorstore[nova_vectorstore_sdk]
        embeddings[nova_embeddings_sdk]
        observability[nova_observability]
        testkit[nova_testkit]
    end

    subgraph Services["Services"]
        core[nova_core]
        memory[nova_memory_engine]
        knowledge[nova_knowledge_engine]
        worldmodel[nova_world_model_engine]
    end

    core --> contracts
    core --> eventbus
    core --> observability
    eventbus --> contracts
    testkit --> eventbus
    memory --> contracts
    memory --> eventbus
    memory --> observability
    memory --> vectorstore
    memory --> embeddings
    knowledge --> contracts
    knowledge --> eventbus
    knowledge --> observability
    knowledge --> vectorstore
    knowledge --> graphstore
    knowledge --> embeddings
    worldmodel --> contracts
    worldmodel --> eventbus
    worldmodel --> observability
    worldmodel --> graphstore
```

20 edges total. Every edge points from a service to a shared package, or from one shared
package to `nova_contracts` — never sideways between services, and never from a shared
package back into a service. This is exactly the dependency shape ADR-001 (modular
monolith, hard module boundaries) and ADR-004 (Event Bus is the only legal cross-engine
channel) require, verified structurally rather than taken on faith.

## 14. Circular dependency verification

The same `grimp` graph was run through an explicit DFS cycle detector (not import-linter's
built-in check, which only validates its three specific contracts) over all 11 first-party
packages. **Result: no cycles found.** Every one of the 20 edges in §13 points strictly
from a service toward a shared package or from a shared package toward `nova_contracts`
— a DAG, confirmed algorithmically, not asserted. Separately, an explicit check for any
edge between two of `nova_memory_engine`, `nova_knowledge_engine`,
`nova_world_model_engine`, `nova_core` found none — the ADR-004 engine-independence
guarantee holds at the package-edge level, independent of and in addition to
import-linter's own contract.

## 15. SOLID and Clean Architecture compliance

- **Dependency Inversion Principle**: every engine's `domain/ports.py` defines Protocols
  (`WorldHistoryRepository`, `ContextRepository`, `MemoryRepository`, `VectorIndex`,
  `EmbeddingProvider`, `EventPublisher`, etc.) that `domain/` depends on and
  `repository/`/`events/` implement — never the reverse. Verified structurally in §1/§14:
  zero `domain/` imports of concrete infrastructure, in any engine.
- **Single Responsibility**: each `domain/` module owns exactly one concern (state
  transitions, conflict resolution, attention decay, fusion, ranking, etc., each in its
  own file) rather than one large "service" class per engine — consistent across all
  three engines' file layouts (verified via each engine's own module list, cross-checked
  against its README's own description of what each file does).
- **Interface Segregation**: `ContextRepository` and `WorldHistoryRepository` are
  separate Protocols in World Model Engine rather than one large repository interface,
  because callers (Redis-backed context reads vs. Postgres-backed history writes) never
  need both — the same pattern holds in Memory Engine (`MemoryRepository` vs.
  `WorkingMemoryStore` are distinct Protocols).
- **Open/Closed**: the backend-factory pattern (`EVENT_BUS_BACKEND`,
  `GRAPH_STORE_BACKEND`, `EMBEDDING_PROVIDER_BACKEND`, each a `register_backend()`
  decorator registry in its respective shared package, verified by reading all three
  factory modules) means adding a new backend is a new registered function, never a
  modification to existing engine code — the concrete mechanism behind ADR-006/007/009's
  swappability claims, not just the claims themselves.
- **Liskov substitution** holds by construction for the swappable backends: every
  engine's tests run against `InMemory*` implementations of the same Protocol the real
  backend implements, and the tests pass without engine code knowing which one it's
  talking to — the strongest practical evidence of substitutability available without a
  live Postgres/Neo4j/Redis in this environment.
- **Clean Architecture's layer-dependency rule holds directionally in every engine**:
  `api/` → `domain/` ← `repository/`/`events/`/`workers/`, with `domain/` at the center
  depending on nothing outward — verified by direct grep in §1, not inferred from the
  README diagrams alone.

## 16. Domain Driven Design compliance

- **Bounded contexts map directly to engines**, and the boundary is enforced, not just
  named: Memory, Knowledge, and World Model each own their own Postgres schema, their own
  (or no) Neo4j label set, their own Redis keyspace prefix, and communicate only via
  events/RPC (§4, §11, ADR-004) — the textbook definition of a bounded context, verified
  at the infrastructure level in this review rather than asserted at the documentation
  level alone.
- **Ubiquitous language is consistent with the Bible's own terminology**: "World Object,"
  "Active Context," "Attention," "knowledge maturity layer," "memory tier" all appear
  identically in the Bible text, the design docs, the ADRs, and the code itself
  (`ObjectState`, `ActiveContext`, `AttentionEntry`, domain model class names verified
  directly) — no translation layer where code uses different words than the design.
- **Repository pattern** is used consistently as the sole persistence abstraction domain
  logic depends on, in every engine, never an ORM session or raw connection leaking into
  `domain/`.
- **Domain models are not anemic**: `domain/state_management.py`,
  `domain/conflict_resolution.py`, `domain/attention.py`, `domain/lifecycle.py`,
  `domain/evolution.py` all contain real behavior (transition rules, decay formulas,
  resolution chains) operating on the domain types, not just data-holding classes with
  logic pushed into API handlers or repositories.
- **Aggregates and consistency boundaries are respected by the saga pattern itself**: the
  outbox pattern exists specifically because a World Object / Knowledge Node and its
  graph representation cannot be written in one transaction — the saga is DDD's
  "eventual consistency between aggregates in different bounded contexts" applied
  correctly, not a workaround.

## 17. Bible compliance verification

Restated from the Phase 1 Architecture Review Report §8 (verified again here rather than
assumed still true): Memory Engine (Bible Part 3) and Knowledge Engine (Bible Part 10)
are implemented at full breadth against their respective Bible parts. World Model Engine
(Bible Part 5 + Part 18, merged per ADR-002) is implemented under the additional
constraint the user imposed before implementation began — a stricter reading of the
Bible's own Memory/Knowledge/World-Model separation than the Bible's prose alone made
explicit — and that constraint is honored throughout, confirmed structurally in this
review (§11's schema evidence, §13/§14's dependency graph, §1's domain-purity checks) and
not just documented. World Simulation (Part 18) remains an intentional, recorded
scope-reduction to an interface-only stub, not a silent gap.

## 18. Future migration risks

- **Embedding model change** (away from `nomic-embed-text`/768-dim): mitigated by design
  — `EmbeddingProvider` (ADR-009) is already an interface, and every embedded table
  carries an `embedding_model` column specifically so a future model change is a
  background re-embedding job, not a schema migration (ADR-010). Low risk.
- **Event Bus backend change** (NATS → Kafka/RabbitMQ): mitigated by design (ADR-006);
  no engine imports NATS directly, verified in §1/§14 (only `nova_eventbus_sdk` does).
  Low risk.
- **Graph database change** (Neo4j → alternative): mitigated by design (ADR-007); no
  engine imports the Neo4j driver directly, verified the same way. Low risk. The one
  caveat: `GraphQuery`/`TraversalSpec`'s lack of a batched multi-node primitive (§5, §9)
  means any future backend must also support the current one-node-at-a-time traversal
  pattern efficiently, or that pattern needs fixing before the backend is swapped, not
  after.
- **Schema evolution across three independent Alembic histories**: each engine owns its
  own migration chain with no cross-engine migration coordination mechanism. Fine while
  each engine's schema is independent (true today, per §11); would need a real strategy
  if a future requirement ever needed a coordinated multi-engine schema change (none
  exists today).
- **The un-pagination-ed API surface** (§5, §9) is itself a migration risk: adding
  pagination later is a breaking change to every list-returning endpoint's response
  shape for any caller that already exists. Cheaper to design the convention now, before
  Phase 2 adds real callers, than to migrate real callers later.

## 19. Recommendations before Phase 2

**Already done as part of this review** (see §4 for detail):
1. Wired `memory-engine`, `knowledge-engine`, and `world-model-engine` into
   `infra/docker/docker-compose.local.yml` — the full Phase 1 stack is now composable.
2. Added all three engines to `build-and-scan.yml`'s image-build-and-scan matrix — their
   Dockerfiles will now actually be built and vulnerability-scanned in CI.
3. Added `pytest-cov` as a root dev dependency — test coverage is now a measurable,
   reportable number (see Metrics) instead of an open question.

**Recommended, not yet done:**
4. Run the now-complete compose stack in a Docker-capable environment to capture the
   three metrics this review could not measure here: startup time, memory footprint, and
   a first real latency measurement against each engine's stated p95 targets (§8) —
   before any Phase 2 engine takes a runtime dependency on those latency budgets.
5. Decide and implement a pagination convention (§5, §9, §18) before Phase 2 traffic
   makes its absence a real cost, not after.
6. Add an automated CI check comparing every subject in every engine's
   `published.py`/`subscribed.py` against `nova_contracts.registry.known_subjects()`
   (§2, §10) — the check this review ran manually and found clean, made permanent.
7. Explicitly document (in `docs/architecture/14-deployment-architecture.md` or
   equivalent) that no Phase 1 engine's port may be published to a host network or the
   internet before `nova-auth` ships (§6) — currently an implicit consequence of
   local-first deployment, not a written constraint.
8. Build the internal CLI/admin API (already flagged in the Phase 1 Architecture Review
   Report) before Phase 2 adds more engines and more cross-engine state that per-engine
   `/docs` inspection alone won't cover well.

None of items 4-8 block Phase 2 from starting — they are operational and risk-reduction
work that can proceed in parallel with, or just ahead of, the first Phase 2 engines,
except item 4's latency verification, which should land before any engine takes a
runtime dependency on World Model's 20ms context-request budget specifically.

## 20. Final Go / No-Go recommendation

**Go.**

The architecture is sound by every check this review could actually run: zero test
failures across 376 tests, zero lint/type errors across 167 source files, zero broken
import contracts, zero circular dependencies, zero unexplained event-contract drift,
zero hardcoded secrets or SQL injection surface, and a verified-not-assumed Clean
Architecture / DDD boundary structure. The three gaps found and fixed during this review
(missing compose wiring, missing CI build coverage, missing coverage tooling) were real
but narrow, and are closed. The gaps found and not fixed (no pagination, no measured
runtime performance, no CLI/admin tool, no auth) are all either explicitly out of Phase
1's documented scope (auth) or genuinely deferrable without blocking Phase 2's own
objectives (pagination, performance measurement, the admin CLI) — none of them are
foundation-level defects that would compound if built on top of.

Phase 1 is closed. Phase 2 — AI Core: Model Orchestration & Reasoning — may begin.

---

## 21. Engineering metrics

Per the new standing requirement: every completed phase reports these thirteen metrics
going forward. All numbers below were produced by commands actually run against this
repository during this review (see each row); none are estimated. Three metrics could
not be measured in this environment and are reported as such rather than guessed — see
the notes under Performance benchmarks / Memory usage / Startup time. The reusable
format for future phases is
[`METRICS_TEMPLATE.md`](METRICS_TEMPLATE.md) in this directory.

### Source lines of code

| Scope | Lines |
|---|---|
| Production source (`src/`, all 11 packages) | 14,177 |
| Tests (`tests/`, all 11 packages) | 5,904 |
| **Total** | **20,081** |

Per package/service (`src/` only):

| Package | Lines | Files |
|---|---|---|
| `knowledge-engine` | 3,704 | 36 |
| `memory-engine` | 3,644 | 41 |
| `world-model-engine` | 2,996 | 37 |
| `nova-eventbus-sdk` | 810 | 7 |
| `nova-graphstore-sdk` | 793 | 7 |
| `nova-contracts` | 715 | 8 |
| `nova-vectorstore-sdk` | 512 | 6 |
| `nova-core` | 452 | 12 |
| `nova-embeddings-sdk` | 285 | 6 |
| `nova-observability` | 199 | 4 |
| `nova-testkit` | 67 | 3 |

*Measured by: `find <path> -name "*.py" -exec cat {} + \| wc -l` per package.*

### Number of modules

- **11 first-party Python packages** (7 shared packages under `packages/`, 4 services
  under `services/`).
- **167 source modules** (`.py` files under `src/`, summed across all 11 packages) + **86
  test modules** (`.py` files under `tests/`) = **253 total Python modules**.

### Number of public APIs

| Kind | Count |
|---|---|
| HTTP REST route handlers (`@router.<verb>(...)`) | 32 |
| Mounted `/internal/metrics` endpoints (one per service) | 4 |
| **Total HTTP endpoints** | **36** |
| Published event types (`events/published.py`, across all 4 services) | 23 |
| Served request/reply RPCs (`bus.serve(...)`) | 5 |
| **Total event-bus-facing contracts** | **28** |

*Measured by: `grep -rE "@(router\|app)\.(get\|post\|patch\|put\|delete)\("` for HTTP
routes; direct count of `published.py` entries and `serve()` registrations for event-bus
contracts.*

### Test count

| Package | Tests |
|---|---|
| `memory-engine` | 123 |
| `knowledge-engine` | 67 |
| `world-model-engine` | 54 |
| `nova-core` | 13 |
| `nova-contracts` | 31 |
| `nova-eventbus-sdk` | 23 |
| `nova-graphstore-sdk` | 24 |
| `nova-vectorstore-sdk` | 19 |
| `nova-embeddings-sdk` | 11 |
| `nova-observability` | 7 |
| `nova-testkit` | 4 |
| **Total** | **376** |

All 376 pass. *Measured by: `pytest --collect-only -q` and `pytest -q`, per package, this
session.*

### Test coverage

`pytest-cov` did not exist in this repository before this review — added as a root dev
dependency specifically to make this metric answerable (§19). Real numbers, this
session:

| Service | Statements | Missed | Coverage |
|---|---|---|---|
| `nova-core` | 220 | 1 | **99%** |
| `memory-engine` | 1,287 | 258 | **80%** |
| `knowledge-engine` | 1,389 | 286 | **79%** |
| `world-model-engine` | 1,101 | 302 | **73%** |
| **Aggregate, 4 services** | **3,997** | **847** | **79%** |

The uncovered lines are concentrated almost entirely in one place per engine: the real
Postgres/Redis repository modules (`postgres_*_repository.py`,
`redis_context_repository.py` — 24-28% covered each) and the `main.py` lazy real-backend
construction branches — both untestable without a live Postgres/Redis/Neo4j, which this
environment does not have (§4). Every fake-backed/in-memory-backed code path (`domain/`,
API routes exercised via `TestClient`, the saga dispatcher against
`InMemoryGraphStore`/`InMemoryEventBus`) is at 85-100%.

Shared packages were also measured but are **not included in the headline number**: their
coverage (4-94%, e.g. `nova-contracts` at 4%) is a measurement artifact, not a quality
signal — `nova-contracts`' event payload classes are exercised extensively by every
engine's *own* test suite (a separate pytest process/coverage context each), not by
`nova-contracts`' own narrow test suite in isolation. Reported for completeness, not
comparability: `nova-contracts` 4%, `nova-eventbus-sdk` 40%, `nova-graphstore-sdk` 67%,
`nova-vectorstore-sdk` 71%, `nova-embeddings-sdk` 82%, `nova-observability` 94%,
`nova-testkit` unmeasured (trivial test-harness code).

*Measured by: `pytest --cov=<package> --cov-report=term-missing`, per package, this
session.*

### ADR count

**19 total** — ADR-001 through ADR-010 (foundational/pre-implementation) + ADR-011
through ADR-019 (per-subsystem, filed this phase). See §12.

### Architecture documents

| Category | Count |
|---|---|
| Bible parts (`docs/bible/`) | 22 |
| SAD architecture docs (`docs/architecture/`, numbered 00-20 + README) | 22 |
| ADR files (`docs/architecture/adr/`) | 9 |
| Phase 1 design docs (`docs/design/`) | 6 |
| Roadmap + architecture review docs (`docs/roadmap/`) | 3 |
| **Total markdown files under `docs/`** | **63** |
| Engine/package `README.md` files (`services/*/`, `packages/*/`) | 11 |
| **Grand total documentation files** | **74** |
| Total word count, `docs/` only | **~74,862** |

*Measured by: `find docs -name "*.md" \| wc -l` and `wc -w`.*

### Build duration

No compiled build step exists for this pure-Python-plus-not-yet-started-frontend
monorepo, so "build duration" is reported as the two durations that actually exist:

| Step | Duration |
|---|---|
| `uv sync --all-packages` (warm cache) | 0.035s |
| Full test suite, all 11 packages, sequential (`pytest -q` × 11 processes) | 16.9s |
| Docker image build (4 Dockerfiles) | **NOT MEASURED** — no Docker daemon reachable in this environment (`docker info` fails; starting one fails on a sandbox `ulimit` permission restriction). Static verification only (§4, §11 methodology): every Dockerfile's `COPY` list matches its `pyproject.toml` dependencies exactly, and every `COPY` source path exists. Real build timing requires the environment recommended in §19 item 4. |

*Measured by: `time uv sync --all-packages`, `time <sequential test loop>`, this session.*

### Static analysis results

| Tool | Result |
|---|---|
| `ruff check .` (whole repo) | **0 issues** |
| `mypy` (per-package, matching CI's exact invocation) | **0 issues**, 167 source files across 11 packages |
| `import-linter` (`lint-imports`) | **3/3 contracts kept**, 0 broken, 153 files / 691 dependencies analyzed |
| `pip-audit` | **0 known vulnerabilities**, all third-party dependencies |

*Measured by: direct invocation of each tool, this session — see §1.*

### Dependency graph

**11 first-party packages, 20 edges, 0 cycles.** Built with `grimp` independent of
import-linter's own scoped contracts; full diagram and methodology in §13/§14.

### Performance benchmarks

**NOT MEASURED.** No engine has ever been load-tested against real infrastructure, in
this environment or any prior session. Every stated performance target (each design
doc's §15) is a design-time intention, not a measured result. Requires the Docker-capable
environment recommended in §19 item 4. See §8 for full discussion — this is the single
most consequential open item before Phase 2.

### Memory usage

**NOT MEASURED.** No engine process has been run against real infrastructure in this
environment (no Docker daemon reachable — confirmed via `docker info`, §4). Requires the
same environment as Performance benchmarks above.

### Startup time

**NOT MEASURED.** Same reason as Memory usage. The `docker-compose.local.yml` wiring
fixed in this review (§4, §19) is what a Docker-capable environment would use to produce
this number — `HEALTHCHECK` directives already exist in every Dockerfile
(`--start-period=5s`, an untested guess at startup time, not a measurement) and would be
the natural first real data point once a daemon is available.
