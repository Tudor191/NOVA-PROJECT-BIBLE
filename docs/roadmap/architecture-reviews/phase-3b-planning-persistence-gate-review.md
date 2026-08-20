# Phase 3B — `planning-engine` Persistence: Gate Review

**Status: complete, fully verified locally and via real GitHub Actions
(see §10) — 24/24 checks green at head `ac364b998e130c944c355e52608b57849407c785`.
Covers exactly one PR-sized unit** (`phase-3b-planning-persistence`,
branched from `phase-3b-planning-domain`) of Phase 3B's multi-PR
implementation — the fourth and, per TDD 3B's own scope, final PR closing
this phase's approved surface (domain foundation → decomposition
orchestration → **this precursor** → nothing else named in TDD 3B remains
unbuilt except the `agent_os.task.completed` subscription, correctly
deferred to Phase 3E per §14).

This PR closes the exact gap the prior two Gate Reviews each disclosed:
Postgres-backed persistence for `TaskGraph`/`TaskNode` (TDD 3B §4), the
`GET`/`POST /v1/plans` API surface (§5), and the
`planning.task_graph.created`/`planning.decompose.request` event
contracts (§6.2) that both prior PRs correctly left unbuilt, "by design,
not an oversight" (decomposition-orchestration Gate Review §11).

---

## 0. Scope executed

Exactly TDD 3B §4, §5, and §6.2 — nothing from §6.1's
`agent_os.task.completed` subscription (explicitly excluded per this PR's
own authorization), no redesign of any already-resolved fork, no change
to `agent-os`/Phase 3E's approved architecture.

1. **Contracts** (`packages/nova-contracts`): `TaskNodeSnapshot`,
   `TaskGraphSnapshot`, `PlanningTaskGraphCreatedPayload`,
   `PlanningDecomposeRequestPayload`, `PlanningDecomposeReplyPayload` —
   wire payloads independently defined from this engine's own domain
   models, translated at the publish boundary (never a direct import of
   `nova_planning_engine.domain.models` into `nova_contracts`, matching
   this codebase's established convention for every other engine).
2. **Persistence** (`services/planning-engine/repository/`): SQLAlchemy
   ORM models (`TaskGraphORM`, `TaskNodeORM`, `OutboxEventORM`) against a
   new `planning` Postgres schema; `PostgresPlanningRepository`
   implementing the `PlanningRepository` Protocol (`find_by_id`,
   `find_node`, `insert`, `append_nodes`, `set_approved_at`,
   `list_dispatch_ready`, `mark_dispatched`); a hand-written Alembic
   migration (`0001_initial_schema.py`) mirroring `action-engine`'s own
   migration structure exactly.
3. **API surface** (`api/plans.py`): `GET /v1/plans/{task_graph_id}`,
   `POST /v1/plans/{task_graph_id}/approve` — exposed directly at this
   engine's own FastAPI app, the same stopgap precedent
   `action-engine`'s `api/approvals.py` established (TDD 3D §2; no
   `api-gateway` exists yet).
4. **`planning.task_graph.created` publication**: enqueued via the
   transactional outbox (`nova_service_kit.outbox`) inside the same
   transaction as the `task_graph`/`task_node` write it accompanies;
   actually published by a new `workers/outbox_worker.py` Arq process
   (`planning-engine-worker`), not directly by the FastAPI process —
   mirrors `memory-engine`'s own outbox/worker split exactly.
5. **`planning.decompose.request` RPC**: served via
   `events/decompose_handler.py`, using the new
   `domain/decomposition.py::decompose_node` function (node-scoped
   decomposition, reusing `decompose()`'s entire model-call/validation
   pipeline unchanged) and the repository's `append_nodes` mutation path.
6. **Infra wiring**: `planning-engine`/`planning-engine-worker` service
   blocks added to `docker-compose.local.yml` (this engine had no
   container image and no compose entry at all before this PR — a gap
   inherited from the decomposition-orchestration PR's own explicit,
   disclosed "no persistence/API to serve yet" scoping, not a defect
   introduced here); `planning-engine` added to `build-and-scan.yml`'s
   matrix (was entirely absent) and `real-infra-checks.yml`'s matrix.

---

## 1. Architecture: no new decisions, only implementation of the approved design

Every structural choice in this PR follows an already-established
codebase convention, applied to `planning-engine` for the first time:

- **Domain-vs-wire-payload split** — `TaskGraph`/`TaskNode`/`Estimate`
  stay engine-local (an already-disclosed Phase 3B deviation, Domain
  Foundation Gate Review §1); the five new `nova_contracts` types are
  independently defined and translated at the boundary
  (`events/snapshot.py`), never a direct import in either direction.
- **Per-engine dedicated Postgres schema + hand-written Alembic
  migration** — `Base.metadata = MetaData(schema="planning")`, a
  namespaced `alembic_version_planning` table, mirroring every other
  engine's own migration convention (verified directly against
  `action-engine`'s `alembic.ini`/`env.py`/`0001_initial_schema.py`
  before writing this engine's own).
- **RPC serve pattern** — `bus.serve("planning.decompose.request",
  handler, source_engine=...)`, registered in `events/subscribed.py`'s
  `SUBSCRIBABLE_SUBJECTS` (confirmed via `action-engine`'s own
  `action.execute` precedent — a served subject belongs in
  `subscribed.py`, not `published.py`).
- **Transactional outbox + separate Arq worker** — reused unmodified
  (`nova_service_kit.outbox.dispatch_ready_events`, ADR-034), mirroring
  `memory-engine`'s own `workers/outbox_worker.py`/`workers/__init__.py`
  structure line-for-line, including the "own `configure_observability()`
  call, own engine name suffix (`planning-engine-worker`)" pattern for a
  genuinely separate OS process.
- **SQLAlchemy `relationship()` usage** — corrected mid-implementation to
  match the one existing precedent (`communication-engine`'s own plain
  `back_populates` pattern) after an initial draft invented an
  unprecedented `lazy="raise"` option; caught by grepping the codebase for
  every existing `relationship(` call before finalizing this engine's own,
  per the standing "use existing patterns, don't invent" instruction.

**No fork was reopened.** Forks 3B-1 through 3B-4 (Domain Foundation and
Decomposition Orchestration Gate Reviews) are unchanged by this PR.

---

## 2. "Mutation, not regeneration" — scoped to the one path the TDD unambiguously specifies

TDD 3B §4's "mutation, not regeneration" requirement is implemented
exactly where the TDD's own text supports it and nowhere else:

- **`planning.decompose.request`'s node-scoped append path**
  (`decompose_handler.py`) — unambiguous: the request payload names an
  existing `task_node_id`, `PostgresPlanningRepository.find_node` locates
  its containing graph, and `append_nodes` appends the newly proposed
  child nodes to that already-persisted graph, recomputing
  `critical_path` over the combined node set. The original node's own row
  is never deleted or replaced.
- **`reasoning.process.completed` → `decompose()`** — always produces a
  **new** `TaskGraph` via `PlanningRepository.insert`, never merges into
  an existing one. No `reasoning_process_id`-to-`task_graph_id` linkage is
  specified anywhere in TDD 3B, doc 06 §3, or the Phase 3E research
  documents that reference this handler — inventing one here would have
  been new, unauthorized architecture, not implementation of an existing
  decision. This is the same conclusion the Phase 3E research document
  already draws for its own, unrelated purposes (see §7 below for the
  cross-reference).

This is an interpretation call, not a new architectural decision: TDD 3B
§4's own prose ("Dynamic Replanning updates existing `task_node` rows...
and appends new nodes when decomposition reveals previously-unknown
subtasks") names exactly one mutation trigger — the node-scoped decompose
request — and the schema itself provides no mechanism to correlate a
`reasoning.process.completed` event with any existing `TaskGraph`.

---

## 3. Outbox-payload timing — a self-caught design correction before verification

The first draft of `decompose_handler.py` built the
`planning.task_graph.created` outbox payload **before** the graph
mutation — using `critical_path` computed from the pre-mutation node set,
not the post-mutation one — and left an unimplemented
`_find_graph_and_node` stub (`raise NotImplementedError` followed by
unreachable code). This was caught and redesigned before any test was
written against it, not patched over: `PlanningRepository.append_nodes`'s
signature was changed from a static `outbox_event: OutboxEvent` parameter
to `outbox_event_builder: Callable[[TaskGraph], OutboxEvent]`, called
**after** the mutation and critical-path recomputation, inside the same
transaction, with the fully up-to-date `TaskGraph`. A new
`find_node(task_node_id) -> tuple[TaskGraph, TaskNode] | None` port method
was added to make the two-step lookup (node → its graph) a proper
repository primitive rather than an ad hoc query inline in the handler.

---

## 3a. CI-caught defect, fixed same-day (commit `ac364b9`)

The first pushed commit (`3c71e77`)'s real-infra CI run
(`real-infra-checks.yml`, `planning-engine` matrix entry, first execution
ever for this engine) caught a genuine bug that no local check could have
caught in this environment (no Docker daemon; see §6/§9's own disclosure):
`_node_orm()` passed `node.depends_on` (`list[UUID]`) directly into
`TaskNodeORM.depends_on` (a JSONB column) without stringifying, unlike the
identical `critical_path` field a few lines above it, which already does
`[str(node_id) for node_id in graph.critical_path]`. This only fails for a
`TaskNode` with a **non-empty** `depends_on` — `json.dumps` cannot
serialize a bare `UUID` object — which is why 9 of the 10 new real-infra
tests passed and exactly one (the only one inserting a node with a
dependency) failed: `TypeError: Object of type UUID is not JSON
serializable`.

Fixed by mirroring the existing `critical_path` pattern exactly:
`_node_orm()` now stringifies (`[str(dep_id) for dep_id in
node.depends_on]`) on write, and `_node_to_domain()` now parses back
(`[UUID(dep_id) for dep_id in row.depends_on]`) on read. Local
ruff/mypy/the 67-test non-real-infra suite were re-verified clean before
pushing the fix; the corrected commit's own real-infra CI run confirmed
"10 passed, 67 deselected." No other test or code path was affected —
every other new test that exercises `depends_on` uses an empty list, so
this defect was real but narrowly scoped to the one path CI's own
non-empty-dependency test happened to exercise.

---

## 4. Verification did not reveal an architectural conflict

Per the standing "stop and report before choosing a solution" instruction:
implementing this PR's exact, pre-approved TDD 3B §4/§5/§6.2 scope
revealed **no genuine conflict** with the approved architecture. The one
prerequisite this PR itself exists to close — planning-engine having zero
real persistence despite TDD 3E's Kernel design assuming it — was already
identified, reported, and resolved by the user's explicit approval of
this precursor PR before implementation began; nothing new surfaced
during the implementation itself.

---

## 5. Exact files changed

**New:**
- `services/planning-engine/alembic.ini`, `alembic/env.py`,
  `alembic/script.py.mako`, `alembic/versions/0001_initial_schema.py`
- `services/planning-engine/src/nova_planning_engine/repository/models.py`
- `services/planning-engine/src/nova_planning_engine/repository/postgres_planning_repository.py`
- `services/planning-engine/src/nova_planning_engine/repository/outbox_dispatcher.py`
- `services/planning-engine/src/nova_planning_engine/events/snapshot.py`
- `services/planning-engine/src/nova_planning_engine/events/decompose_handler.py`
- `services/planning-engine/src/nova_planning_engine/api/plans.py`
- `services/planning-engine/src/nova_planning_engine/workers/__init__.py`,
  `workers/outbox_worker.py`
- `services/planning-engine/tests/fakes/repository.py`
- `services/planning-engine/tests/integration/test_events_decompose_request.py`
- `services/planning-engine/tests/integration/test_plans_api.py`
- `services/planning-engine/tests/integration/test_repository_real_postgres.py`
- `packages/nova-contracts/typescript/PlanningTaskGraphCreatedPayload.ts`,
  `PlanningDecomposeRequestPayload.ts`, `PlanningDecomposeReplyPayload.ts`

**Modified:**
- `packages/nova-contracts/src/nova_contracts/events/planning.py` (five
  new payload/snapshot types)
- `packages/nova-contracts/src/nova_contracts/__init__.py` (exports)
- `packages/nova-contracts/tests/test_planning_events.py` (3 new tests)
- `packages/nova-contracts/codegen/generate_typescript.py` (three new
  types added to the script's hardcoded import/`MODELS` lists — the
  script does not auto-discover `@register_payload`-decorated types; a
  real footgun caught by re-running codegen and seeing zero new files on
  the first attempt)
- `packages/nova-contracts/typescript/index.ts` (re-exports)
- `services/planning-engine/src/nova_planning_engine/domain/models.py`
  (`TaskGraph.approved_at`)
- `services/planning-engine/src/nova_planning_engine/domain/ports.py`
  (`PlanningRepository`, `OutboxEvent`, `OutboxRow`,
  `TaskGraphNotFoundError`)
- `services/planning-engine/src/nova_planning_engine/domain/decomposition.py`
  (`decompose_node`)
- `services/planning-engine/src/nova_planning_engine/events/handlers.py`
  (persists via `PlanningRepository.insert`)
- `services/planning-engine/src/nova_planning_engine/events/published.py`
  (`planning.task_graph.created` added to `PUBLISHABLE_SUBJECTS`)
- `services/planning-engine/src/nova_planning_engine/events/subscribed.py`
  (`planning.decompose.request` added to `SUBSCRIBABLE_SUBJECTS`)
- `services/planning-engine/src/nova_planning_engine/main.py` (repository
  construction, RPC handler registration, `plans` router mounted)
- `services/planning-engine/src/nova_planning_engine/config.py`
  (`postgres_dsn`, `redis_url`, `outbox_dispatch_batch_size`)
- `services/planning-engine/src/nova_planning_engine/observability.py`
  (five new named instruments, `outbox_dispatched_total`)
- `services/planning-engine/pyproject.toml` (`nova-service-kit`,
  `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `redis`, `arq`)
- `services/planning-engine/package.json` (`test` script gains the
  missing `-m "not real_infra"` filter every other engine's own `test`
  script already had — this engine's script was the one exception,
  corrected here since real-infra tests now exist for the first time)
- `services/planning-engine/Dockerfile` (`nova-service-kit` copied into
  the build context; `apt-get upgrade -y` added — the one Dockerfile in
  the whole repository still missing the TRIVY-2 CVE fix, since this
  engine had no `build-and-scan.yml` matrix entry to catch it until now)
- `services/planning-engine/tests/integration/test_events_reasoning_completed.py`
  (injects `FakePlanningRepository`, asserts persistence/outbox-enqueue)
- `services/planning-engine/tests/unit/test_decomposition.py` (4 new
  `decompose_node` tests)
- `infra/docker/docker-compose.local.yml` (`planning-engine`,
  `planning-engine-worker` service blocks)
- `.github/workflows/build-and-scan.yml` (`planning-engine` added to the
  matrix — was entirely absent)
- `.github/workflows/real-infra-checks.yml` (`planning-engine` added to
  the matrix)
- `docs/design/phase-3/05-tdd-3b-planning-engine.md` (top status banner)
- `docs/roadmap/architecture-reviews/phase-3b-domain-foundation-gate-review.md`,
  `phase-3b-decomposition-orchestration-gate-review.md` (additive forward
  pointers to this document)
- `uv.lock` (new dependency resolution)

---

## 6. Tests

**Unit** (`tests/unit/`, fake-backed, no I/O):
- `test_decomposition.py` — 4 new tests for `decompose_node`: already-
  minimal (single-task reply → `[]`), genuine breakdown (multi-task reply
  → the proposed nodes), and `DecompositionError` propagation.
- `test_models.py`, `test_task_graph.py`, `test_model_orchestration_client.py`
  — pre-existing, unchanged, still passing (`TaskGraph.approved_at`'s
  default `None` does not break existing construction call sites).

**Contract** (`packages/nova-contracts/tests/test_planning_events.py`):
3 new tests — `TaskGraphSnapshot`/`TaskNodeSnapshot` subject registration,
`PlanningTaskGraphCreatedPayload` multi-node round trip,
`PlanningDecomposeRequestPayload`/`.ReplyPayload` round trip.

**Integration** (`tests/integration/`, real `create_app()`, real in-memory
`EventBus`, fake `PlanningRepository`/`ModelOrchestrationPort`):
- `test_events_reasoning_completed.py` (4 tests, modified) — now asserts
  the resulting `TaskGraph` is durably persisted and its outbox row
  enqueued, not merely produced and discarded.
- `test_events_decompose_request.py` (3 new tests) — a genuine breakdown
  round-trips through the real served RPC (`planning.decompose.request`)
  via the established "second `BoundEventBus` as external caller" pattern
  (mirrors `action-engine`'s own `test_events_action_execute.py`);
  already-minimal reporting; `TaskNodeNotFoundError` raised for an unknown
  `task_node_id`.
- `test_plans_api.py` (4 new tests) — `GET`/`POST /v1/plans/{id}/approve`
  round trip through a real `TestClient`, including both 404 cases,
  mirroring `action-engine`'s own `test_approvals_api.py`.
- `test_health.py` — pre-existing, unchanged.

**Real-infrastructure** (`tests/integration/test_repository_real_postgres.py`,
`@pytest.mark.real_infra`, 10 new tests): insert/find round trip;
multi-node persistence and ordering; `find_node`'s two-step lookup;
`append_nodes`'s mutation-not-regeneration behavior including the
`outbox_event_builder` callback receiving the fully-updated,
post-mutation graph; `TaskGraphNotFoundError` for both `append_nodes` and
`set_approved_at` against an unknown `task_graph_id`; `set_approved_at`
persistence; outbox `list_dispatch_ready`/`mark_dispatched` round trip;
and the TDD's own §12/§13-acceptance-criterion-4 restart-survival test
("simulated via a fresh repository instance against the same real
Postgres," the TDD's own exact wording) — a second, independently
constructed `PostgresPlanningRepository` reads back what the first wrote.

**Not executed in the environment this PR was authored in** — no
reachable Docker daemon there (`docker version` fails to connect to the
daemon socket); collected cleanly (`pytest -m real_infra --collect-only`,
10/77 collected, 0 errors) and reviewed line-by-line against
`action-engine`'s own already-CI-verified equivalent, but real execution
rests on `real-infra-checks.yml`'s separate GitHub Actions workflow (which
has a real Docker daemon) — see §10 for that workflow's result once this
PR is opened.

**Totals:** 67 tests passing locally (10 real-infra tests correctly
deselected by the package's own `test` script), domain-layer coverage
98.68% (required: 85%).

---

## 7. Cross-reference: Phase 3E reconciliation note

The Phase 3E research document's own reasoning for why no
`reasoning_process_id`-to-`task_graph_id` linkage should be invented
(§2 above) predates this PR and is unaffected by it. A dated reconciliation
note was added to `docs/design/phase-3/14-3e-agent-os-research.md`
disclosing that the persistence prerequisite this precursor closes was
discovered during Phase 3E's own pre-implementation research pass and is
now resolved under Phase 3B, without rewriting any of Phase 3E's six
already-approved architectural decisions.

---

## 8. Verification classification (5 categories, not collapsed)

| Claim | Evidence | Category |
|---|---|---|
| Domain/contract logic correct | 4 new `decompose_node` unit tests + 3 new contract round-trip tests, all passing | Fully verified |
| Repository translation/mutation logic correct against real schema | 10 new real-Postgres tests; written and reviewed in an environment with no Docker daemon, then genuinely executed via CI (§10): "10 passed" against a real `postgres:16-alpine` container — one real defect caught and fixed in this process (§3a) | Fully verified (real-infra, §10) |
| `planning.decompose.request` RPC serve/reply wiring correct | 3 new integration tests against a real `create_app()` + real in-memory `EventBus`, fake repository/model port | Local integration verified |
| `GET`/`POST /v1/plans` API correct | 4 new integration tests against a real `TestClient` | Local integration verified |
| `reasoning.process.completed` → persisted `TaskGraph` + enqueued outbox row | 4 modified integration tests, fake repository | Local integration verified |
| Outbox worker (`workers/outbox_worker.py`) actually dispatches to a real NATS/Postgres pair | Not exercised — no engine's own worker test suite exercises this beyond unit-level `run_outbox_dispatch` composition (same gap disclosed for every other engine's own outbox worker) | Genuinely unverified (explicitly, not silently assumed) |
| `reasoning.process.completed`/`planning.decompose.request` over real NATS JetStream (redelivery, consumer groups) | Not exercised — same disclosed gap as the decomposition-orchestration PR's own §9; no engine in this codebase uses the `nats_event_bus` fixture for a subject-subscription proof yet | Genuinely unverified (explicitly, not silently assumed) |
| Docker image builds successfully, zero critical/high CVEs | `docker-compose config` validates; not built locally (no Docker daemon), but CI's `build-and-scan (planning-engine)` (§10) built the image and Trivy reported zero critical/high findings | Fully verified (real CI, §10) |
| ruff/mypy/import-linter/TS-codegen zero-drift | All re-run after every change in this PR, all clean | Fully verified |

---

## 9. Full verification suite (local)

- `pnpm exec turbo run lint` — 22/22 tasks successful (ruff + mypy across
  the whole workspace, `mypy src` scope per every engine's own `lint`
  script).
- `pnpm exec turbo run test` — 22/22 tasks successful; `planning-engine`:
  67 passed, 10 deselected (`real_infra`), domain coverage 98.68%.
- `uv run lint-imports` — 6/6 contracts kept, 0 broken.
- TypeScript codegen — re-run after the contract additions; exact 3-file
  drift expected and confirmed (`PlanningTaskGraphCreatedPayload.ts`,
  `PlanningDecomposeRequestPayload.ts`, `PlanningDecomposeReplyPayload.ts`),
  87 total generated files (was 84).
- `docker compose -f infra/docker/docker-compose.local.yml config
  --quiet` — valid, exit 0.
- `docker version` — daemon unreachable in this environment (disclosed,
  not silently skipped); image build and container-level verification
  deferred to `build-and-scan.yml`'s CI run (§10).

---

## 10. GitHub Actions (confirmed after push, PR #18, head `ac364b9`)

24/24 checks green, confirmed via `pull_request_read(method="get_check_runs")`,
not assumed, at head commit `ac364b998e130c944c355e52608b57849407c785`:

- `checks` (`pr-checks.yml`) — `success`.
- `dependency-audit` — `success`.
- `build-and-scan` — all 13 matrix entries `success`, including
  **`build-and-scan (planning-engine)`** for the first time ever (this
  engine had no matrix entry before this PR). Trivy's own scan table
  (`severity: CRITICAL,HIGH`, `exit-code: 1`) reports every layer/package
  row `0` ("Clean, no security findings detected") — zero critical/high
  CVEs in the built image, consistent with every other engine's image on
  this same base after TRIVY-2's fix plus this Dockerfile's own new
  `apt-get upgrade -y` line (§5).
- `real-infra` — all 10 matrix entries `success`, including
  **`real-infra (planning-engine, services/planning-engine)`** for the
  first time ever: **"10 passed, 67 deselected"** against a real
  `postgres:16-alpine` container via `testcontainers` — every one of the
  10 tests in §6/§8's real-Postgres suite genuinely executed and passed,
  not merely written. (First push, commit `3c71e77`, failed one of these
  10 with a real defect; see §3a. The re-push, commit `ac364b9`, is the
  result cited here.)

`mergeable_state` is `clean`.

---

## 11. Acceptance criteria (TDD 3B §13)

| # | Criterion | Status |
|---|---|---|
| 1 | A scripted `reasoning.process.completed` at/above the decomposition-confidence threshold produces a structurally valid `TaskGraph` | **Met** — shipped in the decomposition-orchestration PR, unaffected by this PR; re-verified passing (`test_events_reasoning_completed.py`, now also asserting persistence) |
| 2 | A second decomposition call against an existing `TaskGraph` mutates it in place, confirmed by primary-key stability | **Met** — `test_append_nodes_mutates_in_place_and_recomputes_critical_path` (real-infra) and `test_decompose_request_round_trips_a_genuine_breakdown` (integration) both assert the original node's `id` and the graph's `id` are unchanged after mutation |
| 3 | `planning.decompose.request` served correctly, including the "already minimal" non-decomposable case | **Met** — `test_events_decompose_request.py`, 3 tests covering genuine breakdown, already-minimal, and unknown-`task_node_id` |
| 4 | `TaskGraph`/`TaskNode` state survives a real-Postgres restart simulation unchanged | **Met, confirmed via real CI (§10)** — `test_a_fresh_repository_instance_reads_back_a_graph_written_earlier` passed against a real `postgres:16-alpine` container, matching the TDD's own "simulated via a fresh repository instance against the same real Postgres" wording exactly |
| 5 | `POST /v1/plans/{id}/approve` round-trips through a real FastAPI app and correctly sets `approved_at` | **Met** — `test_plans_api.py::test_approve_plan_records_an_approval_decision` |

All five of TDD 3B §13's acceptance criteria are met by this PR's own scope; criterion 4's real-Postgres execution is confirmed pending CI, not silently assumed.

## 12. Known limitations (of this PR's scope, not defects)

- No persistent idempotency guard on `PlanningRepository.insert`/
  `append_nodes` — a duplicate `reasoning.process.completed` or
  `planning.decompose.request` delivery produces a second, independent
  write. TDD 3B §4/§5/§6.2 do not specify a duplicate-detection
  requirement for this scope (unlike `action-engine`'s natural-key
  idempotency guard, built against an explicit TDD 3D requirement) — not
  silently dropped, simply not part of what this PR was authorized to
  build. A future PR closing this gap would need an explicit natural-key
  or dedup-token design, which is itself a small architectural decision
  this PR does not make.
- `MemoryPort`/`KnowledgePort` consultation during decomposition remains
  unimplemented — unchanged from the decomposition-orchestration PR's own
  disclosed scope; this PR touches persistence/API/event-contracts only,
  not the decomposition domain logic itself (beyond `decompose_node`,
  which reuses `decompose()`'s pipeline unchanged).
- The outbox worker's cron schedule (`arq`, every 10 seconds) is the same
  fixed interval `memory-engine` uses — not tuned or load-tested for
  `planning-engine`'s own traffic shape, mirroring every other engine's
  own unvalidated default.
- No `api-gateway` fronts `/v1/plans` — the same disclosed stopgap every
  other engine's own directly-exposed API endpoint carries (TDD 3D §2
  precedent), not new to this PR.

## 13. Remaining Phase 3 dependencies

- TDD 3B is now fully closed except §6.1's `agent_os.task.completed`
  subscription, correctly deferred to Phase 3E (its only real publisher,
  `agent-os/kernel`, does not exist yet).
- TDD 3E's own `planning.goals.current.request`/`.reply` RPC (approved
  2026-08-19, TDD 3B §6.2's own additive note) and the `GoalsPort`
  real-RPC migration remain unimplemented — explicitly out of this
  precursor's scope per the user's own instruction, authorized only once
  Phase 3E's own implementation PR is separately approved.
- TDD 3C/3D remain unaffected — neither has any technical dependency on
  `planning-engine`'s persistence layer.
