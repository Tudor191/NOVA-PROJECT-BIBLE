# STEP 3 — nova-service-kit Extraction: Architecture Review & Gate Review

**Status:** Complete. Extractions A (health router), B (engine/session factory),
C (transactional outbox loop, including the memory-engine prerequisite), and D
(`bind_event_bus`) are implemented and verified. Extraction E (shared
`nova_contracts` reference types) was explicitly **not** started, per direct
instruction — it remains a separately-gated future step.

**Scope:** STEP 3 of the Project Health Review's approved 5-step plan
([project-health-review-2026-08.md](project-health-review-2026-08.md)),
implementing the approved proposal
(`docs/design/nova-service-kit/boilerplate-extraction-proposal.md`) in its
recommended risk-tiered order: D → B → A → C (7 conforming engines) → C
(memory-engine prerequisite) → C (memory-engine cutover).

---

## 1. Architecture Review

### 1.1 What was built

A new shared package, **`nova-service-kit`**, holding exactly the three
modules the approved proposal scoped it to — nothing more:

- **`health.py`** — `make_health_router()`, a zero-parameter factory
  reproducing the 27-line `/internal/health`/`/internal/readiness` router
  byte-identical across 9 engines. `nova-core`'s own `api/health.py` is
  **untouched** — it reads real boot-sequence state
  (`request.app.state.host`), a genuine semantic difference kept explicit as
  its own file rather than hidden behind an override-parameter mechanism on
  the shared factory (a deliberate, mid-implementation revision to the
  original proposal's design — see §1.3).
- **`db.py`** — `create_engine()`/`create_session_factory()`, byte-identical
  (below the docstring) across the 9 engines with a Postgres schema.
- **`outbox.py`** — `dispatch_ready_events()`, the transactional-outbox
  dispatch loop, parameterized entirely over structural `Protocol`s
  (`OutboxRow`, `OutboxRepository`, `OutboxMetrics`) so this module never
  imports any engine's own repository, row, or metrics type. Deliberately
  excludes `apply_pending_graph_writes` (the two-phase saga step
  `knowledge-engine`/`world-model-engine` each have) — genuinely
  engine-specific, stays in each engine's own file.

A fourth extraction, **`bind_event_bus()`**, was added to the *existing*
`nova_eventbus_sdk` package rather than `nova-service-kit` — it already owned
`BoundEventBus`/`get_event_bus`, so a one-line convenience wrapper is normal
package growth, not a new architectural surface, exactly as the proposal
specified.

**ADR-034** (`docs/architecture/adr/
ADR-034-shared-infrastructure-packages-carry-zero-engine-specific-knowledge.md`)
formalizes the general rule this package is built to, generalizing ADR-033's
existing `nova-testkit` boundary mechanism to production-dependency shared
packages. A new import-linter contract enforces it structurally.

### 1.2 Architectural rules preserved — verified, not assumed

| Rule | Verification |
|---|---|
| Zero engine-to-engine imports | `lint-imports`: 6/6 contracts kept throughout every checkpoint, including the "Engines are independent (ADR-004)" contract, unchanged |
| `nova-service-kit` carries zero engine-specific knowledge | New ADR-034 contract, `lint-imports` confirms `nova_service_kit` cannot import any engine's top-level package; `outbox.py`'s `Protocol`-based design was specifically chosen so this holds even for the outbox loop, which needs an engine's repository/metrics shape without ever naming an engine's concrete types |
| Domain-layer purity | `MemoryRepository`'s two new methods and `OutboxRow` live in `domain/ports.py`/`domain/models.py` conventions already established; no `api`/`repository`-layer import entered any engine's `domain/` |
| ADR-020 provider boundary | Untouched — no extraction in this wave touches `ai-model-orchestration-engine`'s connector layer or any other engine's model-provider access |
| Transactional-outbox consistency | The shared loop reproduces the exact commit-per-row semantics (publish → mark-dispatched → next row) every engine already had; memory-engine's cutover from raw `session_factory` SQL to the repository-port pattern was scoped as its own reviewable prerequisite, not silently folded in |
| Engine independence | Every engine still owns its own `domain/`, `api/`, `repository/`, `events/` layout; `nova-service-kit` is a leaf dependency, never a coordination point between engines |
| `nova-testkit` stays engine-agnostic | Untouched in this entire pass — no file in `packages/nova-testkit/` was modified |
| No hidden cross-engine dependency | Every extraction was checked against this explicitly: `outbox.py`'s Protocols (not concrete types), `bind_event_bus`'s explicit-parameter (not implicit-lookup) design, `nova-core`'s health.py staying separate rather than parameterized |

### 1.3 A design fork surfaced and resolved mid-implementation

The original proposal specified `nova-core` calling `make_health_router()`
with override-callback parameters (`health_status`, `readiness_check`,
`extra_health_fields`). Implementing that literally would have meant a
generic-configuration mechanism inside the shared factory serving exactly one
engine's genuine semantic difference — in tension with this pass's explicit
instruction to keep genuine differences explicit rather than hidden behind
configuration. This was surfaced to the user directly (not decided silently);
the resolution: `make_health_router()` takes **zero parameters**, and
`nova-core`'s `api/health.py` is left completely untouched. This captures
100% of the real reuse value (9 identical engines share one factory) without
inventing a single-consumer parameterization surface. See
`docs/design/nova-service-kit/boilerplate-extraction-proposal.md` for the
original design; this review documents the resolved, as-built one.

### 1.4 Two corrections found during implementation, disclosed here

Verification-first implementation surfaced two small factual corrections to
the approved proposal's own numbers — neither changes any architectural
decision, both are recorded for the record:

1. **`nova-core` was miscounted as excluded from Extraction D.** The proposal
   stated nova-core has no `PUBLISHABLE_SUBJECTS`/`SUBSCRIBABLE_SUBJECTS`
   module; direct inspection found it does (three real publishable subjects,
   an intentionally-empty-for-now subscribable set) and does construct a
   `BoundEventBus` in its own `main.py`. It was included in Extraction D's
   cutover (19th call site: 9 engines × 2 sites (`main.py` +
   `workers/__init__.py`) = 18, plus nova-core's `main.py`-only site = the
   proposal's "18 call sites" total was numerically right, just composed as
   10 `main.py` + 8 `workers/__init__.py` rather than "9 + 9, nova-core
   excluded").
2. **The `dispatch_ready_events` "5-6 engines" count was 5, not 6.** Fixed in
   the proposal document itself as part of this pass's verification (§2.3
   miscounted "6 engines" against 5 actually named).

### 1.5 A real bug caught by the "prove behavioral equivalence" requirement

During Extraction A's mechanical cutover, a scripted edit merged
`make_health_router`'s import into a *conditionally-executed* lazy-import
block (inside `if repository is None:`) in all 9 engines' `main.py`. Since
several engines' fake-backed integration tests construct `create_app(...,
repository=FakeRepository())` — skipping that conditional branch entirely —
this would have raised `NameError: name 'make_health_router' is not defined`
the moment those tests ran, not silently passed. It was caught, fixed (moved
to a proper top-level import), and **the fix was confirmed by the same tests
that would have caught the bug** (`test_api_reason.py`,
`test_events_reason_request.py`, and equivalents across engines, all
constructing `create_app(repository=...)` and all passing after the fix) —
not merely inferred from re-reading the code. This is the kind of failure
class "prove behavioral equivalence" was meant to catch, and it worked.

### 1.6 A second real bug: mypy Protocol-attribute invariance

`nova_service_kit.outbox`'s `OutboxRepository`/`OutboxMetrics` Protocols
initially declared plain data attributes (`payload: Mapping[str, Any]`,
`outbox_dispatched_total: _Counter`). mypy requires **invariant** matching
for plain Protocol attributes (both read and write compatibility), and every
engine's concrete `payload: dict[str, Any]` and `outbox_dispatched_total:
Counter` (OpenTelemetry) failed that invariant check even though both are
structurally read-only in practice. Fixed by declaring the relevant Protocol
members as read-only `@property` methods, which mypy checks covariantly —
the textbook-correct pattern for this exact situation. Caught by running
`mypy` per-package (not just ruff), confirming the value of running the full
verification suite rather than a subset.

---

## 2. What changed — exact files

**65 files touched**: 18 deleted, 44 modified, 3 new (`packages/nova-service-kit/`
as a 13-file new package, plus `docs/architecture/adr/ADR-034-...md`).

### Deleted (18)
9× `api/health.py` (all engines except `nova-core`) + 9× `repository/db.py`
(all engines with a Postgres schema).

### New (3 top-level additions)
- `packages/nova-service-kit/` — `pyproject.toml`, `package.json`, `README.md`,
  `src/nova_service_kit/{__init__,health,db,outbox}.py`, `src/nova_service_kit/py.typed`,
  `tests/{test_health,test_db,test_outbox}.py` (13 files)
- `docs/architecture/adr/ADR-034-shared-infrastructure-packages-carry-zero-engine-specific-knowledge.md`
- (the proposal document itself, `docs/design/nova-service-kit/boilerplate-extraction-proposal.md`,
  was created in the prior, already-committed STEP 3 proposal step, not this one)

### Modified (44)
- `pyproject.toml` (root) — `nova_service_kit` added to `root_packages` + new
  ADR-034 import-linter contract
- `packages/nova-eventbus-sdk/src/nova_eventbus_sdk/{__init__,boundary}.py` +
  `tests/test_boundary.py` — `bind_event_bus()` added and tested
- 9× engine `pyproject.toml` — `nova-service-kit` added under `[project]
  dependencies` (a production dependency, per ADR-034 §4 — the deliberate,
  correct difference from `nova-testkit`'s dev-only status)
- 10× engine `main.py` (9 cut over to `make_health_router()`/`bind_event_bus()`;
  `nova-core`'s `main.py` picks up only the `bind_event_bus()` change)
- 8× `workers/__init__.py` — `bind_event_bus()` cutover
- 7× `repository/outbox_dispatcher.py` (the conforming engines) — reduced to
  thin wrappers around `nova_service_kit.dispatch_ready_events`
- `memory-engine`'s `domain/ports.py` (new `OutboxRow` model + two new
  `MemoryRepository` Protocol methods), `repository/postgres_memory_repository.py`
  (implementations), `repository/outbox_dispatcher.py` (rewritten as a thin
  wrapper, function renamed `dispatch_pending` → `dispatch_ready_events`),
  `workers/outbox_worker.py` (repository-based signature), `workers/__init__.py`
  (`bind_event_bus`/`nova_service_kit.db` cutover), `tests/fakes/memory_repository.py`
  (two new no-op methods matching every other engine's fake)
- `tools/scaffold-engine.py` — `_CONTRACT_MODULES_KEY` extended with the new
  ADR-034 contract entry, so future scaffolded engines are wired into it
  automatically
- `uv.lock` — regenerated by `uv sync` for the new package/dependency edges

## 3. Production SLOC — before/after

Measured via `scc` (consistent with the STEP 2 checkpoint's own methodology),
same `src/` + Alembic `versions/` scope, now including `packages/nova-service-kit/src/`:

| | Before (STEP 2 checkpoint) | After (this wave) | Δ |
|---|---|---|---|
| **Production SLOC** | 32,262 | **32,017** | **−245** |
| Total SLOC (all languages/purposes) | 80,768 | **81,923** | +1,155 |

**Reconciling the two directions**: Production code shrank (duplication
genuinely removed) while Total SLOC grew — the difference is
`nova-service-kit`'s own new test suite (`tests/`, not counted in "Production"
by this metric's own `src/`-only definition), `ADR-034`, the package's
`README.md`, and `pyproject.toml`/`package.json` boilerplate for the new
package plus 9 dependency-declaration lines. Both figures are real; they
measure different things, exactly as the STEP 2 report already established
for this project's own metrics conventions.

**Against the proposal's own estimate** (~490-530 net reduction for A+B+C+D):
the actual net reduction (245) is smaller. Verified root cause: the
proposal's canonical-implementation line estimates (e.g. "~30 lines" for the
outbox loop) undercounted the `Protocol`-based decoupling this codebase's own
ADR-034 rule required — `nova_service_kit/outbox.py` is 111 lines specifically
*because* it needs three separate structural Protocols (`OutboxRow`,
`OutboxRepository`, `OutboxMetrics`) to avoid importing any engine's concrete
types, each with a documented rationale for its read-only `@property`
declarations (§1.6). This is a real, disclosed, and architecturally
justified cost — not an error — but it does mean the SLOC savings are more
modest than originally projected. The **duplication genuinely removed**
remains real regardless: 18 files deleted outright (health.py + db.py); the
outbox pattern's per-engine footprint shrank from 512 combined lines (8
engines' full implementations) to 365 (thin wrappers) plus one 111-line
canonical implementation instead of eight variously-duplicated ones.

**50,000 SLOC milestone**: 32,017 / 50,000 ≈ **64.0%** (17,983 lines remaining;
unchanged in direction from STEP 2's 64.5%, since this wave was a net
reduction, not growth).

## 4. Test results

**Full workspace** (`pnpm turbo run test --force`, all 18 packages including
the new `nova-service-kit`): **18/18 tasks successful, 0 failures.**

| Package | Result | vs. STEP 2 baseline |
|---|---|---|
| nova-eventbus-sdk | 24 passed | +1 (`bind_event_bus` test) |
| nova-observability | 7 passed | unchanged |
| nova-contracts | 76 passed | unchanged (untouched this wave) |
| **nova-service-kit** | **9 passed** | new package |
| nova-core | 13 passed | unchanged |
| nova-vectorstore-sdk | 19 passed | unchanged |
| nova-graphstore-sdk | 24 passed | unchanged |
| nova-embeddings-sdk | 11 passed | unchanged |
| nova-testkit | 11 passed, 11 deselected | unchanged |
| ai-model-orchestration-engine | 172 passed | unchanged |
| communication-engine | 70 passed, 6 deselected | unchanged |
| executive-cognition-engine | 66 passed | unchanged |
| knowledge-engine | 67 passed | unchanged |
| memory-engine | 123 passed | unchanged |
| perception-engine | 89 passed, 7 deselected | unchanged |
| personality-engine | 54 passed, 5 deselected | unchanged |
| reasoning-engine | 71 passed | unchanged |
| world-model-engine | 64 passed | unchanged |
| **Total** | **970 passed**, 29 deselected (real_infra) | **+10** (960→970) |

Every engine's test *count* is byte-for-byte identical to the STEP 2
baseline except the two packages that gained new tests (`nova-eventbus-sdk`,
`nova-service-kit`) — direct evidence of behavioral equivalence, not just
"nothing crashed." The 29 deselected `real_infra` tests are unchanged in
count and were confirmed to still **collect** (import chain resolves) for
the three priority engines plus `nova-testkit`, though they remain
unexecuted in this sandboxed environment for the same Docker-access reason
established at the STEP 2 verification checkpoint — unrelated to this wave's
changes and not reproduced or worsened by them.

## 5. Coverage

The 85% `domain/`-scoped coverage gate was re-confirmed as **genuinely
enforcing**, not merely reporting, via the same negative-control method used
at the STEP 2 checkpoint: running `memory-engine`'s suite with
`--cov-fail-under=100` (unreachable) produced exit code 1
(`FAIL Required test coverage of 100% not reached. Total coverage: 95.96%`).
`memory-engine`'s own domain coverage moved from 540→547 statements (97%→97%,
same 16 absolute misses) — the +7 statements are the new `OutboxRow` model
added to `domain/ports.py` (in-scope for the gate since it lives in
`domain/`), fully exercised by the existing test suite. No other engine's
`domain/` coverage changed (no other engine's `domain/` layer was touched by
this wave).

## 6. Import-linter results

**6/6 contracts kept, 0 broken**, at every checkpoint throughout this wave
(re-run after each of the 4 extractions, not just at the end):

1. Engines are independent (ADR-004) — KEPT
2. No engine imports a message broker client directly (ADR-006) — KEPT
3. No engine imports a graph database client directly (ADR-007) — KEPT
4. No engine imports an LLM/AI provider SDK directly (ADR-020) — KEPT
5. nova-testkit has no engine-specific knowledge (ADR-033) — KEPT
6. **nova-service-kit has no engine-specific knowledge (ADR-034)** — KEPT (new)

## 7. Duplication removed

| Pattern | Before | After | Files affected |
|---|---|---|---|
| `api/health.py` | 9 byte-identical 27-line copies (243 lines) | 0 (deleted) + 1 canonical 36-line factory | 9 engines |
| `repository/db.py` | 9 byte-identical-below-docstring 19-line copies (171 lines) | 0 (deleted) + 1 canonical 23-line module | 9 engines |
| `repository/outbox_dispatcher.py` full loop | 512 combined lines across 8 engines (5×53 + 2×[87,82] + 1×78) | 365 combined lines (8 thin wrappers, 34-75 lines each) + 1 canonical 111-line module | 8 engines |
| `BoundEventBus(...)` construction | 18 call sites, ~6 lines each | 18 call sites, ~5 lines each + 1 canonical ~19-line helper | 9 engines (18 sites: 10 `main.py` + 8 `workers/__init__.py`) |
| Naming drift (`dispatch_pending` vs. `dispatch_ready_events`) | 1 engine (memory-engine) diverged | 0 — resolved as a byproduct of the cutover | memory-engine |
| Repository-port bypass (raw SQL instead of `list_dispatch_ready`/`mark_dispatched`) | 1 engine (memory-engine) | 0 — now conforms to the same port shape as every other engine | memory-engine |

## 8. New technical debt

None introduced by this wave that wasn't already disclosed in the approved
proposal's own risk register. Specifically re-checked:

- **No new "generic shared package" risk**: `nova-service-kit`'s scope is
  exactly the 3 modules proposed, nothing added speculatively; ADR-034 and
  its import-linter contract are now the standing guard against future scope
  creep, mirroring ADR-033's proven mechanism for `nova-testkit`.
- **`nova-core`'s health.py divergence remains genuinely undocumented as a
  parameterization risk** — because it was deliberately never turned into
  one (§1.3). This is the intended outcome, not debt.
- **The proposal's own deferred items remain deferred, untouched**:
  Extraction E (`nova_contracts` reference types), `ConfidenceTier`
  unification, the weighted-composite-scorer pattern, `workers/__init__.py`'s
  full-file extraction, and every narrow ID+summary cross-engine value
  object. None were touched in this pass.
- **17-cicd-pipeline.md's Turborepo affected-graph inconsistency** — flagged
  out of scope at the STEP 2 checkpoint, remains untouched here too.

## 9. Architectural risks

No high-severity risks identified, consistent with the proposal's own
risk register (`docs/design/nova-service-kit/boilerplate-extraction-proposal.md`
§10). Two items worth carrying forward, both already anticipated:

1. **`nova-service-kit`'s scope discipline is enforced structurally now
   (ADR-034 + import-linter contract), not just by convention** — the
   mechanism that failed silently for `16-testing-strategy.md`'s claims in
   the original Project Health Review cannot repeat here for this specific
   boundary, because a contract violation would fail CI, not merely go
   unnoticed in prose.
2. **`Protocol`-based structural typing (outbox.py) is a real technique
   this codebase hadn't used before this wave** — future contributors
   extending `nova_service_kit.outbox` should understand the read-only
   `@property` pattern (§1.6) before adding new Protocol members, or they
   will hit the same mypy invariance error this wave already diagnosed and
   documented.

## 10. Engine-boundary confirmation

Confirmed intact via direct, repeated verification (not assumed):

- **Zero engine-to-engine imports** — `lint-imports`'s independence contract
  kept at every checkpoint.
- **Zero new cross-engine coupling** — every extraction's design was
  evaluated against this explicitly (Protocol-based `outbox.py`, parameter-based
  `bind_event_bus`, untouched `nova-core` health.py).
- **`nova-service-kit` itself cannot become a coupling point** — structurally
  enforced (ADR-034 contract), not merely documented.
- **Every engine's own `domain/`, `api/`, `repository/`, `events/`, `workers/`
  boundary and ownership is unchanged** — this wave only replaced *what*
  populates certain files (health router construction, engine/session-factory
  construction, outbox dispatch loop, event-bus binding), never *which*
  engine owns what, and never introduced a new inter-engine data path.

---

## 11. Gate Review

### 11.1 Deliverables checklist

- [x] `nova-service-kit` package created, scoped exactly per the approved proposal
- [x] Extraction A (`make_health_router`) — implemented with a resolved design fork (§1.3), verified
- [x] Extraction B (`create_engine_and_session_factory`) — implemented, verified
- [x] Extraction C (`dispatch_ready_events`, 7 conforming engines) — implemented, verified
- [x] Extraction C prerequisite (memory-engine repository port methods) — implemented, verified, reviewed as its own change
- [x] Extraction C cutover (memory-engine dispatcher) — implemented, verified, naming drift resolved as a byproduct
- [x] Extraction D (`bind_event_bus`) — implemented in the correct existing package, verified
- [x] ADR-034 written, import-linter contract added, `tools/scaffold-engine.py` updated for future engines
- [x] Extraction E — **not started**, remains separately gated per direct instruction
- [x] Full verification suite: ruff, mypy (all 18 packages), full test suite (970 passed, 0 failed), import-linter (6/6), docker-compose config, coverage gate re-confirmed, diff inspection
- [x] This document

### 11.2 Gate criteria

| Criterion | Status |
|---|---|
| All existing tests pass unmodified in behavior (only counts changed where new tests were added) | ✅ Confirmed — see §4 |
| No engine boundary violated | ✅ Confirmed — see §10 |
| No new architectural risk beyond what was disclosed and approved | ✅ Confirmed — see §9 |
| Coverage gate still functions | ✅ Confirmed via negative control — see §5 |
| Import-linter contracts intact, one new contract added correctly | ✅ Confirmed — see §6 |
| Two real bugs introduced during implementation were caught before being reported as done | ✅ See §1.5, §1.6 |
| One genuine design fork was surfaced to the user rather than resolved silently | ✅ See §1.3 |
| No unrelated technical debt or documentation touched | ✅ Confirmed — `17-cicd-pipeline.md`, Extraction E, and every other explicitly-deferred item remain untouched |
| Docker/real-infra verification status | Unchanged from STEP 2 — still blocked in this sandboxed environment; not worsened or re-attempted by this wave, and not this wave's scope |

### 11.3 Recommendation

**Gate passed.** The A+B+C+D extraction wave is complete, verified against
its own approved proposal, and ready for the user's review. Two disclosed,
justified deviations from the written proposal exist (§1.3's resolved design
fork, §1.4's two small factual corrections) — both were surfaced or corrected
transparently, not silently absorbed.

**Recommended next steps**, in the order the user's own instructions imply:
1. Review this report.
2. Decide whether to approve Extraction E (`nova_contracts` reference types
   for `MemoryReference`/`WorldModelSnapshot`/`PersonalContext`) as its own,
   separately-gated step — not started, not assumed.
3. Decide whether to resume Phase 2D-C — also not started, per explicit
   instruction to stop after this wave.

Neither Extraction E nor Phase 2D-C begins without further explicit approval.
