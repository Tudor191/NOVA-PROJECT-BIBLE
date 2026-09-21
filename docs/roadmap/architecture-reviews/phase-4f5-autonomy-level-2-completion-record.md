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

---

## 1. Status

| | |
|---|---|
| **Slice 4F.5** | **IMPLEMENTATION-COMPLETE; locally verified; real-infrastructure evidence PENDING in CI** |
| **Phase 4F** | **NOT complete.** 4F.6–4F.8 not started |
| **4F.1 – 4F.4** | **Intact.** None is touched, rewritten or reinterpreted |
| **`main`** | `7e273e62e942ecd5528ca807e65933d6bb675669` — **untouched** |
| **`phase-4`** | `e83f1f314451c795184301e1d83205a31412fce2` — **untouched** |
| **`phase-4f.5`** | `6a1ca27f99ba224d8fc755548bfdcd9a8fb39fb5` — two commits above base |
| **CF-9 / CF-10 / CF-11** | **All OPEN** (§8.2) |
| **Deferred ledger** | **15 rows**, L-17 opened by this slice (§10) |

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
| **X-1** | Level 2 selectable, persisted in real Postgres | `test_x1_level_two_is_selectable_through_the_production_route` — real uvicorn in-loop, real HTTP, real repository, `SMALLINT` verified by **independent SQL** | **PASS** (CI) |
| **X-2** | Levels 3–5 still 422 with the reason | `test_levels_three_to_five_are_rejected_with_422_and_a_reason[3,4,5]` + real-route variant | **PASS** |
| **X-3** | `AUTO_EXECUTE` + LOW + every applicable gate → **exactly one** dispatch | `test_a_level_two_decision_dispatches_over_real_nats_and_persists_execute`; unit twin asserts `len(payloads) == 1` | **PASS** (CI) |
| **X-4** | Identical request at Level 1 → suggestion, no RPC | `test_x4_the_identical_request_at_level_one_proposes_and_dispatches_nothing` | **PASS** |
| **X-5** | Absent policy → approval, dispatches nothing | `test_invariant_1_absent_policy_does_not_dispatch` + real-bus variant | **PASS** |
| **X-6** | `moderate`+ never auto-executes | `test_invariant_4_auto_execute_is_inert_above_low[moderate,high,critical]` | **PASS** |
| **X-7** | `DENY` beats `AUTO_EXECUTE` | `test_invariant_5_deny_beats_auto_execute_at_any_ordering[deny-first,auto-first]` | **PASS** |
| **X-8** | No code path differs up to the dispatch point | `test_x8_both_runs_consult_the_same_gates_in_the_same_order` — `SpyTrustSource`, both runs reach trust | **PASS** |
| **X-9** | Level 2 cannot execute by flag alone | `test_control_3_a_flag_without_a_wired_path_still_fails`; `test_level_two_without_a_wired_dispatcher_raises_rather_than_executing` | **PASS** |
| **X-10** | Publishes `action.execute` and nothing else | `test_control_6_this_engine_publishes_action_execute_and_nothing_else` + real-bus `SubjectNotAllowedError` | **PASS** |
| **X-11** | Decision log records the execution, with the permitting policy checks | `test_a_level_two_decision_dispatches_over_real_nats_and_persists_execute` — asserts `outcome`, `autonomy_level` **and** `policy_checks` | **PASS** (CI) |
| **X-12** | CF-10 still unresolved | 4E's five sub-properties `test_control_9a`–`9e` pass **unmodified** in `digital-twin-engine`, incl. **9d** (autonomy's trust adapter byte-identical); plus `score is None`, `input_status is UNAVAILABLE` | **PASS** |
| **X-13** | No reply in 15 s → timeout outcome, no retry, no duplicate | `test_a_silent_responder_produces_a_persisted_timeout_and_no_retry` + 4 unit tests | **PASS** (CI) |
| **X-14** | Missing any execution field → suggestion, no RPC | `test_invariant_6_a_missing_execution_field_yields_a_suggestion[×3]` + real-bus variant | **PASS** |
| **X-15** | `permits_execution` is eligibility, not permission | `test_x15_each_precondition_is_independently_load_bearing` — four removals, each alone stops dispatch | **PASS** |
| **X-16** | Trust `UNAVAILABLE` never coerced into a pass | `test_invariant_7a/7b`, `test_no_threshold_is_consulted_on_the_dispatch_path` | **PASS** |
| **X-17** | Request/reply, never fire-and-forget | `test_control_6_the_only_bus_call_is_a_request_for_action_execute` — AST: `requesters == ["action_dispatch.py"]` | **PASS** |

**(CI)** marks a criterion whose evidence is a `real_infra` test that has **not
executed locally** — see §0.1 and §6.1.

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

`phase-4f.5`, two commits above `phase-4`, linear, **no rebase, no squash, no
force push**:

| SHA | |
|---|---|
| `d2cdf2e` | The implementation |
| **`6a1ca27`** | Closes the X-1 and X-11 evidence gaps the audit found; ratifies **L-17**. **Tests and documentation only — zero production files** |

**CI evidence: PENDING.** The PR is opened to obtain it at this exact SHA
(protocol §11.1). **No CI result is claimed in this document**, and the record's
status in §1 reflects that.

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

### 10.2 Still open, each with its owner — fifteen rows

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

**L-1 … L-16 are carried forward unchanged.** None is closed, absorbed, renamed
or renumbered.

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

### 11.1 SLOC

**46,313 on the 4F scope. Headroom to the 50,000 hard gate: 3,687. The gate is
NOT crossed.**

`cloc` v2.06 `--skip-uniqueness` over a pristine `git archive` of `6a1ca27`, the
4E Gate Review's tool and flags unchanged: Comparable **36,694**, Wider
**42,035**, Full **45,667**, **4F scope 46,313**.

Growth over 4F.4's 46,125 is **+188**, inside TDD 4F §17's **150–300** estimate
for *"Autonomy Level 2 + dispatch + publisher"*. All of it is `autonomy-engine`
production source; the 55 tests contribute **0**, since tests are outside every
scope (TDD 4F §17).

**Code was never moved or reduced to game the metric.**
