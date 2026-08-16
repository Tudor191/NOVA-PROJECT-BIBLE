# Phase 3B — `planning-engine` Domain Foundation: Gate Review

**Status: complete, fully verified (domain-only). Covers exactly one
PR-sized unit** (`phase-3b-planning-domain`, branched from `phase-3`) of
Phase 3B's multi-PR implementation — not the whole of Phase 3B. No event
subscription, persistence, API, or decomposition logic exists yet; those
are later, separately scoped and separately reviewed PRs.

**Post-initial-review update (commit `41122e2`):** an independent review
pass (requested separately from the original implementation) found and
fixed a real defect — duplicate `TaskNode.id` handling — and corrected an
inaccurate coverage claim in this document's original version. See §3a
and §6 below for the full evidence trail. Both issues are now resolved;
this status reflects the corrected, post-fix state.

---

## 0. Scope executed

`services/planning-engine`'s domain layer: `TaskNode`, `TaskGraph`,
`Estimate` (`domain/models.py`), graph invariants and critical-path
computation (`domain/task_graph.py`), plus `RiskLevel` in
`nova_contracts.events.planning` (a new module). The engine was scaffolded
via `tools/scaffold-engine.py` (standard skeleton: `main.py`, `api/health.py`,
`events/subscribed.py`/`published.py`, `repository/__init__.py`, `models/__init__.py`
— all left as generated, inert stubs, not implemented in this PR).

## 1. Deviation from TDD 3B, disclosed

TDD 3B §11 originally proposed defining `TaskNode`, `TaskGraph`, `Estimate`,
and `RiskLevel` together, directly in `nova_contracts.events.planning`.
This PR implements a split instead:

- **`TaskNode`/`TaskGraph`/`Estimate` stay domain-local**
  (`nova_planning_engine.domain.models`), never imported from
  `nova_contracts`.
- **`RiskLevel` alone is defined in `nova_contracts.events.planning`.**

**Evidence for the split:**

1. Every existing engine keeps its own domain model distinct from any wire
   payload it publishes — confirmed directly against `reasoning-engine`
   (`ReasoningProcess`/`Decision`/`Alternative` are `domain/models.py`-local;
   `nova_contracts.events.reasoning` defines separate, narrower wire
   payloads for the same concepts) and `executive-cognition-engine` (same
   shape). `TaskNode`/`TaskGraph`/`Estimate` following the identical
   convention is not a new pattern, it's the established one — TDD 3B §11's
   original proposal would have been the first engine to break it.
2. **No other Phase 3 TDD references `TaskNode`, `TaskGraph`, or `Estimate`
   by name** — confirmed by direct grep of `docs/design/phase-3/06-tdd-3c-capability-engine.md`
   and `07-tdd-3d-action-engine.md`, zero hits for either. Nothing outside
   `planning-engine` needs them as a shared, importable type today, so
   nothing forces them into `nova_contracts`.
3. **`RiskLevel` is the one confirmed exception.** TDD 3D reuses it
   directly: `07-tdd-3d-action-engine.md:81` — `ActionObject.risk: RiskLevel # reused from TDD 3B, Bible Part 14`
   — plus its own `ActionPriority`-vs-`RiskLevel` distinction (§3.3) and an
   ADR-032 policy gate, `minimum_confidence_by_risk: dict[RiskLevel, float]`
   (line 235). Per ADR-004, `action-engine` cannot import
   `nova_planning_engine`'s internals directly (enforced by the import-linter
   "Engines are independent" contract) — the only way TDD 3D's own explicit
   requirement ("must be designed so that Phase 3D action-engine can
   consume it directly without reinterpretation or an incompatible second
   risk model") is satisfiable is for `RiskLevel` to live in the one
   package every engine is already allowed to depend on:
   `nova_contracts` (ADR-034's own exemption: "does not apply to
   `nova_contracts`, which is deliberately the *shared vocabulary* layer
   every engine depends on").
4. **Direct precedent for exactly this shape**: `ReasoningMode`
   (`nova_contracts.events.reasoning`) is a simple `StrEnum` defined once
   in `nova_contracts`, imported both by `reasoning-engine`'s own
   `domain/models.py` (`ReasoningProcess.reasoning_mode: ReasoningMode`)
   and by wire payloads (`ReasoningRequestPayload.reasoning_mode_hint`).
   `RiskLevel` follows the identical shape.

**Which future Phase 3 component depends on this decision:** TDD 3D
(`action-engine`) depends on `RiskLevel` living somewhere it can import —
this decision is what makes that possible without a second, incompatible
risk model. No other Phase 3 TDD is affected. `TaskNode`/`TaskGraph`
themselves remain free to move into `nova_contracts` later, additively, the
moment a real cross-engine consumer needs them directly (e.g. if TDD 3E's
`agent-os` kernel ever needs more than the wire payload) — not a breaking
change to what this PR ships, since nothing outside `planning-engine`
references them yet.

## 2. Fork 3B-1 (`Estimate`/`RiskLevel` shape) — implemented as approved

- `Estimate = {effort_hours: float (> 0), confidence: float (0.0-1.0)}` —
  implemented verbatim as proposed; still the only shape ever proposed for
  this concept anywhere in the project (re-confirmed: no competing shape
  found in a fresh repo-wide search before implementation).
- `RiskLevel` — Bible Part 14's five-tier scale
  (Negligible/Low/Moderate/High/Critical), reused verbatim, in Bible's own
  order.

## 3. Fork 3B-2 (WBS field mapping) — implemented as approved

`TaskNode` carries exactly the four of Bible Part 9's seven WBS fields
doc06 §3 itself maps (`estimated_effort`, `depends_on`,
`assigned_agent_category`, plus `risk`). The remaining three
(`completion_criteria`, `deliverables`, `required_knowledge`,
`required_tools`) are confirmed, via fresh grep of TDD 3C/3D/3E before
implementation, to have **no reference or consumer in any downstream Phase
3 TDD** — classified as Bible-Part-9-only / historical-document fields for
Phase 3, not required-for-Phase-3 or required-for-a-named-later-phase.
Locked in with a regression test
(`test_task_node_omits_the_four_undecided_wbs_fields`), not merely
documented, so a future change re-adding one requires an explicit,
reviewed decision rather than a silent contract drift.

## 3a. Independent review finding: duplicate `TaskNode.id` handling (fixed)

An independent review pass of this PR (requested separately, after the
original implementation) checked graph invariants against an edge case the
original implementation did not consider: what happens if `TaskGraph.nodes`
contains two `TaskNode`s sharing the same `id`. Nothing at the Pydantic
level prevents this — `nodes` is a plain `list[TaskNode]`, not a set or a
dict keyed by `id`.

**The defect:** `find_cycle`, `find_dangling_dependencies`, and
`compute_critical_path` each build `by_id = {node.id: node for node in
nodes}` — a dict comprehension that silently keeps only the *last* node
sharing an `id` and drops the rest. A duplicate `id` would have silently
corrupted every one of these checks (wrong cycle detection, wrong dangling
report, wrong critical path) with no error and no signal to the caller.

**The fix (commit `41122e2`):**
- Added `find_duplicate_ids(nodes) -> list[UUID]`, a pure function
  reporting which `id`s appear more than once.
- Wired it into `compute_critical_path` as the **first** check, ahead of
  cycle and dangling-dependency detection — both of those would themselves
  misreport against a graph with duplicates, since they use the identical
  `by_id` pattern.
- Added docstring caveats to `find_cycle`/`find_dangling_dependencies`
  stating they assume no duplicate `id`s and directing callers to
  `find_duplicate_ids` first.
- Added 3 new tests: duplicate detection with a shared ID, empty-result on
  a well-formed graph, and `compute_critical_path` raising `ValueError`
  (not silently picking a winner) on a duplicate.

This was found and fixed during review, not flagged by a failing test —
no test in the original PR exercised this input at all.

## 3b. Independent review finding: inaccurate coverage claim (corrected)

The original version of this document (§6, before this correction)
reported "100%" domain coverage. That figure was produced by running
`pytest --cov=nova_planning_engine.domain` **without**
`--cov-report=term-missing`, which happened to render a summary table
without visible Branch/BrPart columns — easy to mistake for "no missed
branches" when the columns simply weren't shown.

Root `pyproject.toml`'s `[tool.coverage.run] branch = true` means the
gate-enforced metric (`fail_under = 85`) is genuinely **branch** coverage,
not statement coverage. Re-running the identical command with
`--cov-report=term-missing` (and confirmed again on a second, fresh run)
showed the true original figure was **98.50%**, not 100% —
`task_graph.py` had 2 uncovered partial branches (`54->47`, `61->60`),
both inside `find_cycle`'s DFS `visit()` function.

**Root cause:** every original test graph listed dependencies before their
dependents (already topologically ordered), so `find_cycle`'s DFS never
needed to recurse into a second still-white sibling dependency from
within one `visit()` call, and its top-level loop never encountered a
node a prior root's recursion had already colored black.

**The fix:** added
`test_cycle_and_critical_path_detection_do_not_depend_on_topological_listing_order`,
constructing a graph with a join node listed *before* the two dependencies
it references (`[join, short, long_branch]`) — this exercises exactly the
missing branches. Re-verified after the fix: 35/35 tests passing,
genuinely 100% statement **and** branch coverage (`task_graph.py`: 86
stmts/40 branches, 0 missed — see corrected §6).

## 4. Exact files changed

| File | Change |
|---|---|
| `packages/nova-contracts/src/nova_contracts/events/planning.py` | New — `RiskLevel` only. |
| `packages/nova-contracts/src/nova_contracts/__init__.py` | Export `RiskLevel`. |
| `packages/nova-contracts/tests/test_planning_events.py` | New — 2 tests. |
| `services/planning-engine/` | New engine, scaffolded; `domain/models.py`, `domain/task_graph.py`, and their tests are the only hand-written, non-stub source. |
| `pyproject.toml`, `uv.lock` | Scaffold-tool-driven: `nova_planning_engine` added to `root_packages` and the three per-engine import-linter contracts; new lockfile entry. |

## 5. Tests

35 tests in `services/planning-engine` (`tests/unit/test_models.py`,
`tests/unit/test_task_graph.py`, plus the scaffold's own
`tests/integration/test_health.py`), covering: required/optional field
validation, `Estimate`/`RiskLevel` behavior, the WBS-field-presence and
WBS-field-absence regression tests above, deterministic node-insertion
ordering, JSON round-trip serialization, cross-package `RiskLevel`
consumption (simulating action-engine's own future usage without importing
`nova_planning_engine`), cycle detection (direct, indirect, and
self-referencing cycles), duplicate-node-`id` detection and rejection
(§3a), dangling-dependency detection, critical-path computation (single
node, linear chain, branch-preference by effort, deterministic
tie-breaking, raising instead of hanging on a cycle, raising instead of
silently picking a winner on a duplicate `id`), and detection/computation
correctness when nodes are listed out of topological order (§3b). Plus 2
new contract tests in `nova-contracts` for `RiskLevel`. (Original PR: 30
tests; +5 added during independent review, §3a/§3b.)

## 6. Verification results

| Check | Result | Classification |
|---|---|---|
| ruff + mypy, `planning-engine` | Clean, 13 source files | Fully verified |
| ruff + mypy, `nova-contracts` | Clean, 16 source files | Fully verified |
| `planning-engine` test suite | 35/35 passed (30 original + 5 from independent review, §3a/§3b) | Fully verified |
| `planning-engine` domain coverage | 100% statement **and** branch (`domain/models.py`: 24 stmts/0 branches; `domain/task_graph.py`: 86 stmts/40 branches, 0 missed) vs. 85% branch-coverage gate — corrected from an inaccurate original "100%" claim that was actually 98.50% branch coverage under statement-only reporting; see §3b for the full correction | Fully verified (re-verified with `--cov-report=term-missing` after the fix, not assumed) |
| `nova-contracts` test suite | 86/86 passed (84 prior + 2 new) | Fully verified |
| Full monorepo test suite | 20/20 packages, all green | Fully verified |
| Full monorepo lint | 20/20 packages, all green | Fully verified |
| import-linter | 6/6 contracts kept, `nova_planning_engine` correctly wired and independent | Fully verified |
| `docker-compose config` | Valid, unmodified by this PR (no service block yet — no API/persistence to serve) | Fully verified |
| TypeScript codegen | Correctly unaffected — `RiskLevel` isn't referenced by any registered payload yet, so it does not yet appear in generated TypeScript; will appear automatically once a payload embeds it | Fully verified (confirmed no drift, not merely assumed) |
| Real-infrastructure | **Not applicable.** This PR introduces no persistence, no new Event Bus subject, no cross-process integration — nothing for a real-infra test to exercise. | Genuinely not applicable, not deferred |
| `checks` (pr-checks.yml, ruff/mypy/pytest gate) — GitHub Actions | Passed on PR #2 | Real-infrastructure-verified |
| `build-and-scan.yml` — GitHub Actions | **Fails on this PR — but pre-existing, unrelated to PR #2. See §6a.** | Documented, not fixed in this PR (correctly out of scope) |

**No contract/fake-verified, local-integration-verified, or genuinely
unverified items in this PR's own scope** — everything this PR touches is
either a pure domain function (fully unit-tested) or a scaffold-generated
stub not yet exercised by any real caller.

## 6a. Pre-existing, unrelated CI infrastructure failure (`build-and-scan.yml`)

Investigated as part of this PR's review, per explicit instruction not to
merge without first classifying the visible CI red X. Three
`build-and-scan` matrix jobs show `failure`
(`world-model-engine`, `communication-engine`, `nova-core`); eight more
show `cancelled`.

**Root cause:** `.github/workflows/build-and-scan.yml:84` pins
`uses: aquasecurity/trivy-action@0.24.0` in the `Scan ${{ matrix.service }}
image` step, identically across all 11 matrix entries (`planning-engine`
is correctly not yet in this matrix — deliberately deferred, no container
to scan). That version tag is no longer resolvable by GitHub's
action-resolution service (`Unable to resolve action
'aquasecurity/trivy-action@0.24.0', unable to find version '0.24.0'`) — an
external Marketplace-action issue, failing before checkout or any real
build/scan step runs (~2s job duration).

**Fail-fast:** the `strategy:` block has no `fail-fast: false` override,
so the default `fail-fast: true` cancels the other 8 matrix jobs
automatically the instant the first 3 fail — those cancellations are not
independent failures.

**Confirmed pre-existing, not introduced by this PR or by PR #1:** this
repo's entire `build-and-scan.yml` run history is 3 runs, and all 3 fail
identically — including the very first run ever executed (a push to
`main` at commit `3b6d9a3`, before any Phase 3B PR existed).
`.github/workflows/build-and-scan.yml` is untouched by this PR's diff, and
`communication-engine`/`nova-core`/`world-model-engine` are not part of
the Phase 3B change path.

**Not fixed here, by design:** fixing this requires editing
`.github/workflows/build-and-scan.yml` (re-pinning `trivy-action` to a
resolvable version, and optionally adding `fail-fast: false` for better
diagnosability) — out of scope for a planning-engine domain-foundation PR.
Tracked as a separate, pre-existing infrastructure defect requiring its
own dedicated fix.

## 7. Known limitations (of this PR's scope, not defects)

- `events/subscribed.py`, `events/published.py`, `api/health.py` (beyond
  the scaffold default), and `repository/__init__.py` remain inert stubs —
  by design, deferred to later PRs.
- `TaskGraph.critical_path` is not auto-computed; a caller must call
  `compute_critical_path()` explicitly and assign the result. No
  `@model_validator`-based auto-computation was introduced, since no
  precedent for that pattern exists anywhere in this codebase's domain
  layers today (confirmed via repo-wide search before implementing).
- No mutation/merge logic for updating an existing `TaskGraph` in place
  (Dynamic Replanning, doc06 §3) — deferred to the persistence-layer PR,
  where "mutation, not regeneration" is actually meaningful (against a
  persisted graph, not an in-memory one).

## 8. Remaining Phase 3 dependencies

- `RiskLevel` in `nova_contracts` is now available for TDD 3D
  (`action-engine`) to import directly once that phase begins — no
  incompatible second risk model is possible by construction (there is
  only one `RiskLevel` type in the project).
- `TaskNode`/`TaskGraph`/`Estimate` remain planning-engine-local; TDD 3C
  and 3E have no current need for them as shared types (3C: zero technical
  dependency, confirmed; 3E: consumes the wire payload once it exists, not
  planning-engine's internals, per ADR-004).
