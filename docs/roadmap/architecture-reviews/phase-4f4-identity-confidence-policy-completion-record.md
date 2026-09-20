# Phase 4F.4 — Slice Completion Record
## CF-9's write surface: the `IdentityConfidencePolicy` row stage 3 could never have

**Date:** 2026-09-20
**Slice:** 4F.4 of 4F's eight (TDD 4F §18)
**Branch:** `phase-4f.4`, at **`5706e4a7f6aafef3f1305bf04707ed7ce3f0aa0a`**
**Base:** `phase-4` at **`428ff25c1e5e78c79d60d7bf41d9710c947a4029`** — **unchanged by this slice**
**`main`:** **`7e273e62e942ecd5528ca807e65933d6bb675669`** — **untouched**
**PR:** [#33](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/pull/33) (`phase-4f.4` → `phase-4`) — **open and NOT merged**, `mergeable_state: clean`
**Protocol:** [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md),
sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`,
1131 lines, read from `origin/main` and verified in this session.
**TDDs:** [TDD 4F](../../design/phase-4/06-tdd-4f-companion-and-cognitive-state.md)
§5.2, §5.3, §5.4, §17, §18, §22 · [TDD 4F.4](../../design/phase-4/08-tdd-4f4-identity-confidence-policy.md) in full.
**ADR:** [ADR-032](../../architecture/adr/ADR-032-identity-confidence-is-also-an-authorization-signal.md) decision point 2.

---

## 0. What this document is, and is not

**This is a Slice completion record. It is not a Gate Review, and 4F.4 does not
get one.**

Protocol **§0.1**'s unit table reserves a Gate Review for a **Phase or
Sub-Phase** — *"Declaring the phase complete; writing its Gate Review"* — and
assigns a **Significant Slice** categories **1, 2, 8, 9, 10, 11, 13 and 14 in
full**, with categories **3–7 and 12 as a deferred-obligations ledger** (§0.2).
**Category 3 is precisely "Gate Review and Go / Conditional-Go / No-Go
criteria."** A slice defers it; it does not issue one.

This record therefore executes the eight in-full categories below and defers the
rest in writing (§11). **There is no Go / Conditional-Go / No-Go verdict here**,
because that verdict is category 3 and belongs to **4F's Gate Review, at 4F.8**,
where it is already ledgered as **L-1**. The slice's own verdict — *complete,
verified, closed* — is a different and narrower thing, and §12 states it.

This follows the [4F.2](phase-4f2-workspace-perception-completion-record.md) and
[4F.3](phase-4f3-nova-companion-completion-record.md) records, whose §0 says the
same in the same words for the same reason. It is not a reinterpretation.

**Phase 4F is NOT complete.** Four of eight slices (4F.5–4F.8) have not started.

---

## 1. Status

| | |
|---|---|
| **Slice 4F.4** | **COMPLETE / VERIFIED / CLOSED** |
| **Phase 4F** | **NOT complete.** 4F.5–4F.8 not started |
| **4F.1, 4F.2, 4F.3** | **Intact.** None is touched, rewritten or reinterpreted by this slice |
| **PR #33** | **Open, NOT merged**, `mergeable_state: clean`, head `5706e4a`, base `phase-4` |
| **`main`** | `7e273e62e942ecd5528ca807e65933d6bb675669` — **untouched** |
| **`phase-4`** | `428ff25c1e5e78c79d60d7bf41d9710c947a4029` — **untouched** |
| **`phase-4f.4`** | `5706e4a7f6aafef3f1305bf04707ed7ce3f0aa0a` — five commits above base, linear, no rewrite, no force push |
| **`phase-4f.5`** | **Does not exist.** Not started |
| **CF-9** | **OPEN** (§9.2) |
| **L-15** | **OPEN** (§11.2) |

### 1.1 The slice's exit criterion (TDD 4F §18)

> ***"Stage 3 can pass for LOW risk, fail-closed unchanged."***

**Met, in both halves, against real PostgreSQL.**

*Can pass:* `test_w2_a_policy_written_through_the_api_admits_the_same_action` —
a policy written through the production HTTP surface admits a LOW-risk action
at confidence `0.70`.

*Fail-closed unchanged:* four negative controls deny the **identical** action —
absent row (`test_w3_…`), tier omitted from the map, **stored empty map**, and
absent identity signal. `domain/pipeline.py` has a **zero diff** against
`phase-4`, so nothing about how the row is read or compared was altered.

---

## 2. Category 2 — the eight acceptance criteria

Each is TDD 4F.4 §10's claim, then the evidence that decides it. Every real-PG
test named below **PASSED by name** in CI job
[`106068931480`](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/35507205308/job/106068931480)
at `5706e4a`.

| # | Claim | Evidence | Status |
|---|---|---|---|
| **W-1** | A policy row can be created **through the production HTTP surface** and read back by `find_identity_confidence_policy` in real Postgres | `test_w1_a_policy_written_through_the_api_is_persisted_and_read_back` — real `PUT`, verified by **independent SQL on its own connection** *and* by the production read method | **Met** |
| **W-2** | With that row present, **stage 3 admits a LOW-risk action** at or above the threshold | `test_w2_…` — drives the **real `execute_action`**, not a re-implemented comparison | **Met** |
| **W-3** | **Absent policy still denies** at threshold 1.0 | `test_w3_absent_policy_denies_a_low_risk_action` — asserted **before** any admission test, so a later pass cannot be mistaken for the gate never having worked | **Met** |
| **W-4** | A client-supplied `user_id` **cannot** reach the row | `test_a_client_supplied_user_id_never_reaches_the_real_row` (real table) + `test_the_request_model_has_no_user_id_field` + `test_cross_user_access_is_structurally_impossible` (real route table) | **Met** |
| **W-5** | Invalid input is **rejected, not stored** | 9 contract rejections (3 unknown keys, 3 out-of-range, 3 above-ceiling) + `test_rejected_input_leaves_the_real_table_untouched` against the real table | **Met** |
| **W-6** | **Stage 3's evaluation code is unchanged** | `test_stage_three_evaluation_is_untouched_by_this_slice` (structural, over `inspect.getsource`) **plus** `git diff 428ff25..5706e4a -- domain/pipeline.py` → **0 lines** | **Met** |
| **W-7** | `SINGLE_SIGNAL_CONFIDENCE_CEILING` **unchanged at 0.75** | `test_the_ceiling_is_still_0_75` + `test_the_two_ceilings_agree` (both read as source text, neither imports) **plus** zero diff in `perception-engine` | **Met** |
| **W-8** | **DELETE returns the deployment to fail-closed** | `test_w8_delete_restores_fail_closed_behaviour` — admit, delete, verify the table is empty, then deny the **identical** action | **Met** |

**W-3 and W-8 are the two that matter most.** A write surface that quietly made
the system permissive would satisfy W-1 and W-2 and still be a defect.

### 2.1 Category 2 — TDD §10.1's nine pre-declared negative tests

Defined **before** implementation, and each now has a named test.

| # | §10.1 requirement | Evidence |
|---|---|---|
| 1 | Absent policy → 1.0 → LOW denied | `test_w3_absent_policy_denies_a_low_risk_action` (real PG) |
| 2 | Policy deleted → same action denied again | `test_w8_delete_restores_fail_closed_behaviour` (real PG) |
| 3 | Unknown risk key → `422`, nothing stored | `test_an_unknown_risk_tier_is_rejected_and_stores_nothing` ×3 + real-PG variant |
| 4 | `1.5` and `-0.1` → `422`, nothing stored | `test_an_out_of_range_threshold_is_rejected_and_stores_nothing` ×3 |
| 5 | Body carrying `user_id` → never reaches the row | contract + real-PG pair (W-4) |
| 6 | **Empty map stored → stage 3 still at 1.0** | **`test_an_empty_stored_map_is_not_an_absent_row_and_stays_fail_closed`** (real PG) — see §4.1 |
| 7 | No new Event Bus subject; `PUBLIC_TOPICS` still 18 | Registry **119**; `len(PUBLIC_TOPICS) == 18` pinned by two pre-existing tests in the green `checks` job (§5) |
| 8 | `perception-engine` and `api-gateway` diffs **empty** | `git diff --name-only 428ff25..5706e4a` over both → **0 files** |
| 9 | No migration file added; no ORM model added or altered | `git diff 428ff25..5706e4a -- 'services/*/alembic' 'services/*/src/*/repository/models.py'` → **0 lines** |

**All nine are satisfied.** Item 6 was the subject of discrepancy **D-1** and was
closed at `5706e4a`.

### 2.2 What this slice explicitly does not claim

- **It does not close CF-9.** TDD 4F §5.3 forbids it; §9.2 records the status.
- **It does not make AC-8 pass.** It makes stage 3 *capable* of passing. AC-8
  also needs 4F.5 (Level 2 dispatch) and 4F.6 (the trigger), and the acceptance
  run is **4F.8's**.
- **It does not choose a threshold value.** D-4F4-4: no production default, no
  seed, no constant in `src/` standing in for a chosen threshold.

---

## 3. Category 1 — implementation against the TDDs and ADRs

### 3.1 Scope delivered — six deliverables (TDD 4F.4 §4)

| # | Deliverable | Delivered as |
|---|---|---|
| 1 | Write methods on the repository port and its Postgres implementation | `domain/ports.py` (+26) — `upsert_identity_confidence_policy`, `delete_identity_confidence_policy`; `repository/postgres_action_repository.py` (+47) — a real `INSERT … ON CONFLICT DO UPDATE`, not a racy read-then-write |
| 2 | HTTP surface | `api/identity_confidence_policy.py` (+182, new module) |
| 3 | Request/response schemas with validation | same module — bounded confidences, `RiskLevel`-derived keys, the §16.5 ceiling |
| 4 | Router registration and `Settings.primary_user_id` | `main.py` (+6), `config.py` (+17) |
| 5 | Tests — **unit, integration, and the real-Postgres evidence §11 requires** | **12 + 25 + 11**, all three tiers present (§6) |
| 6 | Ceiling drift guard | `tools/tests/test_identity_confidence_ceiling_drift.py` (+116, 3 tests) |

**Six of six.** No migration, no new table, no new model, no new ORM class, no
Event Bus subject, no gateway change.

### 3.2 The four ratified decisions, verified as built

| Decision | As built |
|---|---|
| **D-4F4-1** — risk tier **is** the capability class | The existing risk-tier-keyed schema is used unchanged. **No capability id, no capability table, no new schema, no second keying dimension.** `minimum_confidence_by_risk` is keyed by `RiskLevel` values, asserted by a test parametrized over the enum itself |
| **D-4F4-2** — single-resource API | `GET`/`PUT`/`DELETE /v1/action/identity-confidence-policy`. `user_id` server-derived; `GET` with no policy returns **404**; `DELETE` restores fail-closed. **No invented collection id**, and no route takes a path parameter — asserted over the router's real route table |
| **D-4F4-3** — no audit trail; **L-15 opened** | **No audit persistence of any kind**, and **no Event Bus subject** created to carry the gap. L-15 is recorded OPEN in §11.2 |
| **D-4F4-4** — no production threshold value | **No default, no seed, no migration insert.** Verified by grep over every `services/*/src/` and `services/*/alembic/`: the only literal in production source is `MAX_CONFIGURABLE_CONFIDENCE = 0.75`, which is a **validation ceiling**, not a policy value. Test fixtures choose numbers; none reaches `src/` |

### 3.3 Architectural boundaries, each verified at `5706e4a`

| Boundary | Verification | Result |
|---|---|---|
| **Ownership** | `IdentityConfidencePolicy` stays in `action-engine` (D-4D-2, TDD 4F §5.4) | Unchanged |
| **Persistence** | `git diff` over `services/*/alembic` and `repository/models.py` | **0 lines. 0 migrations, 0 ORM changes** |
| **Evaluation** | `git diff` over `domain/pipeline.py` | **0 lines** — byte-identical (TDD 4F §22) |
| **Fail-closed** | Four real-PG negative controls | Unchanged |
| **Identity** | `IdentityConfidencePolicyRequest.model_fields` | **No `user_id` field** — forgery is unrepresentable, not merely rejected (ADR-025) |
| **Event Bus** | `len(_REGISTRY)` from the runtime registry | **119** — no subject registered, published or consumed |
| **`PUBLIC_TOPICS`** | AST parse of `ws-gateway/domain/protocol.py` | **18** |
| **Gateway** | `api-gateway/domain/routing.py:126` already forwards the `/v1/action` subtree | **`api-gateway` not modified — 0 files** |
| **Cross-engine (ADR-004)** | `test_action_engine_does_not_import_perception_engine` + `lint-imports` | **7 contracts kept, 0 broken.** The ceiling is *duplicated* because the import is forbidden, and the drift guard reads **both as source text** |
| **Untouched engines** | `git diff --name-only` over `ws-gateway`, `api-gateway`, `world-model-engine`, `perception-engine`, `nova-contracts`, `apps`, `companion` | **0 files in all seven** |

### 3.4 The one correction this slice carried

TDD 4F.4 §2.1 originally asserted that `Settings.primary_user_id` already
existed in `action-engine`. **It did not** — the idiom existed in
`perception-engine` and `autonomy-engine` only. The TDD was corrected
additively before implementation began (protocol §0.3.4), and the setting was
added here mirroring `autonomy-engine` exactly, including its default. It is the
**only** source of identity for this surface.

---

## 4. Discrepancy closure at `5706e4a`

The final pre-Gate audit at `0af5466` found two gaps against this slice's own
TDD. Both were closed by a **documentation-and-tests-only** commit changing
**3 files, +186, −0, and no production file**.

### 4.1 D-1 — TDD §10.1 item 6 was half implemented

**The gap.** `test_an_empty_map_is_accepted_and_is_not_the_same_as_no_row`
proved an empty map is *accepted* and readable back, but nothing stored `{}` and
then drove stage 3. The nearest test omitted a tier from a **non-empty** map,
which is a different input.

**The closure.**
**`test_an_empty_stored_map_is_not_an_absent_row_and_stays_fail_closed`**, in
`services/action-engine/tests/integration/test_identity_confidence_policy_real_postgres.py`.

It proves, in one test:

| | |
|---|---|
| The **empty stored policy row exists** | `SELECT` on an independent connection returns exactly one row, `user_id == PRIMARY_USER_ID`, `minimum_confidence_by_risk == {}` |
| The **repository read returns a policy, not `None`** | `find_identity_confidence_policy(...) is not None` — the exact distinction stage 3's `policy is not None` sees |
| **Real `execute_action` stage 3 remains fail-closed** | The production pipeline function is driven, not a re-implementation |
| **LOW risk at `0.70` is denied** | `== "denied"`, exact — not weakened or generalized |
| **Real PostgreSQL** | `@pytest.mark.real_infra`, `postgres_container` + `run_alembic_upgrade`, production `create_engine`/`create_session_factory` (committing) |
| **No ORM fixture insertion** | The row is created only by `PUT` through the production HTTP surface |
| **No mocked repository** | `PostgresActionRepository` against the real table |
| **No production change** | Test file only |

**This separates two security states that share one observable behaviour.** An
absent row and a deliberately empty map both leave stage 3 at 1.0 — but only one
of them is a configuration an operator performed. The property held before the
test existed, since `risk.value in policy.minimum_confidence_by_risk` is false
for every tier when the map is `{}`. **This is evidence that was owed, not a
defect that was repaired.**

### 4.2 D-2 — the unit tier named by §4 deliverable 5 was empty

**The gap.** §4 deliverable 5 names *"unit, integration, and the real-Postgres
evidence"*. `services/action-engine/tests/unit/` — an existing directory in this
engine, alongside `test_pipeline.py`, `test_parameter_validation.py` and
`test_risk_classification.py` — had no 4F.4 test.

**The closure.**
`services/action-engine/tests/unit/test_identity_confidence_policy_validation.py`
— **12 tests** exercising `IdentityConfidencePolicyRequest` as the plain Pydantic
model it is: **no app, no client, no repository, no fake**. This satisfies the
literal unit-tier requirement **with no production change**; the module was
already a plain model, so no seam was introduced for the test's benefit.

The 12 assert three things a `422` through the app cannot show:

| | |
|---|---|
| **The accepted key set is derived from `RiskLevel`, not written out** | `test_every_risk_level_value_is_a_configurable_tier` is parametrized over the enum (5 cases), plus `test_the_validator_accepts_all_five_tiers_at_once`. Every HTTP test only ever sends `low` and `moderate`, so a hardcoded subset would pass all of them and fail only here |
| **The rejection names the remedy** | `test_an_above_ceiling_rejection_names_omission_as_the_remedy` — §16.5's rule removes no security capability *because* omitting a tier is how maximum strictness is expressed; an error that does not say so turns a safe design into a confusing one. `test_an_unknown_tier_rejection_lists_the_tiers_that_exist` is its sibling |
| **The ceiling is a strict `>` at float resolution** | `test_the_smallest_float_above_the_ceiling_is_rejected` probes one ULP above `0.75` via `math.nextafter`, not a round `0.76`; `test_the_ceiling_itself_is_accepted` pins the boundary |

Plus `test_zero_is_accepted_and_is_not_confused_with_absence` (`0.0` is falsy — a
truthiness check would silently drop a legitimate threshold) and
`test_an_empty_map_is_valid_at_the_model_level`.

**The unit tier does not replace the integration tiers, and no claim here says
it does.** The three tiers **coexist**: the unit tier decides what the validator
does in isolation, the contract tier decides what the wired app returns, and the
real-Postgres tier decides everything about persistence and the gate. The
load-bearing security evidence remains the real-Postgres tier — a fake
repository could only prove that the fake agrees with itself.

---

## 5. Category 8 — contracts and codegen

| Check | Result |
|---|---|
| Codegen drift | `python codegen/generate_typescript.py` → **117 TypeScript contract files, zero drift** (`git status` clean afterwards) |
| New Event Bus subjects | **0.** Runtime registry `len(_REGISTRY)` = **119** at base and at head |
| `PUBLIC_TOPICS` | **18**, byte-identical. Pinned by `len(PUBLIC_TOPICS) == 18` in two pre-existing tests (`ws-gateway/tests/unit/test_protocol.py`, `digital-twin-engine/tests/contract/test_phase_4e_boundaries.py`), both green in the `checks` job |
| `nova-contracts` diff | **0 files** |
| Contract reuse | `RiskLevel` is imported from `nova_contracts.events.planning`; no new contract type was introduced |

**The subject count is taken from the runtime registry, not by grepping
decorators** (TDD 4F.3 §21.1): a regex over `@register_payload("…")` returns 120,
the extra match being the docstring example at `nova_contracts/registry.py:4`.

---

## 6. Category 9 — tests, lint, types, imports

### 6.1 Test counts at `5706e4a`

| Tier | Count | File |
|---|---|---|
| **Unit** | **12** | `services/action-engine/tests/unit/test_identity_confidence_policy_validation.py` |
| **Contract / integration** | **25** | `services/action-engine/tests/integration/test_identity_confidence_policy_api.py` |
| **Real PostgreSQL** | **11** | `services/action-engine/tests/integration/test_identity_confidence_policy_real_postgres.py` |
| **Repository-wide guards** | **3** | `tools/tests/test_identity_confidence_ceiling_drift.py` |

**48 added across the three engine tiers**, plus the 3 `tools/tests` guards,
which are counted separately because they are repository invariants rather than
this engine's suite.

### 6.2 Suite, lint, types, imports

| Check | Result |
|---|---|
| `turbo run test --force` | **32/32 successful, `Cached: 0` — 2,792 passed** |
| `action-engine` alone | **103 passed / 27 deselected** (the 27 being `real_infra`, which needs Docker) |
| `turbo run lint` | **32/32** — ruff clean; mypy *"no issues found in 24 source files"* for `action-engine` |
| `turbo run typecheck` | **5/5** |
| `turbo run build` | **32/32** |
| `tools/tests` | **295 passed** |
| `lint-imports` (ADR-004 / ADR-006) | **7 contracts kept, 0 broken** |

*(The 2,792 total is 12 above the 2,780 recorded at `5974c40`, exactly the unit
tests D-2 added.)*

---

## 7. Category 10 — real infrastructure

**The load-bearing evidence for this slice, and the reason PR #33 exists.**

`action-engine` was **already** in `real-infra-checks.yml`'s matrix, so this
slice added no CI matrix row.

### 7.1 The chain, with nothing faked in the load-bearing path

```
real HTTP over a real TCP socket   (httpx → in-loop uvicorn, port 0)
  → production router               api/identity_confidence_policy.py
  → production repository           PostgresActionRepository
  → real table                      action.identity_confidence_policy
  → real gate                       execute_action() stage 3
  → verified by independent SQL     a second connection, not the writer
```

| Property | How it is guaranteed |
|---|---|
| **The write goes through the production surface** | Nothing in the file inserts `IdentityConfidencePolicyORM` directly — which is exactly what ADR-032 names as the reason decision point 2 counted as unimplemented |
| **Stage 3 is the real function** | `from nova_action_engine.domain.pipeline import execute_action`; no threshold comparison is re-implemented in the test |
| **Verification cannot agree with itself** | `_rows()` reads with raw SQL on its own connection, so a repository-level bug cannot confirm its own write |
| **Writes actually commit** | The production `create_engine`/`create_session_factory` are composed directly. The shared `postgres_session_factory` fixture is **deliberately not used**: it binds every session to one connection inside a rolled-back transaction, so writes never commit and are invisible to another connection — both properties wrong when the claim is persistence |
| **Only the identity RPC is faked** | `IdentityPort` is an Event-Bus RPC to `world-model-engine` and is the subject of no claim here. The policy row, the repository, the table and the gate are all real |

### 7.2 Result

**CI job [`106068931480`](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/35507205308/job/106068931480)
at `5706e4a`: `27 passed, 103 deselected` in 14.22s** — 16 pre-existing plus the
11 new, each **PASSED by name** in the log, including:

```
test_an_empty_stored_map_is_not_an_absent_row_and_stays_fail_closed PASSED [ 25%]
```

**Docker is unreachable in the authoring environment**, so no local
real-Postgres result is offered and none is claimed (protocol §0.3 principle 5).
The tests collect cleanly locally (27 selected of 130) and their execution is
delegated entirely to CI.

---

## 8. Category 11 — PR, branch, commit and CI evidence

### 8.1 Branch and commits

`phase-4f.4`, five commits above `phase-4`, **linear, no merge commit, no
rebase, no squash, no force push**:

| SHA | |
|---|---|
| `8c54a88` | TDD — design preparation, NOT ratified |
| `6b0b93c` | Ratify the four decisions, open L-15, correct one unchecked claim |
| `5974c40` | The implementation |
| `0af5466` | Fix the real-Postgres harness (test file only; no production file) |
| **`5706e4a`** | **Close D-1 and D-2** (this record's SHA) |

Total diff against `phase-4`: **11 files, +1,835, −0. Zero deleted lines in the
whole slice.**

### 8.2 CI at the exact implementation SHA

**40/40 check runs green at `5706e4a`. Zero failed, zero cancelled, zero
skipped. `run_attempt: 1` on all three runs.**

| Workflow | Run | Result |
|---|---|---|
| **Real-Infrastructure Checks** | [`35507205308`](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/35507205308) | **success — 15/15** |
| **Build & Scan** | [`35507205287`](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/35507205287) | **success — 22/22** built and Trivy-scanned; `dependency-audit` green |
| **PR Checks** | [`35507205283`](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/35507205283) | **success** — `checks` (`Tasks: 32 successful, Cached: 0`) and **Playwright golden path green** |

**No new image was expected or produced**; `action-engine`'s existing Dockerfile
built and scanned clean.

### 8.3 An earlier CI failure, recorded rather than hidden

The **first** CI run of the real-Postgres file (at `5974c40`) **failed 10 of
12**. Both causes were defects in the test harness, not the implementation:

1. **An event-loop mismatch** (9 failures) — `TestClient` drives the app through
   an anyio portal on its own thread with its own loop, while the asyncpg
   connections belonged to the test's loop. The fix removed the thread boundary
   rather than working around it: a real uvicorn server in the test's own loop,
   reached by `httpx` over a real TCP socket. **The evidence got stronger, not
   weaker** — the request now crosses a real socket instead of an in-process
   transport.
2. **A missing contract field** (1 failure) — `ActionExecuteRequestPayload`
   needs `verification_method`, `requesting_engine` and `correlation_id`. The
   contract caught it.

`0af5466` fixed both, **test file only, zero production files**. No assertion was
weakened, no mock introduced, no real-Postgres test removed, and neither the CI
nor the Trivy policy was altered.

---

## 9. Category 13 — findings, carry-forwards and ambiguities

### 9.1 Findings raised by the final pre-Gate audit

| # | Finding | Disposition |
|---|---|---|
| **D-1** | §10.1 item 6 half implemented | **CLOSED** at `5706e4a` (§4.1) |
| **D-2** | Unit tier named by §4 deliverable 5 was empty | **CLOSED** at `5706e4a` (§4.2) |

**No third discrepancy was found**, and the audit's other eleven areas —
scope, API, security, ADR-032, real integration, Event Bus, architecture
boundaries, code quality, SLOC, deferred obligations, phase boundaries — each
verified clean at `0af5466` and re-verified at `5706e4a`.

### 9.2 CF-9 — **OPEN**, and this record does not close it

TDD 4F §5.3 is explicit: *"4F implementing the capability does not close CF-9,
and no 4F document may record it as closed."* **This document records it as
OPEN.** What follows is only the evidence 4F.4 contributes.

| # | §5.3 condition (verbatim) | 4F.4's contribution |
|---|---|---|
| 1 | *"A policy row can be created through a production surface — **and** read back by stage 3 in real Postgres."* | **Evidenced** by W-1 + W-2 at `5706e4a`, real PG, production surface, no ORM insert |
| 2 | *"The threshold is **per privileged capability or per capability class**, never a single hardcoded system-wide value."* | **Answered by ratification D-4F4-1** — risk tier *is* the capability class, and the existing risk-tier-keyed schema is authoritative. The closure evidence must still cite that ratification |
| 3 | *"Absent policy still fails closed at 1.0, proven by a negative control."* | **Evidenced** by W-3, plus three further controls (omitted tier, empty map, absent signal) |
| 4 | *"`perception-engine`'s `SINGLE_SIGNAL_CONFIDENCE_CEILING` is unchanged."* | **Evidenced** by W-7, the drift guard, and a zero diff in `perception-engine` |
| 5 | *"The Phase 4B Gate Review §0.3, Phase 4C's health record and master scope §4's register are each updated, with the closing evidence cited."* | **Not 4F.4's.** Those are category 3–5 documents, which protocol §0.1 defers for a slice. **OPEN**, at 4F closure or later |

**Condition 5 is unmet and condition 2 awaits citation, so CF-9 stays OPEN**, as
§5.3 requires and as D-4D-2 ratified. No document in this slice records it
otherwise.

### 9.3 Carry-forwards outside this slice — all unchanged

| | Status | Owner |
|---|---|---|
| **CF-10** | **OPEN** — Trust Engine unavailable / fails closed. Untouched by 4F.4 | Outside 4F |
| **CF-11** | **OPEN** — the initiative trigger's producer. Untouched by 4F.4 | **4F.6** |
| **Downstream world-model E2E** | **OPEN** — not moved by this slice | **4F.8** (TDD 4F §20.1, §18) |
| **AC-7 / AC-8 acceptance run** | **OPEN** | **4F.8** |
| **Autonomy Level 2** | **OPEN** | **4F.5** |

**4F.4 absorbs none of these.**

### 9.4 One new finding, requiring the user's ratification before it gets a number

Adding three routes made two documents **incomplete** — neither is false, but
both enumerate this engine's API surface and neither lists the new routes:

| Document | What became stale |
|---|---|
| `services/action-engine/README.md` §*"Owned APIs"* (lines 100–113) | Lists `GET /v1/action/approvals`, `POST …/decide` and the three `/internal/*` routes. **The three `/v1/action/identity-confidence-policy` routes are missing** |
| [`docs/architecture/11-api-architecture.md`](../../architecture/11-api-architecture.md) lines 57–59 | Enumerates the `/v1/action` surface; **the new route is missing** |

The second falls under the existing **L-10** (`docs/` staleness sweep) and is
named there in §11.2 rather than given a new row. **The first does not fall under
any existing row** — L-7 was `perception-engine`'s README (settled by 4F.3) and
L-8 is `ws-gateway`'s.

**Per the ordering rule the next free row is L-16, but that is the user's to
ratify, and no number is assigned here.** This follows the precedent set for
L-15, which was recommended in TDD 4F.4 §15 and numbered only on ratification.
It is recorded as a finding so that it is visible rather than quietly absorbed,
and so 4F's Gate Review inherits it either way. **Neither document was edited by
this slice** — READMEs are category 7, which a slice defers.

---

## 10. Category 14 — documentation updated by this slice

| Document | Change | Additive? |
|---|---|---|
| [`docs/design/phase-4/08-tdd-4f4-identity-confidence-policy.md`](../../design/phase-4/08-tdd-4f4-identity-confidence-policy.md) | Created (§1–§18); **§16** added on ratification; **§2.1** corrected the `primary_user_id` claim; **§10.2** records the D-1/D-2 closure | **Yes** — §15's four questions preserved verbatim, the pre-ratification status line preserved inline, §4 and §10.1 unchanged |
| This record | Created | n/a |

**No historical document was rewritten.** The 4F.3 completion record still says
PR #32 was open and unmerged, and `phase-4` was at `6632dd1` — both true when
written, and both preserved exactly (protocol §0.3.4). The current state of those
objects is stated here, separately, in §1.

**No production file was changed by the closure work**, and no production file
was changed by this record.

---

## 11. Deferred-obligations ledger — protocol §0.2

**This is the ledger §0.2 requires**, so 4F's eventual Gate Review inherits a
complete list. **A Sub-Phase may not be declared complete while any row here is
unsettled** — which is why Phase 4F is not complete.

### 11.1 Settled by this slice

**None.** 4F.4 settles no pre-existing ledger row. It is a write surface inside
one engine; it makes no README, roadmap entry or health record accurate that was
not accurate before.

*(L-7 and L-12 were settled by 4F.3 and are not repeated here.)*

### 11.2 Still open, each with its owner — thirteen rows

| # | Obligation | Owner | Blocks 4F.4? |
|---|---|---|---|
| L-1 | 4F Gate Review (category 3) | **4F closure, after 4F.8** | No |
| L-2 | `docs/project-health/phase-4f.md` (category 4) | **4F closure** | No |
| L-3 | `project-health-master.md` summary row for 4F | **4F closure** | No |
| L-4 | `ENGINEERING_ROADMAP.md` 4F row, full category-5 treatment | **4F closure** | No |
| L-5 | `00-master-scope.md` §17 SLOC table + the §2 methodology entry — **F-2's owner** | **4F closure** | No |
| L-6 | `README.md` — *"a new engine now exists"*, fired at 4F.1 | **4F closure** | No |
| L-8 | `ws-gateway/README.md` — the `perception.*` narrowing | **4F closure** | No |
| L-9 | Cross-file consistency sweep (category 12) | **4F closure** | No |
| L-10 | `docs/` staleness sweep (category 6) — **now also covers `docs/architecture/11-api-architecture.md` lines 57–59, which 4F.4 made incomplete** (§9.4) | **4F closure** | No |
| L-11 | Fusion for workspace signals | **4F closure** *(corrected by 4F.3 §10.3 from "4F.3")* | No |
| L-13 | `known_projects` population | **4F closure or later** | No |
| L-14 | Doc 22 Principle 8 per-source consent for `filesystem` | **4F closure**, or earlier if separately ratified | No |
| **L-15** | **Opened by 4F.4 — see §11.3** | **`action-engine`** | No |

**Every row above is carried forward unchanged.** None is closed, absorbed,
renamed or renumbered by this slice.

### 11.3 L-15 — opened by this slice, and explicitly still OPEN

| | |
|---|---|
| **Row** | **L-15** |
| **Status** | **OPEN** |
| **Obligation** | **Administrative changes to `IdentityConfidencePolicy` are unaudited.** Creating, updating or deleting an identity-confidence threshold is a security-relevant administrative act, and nothing records who changed it, when, or from what to what |
| **Why deferred** | TDD 4F §5.2 fixes the minimum surface at *"create/read/update a policy … and nothing more"*. `action_execution_history` models the *action* lifecycle, not administrative mutation, so using it would need a schema decision outside this slice |
| **Owner** | **`action-engine`** — unchanged |
| **Settled by** | **4F closure**, or earlier if an audit design is separately ratified |

**Verified at `5706e4a`, not assumed:**

- **No audit persistence was introduced.** No new table, no new ORM class, no
  migration, and no write to `action_execution_history` from the policy surface.
- **No Event Bus subject was introduced** to carry the gap — D-4F4-3 forbids
  creating one merely for this purpose, and the registry is still **119**.
- **L-15 is not closed here**, and no evidence in this record is offered toward
  closing it.

### 11.4 F-2 — SLOC scope ambiguity, unchanged

**F-2 remains OPEN under L-5**, exactly as 4F.3 left it: whether `companion/`'s
`Cargo.toml`/`Dockerfile`/`README.md` belong in the count, a 142-line
difference. 4F.4 adds no Rust and no companion file, so **the question is
unchanged and the gate is uncrossed under either reading**.

---

## 12. Final status

**Phase 4F.4 is COMPLETE, VERIFIED and CLOSED as a slice.**

*Verified* means: its exit criterion is met by real evidence at a known SHA; all
eight acceptance criteria are met and all nine pre-declared negative tests exist;
its four ratified decisions hold structurally rather than by convention; both
discrepancies the pre-Gate audit raised are closed with named, executed tests;
40/40 CI checks are green at that SHA; and every obligation it did not discharge
is named in §11 with an owner.

**And, stated as plainly as the closure itself:**

- **Phase 4F is NOT complete.** 4F.5 through 4F.8 have not started. Its Gate
  Review and its Project Health record are **4F.8's**, ledgered as **L-1** and
  **L-2**.
- **No Go / Conditional-Go / No-Go verdict is issued here.** That is category 3,
  which a slice defers (§0).
- **4F.1, 4F.2 and 4F.3 remain intact** and are not reinterpreted.
- **PR #33 remains open and unmerged.**
- **`main` is untouched** at `7e273e62e942ecd5528ca807e65933d6bb675669`.
- **`phase-4` is untouched** at `428ff25c1e5e78c79d60d7bf41d9710c947a4029`.
- **`phase-4f.4` is intact** at `5706e4a7f6aafef3f1305bf04707ed7ce3f0aa0a`.
- **`phase-4f.5` has not been created.**
- **CF-9 remains OPEN.** Conditions 1, 3 and 4 are evidenced; 2 is answered by
  ratification and awaits citation; **5 is unmet.**
- **L-15 remains OPEN**, owned by `action-engine`.
- **CF-10, CF-11, L-1…L-6, L-8…L-11, L-13 and L-14 all remain OPEN.**
- **One new finding (§9.4) awaits the user's ratification** before it receives a
  ledger number.
- **4F.8 owns** the downstream world-model E2E and the AC-7/AC-8 acceptance run.

### 12.1 SLOC

**46,125 on the 4F scope. Headroom to the 50,000 hard gate: 3,875. The gate is
NOT crossed.**

`cloc` v2.06 `--skip-uniqueness` over a pristine `git archive` export of
`5706e4a`, the 4E Gate Review's tool and flags unchanged: scopes
`services/*/src` + `packages/*/src` + `services/*/alembic/versions` (Comparable
**36,506**), plus `agent-os/*/src`, `agent-os/*/alembic/versions`, `agents`
(Wider **41,847**), plus `apps/*/src` (Full **45,479**), plus `companion/` less
`companion/*/tests` (**4F scope 46,125**).

Of the **+120** over 4F.3's 46,005, all is `action-engine` production source:
the API module, the repository methods, the port declarations, the router
registration and the setting. **The 48 tests and the 3 guards contribute 0** —
tests are outside every scope (TDD 4F §17), which is also why the D-1/D-2
closure moved the figure by **zero**.

The growth is inside TDD 4F §17's **100–200** estimate for CF-9's write surface.

**Code was never moved or reduced to game the metric** (TDD 4F §17).
