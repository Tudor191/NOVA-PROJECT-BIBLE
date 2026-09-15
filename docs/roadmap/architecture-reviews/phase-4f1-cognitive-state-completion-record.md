# Phase 4F.1 — Completion Record
## `cognitive-state-engine`: domain and persistence

**Date:** 2026-09-15
**Branch:** `phase-4f`
**Head:** `99fcec627b02c02efd8674b893273e174d0bd09f`
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
| Real-infra tests | **Done** — 10 written, delegated to CI (§6) |
| CI integration | **Done** — one `real-infra-checks` row, one `build-and-scan` row |
| **No runtime wiring yet** | **Correct and deliberate** — §8 |

---

## 2. Commits

| SHA | Role |
|---|---|
| **`99fcec627b02c02efd8674b893273e174d0bd09f`** | **The 4F.1 implementation commit** — one coherent commit, as required |
| `b5aa471cc91cb4c32c5465bafabfd17b36445b65` | **The TDD merge** — `phase-4f-tdd` → `phase-4f`, a normal two-parent merge |

**Why the TDD merge exists.** `phase-4f` was created from `phase-4`'s HEAD
`c04b58e`, where the ratified 4F TDD does not exist and the master scope still
carries the **superseded one-second AC-7**. Implementing against a ratified
design the branch itself contradicted would have been incoherent, and keeping the
TDD and master scope internally consistent is inside 4F.1's scope. Reviewed and
**accepted**; the history is not to be rewritten or repaired.

All five commits above `c04b58e` remain reachable: `9c2d503` · `abb0f30` ·
`bcd8bb2` · `b5aa471` · `99fcec6`. No rebase, no squash, no force push.

---

## 3. Test results — at head `99fcec6`

| Check | Result |
|---|---|
| `cognitive-state-engine`, default tier | **56 passed, 10 deselected** |
| `cognitive-state-engine`, domain coverage | **100%** — 130 statements, **0 missed**, against the 85% gate |
| `npx turbo run test --force` | **32/32 tasks, `Cached: 0`** — **2,670 passed, 404 deselected, 0 failed** |
| `uv run pytest tools/tests -q` | **286 passed** |
| `npx turbo run lint --force` | **32/32** |
| `npx turbo run typecheck build --force` | **35/35** |
| `uv run lint-imports` | **7 kept, 0 broken** |
| Codegen | **116 TypeScript files, zero drift** |

### 3.1 The controls this slice adds

Twelve contract tests in `tests/contract/test_boundaries.py` assert TDD §6.2's
checkable prohibitions: publishes nothing, subscribes to nothing, no
`action.execute` in executable code, no cross-engine import (four engines,
parametrized), no HTTP client, no other engine's schema named, and no execution
vocabulary anywhere in the domain. **Every source scan strips docstrings via the
AST first**, so this engine's own prose about `action-engine` cannot trip a
control — Phase 4D's recorded precision failure, avoided by construction. One
anti-vacuity test asserts there is source to scan at all.

---

## 4. Real-infrastructure verification

**Written, not executed locally. Delegated to CI.**

Ten `real_infra` tests exist and are collected (`-m real_infra` collects
`10/66`). **Docker is unreachable in this environment**, so they have not run
here, and no local result is offered as evidence for them — the same disclosure
discipline 4D and 4E used.

**They run in CI** via the `real-infra-checks.yml` matrix row this slice adds.
What they prove, and why a fake cannot:

1. **A 90-day-old `created_at` survives the round trip** — the Phase 4E defect
   made impossible. The column carries `server_default now()`, so this passes
   only because the repository writes both timestamps explicitly.
2. **Re-upserting does not move `created_at`** — an Active Thought is *ongoing*,
   so its age is meaningful.
3. **The CHECK constraints are real** — asserted by bypassing the domain model
   deliberately; a Protocol has no constraint to violate.
4. **`JSONB` round-trips** the three relation lists through the driver's
   `UUID` → `str` → `UUID` conversion.
5. **Ordering is deterministic across a genuine timestamp tie.**
6. **The schema holds exactly one table** — no speculative table for a later
   slice.

---

## 5. SLOC

`cloc` v2.06, `--skip-uniqueness --quiet`, from pristine `git archive` extracts.
**Scope includes `companion/`**, per the ratified methodology change (TDD §17) —
the directory does not exist yet, so it contributes zero, but it is **in the
measured scope** so a later slice cannot land there uncounted.

| | Base `c04b58e` | Head `99fcec6` | Δ |
|---|---|---|---|
| 4F scope (incl. `companion/`) | **44,706** | **45,107** | **+401** |
| Comparable | 35,733 | 36,134 | +401 |
| Wider | 41,074 | 41,475 | +401 |

**Headroom to the 50,000 hard gate: 4,893.** The gate is **respected and not
threatened**. The engine's own footprint is 401 lines across 18 files; tests are
outside every scope by definition.

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

## 7. Boundary confirmations — each verified at head

| Property | Evidence |
|---|---|
| **`PUBLIC_TOPICS` unchanged** | `git diff c04b58e..HEAD -- services/ws-gateway/` is **0 lines** |
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
| Exact head SHA | `99fcec627b02c02efd8674b893273e174d0bd09f` |
| Working tree | **Clean** |
| Diff contains only intended changes | **Yes** — the new engine, two CI matrix rows, and the three lockfile/config files a new workspace member requires |
| History | Linear above one deliberate, reviewed merge commit; no rebase, squash or force push |
| CI at the exact head | Recorded in §11 when the PR's run completes |

**Merge is not performed by this record.** Authorization is the user's, and
Phase 4F's own Gate Review comes at the end of 4F.8, not here.
