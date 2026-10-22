# Phase 4 — Master Closure Matrix

**Date:** 2026-10-17, **revised 2026-10-18 and 2026-10-19**. **Base:** `phase-4` = `a7d52c16eb704ea95d113f70a610f83d54710805`.
**Protocol:** [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md),
read in full from `origin/main` (sha256 `21185dd1…`, 1131 lines; identical on `phase-4`).

## 0. What this document is, and is not

It **is** the traceable work plan protocol §0.2 asks for:

- one row per open Phase 4 obligation, each with its requirement, source,
  evidence, classification, blocking scope, action and status;
- the reconciliation of the earlier inventories' counts;
- the decisions that only the owner can make.

It **is not:**

- the 4F Gate Review (L-1), the Phase 4 Gate Review (X-11), or any slice's
  completion declaration;
- an approval of anything. Every DEFER, ACCEPT RISK and N/A below is a
  **proposal**, until the owner approves it in a recorded decision.

**It closes nothing by wording.** A row is FIXED only where code or tests
changed and CI ran on the exact head. Even then it stays **pending** until the
change is merged, which needs the owner's authorization. Nothing is merged
here.

**Labels are this document's own, and some collide.** *(Added 2026-10-18;
mapping added 2026-10-19.)* X-nn, N-nn and R-nn are closure-matrix labels. Their
qualified form is `CM:X-nn`, `CM:N-nn` and `CM:R-nn`. This document keeps the
short form, and **nothing is renamed**, because PRs and records already cite the
short form. Outside this document, use the qualified form.

Thirteen are spelled exactly like a ratified label with another meaning:

| Qualified | Here | Same spelling in a source, a different item |
|---|---|---|
| CM:X-10 | SLOC method, Option A or B | TDD 4F.5 X-10: `autonomy-engine` publishes `action.execute` and nothing else |
| CM:X-11 | The Phase 4 Gate Review | TDD 4F.5 X-11: the decision log records the Level-2 execution |
| CM:X-12 | `phase-4.md` and its master row | TDD 4F.5 X-12: CF-10 is still unresolved |
| CM:X-13 | 4B health records say "not merged" | TDD 4F.5 X-13: a dispatch with no reply in 15 s becomes a timeout |
| CM:X-14 | Roadmap Phase 4 status | TDD 4F.5 X-14: a Level-2 request missing an execution field stays a suggestion |
| CM:X-15 | Pre-4F README claims | TDD 4F.5 X-15: `permits_execution` is eligibility, not permission (cited in `domain/decision.py`) |
| CM:X-16 | The protocol's stale counts | TDD 4F.5 X-16: trust `UNAVAILABLE` is never coerced into a pass |
| CM:X-17 | SAD 15 §1 and §3 versus the repository | TDD 4F.5 X-17: `action.execute` is request/reply (cited in `test_autonomy_boundaries.py`) |
| CM:N-10 | The rate-limiter deviation | TDD 4F.8 N-10: remove A-4F8-5's identity-confidence row |
| CM:N-11 | The coverage gate was never enforced | TDD 4F.8 N-11: author `moderate` risk |
| CM:N-12 | The 401 first-run flow was not built | TDD 4F.8 N-12: accept a `failed` EXECUTE as success |
| CM:N-13 | The 429 retry hint | TDD 4F.8 N-13: a correlation miss attaches a guessed `project_id` (cited in `perception-engine`'s tests) |
| CM:N-14 | 4B's TDD was never written or waived | TDD 4F.8 N-14: add a subject to `PUBLIC_TOPICS` |

X-01 … X-09, N-01 … N-09 and R-01 … R-05 differ from TDD 4F.5's X-1 … X-9,
TDD 4F.8's N-1 … N-9 and master scope's risks R-1 … R-6 only by the leading
zero, and are qualified the same way.

Where the short form is already cited outside this document:

| Where (PR) | As written | Means |
|---|---|---|
| `api-gateway` `domain/rate_limit.py` (#43) | *"closure matrix (N-10)"* | CM:N-10 |
| `autonomy-engine` README and `api/autonomy.py` (#45) | N-02 | CM:N-02 |
| `pr-checks.yml` and doc 16 (#48) | *"finding N-11"* | CM:N-11. Not qualified there |
| `perception-engine` `test_workspace_orchestration.py` (#49) | *"(N-13)"* | **TDD 4F.8 N-13**, not CM:N-13 |
| `infra/observability/prometheus.yml`, `tools/tests/test_prometheus_targets.py` (#51) | X-06 | CM:X-06 |
| `nova-contracts` `test_memory_events.py` (#52) | N-08 | CM:N-08 |
| `docs/design/phase-4/README.md` (#53) | N-05, N-14 | CM:N-05, CM:N-14 |

**Terms kept apart throughout.**

| Term | Meaning |
|---|---|
| Technical review | A recorded examination of a change. Here, always by the implementing agent, so **not independent** |
| User approval | A decision recorded as the owner's |
| GitHub review approval | An approving review on the PR: **none exists on any Phase 4 PR** |
| Merge authorization | The owner's instruction to merge one specific PR |

**Revision, 2026-10-18.** This is still an unmerged draft, so it is
corrected in place; what changed is listed here so that nothing changes
silently:

- §1.2 now gives final CI for #51, #52 and #53, and the flaky retry at #43's
  head. §1.5 is new: review findings against the open PRs.
- §2 is rewritten. The earlier tally (13 / 3 / 31 / 4 / 42 / 2) could not be
  re-derived from the row classes, and "counted row by row" was wrong: §3 has
  76 data rows holding 101 IDs.
- FP-18 is no longer an alias of L-18 (§3.3, §3.8).
- X-03 (C-7), N-01 and N-11 are corrected. §3.8 adds R-01 … R-05 and FP-18.
- §5 records the failure-mode mapping (B2); §3.4 records the scope check (B3).
- §7 gives the merge order the prepared amendments require.

**Revision, 2026-10-19.** Also corrected in place:

- §0 maps the labels whose spelling collides with TDD 4F.5's and TDD 4F.8's,
  and says what each short-form citation outside this document means. Nothing
  is renamed.
- §2.1 said three items have no ID; six have none. §2.3 counts items, not IDs.
- §2.2: *"phase-4f preserved"* is a content of L-1 (a 4F closure condition),
  not of the L-9 and L-10 sweeps. The count is unchanged.
- The line above said *"R-01 … R-06"*; §3.8 held R-01 … R-05 and FP-18.
- §4 adds D-C3, which §3 cited and §4 lacked, D-A15 (R-01's policy) and D-A16
  (#42), and restates D-A1 … D-A6's recommendations, which pointed outside the
  repository.
- §7: #42's place and *"with 0 flaky"* are not settled; each waits on a
  decision.

Everything new here was produced by the implementing agent, so it is **not
independent** (§0).

---

## 1. Baseline, verified 2026-10-16/17

### 1.1 Refs

| Ref | SHA | Note |
|---|---|---|
| `main` | `7e273e6` | Unchanged |
| `phase-4` | `a7d52c1` | PR #41's merge. Nothing merged since |
| `phase-4f8` | `1b3ccbd` | Retained |
| `phase-4f8-tdd` | `aff01ae` | Retained |
| `phase-4f8-post-merge` | `6b0093b` | PR #42's head |

### 1.2 Open PRs into `phase-4`, all drafts, none merged

Each row's CI is the conclusion of every check run **at that exact head**.
Implementation PRs are one engine each, or platform-only (SAD 15 §4 item 1).

| PR | Head | Scope | What it settles | CI at the head |
|---|---|---|---|---|
| #42 | `6b0093b` | docs | 4F.8 post-merge record (L-13, L-26) | **40/40** (runs 38462664060, …4034, …3775) |
| #43 | `d7876cb` | `api-gateway` | §9.1 items 3, 9, 10 (metrics); N-03; N-10 disclosed; N-13 server half | **40/40** (38976279923, …973, …280016). **The E2E job passed only on a retry**: one flaky test, `cognitive-state-panel.spec.ts:154` (run #150, job 117226387232; R-02) |
| #44 | `4f27c7c` | `ws-gateway` | §9.1 items 3, 4, 6, 9, 10; L-8; N-04 | **41/41**, including the new real-NATS job: *"4 passed"* (job 117215426434) |
| #45 | `22ef074` | `autonomy-engine` | §9.1 items 3, 4, 9, 10; L-19; N-02 (log line only) | **40/40** (38978730212, …245, …411) |
| #46 | `ab0ac0f` | `cognitive-state-engine` | §9.1 items 3, 10; F-4FP-8 verified | **40/40** (38974862332, …378, …381) |
| #47 | `7b9d020` | `apps/web-client` | N-12, N-13 client half, F-4FP-10 | **39/40.** The one failure is F-4FP-6's flake in `perception-engine`, which #47 does not touch (run 38976046385); #49 fixes it. Re-running the job is refused to this session (403) |
| #48 | `ab4e667` | CI + doc 16 + `world-model-engine` tests | N-11 | **40/40.** The log shows *"Required test coverage of 85.0% reached"* for all 19 measured packages (job 117229308999) |
| #49 | `b4b28d9` | `perception-engine` tests | F-4FP-6 | **40/40** (38977924060, …138, …192) |
| #50 | `0ca0b7b` | `action-engine` | L-16; L-15 (log line only) | **40/40** (38978396982, …7021, …7119) |
| #51 | `65c2683` | infra + `tools/tests` | X-06 | **40/40** (PR Checks #155, run 39069763759) |
| #52 | `5b3a61e` | `nova-contracts` tests | N-08 | **40/40** (PR Checks #156, run 39069850595) |
| #53 | `2e384cb` | docs | N-05; this document; doc 14 | **40/40** (PR Checks #157, run 39070238888) |

**Combined:** all ten implementation PRs merge onto `phase-4` together **with
no conflict**. This was checked in a scratch worktree and never pushed. **No
CI has run on that combination**, and none can run on `phase-4` itself
without a dispatch (R-05).

Every head above has 0 GitHub reviews. The PR Checks run of each head is the
one in the run list (`list_workflow_runs`, 2026-10-17); only #43's contains a
flaky test.

### 1.3 SLOC

The method is the 4E/4F method, reproduced first: `cloc` 2.06
`--skip-uniqueness --quiet` over a pristine `git archive`, tests excluded.
The scopes are those of the 4F.4 record.

| Tree | Comparable | Wider | Full | 4F scope | Headroom to 50,000 |
|---|---|---|---|---|---|
| `c04eaff` (the 4F.8 record's figure, reproduced) | 37,966 | 43,307 | 47,341 | **48,185** | 1,815 |
| `phase-4` `a7d52c1` | 37,966 | 43,307 | 47,341 | **48,185** | 1,815 |
| All ten PRs merged (scratch) | 38,566 | 43,907 | 47,972 | **48,816** | **1,184** |

Per PR: #43 +163, #44 +149, #45 +143, #46 +105, #50 +40, #47 +31; #48, #49,
#51 and #52 add 0 (tests and configuration). **The gate is not crossed.**

### 1.4 Local evidence this pass

These are local runs, **not CI evidence**. Real infrastructure means Postgres
16, `nats-server` and Redis run as processes, because Docker is unavailable.

- **Default tiers:** every changed package's default tier passes.
- **Real infrastructure:**
  - `cognitive-state-engine` 58;
  - `action-engine` 27;
  - `autonomy-engine` 63;
  - `ws-gateway` 4, and 10 of 10 on repetition;
  - `perception-engine`'s edited e2e file 5/5.
- **Coverage gate:** all 32 turbo test tasks pass under the gate that #48
  enforces.
- **Negative controls:** every new test has at least one, recorded in its PR.

### 1.5 Review findings against the open PRs (re-audit, 2026-10-17/18)

These are defects in unmerged fixes. They are tracked under the obligation
each PR remediates, not as new IDs. Every amendment named here was prepared
locally and **has not been pushed**.

| PR | Finding | Obligation | Status |
|---|---|---|---|
| #48 | **The gate does not fail between 84.5% and 85%.** coverage.py exits non-zero only when `round(total, precision) < fail_under`. At the default precision 0, `world-model-engine` at 84.55% (394/466) printed "FAIL … not reached" and **exited 0** | N-11 | Amendment prepared: `precision = 4` and `tools/tests/test_coverage_gate.py`. Two decimals are not enough: a package of 1,013 units can measure 84.99506% and pass. Locally: exit 1 at 84.55%, all 21 domain packages measured, the guard's negative controls fail at precision 0 and 2. Not CI evidence |
| #48 | The new guard fails until `api-gateway` and `ws-gateway` measure `--cov` | N-11 | Merge order: #43 and #44 first (§7) |
| #44 | The test said unsubscribe "stops delivery at the broker", but it inferred that from frames not arriving. No positive control after unsubscribe; close-cleanup untested | X-20 (`ws-gateway` §9.1 item 6) | Amendment prepared: a monitored NATS and `/subsz` counts, a positive-control topic, a close-cleanup test. Three mutations each caught locally; 10/10 local runs. **Reconnect after a broker restart stays untested** |
| #45, #50 | Configuration logs had no `correlation_id`, no target `user_id`, no refused writes. Before-values come from a separate read | N-02, L-15 | Amendments prepared (§3.6 N-02 gives the fields). **Still operational stdout logs, not an audit trail** |
| #47 | 39/40 at its head (`checks`: F-4FP-6) | N-12, N-13, F-4FP-10 | Needs green CI at an exact head; R-02's spec fix prepared for this branch |

---

## 2. Count reconciliation

### 2.1 Counting rules

- **One ID per obligation.** An alias recorded in a source as the same
  obligation is merged under one canonical ID, with the alias kept beside it.
- **Contents are not counted twice.** An item a source places inside another
  obligation is counted once, as that obligation.
- **Six items have no ID** and count once each: demotion/INTERRUPTIONS,
  the slice-completion declarations, the stale slice statuses, the "PR
  reviewed" ruling, and TDD 4F.P §30.8's more ingestion sources and
  model-based authoring.
- **Defects in unmerged fixes are not new IDs** (§1.5). They are tracked
  under the obligation the PR remediates.
- **Met acceptance criteria are counted separately**, as re-verification
  tasks, and settled items are listed, not counted as open.

### 2.2 From the inventory to this matrix

| Pass | Open | Change, with its source |
|---|---|---|
| Inventory, 2026-10-14 | 101 | A session report; **not in the repository, so not verifiable here**. Its constituents are reproduced below |
| Reconciliation, 2026-10-15 | 89 | **−14 duplicates**, each checked against a repository record: FP-8 = AC-5 (TDD 4F.P l.431); 4B C-1 and C-2 = AC-3 (4B Gate Review l.1466–1467); 4C C-3 = AC-4 (4C Gate Review l.439); F-4F7-7 = X-06 (4F.7 record l.502); K-7, K-8 and `observability.py` packaging = X-20 (TDD 4F.7 l.686–687); FP-18 = L-18; F-4F8-12, the D-4F-1 residual risk, the 4F.1 ledger gap and 4F.3 §8.3 are contents of L-1; "phase-4f preserved" belongs to L-9 and L-10. **−6** met criteria (AC-1, AC-2, AC-5, AC-6, AC-7, AC-8). **+8** found (N-01 … N-08) |
| Matrix, 2026-10-17 | 95 | **+6** found (N-09 … N-14) |
| **This revision, 2026-10-18** | **101** | **+1**: FP-18 split from L-18. Its source calls it *"the L-18 family"* (TDD 4F.P l.1627), not the same obligation, and its fix site and owner differ (`action-engine`'s identity client; L-18 is `nova-eventbus-sdk`'s). **+5** found: R-01 … R-05 (§3.8) |

*Correction, 2026-10-18.* The 2026-10-15 row placed *"phase-4f preserved"*
under L-9 and L-10. Its sources make it a **4F closure condition**: *"merged into
`phase-4` by a normal two-parent merge; `phase-4f` preserved; `main` untouched"*
(TDD 4F l.1215–1217; TDD 4F.8 §21.2 l.1453). It is counted as a content of L-1,
so the count is unchanged. `phase-4f` exists at `c0798a1`, 4F.1's head, and is an
ancestor of `phase-4`. Because the 4F slices merged into `phase-4` directly, the
4F Gate Review must state how the merge condition is met. The other four
contents of L-1 are as sourced: F-4F8-12 (4F.8 record l.568), the D-4F-1
residual risk (TDD 4F.8 §20.1 item 2), the 4F.1 ledger gap (4F.2 record §11.3)
and 4F.3 §8.3's wrong commit-message figures (protocol §11.1).

**The two 101s are different sets.** The inventory's counted duplicates and
met criteria; this one counts neither. The match is a coincidence.

FP-7 and FP-15 stay one obligation: TDD 4F.P l.3030 defers them together as
*"persistent lost-trigger auditability, including FP-7's and FP-15's
windows"*.

### 2.3 Rows and IDs

§3 holds **82 data rows**: the 76 of 2026-10-17 (73 open, plus 3 rows of met
criteria) and the 6 rows of §3.8. They carry **107 items**: 101 open and 6
met. Six of the open items have no ID (§2.1).

**18 items are settled and unchanged**, all named:
CF-1, CF-2, CF-3, CF-7 and CF-12 (4D Gate Review §21.9); L-7 and L-12 (4F.3
record §10.1); L-29 and L-31; L-13 and L-26, settled by `a7d52c1` and
recorded only on PR #42; F-4F7-1, repaired under A-4F7-6 (a) (TDD 4F.P
l.2409); and F-4F8-3, -6, -9, -13, -14 and -16, which are by design and
**must be disclosed in the 4F Gate Review**.

### 2.4 Where the 101 stand

| Disposition | Count | IDs |
|---|---|---|
| CLOSED ON VERIFIED EVIDENCE | **0** | Nothing is merged |
| FIX REQUIRED | **15** | Fix in an unmerged PR (status source: §1.2): L-8, L-16, L-19, F-4FP-6, F-4FP-10, N-03, N-04, N-05, N-08, N-11 (**fix incomplete**, §1.5), N-12, N-13, X-06 (**live scrape unverified**). No fix in any PR: R-01, R-02 (a fix is prepared, not pushed) |
| DOCUMENTATION REQUIRED | **34** | L-1 … L-6, L-9, L-10, L-20 … L-25, L-27, L-28, L-30; CF-6, CF-9, CF-11; 4F.6 F-3, F-5; stale slice statuses; X-01, X-02, X-10 … X-16; N-07; R-04 |
| USER DECISION REQUIRED | **52** | AC-3, AC-4; CF-4, CF-5, CF-8, CF-10; L-11, L-14, L-15, L-17, L-18; A-4F8-9; 4F.6 F-1, F-2, F-4, F-7; F-4F7-4, K-1, K-6; K-5, A-4F6-4, demotion/INTERRUPTIONS; FP-7/FP-15, FP-13, FP-18, A-4FP-14(b), more ingestion sources, model-based authoring; F-4FP-4, F-4FP-7; slice declarations; the "PR reviewed" ruling; X-03, X-04, X-05, X-07, X-08, X-09, X-17 … X-22; N-01, N-02, N-06, N-09, N-10, N-14; R-03, R-05 |
| APPROVED DEFERRAL | **0** | No open item is fully discharged by a recorded approval. Only clauses are: AC-3's plan and trace (2026-09-06) and AC-4's clauses 2–3 (2026-09-07), with no receiving milestone named |
| CARRY FORWARD WITH OWNER AND MILESTONE | **0** | Only L-15 names both (`action-engine`, "4F closure"; D-4F4-3), and its milestone is now, so it is a decision. Every other owner is **UNASSIGNED** |

15 + 34 + 52 = **101**.

**Unverified, and outside the 101:** AC-1, AC-2, AC-5, AC-6, AC-7 and AC-8
at the final SHA (met at `a7d52c1`'s code); a live Prometheus scrape (X-06);
the first ~5,767 lines of the 4F.8 E2E log, which the log tool cannot return.

**Zero rows are closed by this document.**

---

## 3. The matrix

**Blocks:** **4F** (Phase 4F's closure; under protocol §0.2 and TDD 4F §21 it
then also blocks GO), **GO** (the Phase 4 Gate Review's verdict), **P**
(promotion only), **—** (none).

**Class:** FIX, DOCUMENT, VERIFY, DEFER, ACCEPT RISK, N/A or BLOCKED, as
defined by the request. DEFER, ACCEPT RISK and N/A are proposals until approved.

**Owner** is named only where the repository names one. Otherwise it is
**UNASSIGNED**, and the Gate Review must say so (GO condition 10).

**Sources.** A status of the form "FIX ready (#N)" cites PR #N's head and CI
in §1.2. Every other status cites the record in its Evidence column. A status
with neither is **UNVERIFIED**.

### 3.1 Acceptance criteria (master scope §1)

| ID | Requirement | Evidence now | Blocks | Class | Action, and what remains |
|---|---|---|---|---|---|
| **AC-3** | *"Every Phase 3 sub-phase … exercised from the browser"*: plan, trace, install, approval | 1 of 4 clauses met (install). Plan and trace are deferred by approval (2026-09-06; 4B C-2), but no receiver is designated. **Approval clause (B5, this pass):** the approval spec skips because stage 3 denies every Critical action. In CI there is no identity signal (confidence 0.0), so passing would need a critical-tier threshold of 0.0. 4B's design rejected that explicitly; P8's harness already discloses `negligible: 0.0` as test configuration | GO | DEFER | **D-C2**: approve the deferral through closure and promotion (receiver UNASSIGNED), **or** approve a disclosed test-only critical threshold so the approval clause can be demonstrated |
| **AC-4** | Containers; *"renders live agent instances, supervisor structure, and at least one real peer-review round"* | Clause 1 (containers) met in 4C.1. Clauses 2 and 3 deferred by approval (2026-09-07); provider-gated, receiver undesignated. **Supervisor structure (B4, this pass):** rendered as the single `engineering` supervisor, the observed topology per 4C scope-mapping decision 6 (`api/agents.py`), unit-tested (`agents-panel.test.tsx` l.223). **No Playwright spec opens the Agents panel**, so nothing is browser-evidenced. Membership is empty without a provider | GO | DEFER + VERIFY | **D-C2**: classify supervisor structure, either as met by design with a browser test to add, or as inside clause 2's deferral. Then approve the carry |
| AC-1, AC-2, AC-6 | — | Met, as recorded in the 4B and 4E Gate Reviews; golden path green at every head in §1.2 | GO | VERIFY | Re-verify at the final candidate SHA |
| AC-5 (alias FP-8) | — | Met: approving a Level-1 suggestion executes nothing (`api/autonomy.py`, decide) | GO | VERIFY + DOCUMENT | The Gate Review states this reading |
| AC-7, AC-8 | — | Met in CI (P-AC7-1, P-AC8-1; acceptance runs at every head in §1.2) | GO | VERIFY + DOCUMENT | State AC-7's reading and limits. The roadmap's original text ("IDE", "1 s") differs; disclose it (protocol §5.4) |

### 3.2 Carry-forwards

CF-1, CF-2, CF-3, CF-7 and CF-12 are closed.

| ID | Requirement | Evidence | Blocks | Class | Action |
|---|---|---|---|---|---|
| CF-4, CF-5, CF-8 | Master scope §4 | Open, carried | 4F | DEFER | **D-C15**: carry, owner UNASSIGNED |
| **CF-6** | Real-Postgres verification for personality, communication and perception (*"not claimed as closure"*) | **Now evidenced:** the CI logs at `6b0093b` show 5, 13 and 28 real-infrastructure tests passed, with 0 failed or skipped | 4F | DOCUMENT | Close in the 4F record, citing the job logs |
| CF-9 | ADR-032 point 2: the identity-confidence write surface | Conditions 1, 3 and 4 evidenced (4F.4 record §9.2). Its writes are now logged (#50) | 4F | DOCUMENT | Record conditions 2 and 5 |
| **CF-10** | The Trust Engine input does not exist; `_trust_denies` never refuses | `decision.py` l.324–350; Level 2 selectable | **GO** | DEFER + ACCEPT RISK | **D-C7**: defer beyond Phase 4, explicitly accepting that trust never refuses. Receiver UNASSIGNED |
| CF-11 | The initiative trigger's claims | Claim 3 evidenced (E-14, in CI) | 4F | DOCUMENT | Record claim 4 |

### 3.3 Ledger, L-1 … L-31

Settled: L-7, L-12, L-29, L-31. L-13 and L-26 are settled by `a7d52c1`,
recorded on PR #42.

| Row | Obligation | Evidence | Class | Action / status |
|---|---|---|---|---|
| L-1 | The 4F Gate Review, carrying F-4F8-12's exact-SHA citations, the D-4F-1 residual risk, the 4F.1 ledger gap, the 4F.3 §8.3 confirmation, TDD 4F §21's six items, and TDD 4F's closure conditions (two-parent merge, `phase-4f` preserved, `main` untouched; §2.2) | Absent | DOCUMENT (BLOCKED on the decisions in §4) | Written after the decisions; a docs-only PR |
| L-2, L-3 | `phase-4f.md`; the master health row | Absent | DOCUMENT | With L-1 |
| L-4 | Roadmap 4F row | Still *"2 of 8 slices merged"* | DOCUMENT | With L-1 |
| L-5 | Master scope §17 SLOC and §2 methodology | Not reconciled | DOCUMENT | With L-1; §1.3 here holds the figures |
| L-6 | README for the new engines | No Phase 4 mention | DOCUMENT | With X-15 |
| **L-8** | `ws-gateway` README: the `perception.*` narrowing | — | **FIX ready (#44)** | 18 topics listed, L-8 narrowing documented |
| L-9, L-10 | Consistency and staleness sweeps | Not run | DOCUMENT | With L-1 |
| L-11 | Multi-modal fusion | Not built | DEFER | **D-C1** (with A-4F8-9) |
| L-14 | Per-source filesystem consent (Doc 22 §8) | The workspace path never calls `has_active_consent` | DEFER + ACCEPT RISK | **D-C9** (privacy) |
| **L-15** | Identity-confidence policy changes unaudited | **#50 now logs every change**, before and after, at WARNING when a tier loosens. It is not persisted, so D-4F4-3 stands | Partly FIX + DEFER | **D-C5**: is a log line sufficient, or is a persisted audit required? |
| **L-16** | `action-engine` README omits the policy routes | — | **FIX ready (#50)** | — |
| L-17 | The panel can re-enable an `AUTO_EXECUTE` policy | `AutonomyPanel.tsx` l.266–273. Re-enabling is now logged with `effect=auto_execute` and enabled false → true (#45) | ACCEPT RISK | **D-C6** |
| L-18 | The NATS SDK leaves `NoRespondersError` untranslated | 4F.5 record §10.4; TDD 4F.5 l.754 (owner `nova-eventbus-sdk`) | DEFER | **D-C15**. *(2026-10-18: FP-18 is no longer recorded as an alias; see §3.8)* |
| **L-19** | `autonomy-engine` README is a scaffold | — | **FIX ready (#45)** | Gate order corrected in `22ef074` |
| L-20 | Doc 20 omits the cognitive-state sensor copy | 0 hits | DOCUMENT | With L-1 |
| L-21, L-22, L-24, L-27, L-30 | Dated status notes in the TDDs, health records, roadmap and README | The roadmap never mentions 4F.P | DOCUMENT | With L-1 |
| L-23 (FP-24) | TDD 4D §4.3 *"exactly four outcomes"* | Six exist (`DecisionOutcome`) | DOCUMENT | Dated note with L-1. #47 aligns the web client |
| L-25, L-28 | A compose comment; three test docstrings (V-6(b)) | Compose l.1030–1032 contradicts l.637 | DOCUMENT (comment-only outside `docs/`) | First commit of the 4F closure PR |

### 3.4 4F findings and decisions

| ID | Evidence | Blocks | Class | Action |
|---|---|---|---|---|
| **A-4F8-9 / F-4F8-10** | Six unowned 4F deliverables, plus fusion, the meeting-begins scenario and per-platform tests. TDD 4F.8 l.958: *"blocks 4F's GO"* | 4F | DEFER | **D-C1**. Building them would cross the SLOC gate (§1.3). Receiver: Phase 5 is a topical fit only (roadmap l.662), or UNASSIGNED |
| 4F.6 F-1 | The reply subject is unregistered | 4F | DEFER | **D-A3**: (a) keep, no contract change |
| 4F.6 F-2 | The 20 s reply wait is unratified | 4F | DOCUMENT (ratify) | **D-A1** |
| 4F.6 F-3; F-5 | Retargeted test; §8 chain wording | 4F | DOCUMENT | **D-A2** |
| 4F.6 F-4; F-7 | Redelivered `propose` reads "degraded"; the `correlation_id` convention | 4F | DEFER | **D-A4** |
| F-4F7-4; K-1; K-6 | Non-strict `digitalTwin.ts` schemas; at-most-once delivery; no pagination | 4F | DEFER | **D-C15** |
| K-5; A-4F6-4; demotion and INTERRUPTIONS | Focus `signals_used` is always empty; TTL; Part 6 interruptions | 4F | Decision | **B3 done (2026-10-17):** no slice delivers any of the three, and TDD 4F §24.12 lists all three as OPEN. Master scope §5 names the *"Focus System"* and *"Attention Layers"* as 4F scope, so K-5 and INTERRUPTIONS are partial deliveries of it; TTL is 4F.6's open semantics (TDD 4F l.1607, l.1767). **D-C3** |
| FP-7/FP-15; more ingestion sources; model-based authoring; A-4FP-14(b); FP-13 | TDD 4F.P §30.8, *"Beyond 4F.P"*, approval not found | 4F | DEFER | **D-C15** |
| F-4FP-4; F-4FP-7 | 4F.P record §8.1 | 4F | DEFER | **D-C15** |
| **F-4FP-10** | `decisionResultSchema` listed 4 of 6 outcomes | 4F | **FIX ready (#47)** | A drift guard reads `DecisionOutcome` |
| **F-4FP-6** | Recurring CI flake: `"ada"` matched inside a random UUID | — | **FIX ready (#49)** | Reproduced deterministically. It recurred on #47 |
| Slice-completion declarations (4F.5, 4F.6, 4F.7, 4F.P, 4F.8) | Records | 4F | BLOCKED | Reserved to the owner, after D-C11 and D-C12 |
| "PR reviewed" rulings | 0 GitHub reviews; agent reviews are not independent | 4F | DOCUMENT (ruling) | **D-C12** |
| Stale slice statuses (4F.1, 4F.3–4F.8) | "PR open", "not merged" | 4F | DOCUMENT | Dated notes with L-1 |

### 3.5 Phase-level and earlier milestones

| ID | Item | Evidence | Blocks | Class | Action |
|---|---|---|---|---|---|
| X-01 | 4A Gate Review and `phase-4a.md` (4B C-6) | Absent | GO | DOCUMENT | Phase 4 closure PR |
| X-02 | 4C.1 Gate Review | 4C Gate Review §19.3 | GO | DOCUMENT | Phase 4 closure PR |
| **X-03** | **4B C-7**: promote E2E to a required check once it is stable (bar ≥10×, protocol §9.2) | **Corrected 2026-10-18.** The unit is a **workflow run** of PR Checks, counted by `list_workflow_runs` (4B Gate Review §7.2, l.791–800); the discharge row adds *"against an unchanged SHA"* (l.1470). **Attempts are not runs:** #140 is one run with 7 attempts, so the earlier "7 at one SHA" was wrong. **Retries are not passes:** Playwright retries once in CI, and #150 was green with one flaky test. Measured (2026-10-17): E2E green in every run #139–#157 (19), across 13 branches and 19 SHAs; whole-run conclusions break at #149 (`checks`), leaving 8 (#150–#157); **no SHA has more than one run, so 0 qualify under the strict reading**. The job is still *"staged, non-blocking"* | GO | Decision, then evidence | **D-A7**: the strict reading is 10 consecutive dispatched runs at the final code SHA, each with E2E green and 0 flaky. Dispatches must be sequential: `pr-checks.yml` cancels an in-progress run on the same ref. Making the job *required* needs branch protection (X-17) |
| X-04 | 4B DEV-4: `GET /v1/system/health` never built | 4B Gate Review l.418 | GO | DEFER (ratify) | **D-A5** |
| X-05 | `ws-gateway`'s broad `communication.*` and `personality.*` bus subscriptions | `events/subscribed.py` l.28, l.49; documented in #44 | 4F | DEFER or FIX | **D-C15**. A narrowing is a one-engine change if wanted |
| **X-06** (F-4F7-7) | Prometheus scrapes only `nova-core` | — | 4F | **FIX ready (#51)** | 20 services plus a drift guard |
| X-07, X-09 | 4E findings 1 (testkit image drift) and 3 (outbox guard misses `memory`) | 4E Gate Review §13.1 | 4F | DEFER or FIX | **D-C15** |
| **X-08** | **4E finding 2**: six digital-twin operations take a caller-supplied `user_id` (security) | `routing.py` l.165–200; no browser consumer | 4F | ACCEPT RISK or FIX | **D-C8**: deny at the gateway (a small `api-gateway` PR), or accept with Phase 7 as a topical receiver |
| X-10 | SLOC method, Option A or B | Open since 4D | — | DOCUMENT (optional) | §1.3 records the method used |
| X-11, X-12 | The Phase 4 Gate Review; `phase-4.md` and its master row | Absent | GO | DOCUMENT | After 4F closure merges |
| X-13 | 4B health records still say "not merged" | Master table l.30 | 4F | DOCUMENT | With L-10 |
| X-14 | Roadmap Phase 4 status; receiving entries; AC-text divergence | — | GO | DOCUMENT | After the D-C decisions |
| X-15 | Pre-4F README claims ("Thirteen engines", "agent-os has no Dockerfile", canonical branch) | README l.69, l.78 | 4F | DOCUMENT | With L-6 |
| X-16 | The protocol's stale counts (contract files, Dockerfiles, real-infra packages) | §8.2, §9.2, §10.1 | GO | DOCUMENT (factual correction, separate from policy) | **D-A6** |
| **X-17** | SAD 15 §1 and §3 versus the repository: no protection, no rulesets, no `CODEOWNERS`, single maintainer | GitHub API | GO | ACCEPT RISK (documented deviation) | **D-C10** |
| X-18 | SAD 15 claims that are false: §4's change-scope linter and §7's README lint do not exist; §6's squash rule contradicts master scope §16's merge commit | `tools/`, workflows | GO | DOCUMENT (deviation) | **D-C10** |
| X-19 | SAD 15 §4 non-conformance on PRs #23–#41: 12 item-1 fails, 5 item-4, 10 item-5 | Reconciliation §5.1 | 4F/GO | ACCEPT RISK (retrospective) | **D-C11** |
| **X-20** | §9.1 gaps (aliases K-7, K-8, observability packaging) | §5 below: 41 cells changed this pass | 4F/GO | Partly FIX + decisions | **D-A8, D-A9, D-C14** |
| X-21 | The promotion PR's SAD 15 §4 obligations | §6 | P | BLOCKED | After GO; **D-C13** |
| X-22 | `ubuntu-latest` moves to Ubuntu 26 from **2026-10-19**; Node 20 deprecation | Run annotations | — (risk to final CI) | ACCEPT RISK or FIX | **D-A10 (new)**: pin `ubuntu-24.04` for the closure window, or accept the drift |

### 3.6 Found by the reconciliation (2026-10-15)

| ID | Item | Blocks | Class | Status |
|---|---|---|---|---|
| **N-01** | Every engine port and an unauthenticated NATS are published on all host interfaces. That contradicts doc 11 l.148 (*"on `localhost` only"*) and lets anyone who can reach the host bypass the gateway. **Scope, measured 2026-10-17:** all **36** published ports bind every interface; NATS (4222, 8222) and Redis (6379) have no authentication; Postgres, Neo4j, MinIO and Grafana use the default password; Grafana allows anonymous viewers; seven images are unpinned `:latest`; perception's identity and consent write routes are reachable on 8009 | **GO** | FIX or ACCEPT RISK | **D-C4.** Binding to `127.0.0.1` closes access from other hosts only. It does not protect against processes on the same host, other containers on the compose network, or DNS rebinding through the user's browser |
| **N-02** | `autonomy-engine` level, policy and permission changes had no record | 4F | Partly FIX (#45: before and after log lines) | **D-C5**: persisted audit or not. *(2026-10-18: #45's lines lack `correlation_id` and target `user_id`, and refused writes were unlogged. The prepared amendment adds `outcome`, `user_id` (server-side, the target), `correlation_id` (a header; not attribution), `actor` (always null: not determinable under the single-token model), and a refusal line for 422 and 404. They remain stdout operational logs, not an audit trail)* |
| **N-03** | `rate_limit.py` claimed a Redis limiter that does not exist | GO | **FIX ready (#43)** | Corrected, quoting the original |
| **N-04** | `ws-gateway` README omitted `agent_os.task.completed` | 4F | **FIX ready (#44)** | — |
| **N-05** | `docs/design/phase-4/` had no README | GO | **FIX ready (this PR)** | — |
| N-06 | 4B DEV-5 (cosmetic) | — | ACCEPT RISK | **D-C15** |
| N-07 | About 20 retained Phase 4 branches; remote deletion is blocked to this session | — | DOCUMENT | Report in the Gate Review |
| **N-08** | `created_at` had no `nova-contracts` test (protocol §8.1) | GO | **FIX ready (#52)** | 3 tests and a negative control |

### 3.7 Found this pass (2026-10-16/17)

| ID | Item | Evidence | Blocks | Class | Status |
|---|---|---|---|---|---|
| **N-09** | About 30 `_seconds` histograms in 13 pre-Phase-4 engines use the SDK's millisecond-default buckets, so almost every observation lands in the lowest bucket and percentiles are unreadable | A scan of every `create_histogram` call; 0 of them set buckets | — (quality) | DEFER or FIX | **D-A11 (new)**. Proposed fix: one `View` in `nova-observability` for `*_seconds` instruments, a single shared-package PR. Not made: it changes every engine's metric output. The four Phase 4 services already set second-scale buckets (#43–#46) |
| **N-10** | The rate limiter deviates from TDD 4A §2.3 and doc 11 §5: in-process fixed window with two classes, versus Redis token bucket with three. The deviation was undisclosed | `domain/rate_limit.py` | GO | DEFER or ACCEPT RISK | Disclosed in #43. **D-C16 (new)**: ratify, or build |
| **N-11** | The 85% domain-coverage gate (doc 16 §1) was never enforced in CI: package-directory runs ignore the root config. A package at 81% passed | Demonstrated | GO | **FIX ready (#48), incomplete** | Gate on in CI; log shows all 19 packages pass. **D-A12 (new)**: doc 16 says *line*, the config says *branch*. *(2026-10-18: the gate still passes 84.5–85% by rounding; see §1.5. #48's head is not a sufficient fix)* |
| **N-12** | TDD 4A §7: *"401 → the frontend re-runs the first-run session flow"* was not built. A 401 left the workspace up with failing panels | 6 of 8 failure-path tests fail on `phase-4` | GO | **FIX ready (#47)** | — |
| **N-13** | TDD 4A §7: *"429 with a structured retry hint"*. The 429 carried no hint, and the client could not show one | Tests fail before the change | GO | **FIX ready (#43 server, #47 client)** | `Retry-After`; no envelope change |
| **N-14** | 4B's TDD was never written and, unlike 4C's, never waived; master scope §17 still says *"Planned"* | 4B Gate Review l.462; master scope l.1383 | GO | DOCUMENT (waiver) | **D-A13 (new)**: waive, as 4C's was. The §17 rows for doc 14 and this package's README wait for PR #42, which edits the same table |

### 3.8 Found by the re-audit (2026-10-17/18)

Labels R-01 … R-05 exist only in this document. They are not master scope's
risks R-1 … R-6, which the Phase 4 Gate Review re-checks (TDD 4F.8 §20.2).

| ID | Item | Evidence | Blocks | Class | Status |
|---|---|---|---|---|---|
| **R-01** (AUD-2) | CI runs no `cargo audit`, though doc 13 §9 requires it for every PR | doc 13 l.111; `build-and-scan.yml` has no `cargo` step. A local run (cargo-audit 0.22.2, RustSec DB `999ec89`): 98 crates, 0 vulnerabilities, 1 yanked (`yoke-derive` 0.8.3, via `ureq`) | GO | FIX | No fix in any PR. CI addition planned; needs authorization |
| **R-02** (AUD-3) | `cognitive-state-panel.spec.ts:154` races: it clicks Refresh when the first section has settled, while another may be on its first fetch, which TanStack Query reuses rather than re-issues | Run #150 annotation (*"Expected: >= 3, Received: 2"*); `query-core` 5.102.8 `query.ts` l.401–411. Local harness, retries off: old spec 10/10 failed with one section in flight, fixed spec 10/10 passed, both 10/10 with no delay | GO (C-7) | FIX | A test-only fix is prepared for #47's branch, not pushed. Not product behaviour |
| **R-03** (AUD-5) | Neither gateway checks `Origin`. SameSite=Strict keeps the cookie from other sites but not from other ports on the same host, so a page served from `localhost` could read the public event stream or send body-less POSTs | `ws-gateway/api/stream.py` handshake; `api-gateway/api/auth.py` l.66 | — (P for networked use) | Decision | No document requires the check. Accept with the stated threat model, or add an allow-list |
| **R-04** (AUD-6) | TDD 4F §15 row 1 (*"Companion absent or crashed: sensors report unavailable"*) is not built. RS-3a and A-4F8-1 rule out inferring failure from silence, so a crashed companion leaves the sensor `running`, labelled with its `reported_at` | TDD 4F l.781; TDD 4F.8 l.582, l.1322; TDD 4F.7 §14 | 4F | DOCUMENT | A dated note on TDD 4F §15 that the ratified rule supersedes row 1 |
| **R-05** (AUD-9) | `pr-checks.yml` never runs on `phase-4`: it triggers on `pull_request`, on `push` to `main` only, and on dispatch. It has 0 runs on `phase-4` | `pr-checks.yml` l.15–30; `list_workflow_runs` for `branch=phase-4` | GO | Decision | Add a `push` trigger for `phase-4`, or record the procedure: update each PR onto the fresh head before merging, and dispatch once at the final SHA |
| **FP-18** | `action-engine`'s identity client does not translate a no-responders error; `autonomy-engine` then records `TIMEOUT` for an action that stopped before executing | TDD 4F.P l.1627 (*"the L-18 family"*; *"`action-engine` is a non-goal"*) | 4F | DEFER | **D-C15** (carry). Owner UNASSIGNED |

---

## 4. Decisions only the owner can make

Each decision is independent unless stated. **Recommended** marks the option
supported by the evidence; it is not a decision.

| ID | Decision | Recommended | Unblocks |
|---|---|---|---|
| **D-C1** | A-4F8-9's deliverables, and L-11 | Defer beyond Phase 4. Receiver: Phase 5 (topical) or UNASSIGNED, stated explicitly | 4F GO |
| **D-C2** | AC-3 and AC-4 remaining clauses through closure and promotion; supervisor structure; the AC-3 approval clause test configuration | Defer the provider clauses (receiver UNASSIGNED). Classify supervisor structure as met by design, with a browser test added | Phase 4 GO |
| **D-C3** | K-5 (Focus `signals_used` always empty), A-4F6-4 (TTL) and demotion/INTERRUPTIONS. No slice delivers them (B3, §3) | Approve each as a recorded narrowing of master scope §5's Focus System and Attention Layers, carried in the 4F Gate Review with a receiver named or UNASSIGNED. Without approval this is silent narrowing, a NO-GO (protocol §3.2) | 4F GO |
| **D-C4** | N-01, host exposure | Bind published ports to `127.0.0.1` (a compose PR), and correct doc 11 | Phase 4 GO (condition 10) |
| **D-C5** | L-15 and N-02: log line or persisted audit | Accept the log lines for Phase 4 (#45, #50), and carry the persisted audit to Phase 7 (topical) or UNASSIGNED | 4F |
| D-C6 | L-17, re-enabling `AUTO_EXECUTE` | Accept: it is now logged, and bounded by risk ≤ low and deny-wins | 4F |
| **D-C7** | CF-10, trust never refuses at Level 2 | Defer and accept explicitly; disabling Level 2 instead would undo AC-8 | Phase 4 GO |
| **D-C8** | 4E finding 2, caller-supplied `user_id` | Deny the six operations at the gateway (no browser consumer) | 4F |
| D-C9 | L-14, per-source consent | Defer with an explicit privacy acceptance | 4F |
| D-C10 | SAD 15 §1, §3, §6 and §7 versus reality | A documented deviation; optionally, protect `main` with required checks only | Phase 4 GO |
| D-C11 | Past PRs' SAD 15 §4 gaps | A retrospective approval naming the PRs; a recorded deviation for item 5 | 4F, GO |
| D-C12 | Do the agent's technical reviews satisfy "PR reviewed"? | The owner's ruling; options as in the 4F.8 record §14.4 | Slice declarations |
| D-C13 | The promotion PR | Item-1 exception in advance; merge commit (master scope §16) | Promotion |
| D-C14 | §9.1 dispositions (§5) | Approve the N/A cells; decide traces (D-A9); set or waive performance targets | 4F, GO |
| D-C15 | Carry list (CF-4/5/8, K-1, K-6, F-4F7-4, F-4FP-4/7, X-05, X-07, X-09, L-18, FP-18, the FP items, N-06) | Carry, owners UNASSIGNED | 4F |
| D-C16 | N-10, the rate limiter design | Ratify the narrowing for single-user Phase 4, and record it in TDD 4A | GO |
| **D-C17 (new)** | R-03, `Origin` validation in both gateways | Accept for local single-user Phase 4, stating the threat model; add an allow-list before any networked or multi-user use | P (networked use) |
| D-A1 … D-A6 | 4F.6 F-2 ratify; F-3/F-5; F-1 (a); F-4/F-7; DEV-4 ratify; protocol counts | As the reconciliation recommended | 4F, GO |
| **D-A7** | C-7's counting unit | Strict: 10 consecutive PR Checks workflow runs, dispatched one after another at the final code SHA, each with E2E green and **0 flaky** (`failOnFlakyTests` in CI); then make the E2E job blocking. *(2026-10-19: "blocking" means a required check, which needs branch protection or a ruleset, D-C10. 4B Gate Review §7.2 counts runs across pushes and §15.1 against an unchanged SHA; this decision chooses between them.)* | GO |
| D-A8 | §9.1 applies to all eight subsystems | Yes, with N/A per cell | §5 |
| **D-A9** | Traces (§9.1 item 10) | Keep the requirement; record repository-wide absence as a deferred gap; a propagation design for HTTP and the bus envelope is a contract decision | §5 |
| D-A10 | Runner pin before 2026-10-19 | Pin `ubuntu-24.04` until Phase 4 is promoted | Final CI stability |
| D-A11 | N-09 histogram buckets | One shared-package PR (a `nova-observability` View) | — |
| D-A12 | Coverage: line (doc 16) or branch (config) | Keep branch, amend doc 16 (stricter, already passing) | — |
| D-A13 | Waive the 4B TDD | Waive on the record, as 4C's was | GO |
| **D-A14 (new)** | R-05, CI on `phase-4` | Record the procedure (update each PR onto the fresh head before merging; dispatch at the final SHA) rather than add a `push` trigger | GO |
| **D-A15 (new)** | R-01: what `cargo audit` fails on | Fail on vulnerabilities, as `pip-audit` does; report yanked, unmaintained and unsound warnings without failing, each listed in the Gate Review (today: `yoke-derive` 0.8.3, yanked) | R-01's fix |
| **D-A16 (new)** | PR #42 (the post-merge record of #41, and the only record that L-13 and L-26 are settled): merge it on its own, or leave it open to become the 4F closure PR | Merge it on its own, after its CI is refreshed at an updated head. The 4F closure PR is then a new documentation PR. Reuse would change #42's title, description and scope, and would hold the §16 rule 7 record until 4F closes | Step 2's #42; step 3's shape |

*Added 2026-10-18.* D-A1 … D-A6 point to the reconciliation, a session
report outside the repository. Their recommendations, restated so they can
be checked here: **D-A1** ratify the 20 s bound; **D-A2** document F-3's
retargeted test and F-5's wording; **D-A3** option (a), no contract change;
**D-A4** defer F-4 and F-7, recorded; **D-A5** ratify DEV-4 as a narrowing;
**D-A6** correct the protocol's counts as facts, separately from any policy
change.

**Authorizations, each separate and none given:** pushing to PR #42; reusing
PR #42 as the 4F closure PR; each merge; opening the Phase 4 closure PR;
opening the promotion PR; triggering C-7 runs; any further code branch beyond
those listed.

---

## 5. SAD 15 §9.1, after this pass

**Legend:** P = pass; F = fail; N = proposed N/A; U = unverified; **→P** =
passes once the named PR merges.

| Subsystem | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| `apps/web-client` | P | →P doc 14 | →P doc 14 | N | P | N | N | →P #47 | N | N |
| `packages/nova-ui` | F | N | →P doc 14 | N | P | N | N | N | N | N |
| `api-gateway` | P | →P doc 14 | →P #43 | P | P | N | F | P | →P #43 | metrics →P #43; traces F |
| `ws-gateway` | P | →P doc 14 | →P #44 | →P #44 | P | →P #44 | F | P | →P #44 | metrics →P #44; traces F |
| `autonomy-engine` | P | →P doc 14 | →P #45 | →P #45 | P | P | F | P (B2) | →P #45 | metrics →P #45; traces F |
| `cognitive-state-engine` | P | →P doc 14 | →P #46 | P (verified, #46) | P | P | F | P (B2) | P | metrics →P #46; traces F |
| `companion/nova-companion` | F | →P doc 14 | →P doc 14 | P | P | N | P | F (R-04) | F | F |
| `companion/sensors` | F | →P doc 14 | →P doc 14 | N | P | N | P | P | N | N |

**What remains, by cell:**

- **Item 1, "before implementation"**, for `nova-ui` and both companion
  crates. This cannot be met retroactively, so it is a recorded deviation for
  D-C14. Doc 14 records the system as built. The companion crates also need a
  Bible Part mapping: Part 11, Perception.
- **Item 7, performance targets.** Only AC-7's five seconds is ratified. **No
  target is invented here.** D-C14 should set or waive targets per service.
  Proposed measurable candidates for approval:
  - `api-gateway` p95 forwarding overhead under 50 ms, excluding the upstream;
  - `ws-gateway` frame fan-out p95 under 100 ms;
  - `autonomy-engine` decision p95 under 250 ms, excluding dispatch;
  - `cognitive-state-engine` ingestion p95 under 500 ms, excluding the
    trigger's wait.
- **Item 8 (B2 done, 2026-10-17; by the implementing agent, not independent).**
  TDD 4D §13: 6 of 6 rows have a test (the policy-raises row asserts the
  denial, not its log line). TDD 4F §15: 8 of 9; row 1 is R-04. TDD 4F.6 §9.1
  (Design A) and TDD 4F.7 §14: every row has a test, except *"the Event Bus
  is unreachable at startup"*, which rests on shared service-kit behaviour and
  is not tested in this engine (UNVERIFIED). The companion tests an
  unreachable engine, an unregistered source, server errors, revocation and
  watch-error redaction.
- **Item 9, `nova-companion`.** Its JSON log lines carry no correlation id;
  adding one is a companion change and an intake contract decision.
- **Item 10, traces.** Absent everywhere (D-A9). The companion has no metrics
  (proposed N/A: it is a CLI daemon with no scrape port, by TDD 4F §7).
- **Timing.** §9.1 asks for these items *"in the same PR or PR series"*. Late
  fixes leave that clause unmet; this is recorded, not hidden.

---

## 6. Promotion readiness (`main` → `phase-4`), unchanged since the reconciliation

- **API surface:** 0 operations removed or changed, 15 added to existing
  engines, 30 in new services (generated OpenAPI, in memory).
- **Contracts:** one model changed, additively: `LongTermMemoryCreatedPayload.created_at`
  (N-08, #52).
- **Required before the promotion PR opens:**
  - Phase 4 GO;
  - D-C13;
  - CI at its exact head;
  - a recorded SAD 15 §4 item-4 review;
  - Bible citations.
- **Security posture at promotion:** N-01 (D-C4) and CF-10 (D-C7) must be
  decided, because GO condition 10 cannot be met with them silent.

---

## 7. Sequence from here (protocol order)

1. **Owner decisions** in §4. None needs code first. Only B2, B3 and the AC-4
   browser test are read-only or test-only work that can run in parallel.
2. **Merge authorizations**, one at a time. *(Revised 2026-10-18.)* The order
   the prepared amendments require: #49 (removes F-4FP-6); #47 with R-02's
   spec fix; #43 and #44 (they add the gateways' `--cov`); #48 (its new guard
   needs both); then #42, #52, #51, the N-01 and X-08 PRs if authorized, #46,
   #45, #50, and #53 last. Before each merge, the PR is updated onto the
   current `phase-4` head and must be green, with 0 flaky, at that new head:
   `phase-4` has no CI of its own (R-05).
3. **The 4F closure PR**, documentation only (L-1 … L-10, CF-6, CF-9, CF-11,
   the slice statuses). It cites CI at the merged code head, under the
   docs-only rule. Reusing PR #42 needs its title, description and scope
   changed, and is the owner's choice.

   *Corrected 2026-10-19.* Two statements in steps 2 and 3 are not settled
   and are not rules:
   - **#42.** Step 2 merges #42, and step 3 offers to reuse it. A merged PR is
     finished and is never reused (protocol §11.1), so it cannot be both.
     Until **D-A16** is decided, #42 is in neither step.
   - **"with 0 flaky".** That is the rule only if **D-A7** is approved. Until
     then, each merge needs every check run green at the updated head, and the
     Playwright flaky count is reported, not gated.
4. **Post-merge verification** of `phase-4` (master scope §16 rule 7).
5. **C-7** per D-A7, then the **Phase 4 Gate Review** (X-01, X-02, X-11, X-12,
   X-14, X-16 … X-19, AC re-verification at the final SHA). That is its own PR.
6. **Promotion PR**, only after **GO** and the owner's authorization to open
   it. Then the owner's merge authorization, a merge commit, and `main` CI.
7. **Phase 5 readiness report** (§8 is its preliminary form).

---

## 8. Phase 5 readiness, preliminary

| Question | Answer now |
|---|---|
| **Can Phase 5 *planning* start?** | **Yes**, as reading and design only. It changes no Phase 4 obligation |
| **Can Phase 5 *implementation* start?** | **No.** Master scope §16 requires `phase-4` closed and promoted first. One milestone branch at a time |
| **Is Phase 4 closed?** | **No.** 4F is not closed; no Phase 4 Gate Review exists |
| **What Phase 5 can build on** | The REST and realtime transport (gateways, envelope, session), the 11 web-client panels, `@nova/ui`, the companion's process model, and the Level 0–2 autonomy path. All are additive-compatible (§6) |
| **Phase 5 dependencies on unfinished Phase 4 work** | **Deliverables that must not slide in silently:** desktop supervision of `nova-companion` (roadmap Phase 5) depends on A-4F8-9's sensors and actuators (D-C1). The *"full panel set"* depends on AC-4's provider-gated clauses (D-C2) |
| **Security limits before dependent features** | **Must be addressed before any multi-user or networked feature:** N-01 (host exposure); X-08 (caller `user_id`); CF-10 (trust never refuses); D-C5 (no persisted audit); the single-token session model (TDD 4A §4.2, Phase 7) |
| **Test and observability work that should precede new features** | The Prometheus targets (#51) and coverage gate (#48), merged; the N-09 buckets; trace propagation (D-A9); a Playwright spec for every panel (roadmap Phase 5's own testing strategy) |

No Phase 4 obligation is moved into Phase 5 by this document. Each transfer
needs the owner's approval, and an entry in the roadmap.
