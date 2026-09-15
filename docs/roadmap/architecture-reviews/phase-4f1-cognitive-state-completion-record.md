# Phase 4F.1 — Completion Record
## `cognitive-state-engine`: domain and persistence

**Date:** 2026-09-15
**Branch:** `phase-4f`
**Code head:** `452df79` — the last commit that changes anything outside `docs/`.
**Documentation head:** this record's own commit. Everything above `452df79` is
documentation-only, so CI at `452df79` is the authoritative evidence for the
code; the invariant is checkable — `git diff 452df79..HEAD -- ':!docs'` is empty.
That is the same convention the Phase 4E Gate Review §18 used.
**Base:** `phase-4` at `c04b58e0d6be4f4236b8fe8c5a7dcf79bf7d56f4`
**Protocol:** [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md),
sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`,
1131 lines, read from `origin/main` and verified against the authoritative value.
**TDD:** [`06-tdd-4f-companion-and-cognitive-state.md`](../../design/phase-4/06-tdd-4f-companion-and-cognitive-state.md)
§13, §18.

---

## 0. What this document is, and is not

**This is a slice completion record, not a Gate Review.** Phase 4F is **one
milestone** with eight slices (TDD §18); its Gate Review and Project Health
record are written once, at 4F's own closure, against the whole milestone. This
record exists so 4F.1's evidence is fixed at its own head rather than
reconstructed seven slices later.

**4F.1 is one slice of eight. Phase 4F is NOT complete**, and nothing here should
be read as a phase-level verdict.

---

## 1. Status

**4F.1 is COMPLETE and VERIFIED. Not merged.**

Every item of the ratified 4F.1 scope is implemented, and nothing outside it is:

| Scope item | Status |
|---|---|
| Cognitive-state domain | **Done** — `domain/models.py`, `attention.py`, `focus.py`, `ports.py` |
| `ActiveThought` | **Done** — all seven Part 6 fields, five validators |
| `AttentionLayer` | **Done** — five layers, Part 6's order, transition table |
| `FocusSignal` | **Done** — Part 6's seven, equally weighted and explicitly so |
| Domain validation | **Done** — invalid states unconstructible |
| `cognitive_state` schema | **Done** — new, additive |
| `active_thought` table | **Done** — the only table |
| Repository | **Done** — four methods |
| Migration | **Done** — `0001_initial_schema.py` |
| Focused tests | **Done** — 56 passing |
| Real-infra tests | **Done** — 12, **executed in CI** and green (§4) |
| CI integration | **Done** — one `real-infra-checks` row, one `build-and-scan` row |
| **No runtime wiring yet** | **Correct and deliberate** — §8 |

---

## 2. Commits

| SHA | Role |
|---|---|
| **`99fcec627b02c02efd8674b893273e174d0bd09f`** | **The 4F.1 implementation commit** — one coherent commit, as required |
| `b5aa471cc91cb4c32c5465bafabfd17b36445b65` | **The TDD merge** — `phase-4f-tdd` → `phase-4f`, a normal two-parent merge |
| `452df79` | **The corrective commit** — the one CI failure, fixed in place (§4.1) |

**Why the TDD merge exists.** `phase-4f` was created from `phase-4`'s HEAD
`c04b58e`, where the ratified 4F TDD does not exist and the master scope still
carries the **superseded one-second AC-7**. Implementing against a ratified
design the branch itself contradicted would have been incoherent, and keeping the
TDD and master scope internally consistent is inside 4F.1's scope. Reviewed and
**accepted**; the history is not to be rewritten or repaired.

**Why a second code commit exists.** The ratified git discipline allows one
implementation commit *"unless a second commit is genuinely required for a clean
corrective fix"*. CI found a real defect in this slice's own test file (§4.1);
folding the fix into `99fcec6` would have required rewriting pushed history,
which is forbidden, and leaving it unfixed would have shipped a red tier.

All commits above `c04b58e` remain reachable: `9c2d503` · `abb0f30` · `bcd8bb2` ·
`b5aa471` · `99fcec6` · `452df79` · this record. No rebase, no squash, no force
push.

---

## 3. Test results — at code head `452df79`

| Check | Result |
|---|---|
| `cognitive-state-engine`, default tier | **56 passed, 12 deselected** |
| `cognitive-state-engine`, domain coverage | **100%** — 130 statements, **0 missed**, against the 85% gate |
| `npx turbo run test --force` | **32/32 tasks, `Cached: 0`** — **2,670 passed, 204 deselected, 0 failed** |
| `uv run pytest tools/tests -q` | **286 passed** |
| `npx turbo run lint --force` | **32/32** |
| `npx turbo run typecheck build --force` | **35/35** |
| `uv run lint-imports` | **7 kept, 0 broken** |
| Codegen | **116 generated payload types** (+ `index.ts`), **zero drift** — `git status` clean after `build` |

**One figure in this table was wrong when this record was first written, and is
corrected here: deselected was recorded as `404`.** That was a double count —
`pytest` prints the deselected total twice, once in its collection line
(`collected 68 items / 12 deselected / 56 selected`) and again in its summary
line, and the aggregation counted both. The true figure at `99fcec6` was `202`;
it is `204` here because this slice's corrective commit adds two `real_infra`
cases. **The passed count was never affected** — the collection line does not
carry one — so `2,670` stood and still stands. Recorded rather than quietly
amended, because a test-evidence number in a completion record is exactly the
kind of figure a reader is entitled to assume was not silently edited.

Re-counting everything else in this record against the tooling turned up one
further slip, corrected in §3.1: the contract suite is **eleven** tests, not
twelve (`pytest --collect-only` reports `11 tests collected`). No other figure
in this record changed under re-verification.

### 3.1 The controls this slice adds

Eleven contract tests in `tests/contract/test_boundaries.py` assert TDD §6.2's
checkable prohibitions: publishes nothing, subscribes to nothing, no
`action.execute` in executable code, no cross-engine import (four engines,
parametrized), no HTTP client, no other engine's schema named, and no execution
vocabulary anywhere in the domain. **Every source scan strips docstrings via the
AST first**, so this engine's own prose about `action-engine` cannot trip a
control — Phase 4D's recorded precision failure, avoided by construction. One
anti-vacuity test asserts there is source to scan at all.

---

## 4. Real-infrastructure verification

**Written here, executed in CI — and CI is where they first ran.** Docker is
unreachable in the authoring environment, so no local result was ever offered as
evidence for this tier; that was disclosed rather than papered over, the same
discipline 4D and 4E used. Twelve `real_infra` tests are collected
(`-m real_infra` collects `12/68`) and all twelve now pass on a real Postgres
via the `real-infra-checks.yml` matrix row this slice adds.

What they prove, and why a fake cannot:

1. **A 90-day-old `created_at` survives the round trip** — the Phase 4E defect
   made impossible. The column carries `server_default now()`, so this passes
   only because the repository writes both timestamps explicitly.
2. **Re-upserting does not move `created_at`** — an Active Thought is *ongoing*,
   so its age is meaningful.
3. **All three CHECK constraints are real, each asserted by name** — one case
   per constraint, bypassing the domain model deliberately. A Protocol has no
   constraint to violate.
4. **`JSONB` round-trips** the three relation lists through the driver's
   `UUID` → `str` → `UUID` conversion.
5. **Ordering is deterministic across a genuine timestamp tie.**
6. **The schema holds exactly one table** — no speculative table for a later
   slice.

### 4.1 What the first execution found

**The tier did its job on its first run: one of the ten original tests failed.**
Recording it here rather than only in the commit log, because a delegated-to-CI
claim is only honest if the delegation's result is reported whichever way it
goes.

`test_the_check_constraints_are_real` failed — **not on the constraint, which
behaved correctly, but in the test's own teardown.** The bad `INSERT` raised the
`IntegrityError` the test asserts and `pytest.raises` caught it. Because the
error was caught, the enclosing `session.begin()` block exited *normally*, so
SQLAlchemy issued its commit: `RELEASE SAVEPOINT sa_savepoint_1` against a
transaction Postgres had already aborted. `InFailedSQLTransactionError` surfaced
as the test result.

Every other engine asserting an expected violation omits `session.begin()` for
exactly this reason — `autonomy-engine`, `personality-engine` and `kernel` all
use the bare-session form, and all three passed in the same run. This engine's
test was the only one that wrapped it. Closing the session rolls the savepoint
back instead of releasing it, which is what recovers the connection.

`452df79` corrects it and takes the opportunity the failure exposed: the single
case became **one case per constraint, each asserting the constraint by name**.
A bare `pytest.raises` only proves that *some* constraint fired — the
`priority >= 0` case could have tripped the confidence range and still passed.
Two of the three constraints had no case at all before this. Collection went
`10 → 12`; the default tier, domain coverage and every boundary property are
unchanged.

**Nothing in the engine changed.** The defect was confined to one test function;
the migration, ORM, repository and domain are byte-identical to `99fcec6`.

---

## 5. SLOC

`cloc` v2.06, `--skip-uniqueness --quiet`, from pristine `git archive` extracts.
**Scope includes `companion/`**, per the ratified methodology change (TDD §17) —
the directory does not exist yet, so it contributes zero, but it is **in the
measured scope** so a later slice cannot land there uncounted.

| | Base `c04b58e` | Code head `452df79` | Δ |
|---|---|---|---|
| 4F scope (incl. `companion/`) | **44,706** | **45,107** | **+401** |
| Comparable | 35,733 | 36,134 | +401 |
| Wider | 41,074 | 41,475 | +401 |

**Headroom to the 50,000 hard gate: 4,893.** The gate is **respected and not
threatened**. The engine's own footprint is 401 lines across 18 files; tests are
outside every scope by definition.

**The corrective commit moves none of these**, and that is verified rather than
assumed: `git diff 99fcec6..452df79 -- services/cognitive-state-engine/src
services/cognitive-state-engine/alembic` is **empty**, and the only
non-documentation file it touches is under `tests/`, which every scope excludes.

---

## 6. Migration and schema

`services/cognitive-state-engine/alembic/versions/0001_initial_schema.py` —
`CREATE SCHEMA cognitive_state`, one table `active_thought`, three CHECK
constraints (`confidence` and `current_progress` bounded to `[0,1]`, `priority`
non-negative), two indexes (`user_id, attention_layer` and `user_id,
updated_at` — exactly the two shapes `list_thoughts` issues).

**Additive only. Zero existing tables altered.**
`action.identity_confidence_policy` is untouched in **structure and content** —
CF-9 is a Phase 4F dependency but it is **4F.4's** work in `action-engine`, its
owning engine, and 4F.1 writes no policy row anywhere.

**One table, deliberately.** Focus is derived rather than stored, and an
Attention Layer is a column rather than an entity. A `real_infra` test asserts
the schema contains exactly `["active_thought"]`.

---

## 7. Boundary confirmations — each re-verified at code head `452df79`

| Property | Evidence |
|---|---|
| **`PUBLIC_TOPICS` unchanged** | `git diff c04b58e..452df79 -- services/ws-gateway/` is **0 files** |
| **Event Bus subject count unchanged** | **118** registered at base and at head; zero `cognitive_state.*`; `nova-contracts` diff is **0 lines** |
| **`action-engine` untouched** | **0 files** |
| **`perception-engine` untouched** | **0 files** |
| **`nova-companion` untouched** | **0 files** — `companion/` does not exist |
| **`autonomy-engine`, `ws-gateway`, `apps/` untouched** | **0 files** each |
| **`phase-4` untouched** | `c04b58e0d6be4f4236b8fe8c5a7dcf79bf7d56f4` |
| **`main` untouched** | `7e273e62e942ecd5528ca807e65933d6bb675669` |
| **No fake clock, fabricated timestamp, fabricated sensor event or bus injection** | Repository-wide sweep for `freezegun`, `time_machine`, `freeze_time`, monkeypatched `datetime`, `FakeClock`, `sleep(`: **0 matches**. The four hits for `fabricat`/`publish` are **docstring prose citing the prohibition**, confirmed individually |

---

## 8. Why there is no runtime wiring

The repository is **not** wired into `main.py`. Nothing consumes it in 4F.1 —
there is no API surface, no handler and no worker — and wiring a dependency ahead
of its consumer is the speculative work the TDD's scope rule for 4F.1 excludes.

Equally absent, each belonging to a named later slice: `/v1/cognitive-state`
(4F.7), a compose service and `run-migrations.sh` entry (4F.7, with deployment),
Event Bus subscriptions (4F.6), the trigger (4F.6),
`perception.workspace.observed` (4F.2), `nova-companion` and the filesystem
sensor (4F.3), CF-9's write surface (4F.4), Level 2 (4F.5), and the AC-7/AC-8
E2E (4F.8).

**4F.2 has not been started.**

---

## 9. Carry-forwards — unchanged by this slice

**CF-9 OPEN** (a 4F dependency, 4F.4's work, in `action-engine`) ·
**CF-10 OPEN** (not a 4F dependency) · **CF-11 OPEN** (a 4F dependency, 4F.6's
work). 4F.1 touches none of them, and this record closes none.

---

## 10. Merge readiness

| Check | Result |
|---|---|
| Exact code head | `452df79` |
| Working tree | **Clean** |
| Diff contains only intended changes | **Yes** — the new engine, two CI matrix rows, and the three lockfile/config files a new workspace member requires |
| History | Linear above one deliberate, reviewed merge commit; no rebase, squash or force push |
| CI at the exact head | **All 39 checks green** — §11 |

**Merge is not performed by this record.** Authorization is the user's, and
Phase 4F's own Gate Review comes at the end of 4F.8, not here.

---

## 11. CI at code head `452df79`

**39 of 39 check runs green. Zero failures, zero skips.**

| Workflow | Rows | Result |
|---|---|---|
| `checks` | 1 | **success** |
| `real-infra-checks` | 15 (incl. the new `cognitive-state-engine` row) | **15 success** |
| `build-and-scan` (build + Trivy) | 21 (incl. the new `cognitive-state-engine` row) | **21 success** |
| `dependency-audit` | 1 | **success** |
| Playwright golden path (staged, non-blocking) | 1 | **success** |

1 + 15 + 21 + 1 + 1 = **39**, matching the PR's reported total exactly.

**The row this slice adds:** `real-infra (cognitive-state-engine,
services/cognitive-state-engine)` — **`12 passed, 56 deselected`** against a real
`postgres:16-alpine` container, this engine's own Alembic chain applied by
`run_alembic_upgrade`.

**Two runs are recorded here, not one**, because the first is the evidence that
this tier works:

| Head | `real-infra (cognitive-state-engine)` | Everything else |
|---|---|---|
| `3b1364e` | **failure** — `1 failed, 9 passed` (§4.1) | 38/38 green |
| **`452df79`** | **success** — `12 passed` | 38/38 green |

The first run is left in the PR's history rather than hidden. A tier introduced
with the claim that it catches what cheaper tiers cannot is more credible, not
less, for having caught something on its first execution — and what it caught
was in the slice's own test, which is the honest thing to report.

**This record's own commit is documentation-only**, so CI at `452df79` is the
authoritative evidence for the code: `git diff 452df79..HEAD -- ':!docs'` is
empty (Phase 4E Gate Review §18's convention).
