# Architecture Review Report — Phase 1: Memory, Knowledge & World Model Engines

**Phase:** 1 — Data & Memory Substrate
**Completed:** 2026-08-04
**Design document(s):** [docs/design/phase-1/](../../design/phase-1/README.md) (00 Shared
Foundations, 01 Memory Engine, 02 Knowledge Engine, 03 World Model Engine, 04
Cross-Engine Integration)
**Author:** Claude (Anthropic), AI-assisted implementation under direct human
architectural direction and review throughout — every design deviation, boundary
decision, and deferral recorded in this report was either explicitly instructed by
the user or self-identified and flagged for the reasoning shown below, never
silently decided.

## 1. What was implemented

Three independently deployable engines, each a full FastAPI service + Arq worker
process pair, plus the shared packages Phase 1 required:

**Shared packages** (`packages/`):
- `nova-contracts` — event payload schemas (Pydantic) for all three engines'
  publish/subscribe/serve contracts, with generated TypeScript types.
- `nova-vectorstore-sdk`, `nova-graphstore-sdk`, `nova-embeddings-sdk` — the three
  new abstraction packages ADR-007/009 required, each with an in-memory backend for
  testing and a real backend (pgvector / Neo4j / Ollama) for production.
- `nova-eventbus-sdk` gained `serve()` (request/reply serving) mid-phase, required
  once Memory Engine needed to *serve* `memory.retrieve.request` rather than only
  publish/subscribe.

**Memory Engine** (`services/memory-engine/`) — Bible Part 3. Owns `memory.*`
Postgres tables (unified `memory_record`, discriminated by `memory_type`), `mem:*`
Redis keys (Working Memory, a primary store), and the `memory_records` vector
collection. Every memory tier (sensory, working, short-term, long-term — episodic,
semantic, procedural, preference, project, decision), the
`active → dormant → archived → scheduled_for_deletion → deleted` lifecycle,
importance scoring, consolidation, and semantic+timeline retrieval. 8 public API
endpoints, 8 published event subjects, 2 served/initiated RPCs. 123 tests (77 unit,
46 integration), all passing.

**Knowledge Engine** (`services/knowledge-engine/`) — Bible Part 10. Owns
`knowledge.*` Postgres tables, the Neo4j graph (`:Project`, `:Person`, `:Concept`,
`:Decision`, ...), and the `knowledge_nodes` vector collection. Acquisition
(normalize → validate → contradiction-check → create-or-corroborate), the
seven-stage knowledge-maturity lifecycle (raw → ... → strategic), relationship
discovery, duplicate flagging (never merging), and semantic+graph+name retrieval. 6
public API endpoints, 4 published event subjects, 3 served RPCs. The Postgres-then-
Neo4j two-phase saga (outbox pattern) introduced here and reused by World Model
Engine. 67 tests, all passing.

**World Model Engine** (`services/world-model-engine/`) — Bible Part 5 + Part 18
(merged, ADR-002). Owns `world_model.*` Postgres tables, distinct
`:WorldProject|File|Window|Application|Agent|Task|Device|SystemResource` Neo4j
labels, and `world:*` Redis keys (Active Context and Attention, primary stores). A
table-driven object-lifecycle state machine, multi-modal perception fusion, a
confidence→policy→recency→unresolved conflict-resolution chain, lazy attention
decay, structural-heuristic prediction, and an honest interface-only World
Simulation stub. 7 public API endpoints, 6 published event subjects, 1 served RPC
(the tightest latency budget in Phase 1: p95 < 20ms). 54 tests (34 unit, 20
integration), all passing.

**Total: 244 tests passing across the three engines** (plus the shared packages'
own suites), `ruff check` and `mypy` clean across every engine's `src/` and `tests/`,
and the root `import-linter` contract (ADR-004/006/007 enforcement: no engine
imports another engine's internals, no engine imports a broker/graph client
directly) passing with zero violations across all three.

No design changed from what [docs/design/phase-1/](../../design/phase-1/README.md)
specified — the one addition beyond the design doc's literal text is
`WorldHistoryRepository.list_recent_history_for_user`, added because
`prediction_worker.py` needs cross-object, user-scoped history and the schema's
`osh_user_idx (user_id, changed_at DESC)` index already anticipated exactly this
query pattern — a schema-supported extension of an existing Protocol, not a new
architectural decision requiring its own ADR.

One roadmap-listed Phase 1 deliverable was **not** built: the "minimal internal
CLI/admin API for manually inspecting memory/knowledge/world state." Each engine
does expose its full state through its own FastAPI routes (and each engine's
auto-generated OpenAPI/Swagger UI at `/docs`), which covers ad hoc inspection during
development, but no dedicated cross-engine CLI or admin surface exists. This is
recorded here rather than left unstated — see §4.

## 2. Why each architectural decision was made

Every non-obvious implementation-time decision across all three engines is now filed
as a structured ADR in [`docs/architecture/adr/`](../../architecture/adr/README.md)
(ADR-011 through ADR-019), per the standing requirement established during this
phase that every significant architectural decision remain traceable years from now.
This section is deliberately short — see the ADR log for full
Context/Problem/Alternatives/Decision/Consequences/Tradeoffs/Future-implications
detail on each. Summary list:

- **ADR-011** — Unified `memory_record` schema (one polymorphic table, discriminated
  by `memory_type`) over one table per memory type.
- **ADR-012** — Redis as the *primary* store (not a cache) for Working Memory
  (Memory Engine) and Active Context/Attention (World Model Engine).
- **ADR-013** — Embedding generation happens asynchronously, off the write path, in
  both Memory Engine and Knowledge Engine.
- **ADR-014** — The Postgres-then-graph two-phase saga (transactional outbox +
  separate dispatcher), introduced in Knowledge Engine and reused verbatim in World
  Model Engine, as the answer to the cross-datastore consistency problem ADR-007's
  `GraphStore` abstraction otherwise leaves open.
- **ADR-015** — Knowledge's seven-stage maturity lifecycle instead of a single
  decaying confidence score.
- **ADR-016** — Contradictions are recorded, never silently resolved by overwrite.
- **ADR-017** — The World Model boundary itself: no embeddings, no forgetting
  lifecycle, no validated-fact graph, distinct Neo4j label set from Knowledge's —
  the decision this whole phase was built under, elevated to a formal ADR.
- **ADR-018** — World Model's "current object state" reads come from Postgres's
  `object_state_history`, never from Neo4j.
- **ADR-019** — The `ACTIVE → IDLE` idle-sweep worker is deliberately not built in
  Phase 1, as an evidence-driven optimization deferral rather than a shipped
  half-correct implementation.

## 3. Tradeoffs considered

- **No read-through cache in any of the three engines.** Every read hits
  Postgres/Redis/Neo4j directly. Acceptable because Phase 1 has no real traffic yet
  to establish a cache-hit-rate justification for the added consistency risk; the
  condition that would flip this decision is production read latency data showing
  Postgres/Neo4j round-trips are the actual bottleneck, not a guess.
- **Fixed-interval scheduled workers (consolidation, maintenance, snapshots,
  predictions) instead of event-driven triggers.** All three engines chose the same
  tradeoff independently converging on the same answer: a cron-style fixed interval
  is simpler and sufficiently correct until there's a concrete latency requirement
  that a fixed interval can't meet. Acceptable for Phase 1's acceptance bar; revisit
  if a later phase's requirements specify a tighter latency bound than the chosen
  intervals provide.
- **No user-directory/active-user-discovery mechanism.** All three engines' scheduled
  workers that need a `user_ids` list currently receive an empty one
  (`known_user_ids = []`), making those cron jobs honest no-ops rather than silently
  wrong or speculatively guessed. Acceptable because no engine in Phase 1 or Phase 2
  yet owns "the current list of active users" as a capability; the moment one does
  (Agent OS or a session registry), wiring it in is a one-line change per engine, not
  a redesign.
- **Placeholder event handlers for every subject with no real Phase 1 producer**
  (Perception, Reasoning, Planning, Agent OS all ship later). Every placeholder
  degrades defensively (log-and-skip on missing fields) rather than raising, and is
  documented as a contract the engine is ready to serve, not a functional gap being
  hidden. This was the single most repeated tradeoff across all three engines and is
  the direct, deliberate consequence of building Phase 1's data substrate before
  Phase 4's Perception Engine exists to feed it.

## 4. Known limitations

Each engine's own README carries the full, engine-specific list under "Known
limitations (Phase 1)." Cross-engine patterns worth calling out here:

- **Deliberately deferred, not accidentally missing:** no read-through cache (all
  three), no idle-sweep worker (World Model only — Memory/Knowledge have no
  equivalent "idle timeout" concept), no user-directory mechanism (all three's
  scheduled workers), World Simulation as an interface-only stub (World Model only —
  Memory/Knowledge have no analogous "simulate the future" requirement).
- **Should probably be revisited, not blocking:** the `/v1/knowledge/graph` and
  `/v1/world/graph` subgraph endpoints both issue one-node-at-a-time `GraphStore`
  calls rather than a single batched query, since `GraphQuery`'s backend-agnostic
  interface (ADR-007) has no label-agnostic "give me everything" primitive.
  Acceptable at visualization-call sizes today.
- **Roadmap-listed but not built: the internal CLI/admin API.** The Phase 1 roadmap
  entry lists "a minimal internal CLI/admin API for manually inspecting
  memory/knowledge/world state" as a deliverable. It was not built. Each engine's own
  FastAPI routes and auto-generated OpenAPI/Swagger UI (`/docs`) provide ad hoc
  per-engine inspection, but no dedicated cross-engine CLI or unified admin surface
  exists. This should be picked up before Phase 2 work makes manual state inspection
  more valuable (more engines, more cross-engine state to reason about) — it is a
  genuine gap against the roadmap, not a deliberate scope reduction, and is called
  out explicitly here rather than left unstated.
- **Untestable in this environment, not untested in principle:** every engine's
  Postgres/Redis/Neo4j-specific repository code is exercised by the fake/in-memory
  substitution pattern in integration tests, but never against real backends, since
  this development environment has no Docker. Validating those code paths requires
  the Docker Compose stack (`infra/docker/docker-compose.local.yml`) — an accepted
  gap already established at Phase 0 and carried through Phase 1 unchanged.

## 5. Technical debt introduced, if any

None accepted as debt in the traditional sense (a shortcut that will need
unwinding). The closest candidates were evaluated and rejected as debt:

- `WorldHistoryRepository.list_recent_history_for_user` was added beyond the
  design doc's literal method list, but it is schema-supported
  (`osh_user_idx (user_id, changed_at DESC)` already anticipates exactly this access
  pattern) and consistent with the repository's existing Protocol shape — not a
  workaround that will need revisiting.
- The three deliberately-deferred items in §4 (no idle-sweep worker, no
  user-directory mechanism, no read-through cache) are scope decisions with a clear
  trigger condition for revisiting, documented per-engine — not debt, because nothing
  was built incorrectly that now needs fixing; nothing was built at all in those
  spots, and that absence is intentional and visible.

## 6. Future improvements

- Build the internal CLI/admin API listed as a Phase 1 roadmap deliverable but not
  yet built (§4) — most useful before Phase 2 adds more engines and more
  cross-engine state that manual per-engine `/docs` inspection doesn't cover well.
- Wire a real user-directory source into `known_user_ids` for all three engines'
  scheduled workers once Agent OS or a session registry exists (Phase 3+).
- Build the `ACTIVE → IDLE` idle-sweep worker once either a Postgres
  "latest-row-per-object-id-filtered-by-staleness" query or a Neo4j
  property-based staleness check has been evaluated against real traffic patterns
  (ADR-019).
- Revisit read-through caching for all three engines once Phase 2+ traffic data
  exists to justify (or rule out) the added consistency risk.
- Extend `GraphQuery`'s backend-agnostic interface with a batched multi-node
  primitive if `/v1/knowledge/graph` or `/v1/world/graph` usage grows beyond
  visualization-call sizes.
- Real cross-engine correlation (Knowledge's `:Project` ↔ World Model's
  `:WorldProject` via shared UUID) is currently a convention with no code path
  exercising it end-to-end; the first future engine that needs this correlation
  (most likely Reasoning Engine, Phase 2) should be the one to build and test it,
  per §5's boundary rule in [doc 20](../../architecture/20-engine-responsibility-boundaries.md).

## 7. Risks

- **Operational:** none of the three engines' `main.py`/`workers/` have been booted
  against real Postgres/Redis/Neo4j in this environment (no Docker available here).
  The fake-backend integration test suite gives strong confidence in domain logic and
  wiring correctness, but first-boot-against-real-infra issues (connection pooling,
  migration ordering, Neo4j constraint conflicts) remain unverified until a Docker
  Compose run happens, ideally before any Phase 2 engine is built on top of these
  three.
- **Architectural:** the World Model/Knowledge Engine non-interaction boundary (§5 of
  doc 20) depends on every future engine respecting the "correlate at the UUID from
  outside both engines, never merge" convention. Nothing currently enforces this at
  the code level beyond the import-linter's engine-independence contract (which
  prevents direct imports but not, for example, a future engine hard-coding
  assumptions about both label sets). Low likelihood in Phase 1 (no consumer exists
  yet); worth an explicit code-review checklist item once Reasoning Engine starts
  reading both.
- **Scale:** none of Phase 1's performance targets (each engine's design doc §15)
  have been load-tested; they are design-time targets, not measured results. Low
  risk at Phase 1's actual traffic (zero — no real Perception producer exists yet),
  but should not be treated as validated until measured.

## 8. Compatibility with the NOVA Project Bible

- **Memory Engine (Bible Part 3):** implemented at full breadth — every memory
  tier and type specified. Faithful implementation; no requirement deferred or
  reinterpreted beyond what ADR-009/010 (embedding abstraction, standardized model)
  already recorded as Phase 1 infrastructure decisions applying system-wide.
- **Knowledge Engine (Bible Part 10):** implemented at full breadth — acquisition,
  validation, contradiction detection, the seven-stage maturity model, discovery,
  compression, retrieval. "Nothing important should disappear permanently" (Part
  10) is enforced as a hard constraint (§4, this report).
- **World Model Engine (Bible Part 5 + Part 18, merged per ADR-002):** implemented
  under the additional constraint — not in the Bible text itself, but imposed by the
  user before implementation began — that it must not become another Memory Engine
  or Knowledge Engine. This constraint is honored throughout (see ADR-017 and doc
  20 §1-2) and is, if anything, a *stricter* reading of the Bible's own separation
  of Part 3 ("historical experience"), Part 10 ("validated facts"), and Part
  5/18 ("current state of reality") than the Bible's prose alone made explicit.
  World Simulation (Part 18's more speculative "predict outcomes before acting"
  capability) is intentionally shipped as an interface-only stub — a scope
  reduction, explicitly recorded as such (ADR entry, doc README), not a silent gap.
- All three engines' documented "Known limitations" sections are, per the user's
  standing instruction from this phase, deliberately preferred over any speculative
  implementation of behavior the design docs did not specify.

## Sign-off

- [x] All items in each engine's design-doc review checklist
      ([docs/design/phase-1/README.md](../../design/phase-1/README.md#review-checklist))
      are satisfied — the design was approved before implementation began and no
      deviation occurred beyond the one schema-supported addition noted in §1.
- [x] The phase's Definition of Done
      ([SAD 15 §4](../../architecture/15-development-workflow.md#4-definition-of-done-per-pr))
      was met for every engine: implementation, tests, observability, and
      documentation delivered together, not as follow-up work.
- [x] The per-subsystem deliverable checklist
      ([SAD 15 §9](../../architecture/15-development-workflow.md#9-per-subsystem-deliverable-checklist))
      was met for all three engines built this phase.
