# Phase 4F.3 — Slice Completion Record
## `nova-companion`: the Rust daemon, the filesystem sensor, and the first real OS signal

**Date:** 2026-09-18
**Slice:** 4F.3 of 4F's eight (TDD 4F §18)
**Branch:** `phase-4f.3`, at **`68a78adbc19f96b1cd79a00beeaa0fc6cc3d12fd`**
**Base:** `phase-4` at `6632dd19a5a01c764e03e9e944beca98aedacef4` — **unchanged by this slice**
**PR:** [#32](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/pull/32) — **open and NOT merged**
**Protocol:** [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md),
sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`,
1131 lines, read from `origin/main` and verified in this session.
**TDDs:** [TDD 4F](../../design/phase-4/06-tdd-4f-companion-and-cognitive-state.md)
§7, §9, §16.4, §17, §18, §20.1 · [TDD 4F.3](../../design/phase-4/07-tdd-4f3-nova-companion.md) in full.

---

## 0. What this document is, and is not

**This is a Slice completion record. It is not a Gate Review, and 4F.3 does not
get one.**

Protocol **§0.1**'s unit table reserves a Gate Review for a **Phase or
Sub-Phase** — *"Declaring the phase complete; writing its Gate Review"* — and
assigns a **Significant Slice** categories **1, 2, 8, 9, 10, 11, 13 and 14 in
full**, with categories **3–7 and 12 as a deferred-obligations ledger** (§0.2).
**Category 3 is precisely "Gate Review and Go / Conditional-Go / No-Go
criteria."** A slice defers it; it does not issue one.

This record therefore executes the eight in-full categories below and defers the
rest in writing (§10). **There is no Go / Conditional-Go / No-Go verdict here**,
because that verdict is category 3 and belongs to **4F's Gate Review, at 4F.8**,
where it is already ledgered as **L-1**. The slice's own verdict — *complete,
verified, closed* — is a different and narrower thing, and §11 states it.

This follows 4F.2's record, whose §0 says the same in the same words for the
same reason. It is not a reinterpretation.

**Phase 4F is NOT complete.** Five of eight slices (4F.4–4F.8) have not started.

---

## 1. Status

| | |
|---|---|
| **Slice** | **COMPLETE / VERIFIED / CLOSED** |
| **Phase 4F** | **NOT complete.** 4F.4–4F.8 not started |
| **4F.1, 4F.2** | **Intact.** Both merged into `phase-4`; neither is touched, rewritten or reinterpreted by this slice |
| **PR #32** | **Open, NOT merged**, `mergeable_state: clean` |
| **`main`** | `7e273e62e942ecd5528ca807e65933d6bb675669` — **untouched** |
| **`phase-4`** | `6632dd19a5a01c764e03e9e944beca98aedacef4` — **untouched** |
| **`phase-4f.3`** | `68a78adbc19f96b1cd79a00beeaa0fc6cc3d12fd` — intact, three commits above base |
| **`phase-4f.4`** | **Does not exist.** Not started |

### 1.1 The slice's exit criterion (TDD 4F §18)

> ***"A real OS signal enters the pipeline."***

**Met.** A real write to a real filesystem, detected by the real `notify`
watcher inside the real `nova-companion` process, submitted over a real TCP
socket to the real `perception-engine` route, persisted as a real row in real
PostgreSQL, and published over a real NATS connection. No segment of that chain
is simulated, injected or mocked.

---

## 2. Category 2 — the four acceptance claims

Each is stated as TDD 4F.3 §3.1 ratified it, then as built.

| Claim | Ratified as | Status | Evidence |
|---|---|---|---|
| **S-1** | *"a real filesystem event … is detected … **No synthetic event injection**"* | **MET** | `companion/sensors/tests/real_filesystem.rs` — **8/8**. Real `tempfile` directories, real writes, real `notify`. Includes both containment directions: a nested file is seen, a sibling directory is not |
| **S-2** | *"Cargo test against a **stub HTTP server**"* | **MET, exceeded** | Delivered as a real crossing instead of a stub: `test_companion_intake_real_http.py` — **8/8**. Real binary → real TCP → real uvicorn → real `create_app` → real route → real `domain/workspace.py` |
| **S-3** | *"Python integration test with a registered `FilesystemSensor`"* | **MET, exceeded** | Delivered against real PostgreSQL: `test_workspace_real_postgres_e2e.py` — **5/5**. Real Alembic schema, real committed rows, verified by **independent SQL on its own connection**, never through the repository that wrote them |
| **S-4** | *"the raw path never leaves … **Asserted on the enqueued payload**"* | **MET, exceeded** | Proven at three layers: the enqueued payload, the **committed Postgres outbox row**, and the **envelope received over real NATS**. The handle is verified as a *transformation* — `object_id == object_id_for_path(real_path)` — not merely an absence |

**What S-4 does not claim.** Downstream `world-model-engine` persistence is
**outside S-4's ratified scope** and is **4F.8's**, per TDD 4F §20.1's AC-7 chain
and §18's assignment of that E2E. The reasoning is recorded in TDD 4F.3 §13.1 and
is not restated here.

### 2.1 What this slice explicitly does not claim

**AC-7 is not met and is not claimed.** TDD 4F.3 §3.2 and TDD 4F §18 assign the
acceptance run to 4F.8, bound by §20.1 to honest measurement. 4F.3 makes AC-7
*measurable* for the first time by supplying the genuine OS event that starts its
interval. **AC-8 is untouched.**

---

## 3. Category 1 — implementation against the TDDs and ADRs

### 3.1 The six deliverables

| # | Deliverable | Built |
|---|---|---|
| 1 | Cargo workspace | `companion/` — two members, `resolver = "3"`, `edition = "2024"` |
| 2 | Filesystem sensor | `companion/sensors/` — one `.watch()` call site in the entire repository |
| 3 | Intake client | `companion/nova-companion/src/intake.rs` — 4F.2's route, contract unchanged |
| 4 | Dockerfile | `companion/nova-companion/Dockerfile` — `debian:trixie-slim` runtime, no toolchain |
| 5 | CI | One `build-and-scan` matrix row, one `pr-checks` Rust step. **Additions only** |
| 6 | `sensors_by_source["filesystem"]` | `main.py:141` — **L-12 settles here** |

### 3.2 The four ratified decisions, verified as built

| Decision | Verified |
|---|---|
| **D-4F3-1** sensor split | Structural, not documentary. The Rust crate cannot register itself; `FilesystemSensor` performs no detection — asserted by stripping docstrings via the AST and failing on `open(`, `listdir`, `watch`, `inotify`, `stat(` in executable code, and by asserting the biometric methods are absent |
| **D-4F3-2** path hashing | The companion contains **no hashing code at all**. `request.path` is consumed at exactly two call sites, both in the engine. `WorkspaceObservation` — the only thing reaching the publisher — **has no path field**, so the raw path is dropped structurally rather than filtered |
| **D-4F3-3** consent as a policy boundary | No consent API, database or policy engine. `NOVA_COMPANION_WATCH_ROOT` is **required with no default**, blank treated as missing, so the process refuses to start rather than falling back to `$HOME`. `permission_status()` documents that it is **not** a consent claim. **L-14 stays open** |
| **D-4F3-4** the hardening guard | Generalized to `RUNTIME_FAMILIES`. Its own failure mode — a parser that shrugs at an unknown base — is itself asserted to fail, and a family listed without a hardening rule fails too. The companion **is** in the matrix, is **not** in `UNSCANNED`, and ships no compiler |

### 3.3 Architectural boundaries, each verified at this head

| Boundary | Verified |
|---|---|
| The companion is **not an engine** | No listening port, no HTTP-server dependency in `Cargo.toml`, no NATS client, no store. ADR-004's engine-to-engine prohibition is not engaged because one side is not an engine |
| **ADR-025** identity | `WorkspaceObservationRequest` has no `user_id` field; identity is resolved server-side from `Settings.primary_user_id`. A client-supplied identity is **unrepresentable**, not merely rejected |
| **ADR-006** Event Bus | The companion never imports a broker client; import-linter's contract holds, 7 kept / 0 broken |
| `world-model-engine` | **0 files changed** |
| `ws-gateway`, `api-gateway`, `nova-contracts`, `apps` | **0 files changed** each |
| Migrations, ORM models | **0** of each |
| Perception HTTP contract | **Unchanged** — `api/observations.py`, `workspace_orchestration.py` and `domain/workspace.py` are untouched by this slice |

---

## 4. Category 8 — contracts and codegen

| Check | Result |
|---|---|
| New Event Bus subjects | **0** |
| Registered subjects | **119**, counted from the runtime registry (`len(_REGISTRY)` after importing every `nova_contracts` submodule) |
| `@register_payload` call sites | **120** — the extra is the usage example in `registry.py`'s own **module docstring**, not a subject. See TDD 4F.3 §21.1 |
| `PUBLIC_TOPICS` | **exactly 18** — parsed from the literal in `ws-gateway/domain/protocol.py` |
| The workspace subject | **Not public**, **not `ws-gateway`-subscribable** |
| Codegen drift | **117 TypeScript contract files, zero drift** — regenerated, `git status` clean |
| `nova-contracts` changes | **0 files** |

---

## 5. Category 9 — tests, lint, types, imports

Measured at `9d21bd2`, the last commit that changed code; `3e46a9f` and
`68a78ad` are documentation-only, and CI re-ran the full suite at `68a78ad`
regardless.

| Check | Result |
|---|---|
| `turbo run test --force` | **32/32 tasks, `Cached: 0` — 2,755 passed, 0 failed** |
| Rust `cargo test --all-targets --locked` | **33 passed** (27 before this slice's F-7 work; +6) |
| `cargo fmt --all --check` | Clean |
| `cargo clippy --all-targets --locked -- -D warnings` | Clean |
| `tools/tests` | **292 passed** (286 before this slice) |
| `turbo run lint` | **32/32** |
| `turbo run build` | **32/32** |
| `turbo run typecheck` | **5/5** |
| import-linter | **7 contracts kept, 0 broken** |

**No test was weakened to accommodate this slice.** Two pre-existing assertions
pinned the sensor count at two and now read three; both were updated with the
original recorded rather than loosened to a subset, because a sensor appearing
there unannounced is what they exist to catch.

---

## 6. Category 10 — real infrastructure

**20 real-infrastructure tests, all passing**, in the `perception-engine`
real-infra job at this exact head:

```
20 passed, 185 deselected, 4 warnings in 51.12s
```

| Group | Count | What is real |
|---|---|---|
| `test_companion_intake_real_http.py` | 8 | Real temp filesystem, real `notify`, real spawned binary, real TCP, real uvicorn |
| `test_workspace_real_postgres_e2e.py` | 5 | All of the above **plus** real PostgreSQL (testcontainers), real Alembic migration, real NATS container, the real outbox dispatcher |
| `test_repository_real_postgres.py` | 7 | Pre-existing; unaffected and still green |

**The harness deliberately cannot skip.** A missing Rust toolchain raises rather
than skipping, because a skip would report absent acceptance evidence as
success — the precise failure mode these tests exist to eliminate.

**One defect was found by this work and fixed before CI could see it:** the
first harness wrote its file before `notify` had registered the inotify watch,
losing the event silently. The fixture now blocks on the daemon's own startup
line. Recorded because a test that races its subject fails in the one direction
that looks like a product defect.

---

## 7. Category 11 — PR, branch, commit and CI evidence

**CI at `68a78adbc19f96b1cd79a00beeaa0fc6cc3d12fd` — 40/40 checks green,
`run_attempt: 1`, zero skipped, zero cancelled.**

| Workflow | Run | Conclusion |
|---|---|---|
| Build & Scan | [35329092243](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/35329092243) | **success** — 22/22 images built **and** Trivy-scanned, + `dependency-audit` |
| Real-Infrastructure Checks | [35329092235](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/35329092235) | **success** — 15/15 |
| PR Checks | [35329092118](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/35329092118) | **success** — `checks` + Playwright golden path |

**The companion image is genuinely built and genuinely scanned.** At the first
CI run of this branch the Trivy step reported `Detected OS family="debian"
version="13.7"`, `pkg_num=78`, `Number of language-specific files num=0` and
**0 vulnerabilities** under the configured `severity: CRITICAL,HIGH` +
`exit-code: "1"` + `ignore-unfixed: true` gate — confirming both that the scan
ran and that no Rust toolchain ships inside the image.

**A prior audit finding, F-1, is discharged here.** Before PR #32 existed, all
three workflows triggered only on `pull_request` or `push: main`, so
`phase-4f.3` had never been built or scanned and the companion image had never
been Trivy-scanned anywhere. That gap is closed.

**Tree identity.** CI for a `pull_request` builds the merge ref, so the image is
tagged with a merge SHA rather than the head SHA. At the first run this was
verified directly: the merge commit's tree was **byte-identical** to the head
commit's tree, so CI exercised exactly this branch's content.

**Commits on `phase-4f.3` above `phase-4` (three, no history rewritten):**

| SHA | |
|---|---|
| `d9d922f` | Implementation — the six deliverables |
| `9d21bd2` | The real-crossing integration tests and the F-7 fix |
| `3e46a9f` · `68a78ad` | Documentation only, additive only |

---

## 8. Category 13 — findings, carry-forwards and ambiguities

### 8.1 Findings raised by the pre-gate audit

| # | Status | Disposition |
|---|---|---|
| **F-1** | **CLOSED** | Zero CI runs existed for this branch. PR #32 produced them |
| **F-2** | **OPEN** | SLOC scope ambiguity. Owned by **L-5**, settled at **4F closure**. Recorded with both figures in TDD 4F.3 §17.1. **Not a 4F.3 blocker** — the gate is uncrossed under either reading |
| **F-3** | **CLOSED** | S-2's real crossing now exists |
| **F-4** | **CLOSED** | S-3's real-Postgres coverage of the workspace outbox path now exists |
| **F-5** | **CLOSED as a 4F.3 finding** | S-4's ratified scope is met. The downstream world-model leg is **4F.8's**, per TDD 4F §20.1 + §18; reasoning in TDD 4F.3 §13.1 |
| **F-6** | **CLOSED** | `run()` is exercised by every S-2 test and its structured output is asserted |
| **F-7** | **CLOSED** | A real leak, confirmed and fixed. `notify::Error`'s `Display` appends `" about {paths:?}"`, and the Linux backend attaches the watched path to nearly every error, so `watch_error` put the configured directory chain into a log line. `describe()` keeps the error *kind* in full and reduces paths to final segments; six regression tests assert that notify's own `Display` leaks while ours does not |

### 8.2 Carry-forwards — all three remain OPEN

**CF-9, CF-10 and CF-11 all remain OPEN.** 4F.3 touches none of them. CF-9 is
**4F.4's**, CF-11 is **4F.6's**, CF-10 is not a 4F dependency.

### 8.3 Two figures this slice's own earlier reporting got wrong

Recorded rather than quietly fixed, because both appear in this slice's commit
messages and PR body, which are historical and are not rewritten.

| Claim | Correct value |
|---|---|
| *"Event Bus subjects 119"* was briefly "corrected" to 120 in a pre-gate report | **119 is right.** 120 counts a module-docstring example. No repository document ever carried 120 (TDD 4F.3 §21.1) |
| *"53 crates in the lockfile"* | **`companion/Cargo.lock` holds 98 package entries**, 96 of them third-party. The binary's own non-dev dependency tree is **31 crates**; 38 including dev-dependencies. The figure appears in no tracked document |

---

## 9. Category 14 — documentation updated by this slice

| Document | Change |
|---|---|
| `companion/nova-companion/README.md` | **New.** What it is, what it never does, configuration, the consent boundary, the image |
| `services/perception-engine/README.md` | **L-7 settles here** — the new subject, the structured intake route, and the `filesystem` sensor type |
| TDD 4F.3 §17.1 | **Additive.** F-2's two readings and their figures |
| TDD 4F.3 §13.1 | **Additive.** Why the downstream world-model leg stays outside 4F.3 |
| TDD 4F.3 §19.2 | **Additive.** L-11's settler corrected |
| TDD 4F.3 §21.1 | **Additive.** How to count Event Bus subjects |
| This record | **New** |

**Every documentation change in this slice is additive** (protocol §0.3.4). No
prior Gate Review, completion record or health record is rewritten. The 4F.2
record's L-11 row stands exactly as written; its correction is recorded against
it in TDD 4F.3 §19.2, not applied to it.

---

## 10. Deferred-obligations ledger — protocol §0.2

**This is the ledger §0.2 requires**, so 4F's eventual Gate Review inherits a
complete list. **A Sub-Phase may not be declared complete while any row here is
unsettled** — which is why Phase 4F is not complete.

### 10.1 Settled by this slice

| # | Obligation | Evidence |
|---|---|---|
| **L-7** | `perception-engine/README.md` | Describes the subject, the structured intake route and the `filesystem` sensor type |
| **L-12** | `"filesystem"` source registration | `main.py:141` — the route no longer 404s on `source=filesystem` |

### 10.2 Still open, each with its owner

| # | Obligation | Owner | Blocks 4F.3? |
|---|---|---|---|
| L-1 | 4F Gate Review (category 3) | **4F closure, after 4F.8** | No |
| L-2 | `docs/project-health/phase-4f.md` (category 4) | **4F closure** | No |
| L-3 | `project-health-master.md` summary row for 4F | **4F closure** | No |
| L-4 | `ENGINEERING_ROADMAP.md` 4F row, full category-5 treatment | **4F closure** | No |
| L-5 | `00-master-scope.md` §17 SLOC table + the §2 methodology entry — **this is F-2's owner** | **4F closure** | No |
| **L-6** | `README.md` — *"a new engine now exists"*, fired at 4F.1 | **4F closure** | No — 4F.3 adds a component, not an engine |
| L-8 | `ws-gateway/README.md` — the `perception.*` narrowing | **4F closure** | No |
| L-9 | Cross-file consistency sweep (category 12) | **4F closure** | No |
| L-10 | `docs/` staleness sweep (category 6) | **4F closure** | No |
| **L-11** | **Fusion for workspace signals** | **4F closure** *(corrected from "4F.3")* | No |
| **L-13** | `known_projects` population | **4F closure or later** | No — `main.py:161` still `{}`; needs a `memory-engine` event path |
| **L-14** | Doc 22 Principle 8 per-source consent for `filesystem` | **4F closure**, or earlier if separately ratified | No |

### 10.3 L-11 — corrected, and explicitly still OPEN

**L-11 is NOT settled by 4F.3 and must not be marked settled.** The 4F.2 ledger
dates it *"Settled by 4F.3"*; that is wrong, and TDD 4F.3 said so before this
audit asked — §1.1 lists multi-modal fusion of workspace signals among the
non-goals, and §19 records that it is *"still not in 4F.3's scope row"*.

Verified against the code, not inferred: neither `workspace_orchestration.py`
nor `domain/workspace.py` names `correlation_buffer` or `identity_fusion`;
4F.3's diff against `phase-4` is **empty for both fusion modules**; and neither
module mentions `workspace`. **S-1 through S-4 are not offered as evidence for
L-11** — they concern detection, transport, persistence and path absence, none
of which is fusion.

**Owner: 4F closure.** TDD 4F §18 names fusion in **4F.2's row only**; no row for
4F.4–4F.8 names it, so with 4F.2 closed and 4F.3 declining it, protocol §0.2's
backstop applies. **No new ledger row was created** — L-11 keeps its number and
only its *Settled by* field is corrected (TDD 4F.3 §19.2).

---

## 11. Final status

**Phase 4F.3 is COMPLETE, VERIFIED and CLOSED as a slice.**

Verified means: its exit criterion is met by real evidence at a known SHA; its
four acceptance claims are met and three exceed their ratified bar; its four
ratified decisions hold structurally rather than by convention; 40/40 CI checks
are green at that SHA; and every obligation it did not discharge is named above
with an owner.

**And, stated as plainly as the closure itself:**

- **Phase 4F is NOT complete.** 4F.4 through 4F.8 have not started. Its Gate
  Review and its Project Health record are **4F.8's**, ledgered as L-1 and L-2.
- **No Go / Conditional-Go / No-Go verdict is issued here.** That is category 3,
  which a slice defers (§0).
- **4F.1 and 4F.2 remain intact** and are not reinterpreted.
- **PR #32 remains open and unmerged.**
- **`main` is untouched** at `7e273e62e942ecd5528ca807e65933d6bb675669`.
- **`phase-4` is untouched** at `6632dd19a5a01c764e03e9e944beca98aedacef4`.
- **`phase-4f.3` is intact** at `68a78adbc19f96b1cd79a00beeaa0fc6cc3d12fd`.
- **`phase-4f.4` has not been created.**
- **L-11 remains OPEN**, owned by 4F closure.
- **F-2 remains OPEN** under **L-5**.
- **4F.8 owns** the downstream world-model E2E and the AC-7/AC-8 acceptance run.

### 11.1 SLOC

**46,005 on the 4F scope. Headroom to the 50,000 hard gate: 3,995. The gate is
NOT crossed.**

`cloc` v2.06 `--skip-uniqueness` over a pristine `git archive`, the 4E Gate
Review's tool and flags unchanged, now scripted and reproducing the 45,982
baseline at `d9d922f` exactly. Of the growth, **+481** is the companion's Rust
source, **+142** its `Cargo.toml`/`Dockerfile`/`README.md`, and **+23** the F-7
fix. The four integration and regression test files contribute **0** — tests are
outside every scope (TDD 4F §17).

The 142 lines are F-2's subject: under the protocol's own definition
(*"`src/` application code + Alembic migrations, excluding … documentation"*)
the figure would be **45,863**. **The gate is uncrossed under either reading**,
which is why F-2 is a documentation reconciliation and not a blocker. Both
figures are recorded in TDD 4F.3 §17.1 for L-5 to settle at 4F closure.
