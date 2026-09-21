# Phase 4F.5 — Slice Completion Record
## Autonomy Level 2: selectable, policy-permitted, single dispatch, and `action.execute`'s first producer

**Date:** 2026-09-21
**Slice:** 4F.5 of 4F's eight (TDD 4F §18)
**Branch:** `phase-4f.5`, at **`6a1ca27f99ba224d8fc755548bfdcd9a8fb39fb5`**
**Base:** `phase-4` at **`e83f1f314451c795184301e1d83205a31412fce2`** — **unchanged by this slice**
**`main`:** **`7e273e62e942ecd5528ca807e65933d6bb675669`** — **untouched**
**PR:** opened against `phase-4` to obtain exact-SHA CI evidence — **not merged**
**Protocol:** [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md),
sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`,
1131 lines, read from `origin/main` and verified in this session.
**TDDs:** [TDD 4F](../../design/phase-4/06-tdd-4f-companion-and-cognitive-state.md)
§6, §11.2, §12, §16, §18 · [TDD 4F.5](../../design/phase-4/09-tdd-4f5-autonomy-level-2.md) in full.

---

## 0. What this document is, and is not

**This is a Slice completion record. It is not a Gate Review, and 4F.5 does not
get one.**

Protocol **§0.1**'s unit table reserves a Gate Review for a **Phase or
Sub-Phase**, and assigns a **Significant Slice** categories **1, 2, 8, 9, 10,
11, 13 and 14 in full**, with categories **3–7 and 12 as a deferred-obligations
ledger** (§0.2). **Category 3 is precisely "Gate Review and Go / Conditional-Go
/ No-Go criteria."** A slice defers it; it does not issue one.

There is therefore **no Go / Conditional-Go / No-Go verdict here**. 4F's Gate
Review belongs to **4F.8**, where it is ledgered as **L-1**. This follows the
[4F.2](phase-4f2-workspace-perception-completion-record.md),
[4F.3](phase-4f3-nova-companion-completion-record.md) and
[4F.4](phase-4f4-identity-confidence-policy-completion-record.md) records.

**Phase 4F is NOT complete.** Three of eight slices (4F.6, 4F.7, 4F.8) have not
started, and nothing here claims Phase 4 closure.

### 0.1 The one verification limitation, stated up front

**The 12 new `real_infra` tests have not executed anywhere.** Docker is
unavailable in the authoring environment — `docker info` reports **NOT
available** — and protocol §10.1 is explicit that this is *"a disclosure
obligation, not a pass."*

**This slice is therefore implementation-complete and locally verified to the
full extent available, but it is NOT fully verified.** The load-bearing
evidence for the dispatch path, the real bounded timeout and decision-log
persistence is delegated to CI, and §6.1 enumerates every delegated test by name.
No claim of real-infrastructure success is made in this document.

> **SUPERSEDED 2026-09-21 — see §12.** The delegation resolved. CI executed the
> tests, **found four real defects**, and after the ratified fix pass
> `real-infra (autonomy-engine)` reports **30 passed, 0 failed, 272
> deselected** with **40/40 checks green**. The text above is preserved exactly
> as written because it was true and correctly disclosed when written — and
> because it is the reason the defects were found rather than shipped. **§12
> carries the current status; this paragraph is history.** Docker remained
> unavailable locally throughout, so **no local real-infra execution is
> claimed** even now: every real-infra result in this record came from CI.

---

## 1. Status

| | |
|---|---|
| **Slice 4F.5** | **COMPLETE and VERIFIED** — implementation, local checks **and executed real-infrastructure evidence**, all green (§12). *(This row read "IMPLEMENTATION-COMPLETE; locally verified; real-infrastructure evidence PENDING in CI" until 2026-09-21, which was accurate while the evidence was pending; preserved per protocol §0.3.4)* |
| **Phase 4F** | **NOT complete.** 4F.6–4F.8 not started |
| **4F.1 – 4F.4** | **Intact.** None is touched, rewritten or reinterpreted |
| **`main`** | `7e273e62e942ecd5528ca807e65933d6bb675669` — **untouched** |
| **`phase-4`** | `e83f1f314451c795184301e1d83205a31412fce2` — **untouched** |
| **`phase-4f.5`** | **All verification below was performed at `6a1ca27f99ba224d8fc755548bfdcd9a8fb39fb5`**, the last commit that touches code. The branch head is higher: it also carries the documentation-only commits that create this record (§7) |
| **CF-9 / CF-10 / CF-11** | **All OPEN** (§8.2). **Unchanged by the fix pass** |
| **Deferred ledger** | **16 rows** — L-17 opened by this slice, **L-18 opened by the fix pass** (§10). *(This read "15 rows" before L-18; preserved per protocol §0.3.4)* |
| **CI** | **40/40 SUCCESS** at `f0ee8ae` (§12.7) |

### 1.1 The slice's exit criterion (TDD 4F §18)

> ***"Level 2: selectable, policy-permitted, single dispatch, `action.execute`
> publication."* Proves: *the five states, separately.***

**Met for the three states this slice owns.** State 1 (*Defined*) was already
true; **state 4 (*Triggered*) is CF-11 and belongs to 4F.6**, which is why
§8.2 records that 4F.5 contributes no CF-11 evidence.

| State | Owner | Outcome |
|---|---|---|
| 1 Defined | — | Already true at base |
| **2 Selectable** | **4F.5** | `SELECTABLE_LEVELS` includes `ASSISTED`; `PUT /v1/autonomy/level {"level": 2}` returns 200 |
| **3 Policy-permitted** | **4F.5** | `PolicyEffect.AUTO_EXECUTE`, bounded to `low`, fail-closed by absence |
| 4 Triggered | **4F.6** | **Untouched.** `decide()` still has **zero** production callers |
| **5 Executing** | **4F.5** | `action.execute` dispatched as a request/reply RPC, 15 s bounded |

---

## 2. Category 2 — the seventeen acceptance criteria

Each is TDD 4F.5 §11's claim, then the evidence. **X-17 was added by the
2026-09-20 ratification**, so the set is X-1 … X-17, not X-1 … X-16.

| # | Claim | Evidence | Status |
|---|---|---|---|
| **X-1** | Level 2 selectable, persisted in real Postgres | `test_x1_level_two_is_selectable_through_the_production_route` — real uvicorn in-loop, real HTTP, real repository, `SMALLINT` verified by **independent SQL** | **PASS** (executed) |
| **X-2** | Levels 3–5 still 422 with the reason | `test_levels_three_to_five_are_rejected_with_422_and_a_reason[3,4,5]` + real-route variant | **PASS** |
| **X-3** | `AUTO_EXECUTE` + LOW + every applicable gate → **exactly one** dispatch | `test_a_level_two_decision_dispatches_over_real_nats_and_persists_execute`; unit twin asserts `len(payloads) == 1` | **PASS** (executed) |
| **X-4** | Identical request at Level 1 → suggestion, no RPC | `test_x4_the_identical_request_at_level_one_proposes_and_dispatches_nothing` | **PASS** |
| **X-5** | Absent policy → approval, dispatches nothing | `test_invariant_1_absent_policy_does_not_dispatch` + real-bus variant | **PASS** |
| **X-6** | `moderate`+ never auto-executes | `test_invariant_4_auto_execute_is_inert_above_low[moderate,high,critical]` | **PASS** |
| **X-7** | `DENY` beats `AUTO_EXECUTE` | `test_invariant_5_deny_beats_auto_execute_at_any_ordering[deny-first,auto-first]` | **PASS** |
| **X-8** | No code path differs up to the dispatch point | `test_x8_both_runs_consult_the_same_gates_in_the_same_order` — `SpyTrustSource`, both runs reach trust | **PASS** |
| **X-9** | Level 2 cannot execute by flag alone | `test_control_3_a_flag_without_a_wired_path_still_fails`; `test_level_two_without_a_wired_dispatcher_raises_rather_than_executing` | **PASS** |
| **X-10** | Publishes `action.execute` and nothing else | `test_control_6_this_engine_publishes_action_execute_and_nothing_else` + real-bus `SubjectNotAllowedError` | **PASS** |
| **X-11** | Decision log records the execution, with the permitting policy checks | `test_a_level_two_decision_dispatches_over_real_nats_and_persists_execute` — asserts `outcome`, `autonomy_level` **and** `policy_checks` | **PASS** (executed) |
| **X-12** | CF-10 still unresolved | 4E's five sub-properties `test_control_9a`–`9e` pass **unmodified** in `digital-twin-engine`, incl. **9d** (autonomy's trust adapter byte-identical); plus `score is None`, `input_status is UNAVAILABLE` | **PASS** |
| **X-13** | No reply in 15 s → timeout outcome, no retry, no duplicate | `test_a_silent_responder_produces_a_persisted_timeout_and_no_retry` + 4 unit tests | **PASS** (executed) |
| **X-14** | Missing any execution field → suggestion, no RPC | `test_invariant_6_a_missing_execution_field_yields_a_suggestion[×3]` + real-bus variant | **PASS** |
| **X-15** | `permits_execution` is eligibility, not permission | `test_x15_each_precondition_is_independently_load_bearing` — four removals, each alone stops dispatch | **PASS** |
| **X-16** | Trust `UNAVAILABLE` never coerced into a pass | `test_invariant_7a/7b`, `test_no_threshold_is_consulted_on_the_dispatch_path` | **PASS** |
| **X-17** | Request/reply, never fire-and-forget | `test_control_6_the_only_bus_call_is_a_request_for_action_execute` — AST: `requesters == ["action_dispatch.py"]` | **PASS** |

**(executed)** marks a criterion whose evidence is a `real_infra` test that
**has now run against real PostgreSQL and a real NATS broker in CI** and
passed — see §12.5.

> **Correction, 2026-09-21 — additive, per protocol §0.3.4.** These four rows
> (**X-1**, **X-3**, **X-11**, **X-13**) read **"PASS (CI)"**, under a legend
> that read *"**(CI)** marks a criterion whose evidence is a `real_infra` test
> that has **not executed locally**."* That was the honest marking while the
> evidence was pending. CI then **falsified three of the four**: X-1 and X-11
> failed outright and X-13 failed in part, on two test-only SQL defects and one
> genuine production gap (§12.1–§12.3). **X-3 was the only one of the four that
> CI proved on its first run.** All four are now proven by **executed**
> evidence at `f0ee8ae`; the marker is changed rather than the history.

**X-5, X-6, X-7, X-9, X-14, X-15 and X-16 are the ones that matter most.** A
Level-2 implementation that dispatched slightly too eagerly would satisfy X-1,
X-3 and X-11 and still be a serious security defect.

### 2.1 The twenty negative and security cases

Audited at `6a1ca27`. **`action.execute` dispatched?**

| Case | | Case | |
|---|---|---|---|
| No policy | **NO** | Level 0 | **NO** |
| `REQUIRE_APPROVAL` | **NO** | Level 1 | **NO** |
| `DENY` | **NO** | Level 2, all gates | **YES — once** |
| `DENY` + `AUTO_EXECUTE` | **NO**, both orderings | Permission denial | **NO** |
| Above LOW (×3 tiers) | **NO** | Trust `UNAVAILABLE` | **YES** — non-blocking, not a PASS |
| At LOW | **YES — once** | Future Trust DENY seam | **NO** |
| At NEGLIGIBLE | **YES — once** | Absent identity policy | **N/A — stage 3's, untouched** |
| Missing `action_type` | **NO** | Empty identity policy row | **N/A — stage 3's, untouched** |
| Missing `execution_target` | **NO** | Bounded timeout | **once, then `TIMEOUT`, no retry** |
| Missing `verification_method` | **NO** | Duplicate protection | **one RPC per decision** |

### 2.2 What this slice explicitly does not claim

- **It does not close CF-11.** It adds **no production caller of `decide()`**,
  which is verified rather than asserted: the count is still **zero**.
- **It does not run AC-8.** That acceptance run is **4F.8's**.
- **It does not close CF-9 or CF-10**, and contributes evidence to neither.
- **It does not claim real-infrastructure success** (§0.1).

---

## 3. Category 1 — implementation against the TDDs and ADRs

### 3.1 The eight deliverables (TDD 4F.5 §4)

| # | Deliverable | Delivered as |
|---|---|---|
| 1 | Level 2 selectable | `domain/models.py` — `SELECTABLE_LEVELS` += `ASSISTED`. **No route change**; the selector derives `selectable` from the set |
| 2 | `permits_execution` level-aware | `domain/levels.py` — `level >= ASSISTED`; `_forbid_execution` **replaced** by `_require_execution_path` |
| 3 | `PolicyEffect.AUTO_EXECUTE` | `domain/models.py` + `domain/policy.py`. **Existing `TEXT` column**, no migration |
| 4 | The single dispatch point | `domain/decision.py` — one read of `GateReport.requires_approval` → `_dispatch_or_propose` |
| 5 | `action.execute`'s first producer | `clients/action_dispatch.py` (new), `domain/ports.py`, `events/published.py`, `main.py`, `config.py` |
| 6 | Execution fields on `DecisionRequest` | `domain/decision.py` — three optional fields, required at the dispatch branch |
| 7 | Distinguishable timeout outcome | `domain/models.py` — `DecisionOutcome.TIMEOUT`, persisted in the **existing** log |
| 8 | Tests | 43 unit + 12 real-infra, across three tiers |

**Eight of eight.**

### 3.2 The four ratified decisions, verified as built

| Decision | As built |
|---|---|
| **D-4F5-1** — `AUTO_EXECUTE`, not `ALLOW` | `evaluate_policies` narrows a match to a permission only when **nothing denied**, **no `REQUIRE_APPROVAL` also matched**, and **`risk_at_most(risk, LOW)`**. `evaluate_gates` then lowers `requires_approval` from its `True` default **only** on that, so absence never touches it |
| **D-4F5-2** — execution fields | `_execution_payload` returns `None` when any field is absent → suggestion. **No `PermissionCategory`→`ActionType` table, no implicit defaults** |
| **D-4F5-3** — 15 s bounded, no retry | `config.action_execute_timeout_seconds = 15.0`, converted to `15_000` ms for that call only. One RPC per decision on every path |
| **D-4F5-4** — eligibility, not permission | `permits_execution(level) → level >= ASSISTED`; dispatch additionally requires **all seven** §22.4 preconditions, each independently load-bearing |

### 3.3 The Trust contract, as built (§22.7)

**`trust.py` was not edited.** `_trust_denies` asks whether trust *refused*, so a
`False` never means trust approved:

- **`UNAVAILABLE` is not a PASS** — nothing records, reports or branches on trust
  as having passed; a dispatch is attributable to preconditions 1–3 and 5–7.
- **`UNAVAILABLE` is not a number** — `TrustScore.score` stays `None`.
- **No Trust threshold exists**, and `satisfies_threshold` is **not called** on
  the dispatch path — a test makes calling it an error.
- **A future explicit Trust DENY remains blocking** — asserted by driving the
  seam directly, **without building the CF-10 implementation** that would
  produce one.

### 3.4 Architectural boundaries, each verified at `6a1ca27`

| Boundary | Result |
|---|---|
| `action-engine` | **0 files changed** |
| `action-engine` stage 3 (`pipeline.py`) | **0-line diff** — byte-identical |
| Migrations / ORM | **0** — the `autonomy` schema has **zero CHECK constraints**; `policy.effect` and `decision_log.outcome` are `TEXT` |
| `nova-contracts`, `apps`, `api-gateway`, `ws-gateway`, `world-model-engine` | **0 files changed** |
| New REST route | **None.** `PUT /v1/autonomy/level` changed behaviour only |
| Gateway exposure | **None added** |
| Browser exposure | **None.** `action.execute` is absent from `PUBLIC_TOPICS` |
| Production callers of `decide()` | **Zero, unchanged** — CF-11 stays 4F.6's |

### 3.5 The one disclosed retirement

Adding `"action.execute"` to `PUBLISHABLE_SUBJECTS` **retires 4D's control 8**
(*"this engine never calls the bus at all"*). TDD 4F §11.2 authorised this
explicitly — *"Disclosed, not silent"* — and §16 control 6 replaces it with
***"publishes `action.execute` and nothing else."***

**The replacement is implemented, not merely documented**, in two halves: the
allow-list assertion, and an AST check that the only bus call in the package is
`.request()` in `action_dispatch.py`. **Nine 4D controls were retargeted, never
deleted**, each preserving its original wording inline as a dated note. Per TDD
4F §11.2 this needs **no new ledger row**, and none was created for it.

---

## 4. Category 8 — contracts and codegen

| Check | Result |
|---|---|
| Registered Event Bus subjects | **119**, unchanged — counted from the runtime registry |
| `action.execute` | **Already registered** since Phase 3D; 4F.5 supplies its first producer |
| **New subjects** | **0** |
| `PUBLIC_TOPICS` | **18**, byte-identical; `action.execute` **not** in it |
| `PUBLISHABLE_SUBJECTS` | **exactly `{"action.execute"}`** |
| `SUBSCRIBABLE_SUBJECTS` | **empty**, unchanged |
| Codegen drift | **117 files, zero drift** |
| `nova-contracts` diff | **0 files** |

---

## 5. Category 9 — tests, lint, types, imports

| Check | Result |
|---|---|
| `pytest -m "not real_infra"` (autonomy) | **263 passed**, 28 deselected |
| `turbo run test --force` | **32/32, `Cached: 0` — 2,833 passed** |
| `turbo run lint` | **32/32** |
| `turbo run typecheck` | **5/5** |
| `turbo run build` | **32/32** |
| `ruff` / `mypy` (autonomy) | clean / **27 files, no issues** |
| `tools/tests` | **295 passed** |
| `lint-imports` | **7 kept, 0 broken** |

**55 tests added**: 34 unit (dispatch decision), 9 unit (the adapter), 12
real-infra. Nine 4D controls retargeted.

---

## 6. Category 10 — real infrastructure

**This is the slice's disclosure obligation, and it is not a pass.**

`docker info` → **NOT available**. The 12 `real_infra` tests in
`tests/integration/test_level_two_real_postgres.py` have **never executed
anywhere**. They collect cleanly (28 selected of 291 for the engine, no import
errors) and their execution is **delegated entirely to CI**.

> **SUPERSEDED 2026-09-21 — see §12.5.** The delegation resolved, and the file
> now holds **14** tests rather than 12. `real-infra (autonomy-engine)` reports
> **30 passed, 0 failed, 272 deselected** — the 14 above plus the 16
> pre-existing — and **all 14 other real-infra jobs passed**. The paragraph
> above is preserved as written: it was true, and protocol §10.1's *"disclosure
> obligation, not a pass"* is exactly what made the four defects CI found
> findable. **`docker info` still reports NOT available locally**, so this
> record claims **no local real-infra execution** at any point; every
> real-infra result here came from CI.

### 6.1 Every delegated test, by name (protocol §10.1)

1. `test_x1_level_two_is_selectable_through_the_production_route`
2. `test_x2_levels_three_to_five_are_still_refused_through_the_route[3]`
3. `test_x2_levels_three_to_five_are_still_refused_through_the_route[4]`
4. `test_x2_levels_three_to_five_are_still_refused_through_the_route[5]`
5. `test_a_level_two_decision_dispatches_over_real_nats_and_persists_execute`
6. `test_trust_unavailable_did_not_block_that_dispatch`
7. `test_absent_policy_dispatches_nothing_over_the_real_bus`
8. `test_a_missing_execution_field_dispatches_nothing_over_the_real_bus`
9. `test_a_silent_responder_produces_a_persisted_timeout_and_no_retry`
10. `test_the_dispatch_client_raises_the_typed_timeout`
11. `test_the_real_bus_refuses_any_subject_but_action_execute`
12. `test_this_engine_still_subscribes_to_nothing`

### 6.2 Do they cover code this slice changed? — **Yes, centrally**

Protocol §10.1 asks this directly. 4F.5 changed the **decision pipeline**, added
an **Event Bus producer**, and made a new **decision-log outcome** persistable.
Every one of those is in the delegated set: the RPC path, the real bounded
timeout, `EXECUTE`/`TIMEOUT` persistence verified by **independent SQL**, and
the allow-list enforced by the real bus. **The exposure is material, not
incidental**, and it is why no "verified" claim is made here.

### 6.3 What the tests do, and do not, fake

| | |
|---|---|
| Real Postgres | Real container, the engine's own Alembic chain, the **production committing** `create_engine`/`create_session_factory` |
| **Not** the rollback fixture | `postgres_session_factory` binds sessions to one connection inside a rolled-back transaction, so writes never commit — wrong when the claim is persistence (TDD §12) |
| Real NATS | `NatsEventBus` against a real broker; the real allow-listed `BoundEventBus` |
| Real HTTP | In-loop uvicorn on a real socket — **not `TestClient`**, whose anyio portal runs on another thread and cannot share this loop's asyncpg connections |
| Independent verification | Raw SQL on its **own** connection, so a repository bug cannot agree with itself |
| The one stand-in | A real NATS responder for `action.execute`. **`action-engine`'s own consumer is proven by its own suite and is not modified here**; what this makes real is the *transport* |

`autonomy-engine` is **already** in `real-infra-checks.yml`'s matrix, so this
slice adds no CI row and **the CI workflow is untouched**.

---

## 7. Category 11 — PR, branch, commit and CI evidence

`phase-4f.5` is linear above `phase-4`, with **no rebase, no squash, no force
push**:

| SHA | |
|---|---|
| `d2cdf2e` | The implementation |
| **`6a1ca27`** | Closes the X-1 and X-11 evidence gaps the audit found; ratifies **L-17**. **Tests and documentation only — zero production files** |
| *(this record)* | This document, and the additive correction below. **Documentation only — zero production files, zero test files** |

**`6a1ca27` is the verification SHA.** Every figure, boundary check and test
count in this record was measured there, and nothing above it touches code.

**A record cannot cite its own SHA**, so the commits that create it are named by
role rather than by hash. The **PR head SHA is reported in the pull request
itself**, which is where §11.1's commit evidence is obtained.

**CI evidence: PENDING.** The PR is opened to obtain it. **No CI result is
claimed in this document**, and the record's status in §1 reflects that.

> **SUPERSEDED 2026-09-21 — see §12.7.** CI ran, went **RED**, and the ratified
> fix pass added four commits on top of this record. The branch now reads:
>
> | SHA | |
> |---|---|
> | `d2cdf2e` | The implementation |
> | `6a1ca27` | The audit's evidence gaps; ratifies **L-17** |
> | `8af7d72`, `a593d04` | This record, and its branch-shape correction |
> | **`568bb2f`** | **`NoRespondersError` is not a timeout** — the one production change of the fix pass (§12.3) |
> | **`442e71b`** | The two schema-name test defects, and the no-responder tests (§12.1, §12.2) |
> | **`082fe00`** | The retargeted 4D Level-2 control and its `vitest` twin (§12.4) |
> | **`f0ee8ae`** | The TDD amendments: §22.8, §22.9 and **L-18** |
>
> **`f0ee8ae` is the final verified SHA**, with **40/40 checks SUCCESS**. Still
> linear, still **no rebase, no squash, no force-push**. The paragraph above is
> preserved because "PENDING" was the correct statement when written.

> **Correction, 2026-09-21 — additive, per protocol §0.3.4.** This section first
> read *"`phase-4f.5`, two commits above `phase-4`"* and listed two SHAs. That
> was written before this record was committed and was true only of the code
> history. The original wording is preserved here; the count above supersedes
> it. **No verification figure changed** — all of them were and remain measured
> at `6a1ca27`.

### 7.1 The audit that produced `6a1ca27`

The implementation audit against the TDD's own criteria found **two evidence
gaps and no production defect**:

- **X-1** required a real-infra test through the production route; the only
  level-setting test was at the fake-repository tier.
- **X-11** required the **permitting policy checks** in the log row; the
  assertion covered `outcome` and `autonomy_level` only.

Both are closed. **The implementation itself was correct as audited** — the
fixes added evidence that was owed, and changed no production file.

---

## 8. Category 13 — findings and carry-forwards

### 8.1 Findings

| # | Finding | Disposition |
|---|---|---|
| **X-1 gap** | Required real-infra tier missing | **CLOSED** at `6a1ca27` |
| **X-11 gap** | `policy_checks` not asserted | **CLOSED** at `6a1ca27` |
| **Frontend enum** | The panel cannot author `AUTO_EXECUTE` | **OPEN as L-17** (§10.3) |
| **Real-infra execution** | Docker unavailable locally | **OPEN — delegated to CI** (§6) |

### 8.2 CF-9, CF-10 and CF-11 — all OPEN

| | Status | 4F.5's contribution |
|---|---|---|
| **CF-9** | **OPEN** — conditions 2 and 5 unmet | **None.** 4F.5 *relies on* 4F.4's write surface; it adds no closure evidence |
| **CF-10** | **OPEN** — Trust Engine unavailable | **None.** Re-asserted unresolved by X-12; §22.7 states 4F.5 must not close it |
| **CF-11** | **OPEN** — the initiative trigger's producer | **None. 4F.6's.** 4F.5 adds **no caller of `decide()`**, so it cannot contribute evidence even incidentally |

### 8.3 Other carry-forwards, unchanged

AC-7/AC-8 acceptance run → **4F.8** · downstream world-model E2E → **4F.8** ·
`/v1/cognitive-state` + panel → **4F.7** · the trigger → **4F.6**.

---

## 9. Category 14 — documentation updated by this slice

| Document | Change | Additive? |
|---|---|---|
| [TDD 4F.5](../../design/phase-4/09-tdd-4f5-autonomy-level-2.md) | **§17.1.1** added — L-17's ledger entry | **Yes.** §17.1's prior sentence is preserved inline |
| This record | Created | n/a |

**No historical record was rewritten.** The 4F.2, 4F.3 and 4F.4 completion
records are untouched, 4F.4 is not reopened, and **L-15 and L-16 are unaltered**.
The nine retargeted 4D controls are documented in the code that retargets them,
authorised by TDD 4F §11.2 — **no separate finding or ledger row was created for
them**, per that authorisation.

**Not updated, and deliberately so:** `ENGINEERING_ROADMAP.md` has no 4F.5 row
(**L-4**, 4F closure); `docs/project-health/phase-4f.md` does not exist
(**L-2**, 4F closure). Both are pre-existing ledger rows, not new gaps.

---

## 10. Deferred-obligations ledger — protocol §0.2

**A Sub-Phase may not be declared complete while any row here is unsettled** —
which is why Phase 4F is not complete.

### 10.1 Settled by this slice

**None.** 4F.5 settles no pre-existing ledger row.

### 10.2 Still open, each with its owner — sixteen rows

*(This heading read "fifteen rows" until **L-18** was opened on 2026-09-21; preserved per protocol §0.3.4.)*

| # | Obligation | Owner | Blocks 4F.5? |
|---|---|---|---|
| L-1 | 4F Gate Review (category 3) | **4F closure, after 4F.8** | No |
| L-2 | `docs/project-health/phase-4f.md` (category 4) | **4F closure** | No |
| L-3 | `project-health-master.md` summary row for 4F | **4F closure** | No |
| L-4 | `ENGINEERING_ROADMAP.md` 4F row | **4F closure** | No |
| L-5 | `00-master-scope.md` §17 SLOC table + §2 methodology — **F-2's owner** | **4F closure** | No |
| L-6 | `README.md` — *"a new engine now exists"* | **4F closure** | No |
| L-8 | `ws-gateway/README.md` — the `perception.*` narrowing | **4F closure** | No |
| L-9 | Cross-file consistency sweep (category 12) | **4F closure** | No |
| L-10 | `docs/` staleness sweep (category 6) | **4F closure** | No |
| L-11 | Fusion for workspace signals | **4F closure** | No |
| L-13 | `known_projects` population | **4F closure or later** | No |
| L-14 | Filesystem consent policy | **4F closure**, or earlier if ratified | No |
| L-15 | `IdentityConfidencePolicy` mutations unaudited | **`action-engine`** | No |
| L-16 | `action-engine/README.md` Owned APIs list | **`action-engine` / 4F closure** | No |
| **L-17** | **Opened by 4F.5 — see §10.3** | **`autonomy-engine` frontend** | No |
| **L-18** | **Opened by 4F.5's fix pass — see §10.4** | **`nova-eventbus-sdk`** | No |

**L-1 … L-16 are carried forward unchanged.** None is closed, absorbed, renamed
or renumbered. **L-17 and L-18 are both OPEN**, and 4F.5 closes neither.

### 10.3 L-17 — opened by this slice, ratified 2026-09-21

| | |
|---|---|
| **Row** | **L-17** |
| **Status** | **OPEN** |
| **Obligation** | **The autonomy frontend policy-authoring enum is stale and does not expose the ratified `AUTO_EXECUTE` effect supported by the 4F.5 API.** `apps/web-client/src/entities/autonomy.ts` declares `POLICY_EFFECTS = ["deny", "require_approval"]` |
| **Owner** | **`autonomy-engine` frontend** |
| **Settled by** | **A later policy-authoring / UI scope** |

**Product scope, not a defect and not a security hole.** The backend accepts
`AUTO_EXECUTE` through the existing `POST`/`PATCH /v1/autonomy/policies` routes;
the panel simply cannot author one yet. Nothing is mis-rendered and no gate is
bypassed.

**Why 4F.5 does not close it.** TDD 4F.5 §18 lists *"A policy authoring UI —
**Not in 4F at all**"* as an explicit non-goal, and §5 forbids new browser
exposure. **Verified: `apps/` has zero files changed**, and `AUTO_EXECUTE`
appears nowhere under `apps/`.

### 10.4 L-18 — opened by the fix pass, ratified 2026-09-21

| | |
|---|---|
| **Row** | **L-18** |
| **Status** | **OPEN** |
| **Obligation** | **The NATS backend does not translate `NoRespondersError` into the SDK's transport abstraction, leaving multiple request clients exposed to raw NATS transport errors.** `packages/nova-eventbus-sdk/.../backends/nats.py` catches `nats.errors.TimeoutError` and re-raises the builtin `TimeoutError`, but has no equivalent for the zero-subscriber signal, so `nats.errors.NoRespondersError` escapes `BoundEventBus` unchanged |
| **Owner** | **`nova-eventbus-sdk` / a later maintenance scope** |
| **Settled by** | **An SDK pass that completes the translation layer** |

**Repository-wide, not 4F.5-specific.** `NoResponders` appears **nowhere** in
the repository, and **every** bus client catches exactly `TimeoutError` and
nothing else — across `perception-engine`, `executive-cognition-engine`,
`capability-engine`, `communication-engine`, `digital-twin-engine` and others.
Each carries the same exposure whenever its target engine is not subscribed.
4F.5 is simply the first slice whose subject has **no** production subscriber,
so it is the first to reach the condition.

**Why 4F.5 does not close it.** The ratified fix site is
`ActionDispatchClient` alone (TDD §22.8.4). **`nova-eventbus-sdk` was
deliberately not modified — 0 files** — because changing it would alter
transport-error handling for six engines at once, inside a slice whose boundary
table forbids touching them, and would deserve its own tests and ratification.
**4F.5 defends itself and discloses the rest.**

---

## 11. Final status

**Phase 4F.5 is IMPLEMENTATION-COMPLETE and locally verified to the full extent
available. It is NOT fully verified, and this record does not claim it is.**

*Locally verified* means: all seventeen acceptance criteria have named evidence;
eight of eight deliverables are built; the four ratified decisions hold
structurally; 2,833 tests pass with lint, types, imports and codegen green; and
every architectural boundary is verified rather than asserted.

*Not fully verified* means: **the 12 `real_infra` tests have not executed
anywhere.** Protocol §10.1 makes that a disclosure obligation rather than a
pass, and they cover exactly the code this slice changed (§6.2).

**And, stated as plainly as the status itself:**

- **Phase 4F is NOT complete.** 4F.6, 4F.7 and 4F.8 have not started. Its Gate
  Review and Project Health record are 4F.8's, ledgered as **L-1** and **L-2**.
- **No Go / Conditional-Go / No-Go verdict is issued here** — category 3.
- **No Phase 4 closure is claimed.**
- **4F.1 – 4F.4 remain intact** and are not reinterpreted.
- **`main` is untouched** at `7e273e62e942ecd5528ca807e65933d6bb675669`.
- **`phase-4` is untouched** at `e83f1f314451c795184301e1d83205a31412fce2`.
- **CF-9, CF-10 and CF-11 all remain OPEN**, with 4F.5 contributing to none.
- **No production caller of `decide()` was introduced** — CF-11 stays 4F.6's.
- **No new Event Bus subject, no API route, no gateway change, no browser
  exposure, no migration, no ORM change**, and **`action-engine` untouched**.
- **L-17 is OPEN**; L-1 … L-16 carried forward unchanged.

> **SUPERSEDED 2026-09-21 — see §12.** Everything in the bulleted list above
> still holds and is re-confirmed at `f0ee8ae`, with **one addition**: **L-18
> is also OPEN** (§10.4). What changed is the headline: the slice is no longer
> *"NOT fully verified"* — CI executed the delegated tests, found four defects,
> and after the ratified fix pass reports **40/40 green** including **30/30**
> autonomy-engine real-infra tests. The two paragraphs opening this section are
> preserved because they were accurate, and deliberately so, when written.

### 11.1 SLOC

**46,313 on the 4F scope. Headroom to the 50,000 hard gate: 3,687. The gate is
NOT crossed.**

> **Updated 2026-09-21.** At the final verified SHA `f0ee8ae` the figure is
> **46,337**, headroom **3,663** — **the gate is still NOT crossed**. The fix
> pass added **+24** to the 4F scope (Comparable **36,718**, Wider **42,059**,
> Full **45,691**), all of it `autonomy-engine` production source; the new
> tests contribute **0**, since tests are outside every scope. Same `cloc`
> v2.06 `--skip-uniqueness` over a pristine `git archive`, same flags. The
> figures below are preserved as measured at `6a1ca27`.

`cloc` v2.06 `--skip-uniqueness` over a pristine `git archive` of `6a1ca27`, the
4E Gate Review's tool and flags unchanged: Comparable **36,694**, Wider
**42,035**, Full **45,667**, **4F scope 46,313**.

Growth over 4F.4's 46,125 is **+188**, inside TDD 4F §17's **150–300** estimate
for *"Autonomy Level 2 + dispatch + publisher"*. All of it is `autonomy-engine`
production source; the 55 tests contribute **0**, since tests are outside every
scope (TDD 4F §17).

**Code was never moved or reduced to game the metric.**

---

## 12. Correction — 2026-09-21: CI executed the delegated tests

**Additive, per protocol §0.3.4.** Nothing above is deleted or rewritten. Every
statement in §0.1 through §11 was accurate when written, and the ones CI later
superseded carry a dated pointer to this section.

**This is the section that matters most in the whole record**, because it is
the one where the disclosed gap closed *against* the slice rather than for it.
Protocol §10.1 calls un-executed real-infra evidence *"a disclosure obligation,
not a pass."* §0.1 honoured that. **CI then found four real defects** — three
mine, one a genuine production gap — which is precisely what the obligation
exists to surface. Had the record claimed a pass, all four would have shipped.

### 12.0 What CI found, at a glance

| | First CI run (`a593d04`) | After the fix pass (`f0ee8ae`) |
|---|---|---|
| Checks | **2 failed** of 40 | **40/40 SUCCESS** |
| `real-infra (autonomy-engine)` | **4 failed**, 24 passed | **30 passed, 0 failed**, 272 deselected |
| Playwright | **failed** | **success** |

### 12.1 A1 — a test-only SQL read-back defect

**The failure.** `UndefinedTableError: relation "autonomy.autonomy_level_setting"
does not exist`, on `DELETE FROM autonomy.autonomy_level_setting`.

**The authority.** `alembic/versions/0001_initial_schema.py` creates
**`autonomy.autonomy_level`**. The `_setting` suffix existed **only** in the
test's raw SQL.

**Production code and the migration were not defective.** Nothing in `src/`
and nothing in the migration chain referenced the wrong name, and
`test_the_migration_creates_exactly_the_five_tables` **passed in the same run**,
proving the schema was built correctly. **Fixed in the test only.**

### 12.2 A2 — a second test-only SQL read-back defect

**The failure.** `UndefinedColumnError: column "subject_id" does not exist`, on
`SELECT subject_id, … FROM autonomy.decision_log`.

**The authority.** The domain field is **`subject_id`**; the persisted column is
**`action_id`**, as doc 07 defines it. `postgres_autonomy_repository` maps them
in **both** directions — `_log_to_orm` writes `action_id=entry.subject_id`, and
`_log_to_domain` reads `subject_id=row.action_id`.

**The production write succeeded and the repository mapping is correct.** In the
failing run, `await repository.append_decision_log(result.log_entry)` **completed
against real Postgres**; only the test's *independent* read-back — deliberately
raw SQL, so a repository bug could not agree with itself — named the domain
field where the column name was required. **Fixed in the test only**, and the
helper now records the field-versus-column distinction so it cannot recur.

### 12.3 A3 — a genuine production runtime gap, and its resolution

**This one was real.** `ActionDispatchClient` caught only `TimeoutError`, so
`nats.errors.NoRespondersError` propagated raw out of `dispatch()` — and
`_dispatch_or_propose` did not handle it either.

**`NoRespondersError` is distinct from the 4F.5 `TIMEOUT` outcome.**

| | **`TIMEOUT`** (§22.3) | **Unavailable** (§22.8) |
|---|---|---|
| What happened | The request reached a responder; no reply within **15 s** | The broker had **zero subscribers** and answered at once |
| Did the action run? | **Unknown — it may have** | **No. There is no responder, so no execution occurred** |
| Outcome recorded | `DecisionOutcome.TIMEOUT` | **`DecisionOutcome.PROPOSE`** |

**The resolution.** The adapter now translates the broker's zero-subscriber
signal into the typed **`ActionDispatchUnavailable`** condition. That condition
**fails §22.4 precondition 6** — *"the `action.execute` path is available"* —
whose structural pre-dispatch check (port wired, subject publishable) is now
complemented by runtime responder availability. §22.4's own consequence then
applies unchanged: no `action.execute`, the decision stays non-executing,
fail-safe preserved. **The existing non-executing proposal path is reused.**

**No new outcome, table, column, migration or audit mechanism was introduced.**
**The existing `PROPOSE` `DecisionLogEntry` plus its `Suggestion` are the audit
representation** — they already carry the level, the policy checks, the subject
id and a reason. The reason is made *specific* ("no subscriber… the action was
not executed… not retried") so an unreachable executor and an ordinary approval
requirement do not read alike, and it **omits the timeout's "may still have
executed" hedge**, which would be the opposite claim on this path. One attempt,
**no retry**. `TIMEOUT` semantics are untouched and remain reserved for the
bounded 15-second no-reply condition.

**Fixed in `ActionDispatchClient` only.** `nova-eventbus-sdk` is **not**
modified; the wider gap is **L-18** (§10.4).

### 12.4 The Playwright control — a stale 4D-era expectation

`apps/web-client/tests/e2e/autonomy-suggestion.spec.ts` asserted **Level 2 is
present and disabled** — 4D decision **D-1**, whose own wording assigns enabling
Level 2 to *milestone 4F*. **4F.5 is that milestone**, and **X-1 intentionally
makes Level 2 selectable**, so the expectation was stale by design rather than
wrong. `_level_options()` renders levels 0–2 and marks each selectable from
`SELECTABLE_LEVELS`; once `ASSISTED` joined it, nothing rendered the
`level-disabled` state at all.

**The test was retargeted, not deleted.** It now requires that no element
renders the disabled state, that the Assisted option is present exactly once,
and that its control is **enabled** — strictly stronger than the single
`toBeDisabled()` it replaces. The control keeps its identity and its 4D wording
as a dated note.

**The `vitest` twin was de-vacuated in the same pass.** It had kept passing
because its stubbed payload still described the 4D state — it was asserting a
fixture, not the engine. Leaving it would have left a green test guarding a
state that no longer exists. The spec's own comment had predicted exactly this:
*"Asserted here as well as in `vitest` because only the real engine can be wrong
about it."*

**No production web-client source was changed — `apps/web-client/src/`: 0
files.** No UI capability was added and no API behaviour changed.

### 12.5 Real-infrastructure evidence — executed, in CI

| | |
|---|---|
| `real-infra (autonomy-engine)` | **30 passed, 0 failed, 272 deselected** |
| Composition | **14** in `test_level_two_real_postgres.py` + **16** pre-existing |
| All other real-infra jobs | **Passed** — 14 of 14 |
| Local execution | **None claimed.** `docker info` reports **NOT available** in the authoring environment, at every point in this slice |
| Source of the evidence | **CI**, at `f0ee8ae` |

**X-1, X-3, X-11 and X-13 are proven by executed real-infrastructure
evidence** against real PostgreSQL and a real NATS broker. X-3 was the only one
of the four CI proved on its first run; the other three were falsified first and
are proven now.

### 12.6 Playwright evidence

**The job completed successfully.** The stale `level-disabled` assertion was
corrected (§12.4), and the previous run's
`ERR_PNPM_RECURSIVE_RUN_FIRST_FAIL` / `Exit status 1` is **gone**.

**No per-test count is claimed.** The summary line sits above what the log API
returns, and this record does not state numbers it cannot evidence. The check
run's conclusion — **success** — is the claim, and it is the whole claim.

### 12.7 Final verification, at `f0ee8ae`

| | |
|---|---|
| **HEAD before this documentation commit** | **`f0ee8ae5a2f0f89cecf073ac7b201be09fad90f1`** |
| **`phase-4`** | `e83f1f314451c795184301e1d83205a31412fce2` — **unchanged** |
| **`main`** | `7e273e62e942ecd5528ca807e65933d6bb675669` — **unchanged** |
| **Working tree** | **clean** before this documentation update |
| **CI** | **40/40 SUCCESS** |
| `turbo lint typecheck build test --force` | **99/99**, `Cached: 0` |
| `ruff check` | **clean** |
| `mypy` | **clean** |
| import-linter | **7 kept, 0 broken** |
| codegen | **117 files, zero drift** |
| `tools/tests` | **295 passed** |
| Registered subjects | **119** |
| `PUBLIC_TOPICS` | **18** |
| `PUBLISHABLE_SUBJECTS` | exactly `{"action.execute"}` |
| `SUBSCRIBABLE_SUBJECTS` | **empty** |
| **SLOC (4F scope)** | **46,337** |
| **Headroom to the 50,000 gate** | **3,663** — **not crossed** |

### 12.8 Boundaries, re-confirmed after the fix pass

Measured as `git diff --name-only e83f1f3..f0ee8ae` over each path:

| | |
|---|---|
| `action-engine` | **0 files** |
| Stage 3 pipeline | **0 files** |
| Migrations | **0 files** |
| ORM / repository | **0 files** |
| `nova-eventbus-sdk` | **0 files** — the deliberate L-18 boundary |
| `apps/web-client/src/` | **0 production files** |
| `nova-contracts` | **0 files** |
| CI workflows | **0 files** |

### 12.9 What remains open — unchanged by the fix pass

- **CF-9 OPEN. CF-10 OPEN. CF-11 OPEN.** 4F.5 closes none of them, and the fix
  pass changed nothing here. **CF-11 in particular remains OPEN because there
  are still no production callers of `decide()`** — **4F.6 owns the trigger
  path**, and 4F.5 adds no caller, so it cannot contribute closure evidence
  even incidentally.
- **L-17 OPEN** — the stale web-client policy-authoring enum. **Not fixed in
  4F.5**; §18 lists a policy authoring UI as *"Not in 4F at all."*
- **L-18 OPEN** — the broader `nova-eventbus-sdk` handling of
  `NoRespondersError`. **4F.5 intentionally did not modify the SDK**; owner
  remains **`nova-eventbus-sdk` / later maintenance**.
- **Phase 4F is NOT complete.** 4F.6, 4F.7 and 4F.8 have not started.
- **No Go / Conditional-Go / No-Go verdict is issued here** — category 3 is the
  Gate Review, and a slice defers it. **L-1** still owns it.
