# Phase 4F.8 — Slice Completion Record
## The acceptance slice: revocation detection, known-project correlation, the one-second dispatch exception, the acceptance-only override, and the AC-7 / AC-8 harness

**Date:** 2026-10-11

**Slice:** 4F.8 — [TDD 4F.8](../../design/phase-4/12-tdd-4f8-acceptance-verification.md) §1.1, D1 … D9, plus the dispatch exception that D-4F-1's reopening authorizes (§30). It is 4F's final implementation slice (TDD 4F §18). This record is **D9's Slice Completion Record**.

**Branch:** `phase-4f8`.

- **Implementation SHA: `3bca5538e7de21c437423bc67791596cb7f7fef3`.** It is the last commit that touches code, tests, CI or compose.
- This record's commit follows it, and is documentation only (§7.1).

**Base:** `phase-4` at **`1ccce7a703cfc5c6d7c164467c5e8ed8c5820c90`**. This slice does not change it.

**`main`:** **`7e273e62e942ecd5528ca807e65933d6bb675669`**. Untouched.

**PR:** **none.** None has been requested, and protocol §11.1 allows a PR only when asked. **Nothing is merged.**

**Protocol:** [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md).

- sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`, 1131 lines.
- Fetched from `origin/main` and read in full at the start of this implementation (TDD 4F.8 §22 step 1). It was re-fetched, hash-verified and read in full again before this record.

**TDDs:**

- **[TDD 4F.8](../../design/phase-4/12-tdd-4f8-acceptance-verification.md) is authoritative.** That includes:
  - §29: the decisions RATIFIED 2026-10-11, and the acceptance plan;
  - §30: D-4F-1 reopened, for `perception-engine`'s dispatch interval only;
  - §31 … §37: the implementation records.
- Also used: [TDD 4F](../../design/phase-4/06-tdd-4f-companion-and-cognitive-state.md) §4.1, §16, §18 and §20.1; [TDD 4F.7](../../design/phase-4/11-tdd-4f7-cognitive-state-panel.md); and [TDD 4F.P](../../design/phase-4/13-tdd-4fp-production-promotion.md), whose P8 stack this slice builds on.

---

## 0. What this document is, and is not

**This is a Slice completion record. It is not a Gate Review.**

- Protocol §0.1 gives a Significant Slice categories **1, 2, 8, 9, 10, 11, 13 and 14 in full**.
- Categories **3–7 and 12** go into a deferred-obligations ledger (§10).
- So this record issues **no GO / CONDITIONAL-GO / NO-GO verdict**. 4F's Gate Review is **L-1**, owned by 4F closure.

**4F.8 is NOT complete.** Every deliverable D1 … D8 is implemented and verified locally, against real PostgreSQL, NATS and Redis, real engine processes and the real companion binary. This record discharges D9. **What remains:**

- **No CI run exists at the implementation SHA** (§7.2).
  - `pr-checks.yml` runs on `pull_request`, on pushes to `main` and on `workflow_dispatch`. A dispatch from this session was refused with HTTP 403.
  - **The decisive evidence for AC-7 and AC-8 is that workflow's e2e job.** A-4F8-6 makes AC-7's measurement the CI acceptance run's. A-4F8-7 puts each criterion's browser-visible clause in a real browser, against that stack.
- **So AC-7 and AC-8 are NOT met, and are not claimed** (§2).
- **The two Playwright specs have never been executed.** The local stack has no gateways.
- **N-16 in CI** needs a run without the override (§5.1).
- **No PR has been opened, and nothing is merged.**

**Phase 4F is NOT complete.** A-4F8-9 still blocks 4F's GO. CF-9, CF-10 and CF-11 stay OPEN. Completing this record does not authorize opening a PR, merging, or starting any further work.

### 0.1 Branch shape — disclosed

- **The cut.** After the user's explicit authorization, `phase-4f8` was cut from **`origin/phase-4` @ `1ccce7a`**.
- **The TDD history.** The ratified TDD lived on `phase-4f8-tdd`:
  - `5a95475`: preparation;
  - `1ea0d0f`: a merge of `phase-4` (re-base on merged 4F.P);
  - `f28e373`: re-verification;
  - `11dc225`: ratification;
  - `aff01ae`: D-4F-1 reopened.

  It was brought onto `phase-4f8` by **one normal merge, `4d0e42e`**, with the commits unchanged.
- **No rewriting.** No history was rewritten, squashed, rebased, amended or force-pushed.
- **Ancestry, re-verified in this session.**
  - `1ccce7a` is an ancestor of HEAD.
  - No 4F.8 commit is an ancestor of `phase-4` or `main`.
  - `origin/phase-4f8` equals the implementation SHA.
  - The working tree was clean before this record.

### 0.2 Decisions in force

- **RATIFIED 2026-10-11 (TDD 4F.8 §29.1):**
  - A-4F8-1 (a), with (a1) and (a2): the revocation owner;
  - A-4F8-2 (a), with (a1) and (a2): known projects;
  - A-4F8-4 (a): the production trigger;
  - A-4F8-6: the AC-7 measurement;
  - A-4F8-7 (a): the evidence surface;
  - A-4F8-8 (a), restricted to §28.8's surfaces: SAD 15 §4 item 1;
  - §28.7 option (B), with §29.2's plan B2: the acceptance-only override.
- **The user's decision of 2026-10-11 (TDD 4F.8 §30):** D-4F-1 reopened, for `perception-engine`'s outbox dispatch interval only, with the serial dispatcher it requires.
- **Answered by 4F.P, as §28.2 records:** A-4F8-3 and A-4F8-5. A-4F8-10 was absorbed by A-4FP-12 (§28.3).
- **Not ratified, and OPEN:** A-4F8-9, the unassigned 4F deliverables. **It blocks 4F's GO, not 4F.8's implementation.**
- **The user's in-session implementation instruction of 2026-10-11.** Its required tests are mapped in §2.

---

## 1. Status

**Implemented, and verified locally:** D1 … D8, and the dispatch exception. D9 is this record and the documentation in §9.

| Deliverable | Commit | Section |
|---|---|---|
| The D-4F-1 dispatch exception | `ab8673b` | TDD 4F.8 §31 |
| D1, revocation detection in `nova-companion` | `6ba6f27` | §32 |
| D2, the filesystem sensor's `failed` path, through one internal route | `fa9217a` | §32 |
| D3, known-project bindings, learned over the bus | `4648f63` | §33 |
| D4, the acceptance stack | absorbed by 4F.P's A-4FP-12 (§28.3); the override in `5a80c9a` | §28.3, §34 |
| D5, D6, D7, D8, the harness, the specs, the CI steps and the guards | `afff6b8` | §35 |
| F-4F8-18's fix, the flakiness record and the documentation notes | `8e05b32` | §36 |
| N-9 and N-11 as real mutations; F-4F8-19's fix | `3bca553` | §37 |

- **Real-infrastructure tests** ran against substitute local services, because Docker is unavailable (§6).
- **The acceptance phases** ran against a local equivalent of the e2e stack: the real engines as processes, the real companion binary as uid 1100, and real PostgreSQL 16, NATS and Redis. **Thirty fresh-stack cycles** ran in all: ten before F-4F8-18's fix, ten after it, and ten at the implementation SHA (§5.2).
- **CI has not run at all for this branch** (§7.2).

### 1.1 The slice's exit criterion

TDD 4F.8 §1.2:

> *"AC-7 and AC-8 each demonstrated against the deployed system, with the evidence recorded."* For AC-7, *"the measured evidence that AC-7 cannot be met"* is equally acceptable.

**Not met.** "The deployed system" is the CI acceptance stack (A-4F8-6, A-4F8-7; §18), and it has not run. The local evidence below shows that the harness, the engines and the companion behave as the criteria require on real infrastructure. It is not the measurement A-4F8-6 ratifies.

**The local evidence, in three runs of ten fresh-stack cycles each:**

| Phase | Before F-4F8-18's fix | After it (`8e05b32`) | At the implementation SHA (`3bca553`) |
|---|---|---|---|
| P8 (4F.P) | 67/67, 10 of 10 | 67/67, 10 of 10 | 67/67, 10 of 10 |
| `ac8` (D6) | 54/54, 10 of 10 | 54/54, 10 of 10 | **55/55**, 10 of 10. F-4F8-19 added one check |
| `ac7-latency` (D5) | 70/70 in 9 cycles; 69/70 in cycle 6 (F-4F8-18) | **70/70, 10 of 10** | **70/70, 10 of 10** |
| `ac7-revocation` (E-5, E-6, E-18) | 7/10, 10 of 10. The three Docker-only checks fail | 7/10, 10 of 10. The same three | 7/10, 10 of 10. The same three |

**AC-7's latency, every local sample** (from the file's OS mtime to the first `200` from `world-model-engine`'s `GET /v1/world/objects/{id}`):

| Run | Samples | Range | Median | Mean | 95th percentile | Over 5.0 s |
|---|---|---|---|---|---|---|
| §35.4's first run | 10 | 0.064–0.955 s | — | — | — | **0** |
| Before the fix | 100 | 0.059–1.064 s | 0.592 s | 0.584 s | 1.015 s | **0** |
| After the fix | 100 | 0.062–1.083 s | 0.554 s | 0.530 s | 0.992 s | **0** |
| At the implementation SHA | 100 | 0.063–1.039 s | 0.564 s | 0.558 s | 0.963 s | **0** |

- §35.4's first ten samples, in seconds: 0.284, 0.574, 0.680, 0.064, 0.400, 0.955, 0.458, 0.284, 0.172, 0.834.
- Every other figure is in TDD 4F.8 §36 and this session's scratchpad logs, which are not committed.
- **IDE and window-focus sensing was not the modality** (E-7; D-4F-8). The modality is the filesystem sensor.

**The revocation, locally, in every one of the 30 cycles** (`ac7-revocation`):

- the workspace's group bits were withdrawn, and the owner's were intact;
- `perception-engine`'s filesystem sensor was `failed`;
- exactly one `failed` report was dispatched, and `cognitive_state.sensor_state` held `failed` from it;
- a write the OS accepted produced no outbox row, no World Model object and no submission for 25 s (E-6);
- the companion's own process log had `permission_revoked` once and `revocation_reported` once.

**What failed locally, each time, and why.** Three checks read the containers: E-5's companion log through `docker compose logs`, and E-18's two `docker compose exec` checks. No Docker daemon exists here. They are the CI run's.

---

## 2. Category 2 — acceptance criteria

**Sources consulted:**

- Master scope §1.1: AC-7 and AC-8, which are authoritative for Phase 4.
- TDD 4F.8 §1.2 (the exit criterion), §16 (E-1 … E-18), §17 (N-1 … N-16, reported in §5.1) and §19 (P-AC7-1, P-AC8-1).
- TDD 4F.8 §29.4 (the acceptance plan) and §30.3 (what the dispatch change must prove).
- `ENGINEERING_ROADMAP.md`'s Phase 4 entry. Its four bullets are not authoritative; its own 2026-09-15 note says they survive within AC-5 … AC-8.
- In-session: the user's implementation instruction of 2026-10-11.

| # | Criterion | Source | Status | Evidence |
|---|---|---|---|---|
| AC-7 | *"A known project becoming active on the user's machine is detected by a `nova-companion` sensor and reflected in the World Model within five seconds, with no user action; and revoking that sensor's OS-level permission stops the perception stream, visibly, in the Digital Twin / Cognitive State panel."* | Master scope §1.1 | **Cannot be verified in this environment.** Not met, and not claimed | A-4F8-6's measurement is the CI acceptance run's, and P-AC7-1 needs a browser and the gateways. Local analogues: §1.1 |
| AC-8 | *"The same action category that is blocked at Level 1 auto-executes at Level 2 for a low-risk case, purely by policy — no code path differs."* | Master scope §1.1 | **Cannot be verified in this environment.** Not met, and not claimed | The CI acceptance run, and P-AC8-1 in a browser. Local: `ac8` passed in 30 of 30 cycles (54/54, then 55/55) |
| X-1 | The exit criterion | TDD 4F.8 §1.2 | **Not met** | §1.1 |
| E-1 | A real companion and directory; a real write becomes a `WorldObject`, with `correlation_id` provenance | §16 | **Met (local); CI pending** | `ac7-latency`'s E-1 checks, 10 samples per cycle, 30 cycles |
| E-2 | *"Known"*: the known `project_id`; `None` outside every known root | §16 | **Met (local); CI pending** | `[miss]` and `[sample n] E-2 (match)` checks |
| E-3 | Within 5.0 s, at least 10 samples, every figure reported | §16; A-4F8-6 | **Cannot be verified in this environment** (A-4F8-6 is CI's) | Locally, 310 samples, none over 5.0 s (§1.1) |
| E-4 | Without user action | §16 | **Met** (structural) | `test_e4_between_a_write_and_its_observation_the_harness_only_reads` |
| E-5 | Revocation reaches `failed`, visibly | §16 | **Not met.** Its local half passes; the container-log check and the panel are CI's (protocol §2.1: partly met is not met) | `ac7-revocation`'s E-5 checks (§1.1). P-AC7-1 has not run |
| E-6 | The stream stops, for a writer that still has permission, for ≥ 25 s | §16 | **Met (local); CI pending** | `ac7-revocation`'s three E-6 checks, 30 of 30 cycles |
| E-7 | The modality is disclosed | §16 | **Met** | §1.1 |
| E-8 | Blocked at Level 1 | §16 | **Met (local); CI pending** | `ac8` |
| E-9 | Auto-executes at Level 2: `completed`, exactly one action row, the real effect | §16 | **Met (local); CI pending** | `ac8`, through P8's executed-run checks |
| E-10 | No code path differs: identical `policy_checks` | §16 | **Met (local); CI pending** | `ac8` |
| E-11 | Low risk, twice | §16 | **Met (local); CI pending** | `ac8`: authored `low`, `negligible` in `action-engine` |
| E-12 | Purely by policy: only the level changes | §16 | **Met (local); CI pending** | `ac8`'s SQL read-backs |
| E-13 | The production trigger | §16; A-4F8-4 | **Met (local); CI pending.** The structural half is met in this session | `test_e13_*` (10 tests); `ac8`'s `uuid5` checks |
| E-14 | CF-11 claim 3 | §16 | **Cannot be verified in this environment.** It rests on E-8, E-9 and E-13 in CI | — |
| E-15 | Boundaries unchanged: registry 120, `PUBLIC_TOPICS` 18, nine prefixes, no `/v1/perception` or `/v1/world` | §16 | **Met** | §2.1 |
| E-16 | Earlier slices intact; stage 3 byte-identical | §16 | **Met** | §2.1 |
| E-17 | Fail-closed at stage 3 | §16 | **Met (local); CI pending** | `ac8`'s denial run |
| E-18 | The revocation is the sensor's alone | §29.4.6 | **Cannot be verified in this environment** (it inspects the containers). Its local analogue is met | TDD 4F.8 §34.2 |
| P-AC7-1 | `running`, the genuine revocation, then `failed` after Refresh, equal to the gateway | §19 | **Not run** | `apps/web-client/tests/e2e/acceptance-ac7.spec.ts` |
| P-AC8-1 | Level 1's proposal awaits approval; Level 2 proposed nothing | §19 | **Not run** | `apps/web-client/tests/e2e/acceptance-ac8.spec.ts` |
| I-1 | The dispatch: one-second cadence, `max_jobs == 1`, exactly one compose replica, other engines' schedules unchanged | In-session; §30.3 item 1 | **Met** | `test_perception_dispatch_cadence.py` (17), `test_worker_settings.py` (3) |
| I-2 | A real Redis/PostgreSQL/NATS no-overlap, no-duplicate test, with a negative control | In-session; §30.3 items 2–3 | **Met (local); CI pending** | `test_outbox_dispatch_cadence_real_infra.py` (3). TDD 4F.8 §31.4 |
| I-3 | Multi-replica safety is not claimed; the single replica is enforced structurally | In-session | **Met** | §30.2; the structural tests in I-1 |
| I-4 | D1 with a real permission-change test | In-session | **Met (local); CI pending** | Cargo `revocation.rs` ×2 (§6) |
| I-5 | D2 through the single approved route, on real infrastructure | In-session | **Met (local); CI pending** | `test_permission_revocation_real_infra.py` |
| I-6 | D3: migration, table, subscription | In-session | **Met (local); CI pending** | `0002_known_project.py`; `test_known_project_real_infra.py` (2) |
| I-7 | The acceptance-only override: a distinct non-root uid, with a structural guard; the revocation reaches the companion and not `capability-engine` | In-session | **Met (local); CI pending.** The structural guard is met; the runtime half is local (§34.2); E-18 in CI is its own row | `test_acceptance_override.py` (6); TDD 4F.8 §34.2 |
| I-8 | D5: ≥ 10 independent Level-0 samples on never-observed paths, every latency reported | In-session | **Met (local); CI pending** | §1.1 |
| I-9 | D6: Level 1 and Level 2 through the real production trigger, correctly attributed | In-session | **Met (local); CI pending** | `ac8` |
| I-10 | D7: P-AC7-1 and P-AC8-1 in their own Playwright runs | In-session | **Built; not run** | `pr-checks.yml` l.768 and l.793 |
| I-11 | E-18, N-16, the remaining negative controls, flakiness | In-session | **Not met.** The remaining controls and the flakiness runs are done (§5); E-18 and N-16 in CI are not | §5 |

**Of 34 criteria: 6 are met; 17 are met on local evidence, with CI pending; 11 are not met.** The eleven:

- **AC-7, AC-8 and X-1** cannot be verified in this environment.
- **E-3, E-14 and E-18** are CI's by their own definition.
- **E-5 and I-11** have a local half that passes, and a CI half that has not run.
- **P-AC7-1 and P-AC8-1** have not run.
- **I-10** is built and not run.

The six met in this session are E-4, E-7, E-15, E-16, I-1 and I-3.

**AC-7 and AC-8 are not met, and not claimed.** No criterion was narrowed, and no threshold was changed.

### 2.1 E-15 and E-16's checks

- **Nothing on the boundary changed.** `git diff --name-only 1ccce7a 3bca553` touches none of `packages/nova-contracts`, `services/api-gateway`, `services/ws-gateway`, `services/action-engine`, `services/autonomy-engine`, `services/capability-engine`, `services/cognitive-state-engine`, `services/world-model-engine`, `services/memory-engine/src`, `packages/` or `apps/web-client/src`.
- **So stage 3 is byte-identical**, and the registry, `PUBLIC_TOPICS` and the gateway's prefixes are unchanged.
- **The tests that pin them passed** in this session's uncached run (§5): `nova-contracts` 171 passed, `api-gateway` 114, `ws-gateway` 110, `action-engine` 103, `autonomy-engine` 379, `cognitive-state-engine` 284.
- **`api-gateway` has no `/v1/perception` prefix**, so D2's route is unreachable from a browser.

---

## 3. Category 1 — implementation against the TDDs and ADRs

### 3.1 Deliverables (TDD 4F.8 §1.1)

| # | Requirement | Verdict | Where |
|---|---|---|---|
| D1 | The companion detects the loss of its OS permission on the watch root, and reports it | **Implemented as specified** (A-4F8-1 (a)) | `companion/sensors/src/lib.rs` l.106 `check_access`, l.118 `access_lost`, l.143 `concerns_access`, l.242 `next_event`. `companion/nova-companion/src/main.rs` l.102 `Permission`, l.170 `lose`, l.182 `report`, l.222 `submit`. `companion/nova-companion/src/intake.rs` l.39 `REVOCATION_ROUTE` |
| D2 | `running → failed` through the existing error path, published on 4F.7's path; later observations dropped | **Implemented as specified** (a1, a2) | `api/permission_revocations.py` l.76. `sensors/filesystem_sensor.py` l.177. `domain/sensor.py` l.87 (`kind`). `main.py` l.208 |
| D3 | Known-project correlation with a ratified population source | **Implemented as specified** (A-4F8-2 (a), a1, a2) | `config.py` l.69 and l.83. `domain/workspace.py` l.87. `events/handlers.py` l.70. `events/subscribed.py` l.22. `workspace_orchestration.py` l.130. `repository/models.py` l.97. `alembic/versions/0002_known_project.py` |
| D4 | The acceptance stack | **Superseded by an approved decision**: A-4FP-12 built it (§28.3). The override is §29.2's | `infra/docker/docker-compose.acceptance.yml` l.27. `pr-checks.yml` l.723 |
| D5 | The AC-7 harness | **Implemented as specified** (A-4F8-6) | `tools/e2e_acceptance.py` l.598 `measure_sample`, l.647 `ac7_latency`, l.798 `_check_samples`, l.914 `ac7_revocation`, l.1046 `_unexpected` |
| D6 | The AC-8 harness | **Implemented as specified** (A-4F8-4, A-4F8-7) | `tools/e2e_acceptance.py` l.341 `ac8`, l.410 `_ac8_run`, l.488 `_check_same_path`, l.541 `_ac8_denied` |
| D7 | Playwright for each criterion's browser-visible clause | **Implemented with a disclosed sequencing detail** (§35.2): two later invocations, and the revocation made by P-AC7-1 | `apps/web-client/tests/e2e/acceptance-ac7.spec.ts`, `acceptance-ac8.spec.ts`. `pr-checks.yml` l.768, l.793 |
| D8 | Structural controls over the harness | **Implemented as specified** | `tools/tests/test_e2e_acceptance.py` (35), `test_acceptance_override.py` (6) |
| D9 | Documentation and this record | **This record**, and §9 | — |
| §30 | The dispatch exception | **Implemented as ratified** | `workers/__init__.py` l.93 (`max_jobs = 1`), l.99 (`second=set(range(60))`) |

### 3.2 Implementation choices the TDD left open, each disclosed

- **The real-infrastructure dispatch test's long run** is produced by a real `SHARE` lock, not by seeding rows. One run reads at most 100 rows, and takes 0.25–0.29 s. Recorded as a test-construction correction in TDD 4F.8 §31.3.
- **P-AC7-1 makes the genuine revocation**, so that it shows `running`, then `failed` (§35.2).
- **The acceptance harness's `ac7-latency` presupposes P8's and `ac8`'s configuration**, as CI's order provides. Run alone, it fails §29.4.3 loudly (§36.4).
- **The AC-7 interval starts at the file's creation mtime**, the earlier of its two OS times (F-4F8-18, §36.2). That can only lengthen a sample.
- **Every acceptance phase records an unexpected error as a failed check**, and still prints its evidence (F-4F8-19, §37.2).

### 3.3 Ratified decisions, verified as built

| Decision | Built as | Verified by |
|---|---|---|
| A-4F8-1 (a): the companion detects, `perception-engine` transitions, through one route | D1, D2 | Cargo `revocation.rs` ×2; `test_api_permission_revocations.py` (8); `test_permission_revocation_real_infra.py` |
| A-4F8-1 (a1): exactly one additional internal route; `workspace-observations` frozen | `/v1/perception/permission-revocations` only | `git diff 1ccce7a 3bca553 -- services/perception-engine/src/nova_perception_engine/api/observations.py` is empty |
| A-4F8-1 (a2): no automatic recovery | The companion latches. A repeat report returns `transitioned: false` | `nova-companion/tests/revocation.rs`; the route tests |
| N-8: `failed` is never inferred from silence | Only `kind="permission_revoked"` fails the filesystem sensor | `test_revocation_is_the_only_failed_path.py` (2) |
| A-4F8-2 (a): operator bindings, made known over the bus | D3 | `test_known_projects.py` (12); `test_known_project_real_infra.py` (2) |
| A-4F8-2 (a1): persisted, current state only | `perception.known_project`, `ON CONFLICT DO NOTHING` | `0002_known_project.py`; the real-infra test |
| A-4F8-2 (a2): `world-model-engine` and `memory-engine` unchanged | No source change in either | §2.1's diff |
| A-4F8-4 (a): the production trigger | The harness publishes nothing, and drives no decision | `test_e13_*`; `ac8`'s `uuid5` attribution |
| A-4F8-6: ≥ 10 samples, OS mtime to the first World Model read, every figure, ≤ 5.0 s each | D5 | `test_the_ratified_figures`; N-1 … N-3 guards |
| A-4F8-7 (a): browser-visible clauses in a browser; the rest by independent SQL | D6, D7 | The specs; `test_every_sql_statement_is_a_select` |
| A-4F8-8 (a), restricted | The diff stays inside §28.8's surfaces | §7.3 |
| §28.7 (B), B2: the companion as `1100:<runner gid>`, acceptance-only | One key on one service | `test_acceptance_override.py` (6) |
| D-4F-1 reopened (§30): one-second cadence, `max_jobs = 1`, one replica | `ab8673b` | I-1, I-2, I-3 (§2) |

### 3.4 Deviation register

| Deviation | Classification | Authority |
|---|---|---|
| §30.3 item 2's *"seeds enough rows that one run naturally outlasts 1 s"* cannot be done. A real `SHARE` lock produces the long run | **Disclosed narrowing**, of test construction only. No behaviour changes | TDD 4F.8 §31.3, recorded at the time |
| D7: two Playwright invocations, not one; P-AC7-1 makes the revocation | **Disclosed narrowing** within A-4F8-7 | TDD 4F.8 §35.2 |
| The local acceptance stack differs from CI's: processes, not containers; in-memory graph and embedding backends; no gateways | **Disclosed** environment limitation | §6 |
| F-4F8-17, F-4F8-18 and F-4F8-19: fixes to test infrastructure, not to engines | **Defects found and fixed**, each recorded | TDD 4F.8 §35.3, §36.2, §37.2 |

**No undisclosed drift was found.**

### 3.5 ADRs

- **ADR-004 (engine isolation):** no cross-engine import. `uv run lint-imports`: **7 kept, 0 broken.** D3 learns of projects over the bus (`memory.long_term.created`), never by reading `memory-engine`'s store.
- **ADR-025 (identity server-side):** D2's body carries no identity (`extra="forbid"`). D3 records only `primary_user_id`'s memories.
- **ADR-033 (testing tiers):** the new real-infrastructure tests carry `real_infra`. The coverage gate is unchanged.
- **ADR-034:** no shared-package change. `nova_service_kit`'s outbox is untouched (§30.2).
- **No ADR is falsified.** No new ADR is needed: D-4F-1's reopening is recorded in TDD 4F §19's note and TDD 4F.8 §30, where D-4F-1 itself lives.

### 3.6 Citations in source

The source docstrings that cite documents were opened against them:

- `api/permission_revocations.py`: TDD 4F.8 §29.1 and TDD 4F §10 (the ownership matrix);
- `workers/__init__.py`: TDD 4F.8 §30;
- `docker-compose.acceptance.yml`: TDD 4F.8 §28.7 and §29.2;
- `tools/e2e_acceptance.py`: TDD 4F.8 §16, §29.1, §29.4.1–§29.4.4, §30, §31 and §36; TDD 4F §4.1.

**One false citation was found, and corrected in this record's commit.** `object_id_for_path`'s docstring in `tools/e2e_acceptance.py` cited TDD 4F §9 for the path-hash handle. §9 does not define it. §20.2, the perception subject contract, does: it defines `object_id` as a path hash. The docstring now cites §20.2. **The code is otherwise identical to the implementation SHA**: the two parse to the same AST, docstrings aside. The guards pass, 35 of 35.

---

## 4. Category 8 — contracts and codegen

- **`packages/nova-contracts/` is unchanged.** `git diff --stat 1ccce7a 3bca553 -- packages/nova-contracts/` is empty.
- **Codegen:** `generate_typescript.py` regenerated **118** files. `git status --short packages/nova-contracts` was empty afterwards, so drift is zero.
- **Event subjects:**
  - no subject was added;
  - `perception-engine` gains one **subscription** to an existing subject, `memory.long_term.created` (`events/subscribed.py` l.22);
  - its `failed` reports use 4F.7's existing `perception.sensor.health_changed`.
- **REST (SAD 15 §4 item 4):** one route was added to `perception-engine`, `POST /v1/perception/permission-revocations`. It is **additive**: no existing route, request or response changed. It is not fronted by `api-gateway`. It is documented in doc 11 §3's note and the engine's README.
- **No breaking change.**

---

## 5. Category 9 — tests, lint, types, imports

Run in this session with a clean tree, at `8e05b32`. The implementation SHA, `3bca553`, changes only `tools/e2e_acceptance.py`, its guard file and TDD 4F.8 (`git diff --stat 8e05b32 3bca553`: three files). So the rows that depend on `tools/` were re-run at `3bca553`. Every other row's inputs are byte-identical between the two.

| Gate | Command | Result |
|---|---|---|
| Lint + types (uncached) | `pnpm turbo run lint --force` | **32/32 tasks successful, 0 cached** |
| Tests (uncached) | `pnpm turbo run test --force` | **32/32 tasks successful, 0 cached** |
| `perception-engine` | (in the above) | ruff clean; mypy **40** source files; **242 passed**, 28 deselected; **domain coverage 99%** (338 statements, 2 missed) |
| `web-client` | (in the above) | **245 passed**; eslint clean. The two new specs are e2e, and run only under Playwright |
| Types, the TypeScript packages (uncached) | `pnpm turbo run typecheck --force` | **5/5 tasks successful, 0 cached** |
| Every other package | (in the above) | All green, with unchanged code: e.g. `autonomy-engine` 379, `cognitive-state-engine` 284, `nova-contracts` 171, `api-gateway` 114, `action-engine` 103 |
| Import boundaries | `uv run lint-imports` | **Contracts: 7 kept, 0 broken** |
| Scaffolding tools | `uv run pytest tools/tests -q` | **385 passed at `3bca553`** (380 at `8e05b32`). Among them: 17 dispatch-cadence, 6 override, 35 acceptance-harness and 27 P8 guards. `ruff check tools/` is clean |
| compose | `docker compose -f infra/docker/docker-compose.local.yml config --quiet` | **valid** (exit 0) |
| compose, with the override | `NOVA_ACCEPTANCE_COMPANION_GID=1001 docker compose -f …local.yml -f …acceptance.yml config --quiet` | **valid** (exit 0). The Compose CLI v5.1.1 is present; the daemon is not |
| Codegen drift | generate + `git status` | **118 files; none** |
| Cargo | `cargo fmt --all --check`; `cargo clippy --all-targets --locked -- -D warnings` | **Both clean** (exit 0) |
| Cargo tests | `cargo test --all-targets --locked`, each test binary run as uid 1100 | **41 passed in 8 binaries**: unit 9, `intake_client` 10, `real_filesystem` 8, `watch_error_redaction` 6, and the two `revocation` binaries 4 + 4 |
| Whitespace | `git diff --check 1ccce7a 3bca553` | clean |

`ruff format` is not a gate (protocol §9.2). The tool files this slice added are formatted; ten pre-existing tool files are not, and were not touched.

### 5.1 Negative controls

**Per slice, recorded at the time** in the TDD's implementation records. Each mutation was temporary and reverted, and each failed its named tests:

| Slice | Mutations | Where recorded |
|---|---|---|
| The dispatch change | `max_jobs = 1` removed; the cadence back to 10 s; `memory-engine`'s schedule moved; `replicas: 2`; a second worker service | TDD 4F.8 §31.4 |
| D1 | The access check removed; the binary never reports | §32.3 |
| D2 | No transition on a revocation; the route not transitioning (N-5); no `running` gate (N-6) | §32.3 |
| D3 | The known check skipped; a guess on a miss (N-13); the subscription dropped | §33.2 |
| The override | A second key; uid 1000; uid 0; `user:` in the base compose; a second step | §34.2 |
| The harness (N-1 … N-4, E-4) | A 5.5 s budget; a clock-aligned write; a discarded sample; a `POST` inside a sample; a non-`SELECT` statement; `retries` in P-AC7-1; `continue-on-error` | §35.4 |
| F-4F8-18 | `elapsed` from the write; no `O_EXCL`; the creation read after the write; N-3 against either mtime alone | §36.2 |
| F-4F8-19 | `ac8` without the catch-all; `_unexpected` passing its check; E-3 decided after the attribution checks; a tuple unpack restored | §37.2 |

**TDD 4F.8 §17, N-1 … N-16:**

| # | Status |
|---|---|
| N-1, N-2, N-3, N-4 | **Caught**, by the harness guards (§35.4, §36.2) |
| N-5, N-6, N-8 | **Caught**, by D2's tests (§32.3) |
| N-7 | **Built in**: E-6's write is by the workspace's owner, and is asserted to have succeeded |
| N-9 | **Caught**, as a real mutation on a fresh stack: no `AUTO_EXECUTE` policy for `read`. 24 named checks failed, among them every E-9 execution check (§37.1) |
| N-10 | **Built in**: it is E-17's own denial run, which every `ac8` run performs |
| N-11 | **Caught**, as a real mutation on a fresh stack: T1 authored `moderate`. 26 named checks failed, among them E-8, E-9, E-10 and E-11 (§37.1) |
| N-12 | **Carried by** E-9's `completed` assertion, which does not depend on the decision's outcome. 4F.P's NP-1 negative-controlled the `failed → EXECUTE` mapping itself. Not separately mutated in this slice |
| N-13 | **Caught**, by D3's tests (§33.2) |
| N-14, N-15 | **Carried by** the unchanged pinned tests (§2.1) |
| N-16 | **Local analogue caught** (§34.2): with the override dropped, E-18's companion half fails. **The CI form needs a run without the override, and is pending** |

### 5.2 Flakiness (≥ 10 runs)

| Tests | Runs | Result |
|---|---|---|
| `test_outbox_dispatch_cadence_real_infra.py` (3) | 10, at `ab8673b` | **10/10 green** (§31.4) |
| Cargo `revocation.rs` ×2 and `real_filesystem.rs` | 10 each, at `6ba6f27` | **10/10 each** (§32.3) |
| `test_permission_revocation_real_infra.py` | 10, at `fa9217a` | **10/10** (§32.3) |
| `test_known_project_real_infra.py` | 10, at `4648f63` | **10/10** (§33.2) |
| The four acceptance phases, each cycle on a fresh stack | 10, before the fix | **P8 10/10, `ac8` 10/10, `ac7-latency` 9/10** (F-4F8-18), `ac7-revocation` 7/10 checks in 10/10 (Docker-only) |
| The same, after the fix | 10, at `8e05b32` | **P8 10/10, `ac8` 10/10, `ac7-latency` 10/10**, `ac7-revocation` 7/10 checks in 10/10 (Docker-only) |
| The same, at the implementation SHA | 10, at `3bca553` | **P8 10/10, `ac8` 10/10 (55 checks), `ac7-latency` 10/10**, `ac7-revocation` 7/10 checks in 10/10 (Docker-only) |

**AC-7's latency is exempt from "must be green ten times"** (§17): its outcome is the measurement. Every one of its 310 local figures was ≤ 5.0 s anyway.

---

## 6. Category 10 — real infrastructure

1. **Docker: NOT available.** `docker info` fails with *"failed to connect to the docker API at unix:///var/run/docker.sock … no such file or directory"*.
2. **What ran instead, disclosed as such:** PostgreSQL **16.13**, `nats-server` **v2.10.7** and Redis **7.0.15**, on kernel 6.18.44.
   - **For the `real_infra` tiers:** a scratchpad-only pytest plugin, never committed, pointed `nova-testkit`'s container fixtures at them, with a fresh database per run.
   - **The permission-changing tests ran as uid 1100** via `setpriv`, because root bypasses permission checks. As root they fail loudly, which was observed.
   - **For the acceptance phases:** a scratchpad-only script ran the engines from this tree as processes, with the real companion binary as uid 1100 and a workspace owned by uid 1001, mode 0755.
   - **The local differences:**
     - processes rather than containers;
     - `world-model-engine` uses the in-memory graph store, and `memory-engine` the in-memory embedding backend;
     - there are no gateways and no browser;
     - `capability-engine` runs as root, so E-18's capability half is not meaningful locally.
   - **This is not the CI environment.** CI's containers remain authoritative.
   - **One interruption, disclosed.** The container restarted once during this session, after the first flakiness run had finished. The local PostgreSQL cluster was then started again from its existing data directory. No result straddles the restart.
3. **Results, local, in this session**, at `8e05b32`, whose `services/` and `companion/` equal the implementation SHA's:

   | Tier | Result |
   |---|---|
   | `perception-engine -m real_infra`, as uid 1100 | **28 passed** (242 deselected), in 51 s |
   | Cargo, every test binary as uid 1100 | **41 passed**, 8 binaries (§5) |

4. **The `real_infra` tests this slice added**, by name:
   - `test_outbox_dispatch_cadence_real_infra.py` (3): the drain, the stall, and the control at arq's default `max_jobs`;
   - `test_permission_revocation_real_infra.py` (1): the real companion binary, a real `chmod`, real uvicorn, PostgreSQL and NATS;
   - `test_known_project_real_infra.py` (2): a real `memory.long_term.created` over real NATS, and the real companion writing under a declared, an inert and an undeclared folder.
   - **Unchanged and still passing:** `test_companion_intake_real_http.py` (8), `test_repository_real_postgres.py` (7), `test_sensor_health_real_infra.py` (2) and `test_workspace_real_postgres_e2e.py` (5).
5. **What each covers.** **Every `perception-engine` real-infra test exercises a module this slice changed**: the outbox worker settings, the lifespan and its new subscription, the sensor's error path, the workspace orchestration's project correlation, or the repository and its migration chain, which now includes `0002`. The four unchanged files were not modified (`git diff --name-only 1ccce7a 3bca553 -- services/perception-engine/tests/integration/` lists only the four new files).
6. **Matrix.** `perception-engine` has a row in `.github/workflows/real-infra-checks.yml` (l.63). This slice did not change that workflow. The Cargo tier runs in `pr-checks.yml` (l.93–95) as the runner's own, non-root user.
7. **Stand-ins.** The real-infra tests use none on the paths they assert. The known-project test's producer is bound as `memory-engine` (TDD 4F §16.1 control 7's precedent), and is labelled in the module docstring.
8. **Unverified.** *These 28 `perception-engine` real-infra tests, the Cargo tier, and the four acceptance phases have not been executed in CI's containers for this change. `Real-Infrastructure Checks` is non-blocking. The e2e job is staged and non-blocking (F-4F8-12). Neither has reported against `3bca553`, because neither has run on this branch (§7.2).*

---

## 7. Category 11 — PR, branch, commit and CI evidence

### 7.1 Branch and commits

**`phase-4f8`, cut from `phase-4` @ `1ccce7a`.** The first-parent history:

| Commit | What |
|---|---|
| `4d0e42e` | Merge `phase-4f8-tdd`: the ratified TDD history, unchanged |
| `ab8673b` | The D-4F-1 dispatch change |
| `6ba6f27` | D1 |
| `fa9217a` | D2 |
| `4648f63` | D3 |
| `5a80c9a` | The acceptance-only override |
| `afff6b8` | D5–D8: the harness, the specs, the CI steps, the guards; F-4F8-17 |
| `8e05b32` | F-4F8-18's fix; TDD §36; the dated documentation notes |
| `3bca553` | N-9 and N-11 as real mutations; F-4F8-19's fix; TDD §37. **The implementation SHA** |
| *(this record)* | Documentation, plus one corrected docstring citation in `tools/e2e_acceptance.py` (§3.6). No behaviour changes |

**Every factual claim in each message was re-checked in this session.**

The counts were re-run at each commit, in a temporary worktree:

| Commit | Claims checked | Result |
|---|---|---|
| `ab8673b` | The cadence file 16, worker settings 3, the real-infra file 3. The file's count is 17 today only because it is parametrized over compose files, and `5a80c9a` added one. The run's own figures (7 runs, 0 overlaps, 3.227 s, 466 deliveries) are §31.4's recorded run. The file passed again in this session (§6) | **True** |
| `6ba6f27` | The 4 + 4 new tests are true. **"The 24 existing ones" is false: there are 33.** That was corrected additively in `fa9217a`'s message and TDD 4F.8 §32.3, because a pushed message cannot be amended | **One false count, corrected** |
| `fa9217a` | +4 sensor tests (12 → 16), +1 lifecycle (16 → 17), 2, 8; 226 passed, 26 deselected, 99%; 26 `real_infra` | **True**, re-run at the commit |
| `4648f63` | The folder match 5 (replacing 3), the orchestration 3 (replacing 1), `test_known_projects.py` 12, the real-infra file 2; 242 passed, 28 deselected, 99%; 28 `real_infra`; `tools/tests` 342 | **True**, re-run at the commit |
| `5a80c9a` | The override guard 6; `tools/tests` 349 | **True**, re-run at the commit |
| `afff6b8` | The harness guards 29. The local evidence: P8 67/67, `ac8` 54/54, `ac7-latency` 70/70 with its ten samples, and the revocation 7/10 | **True**, against the run logs |
| `8e05b32` | The flakiness figures; 114 of 200 and 0 of 200; the five mutations | **True**, against the run logs |
| `3bca553` | 5 new tests (30 → 35); 385 `tools/tests`; N-9's 24 and N-11's 26 named failures | **True** |

### 7.2 CI

- **No CI run exists for `phase-4f8` at any SHA.**
  - `pr-checks.yml` triggers on `pull_request`, on `push` to `main`, and on `workflow_dispatch`.
  - `real-infra-checks.yml` and `build-and-scan.yml` do not run for a push to this branch either. `real-infra-checks.yml`'s daily schedule runs on the default branch only.
  - **A `workflow_dispatch` from this session was refused, HTTP 403**, both through the GitHub MCP tool and through `gh api`.
- **So nothing in this record is CI evidence.** A local pass is never reported as CI evidence (protocol §11.2).
- **What CI must show, at the exact SHA**, before AC-7 or AC-8 can be claimed:
  - `PR Checks`: every job green, including the e2e job's P8 step and the five 4F.8 steps (`pr-checks.yml` l.757–813). That covers P-AC8-1, AC-7's ten samples, each at or below 5.0 s, P-AC7-1, and E-5, E-6 and E-18;
  - `Real-Infrastructure Checks`: `perception-engine`'s 28;
  - `Build & Scan`, with Trivy. No Dockerfile changed in this slice.
- **The PR that would carry this is the user's decision** (§8.4).

### 7.3 Boundary audit (`git diff --name-only 1ccce7a 3bca553`, plus this record's commit)

**A-4F8-8's governed surfaces, and the files in each:**

| Surface | Files |
|---|---|
| `companion/` | 7: `sensors/src/lib.rs`, `sensors/tests/revocation.rs` (new), `sensors/tests/real_filesystem.rs`, `nova-companion/src/main.rs`, `nova-companion/src/intake.rs`, `nova-companion/tests/revocation.rs` (new), `nova-companion/README.md` |
| `services/perception-engine/` | 29: source, one Alembic migration, tests and the README |
| `infra/docker/` | 3: `docker-compose.local.yml` (a comment and one pass-through), `docker-compose.acceptance.yml` (new), `README.md` |

**Recorded, not governed** (A-4F8-8):

- `tools/`: `e2e_acceptance.py` (new), `e2e_real_execution.py`, and four test files;
- `.github/workflows/pr-checks.yml`;
- `apps/web-client/tests/`: the two new specs.

**Documentation outside those surfaces, disclosed:**

- `services/memory-engine/README.md`: one dated note on the new consumer of `memory.long_term.created`. This is not `src/`, so SAD 15 §4 item 1 is not engaged;
- `docs/architecture/07`, `09`, `10`, `11` and `14`: dated notes;
- `docs/design/phase-4/`: `00-master-scope.md`, `06-tdd-4f-…`, `11-tdd-4f7-…` and `12-tdd-4f8-…`.

**No other engine's `src/`, no package, no contract and no Dockerfile changed.** SAD 15 §4 item 1 holds within the A-4F8-8 exception: `perception-engine` is the one engine whose `src/` changed.

### 7.4 SLOC

The method is the 4E methodology: `cloc` **v2.06** `--skip-uniqueness --quiet` over a pristine `git archive`, with tests excluded. The scopes are 4F.P's (§7.4 of its record).

| Scope | `1ccce7a` | `8e05b32` (= `3bca553`) | Δ |
|---|---|---|---|
| Comparable (`services/*/src`, `packages/*/src`, `services/*/alembic/versions`) | 37,797 | 37,966 | +169 |
| Wider | 43,138 | 43,307 | +169 |
| Full | 47,171 | 47,340 | +169 |
| `companion/`, excluding its `tests/` | 646 | 844 | +198 |
| **4F scope** | **47,817** | **48,184** | **+367** |

- **The base reproduces 4F.P's recorded head exactly**, and TDD 4F.8 §23's re-verified base of 47,817.
- **The +367 is inside §23's estimate of 180–450.** The harness, compose and tests count 0. `3bca553` changes only `tools/` and a TDD, so its figures equal `8e05b32`'s.
- **Headroom to 50,000: 1,816. The gate is not crossed.** The ~30,000 reminder was crossed in an earlier phase, and was surfaced then.

---

## 8. Category 13 — findings, gaps and decisions requiring approval

### 8.1 Findings of this slice

| # | Finding | Status |
|---|---|---|
| **F-4F8-17** | P8's V-7 (a1) relied on the 10-second dispatch to space its second modification past the 1-second debounce | **Fixed** in the P8 driver (`afff6b8`), and drift-guarded. No engine changed (TDD 4F.8 §35.3) |
| **F-4F8-18** | The AC-7 harness started its interval at the write's mtime, while the companion may report the creation's | **Fixed** in the harness (`8e05b32`), and guarded. No engine changed (§36.2) |
| **F-4F8-19** | A failing `ac8` run could end on an unpacking error before evaluating E-10 and E-11, or printing its evidence. Found by N-11 | **Fixed** in the harness (`3bca553`), and guarded. Every phase now records any error as a failed check and still prints its evidence (§37.2) |

**The earlier findings, where this slice leaves them:**

| # | Status |
|---|---|
| F-4F8-1, F-4F8-2 | Resolved by 4F.P (§28.5) |
| F-4F8-3 (risk classified twice) | Unchanged by design. E-11 checks both |
| F-4F8-4 (no identity source in CI) | Answered by A-4FP-11's configuration (§28.2). E-17 is the control |
| F-4F8-5 (`known_projects` had no population path) | **Resolved by D3**, once merged |
| F-4F8-6 (the World Model object holds no `project_id`) | Unchanged by design (A-4F8-2 (a2)). E-2 reads the observation's payload |
| F-4F8-7, F-4F8-15 (no revocation path; the silent drop) | **Resolved by D1 and D2**, once merged |
| F-4F8-8 (the acceptance stack could not run AC-7) | **Resolved locally.** CI pending |
| F-4F8-9 (no browser surface for the core facts) | Unchanged by design (A-4F8-7 (a)) |
| F-4F8-10 | **OPEN, as A-4F8-9.** It blocks 4F's GO |
| F-4F8-11 (stale scope statements) | Addressed by TDD 4F.8's preparation (§21.3): the 2026-09-27 dated notes in master scope §5 and on §17's 4F.7 row. This slice's notes (§9) settle the 10-second statements its own dispatch change made stale |
| F-4F8-12 (both acceptance workflows non-blocking) | **OPEN.** Disclosed. 4F closure cites their conclusions at the exact SHA |
| F-4F8-13 (shared credentials) | **Resolved for the acceptance run** by the override. The production model is unchanged, as ratified |
| F-4F8-14 (every new path starts an initiative) | Handled by attribution by `subject_id` |
| F-4F8-16 (P8 services start after the golden path) | Handled: the specs run in their own later invocations |

### 8.2 CF-9, CF-10 and CF-11: all OPEN

This slice closes none of them, and claims nothing toward their closure beyond the local evidence. CF-11 claim 3 rests on E-8, E-9 and E-13 in CI. Claim 4 is 4F closure's.

### 8.3 Residual risks, stated

- **`MTIME_GRANULARITY_SECONDS`, 10 ms.** A CI kernel with a coarser clock could exceed it, and N-3 would then fail with its figures (TDD 4F.8 §36.5). It is not widened on speculation.
- **The single-replica constraint.** Multi-replica dispatch is not safe, and is not claimed (§30.2). It is enforced structurally.
- **No automatic recovery** after a revocation (A-4F8-1 (a2)), as ratified.

### 8.4 Decisions requiring the user's approval

1. **Whether to open a PR, `phase-4f8` → `phase-4`, so that CI runs.**
   - **The documents consulted:**
     - protocol §11.1: no PR unless asked;
     - TDD 4F.8 §21.1: CI at the exact implementation SHA is required;
     - `pr-checks.yml` l.1–30: it runs only for a pull request, a push to `main`, or a dispatch.
   - **The options:**
     - (a) open a PR, possibly as a draft, which runs all three workflows at its head;
     - (b) dispatch the workflows from an account permitted to;
     - (c) leave 4F.8 unverified in CI.
   - **Recommendation: (a), as a draft.** It is the only path available from this session. The PR description must cite the Bible Parts A-4F8-8 names (SAD 15 §4 item 5).
   - **Blocked until decided:** AC-7, AC-8, E-3, E-14, E-18, P-AC7-1, P-AC8-1 and N-16 in CI; 4F.8's completion; and 4F closure.
2. **How to run N-16 in CI.** It needs one acceptance run with the override removed, and the revocation is terminal for a stack.
   - **The options:**
     - (a) a temporary commit on the PR, reverted afterwards;
     - (b) accept the local analogue (§34.2).
   - **Recommendation: (a)**, after the first green run, so that the control's failure is attributable to the override alone.

**Nothing was decided unilaterally.**

---

## 9. Category 14 — documentation updated by this slice

| Trigger (§14.1) | Document | Change | Additive? |
|---|---|---|---|
| A REST endpoint | `docs/architecture/11-api-architecture.md` §3 | Dated note: the companion's engine-level `/v1/perception/*` routes, including D2's | **Yes** |
| | `services/perception-engine/README.md` | Owned APIs; the `failed` path; Known projects; Outbox dispatch | **Yes** |
| A new subscription; the dispatch interval | `09-event-bus-architecture.md` | Dated note: no new subject (120 and 18); `perception-engine` consumes `memory.long_term.created`; the filesystem sensor's `failed` on `perception.sensor.health_changed`; dispatch every second, serially | **Yes** |
| | `10-inter-engine-communication.md` | Dated note: the two new flows, `memory-engine` → `perception-engine` over the bus, and the companion's revocation report | **Yes** |
| | `services/memory-engine/README.md` | Dated note: the new consumer | **Yes** |
| A table and a migration | `07-database-architecture.md` | Dated note: `perception.known_project`, migration 0002 | **Yes** |
| The deployment surface | `14-deployment-architecture.md` | Dated note: the acceptance-only override. The single-replica constraint is stated in the compose comment and the README | **Yes** |
| | `infra/docker/README.md` | The override, and the bindings | **Yes** |
| Companion behaviour | `companion/nova-companion/README.md` | A revocation section | **Yes** |
| A CI workflow | `pr-checks.yml` comments | The steps' own comments | n/a (code) |
| Design documents | TDD 4F.8 §30–§36 | Implementation records | **Yes** |
| | TDD 4F §15, §16.2, §18; master scope (AC-7's note and slice status); TDD 4F.7 §3 and §15 | Dated notes on the stale 10-second statements, and on K-2 and K-3 (§36.6) | **Yes** |
| | TDD 4F.8 §37 | N-9, N-11 and F-4F8-19 | **Yes** |
| | Master scope §17, TDD 4F.8's row | Dated status note: what `phase-4f8` built, this record, no CI, no PR. **In this record's commit** | **Yes** |

**Before/after.** Every change to an existing document is an inserted, dated note at the place named. No existing sentence was edited. The *before* at each location is the unchanged surrounding text, and the *after* is that text plus the note (see the commits' diffs).

**Inspected and found accurate, or N/A:**

- **`17-cicd-pipeline.md`** describes `pr-checks.yml` at file level, not the e2e job's steps. No gate was added, so no change is needed. The same holds for `15-development-workflow.md` §4.
- **`16-testing-strategy.md`, ADR-033:** N/A. There is no new tier or marker.
- **`20-engine-responsibility-boundaries.md`:** ownership is unchanged. The sensor lifecycle stays `perception-engine`'s, and capture stays the companion's (TDD 4F §10). Its staleness about `cognitive-state-engine` is L-20's.
- **`02-repository-and-folder-structure.md`, workspace globs, `[tool.importlinter]`, CI matrices:** N/A. There is no new package, engine or service.
- **`build-and-scan.yml`:** no Dockerfile changed.
- **The observability docs:** N/A. No metric was added. D2 logs `sensor_permission_revoked`, and D1 logs `permission_revoked` and `revocation_reported`.

**SAD 15 §9.1:** no new subsystem is introduced. For the new surfaces:

| Item | Status |
|---|---|
| Architecture documentation | Present: TDD 4F.8 and the notes above |
| Sequence | Present: TDD 4F.8 §13.1–§13.3 |
| API documentation | Present: doc 11's note and the README |
| Unit and integration tests | Present (§5, §6) |
| Failure scenarios | Present: the revocation, the miss, the stall, the denial |
| Logging | Present: the decision points above |
| Performance benchmarks | **None.** AC-7's latency is measured by the acceptance run, not benchmarked |
| Observability metrics | **None added** |

---

## 10. Deferred-obligations ledger (protocol §0.2)

### 10.1 Settled by this slice, once merged

| Row | How |
|---|---|
| **L-13** (`known_projects` population) | D3 (A-4F8-2). It settles on merge into `phase-4` |
| **L-26** (TDD 4F.8's re-verification against merged 4F.P) | Done in `f28e373` (§28). TDD 4F.8 §28.12 keeps it OPEN in the 4F.P record until this branch reaches `phase-4` |

### 10.2 Still open

**L-1 … L-6, L-8 … L-11, L-14 … L-25, L-27 and L-28** are carried forward **unchanged**. That includes:

- L-1 (4F's Gate Review);
- L-4 (the roadmap's 4F row, which still reads *"2 of 8 slices merged"*);
- L-22 and L-27 (status in health, roadmap and README).

### 10.3 Opened by this slice

| Row | Status | Obligation | Owner | Blocks 4F.8? |
|---|---|---|---|---|
| **L-29** | OPEN | CI at the implementation SHA, with the e2e job's five 4F.8 steps green and their figures recorded here. That includes AC-7's samples, P-AC7-1, P-AC8-1, E-18, and N-16 in CI (§8.4) | 4F.8, after the user's PR decision | **Yes** |
| **L-30** | OPEN | Project Health, roadmap and top-level README status for 4F.8 (categories 4, 5 and 7) | 4F closure | No |

---

## 11. Final status

- **Implementation:** D1 … D8 and the dispatch exception, complete against TDD 4F.8 §29 and §30, as ratified.
- **D9:** controls (§5), documentation (§9) and this record. Done locally.
- **Local verification:** complete, with real numbers (§5, §6).
- **The acceptance phases, locally:** 30 fresh-stack cycles. **310 AC-7 samples, from 0.059 s to 1.083 s, none over 5.0 s.** AC-8's runs passed in 30 of 30. The last ten cycles ran at the implementation SHA. Every phase passed, except the revocation's three Docker-only checks.
- **Negative controls:** caught in every case run (§5.1), including N-9 and N-11 as real mutations on fresh stacks. N-16's CI form is pending.
- **Findings:** F-4F8-17, F-4F8-18 and F-4F8-19, all in test infrastructure, all fixed and guarded. No engine defect was found.
- **Real infrastructure:** substitute local services. **Docker is unavailable.**
- **CI: no run exists for this branch.** The e2e job, which carries AC-7 and AC-8, runs only for a PR (§7.2).
- **AC-7 and AC-8: NOT met, and not claimed.**
- **For decision:** the PR (§8.4).
- **A-4F8-9, CF-9, CF-10 and CF-11:** OPEN.
- **Gate verdict:** none. This is a slice (§0).
- **`main` and `phase-4`:** untouched. **No PR. Nothing merged.**
- **4F.8 is NOT complete.** It stays incomplete until four things hold:
  - L-29 is settled: CI's conclusions at the exact head SHA are recorded here, with AC-7's samples and both specs;
  - the PR is reviewed;
  - the merge is explicitly authorized;
  - it is merged.
- **Phase 4F is NOT complete**, and completing 4F.8 would not complete it: A-4F8-9 and 4F closure (L-1 …) remain.

### 11.1 What was not verified, and why

- **The acceptance run in CI's containers:** AC-7's measured samples, E-5's container log, E-18 and N-16. No Docker daemon here, and no CI run on this branch.
- **P-AC7-1 and P-AC8-1 in a browser.** The local stack has no gateways, and no CI run exists.
- **The real-infra and Cargo tiers in CI.** They ran only on local substitute services, as a non-root user via `setpriv`.
- **The CI runner's own gid and kernel.** The override's group-bit design, and the 10 ms mtime allowance, are verified only on this kernel (6.18.44).
- **SAD 15 §4 items 2 and 5.** They are per-PR, and no PR exists.
