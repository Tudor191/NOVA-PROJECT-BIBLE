# Phase 4F.6 — Slice Completion Record
## The initiative trigger: `autonomy.decision.requested`, and the first production caller of `decide()`

**Date:** 2026-09-23
**Slice:** 4F.6 of 4F's eight (TDD 4F §18)
**Branch:** `phase-4f6`. Implementation at **`f7b9c267649909a94d5da9cd5de93ab3ec4d6482`**
**Base:** `phase-4` at **`4f1602ac086c421fc1a6beb54b7effb10f3ef6d9`**, **unchanged by this slice**
**`main`:** **`7e273e62e942ecd5528ca807e65933d6bb675669`**, **untouched**
**PR:** [#37](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/pull/37), `phase-4f6 → phase-4`. Open for review; **not merged**
**Protocol:** [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md),
sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`,
1131 lines. Re-read from `origin/main` in this session; byte-identical to the
copy 4F.5 used.
**TDDs:** [TDD 4F.6](../../design/phase-4/10-tdd-4f6-initiative-trigger.md), and
in particular **§19, the Implementation Contract**, which is authoritative.
Also [TDD 4F](../../design/phase-4/06-tdd-4f-companion-and-cognitive-state.md)
§6.2, §11.4, §12 and §16, and
[TDD 4F.5](../../design/phase-4/09-tdd-4f5-autonomy-level-2.md) §22.

---

## 0. What this document is, and is not

**This is a Slice completion record. It is not a Gate Review.** Protocol §0.1
gives a Significant Slice categories **1, 2, 8, 9, 10, 11, 13 and 14 in full**,
and categories **3–7 and 12 as a deferred-obligations ledger**. Category 3 is
the Gate Review itself. So this record issues **no GO / CONDITIONAL-GO / NO-GO
verdict**. 4F's Gate Review is **L-1**, owned by 4F closure after 4F.8. This
follows the 4F.2–4F.5 records.

**Phase 4F is NOT complete.** 4F.7 and 4F.8 have not started. **Completing
this slice does not authorize starting 4F.7.**

### 0.1 Branch shape — disclosed

`phase-4f6` was branched from `phase-4 @ 4f1602a` and **fast-forwarded** (no
merge commit) through the six documentation-only TDD commits `9eed0b1 …
c6a3c01`. Those commits had never been pushed or opened as a PR. PR #37
therefore carries the ratified TDD and its implementation together. No history
was rewritten, squashed or force-pushed.

---

## 1. Status

| | |
|---|---|
| **Slice 4F.6** | **Implementation-complete. Locally verified, including the real-infrastructure tier against locally installed PostgreSQL 16 and NATS (§6).** Exact-SHA CI evidence: §7.2 |
| **Phase 4F** | **NOT complete.** 4F.7 and 4F.8 not started |
| **4F.1–4F.5** | **Intact.** 4F.5's dispatch semantics, its seven §22.4 preconditions, the 15-second bound, `ActionDispatchUnavailable` and the §22.7 Trust contract are unchanged (§3.2, row 20) |
| **CF-9 / CF-10 / CF-11** | **All OPEN.** 4F.6 closes none (§8.2) |
| **Registry** | **120** (was 119). One new subject, `autonomy.decision.requested` |
| **`PUBLIC_TOPICS`** | **18, unchanged**. The new subject is not in it |
| **Deferred ledger** | **17 rows open** (§10): the 16 rows open in 4F.5's record §10.2, carried unchanged, plus **L-19**, opened here. L-7 and L-12 do not appear in 4F.5's open list, and 4F.6 does not revisit them |

### 1.1 The slice's exit criterion

TDD 4F §18 assigns 4F.6 Level 2's **state 4, *Triggered***: *"the first
production caller of `decide()`, and CF-11's producer under §6.2."*

**Met, with the caller running in production.**
`decision_orchestration.handle_decision_request` is the **only** production
call site of `decide()`. Verified by grep: the one hit is
`services/autonomy-engine/src/nova_autonomy_engine/decision_orchestration.py:188`.
It is registered by the `serve()` in `autonomy-engine`'s `main.py` lifespan.
The **producer** side, `promote_thought`, has **no production caller yet**:
nothing in `cognitive-state-engine`'s running topology promotes a thought. That
surface belongs to 4F.7, and it is why CF-11 stays OPEN (§8.2).

> **Correction, 2026-09-26 (4F.7 ratification, RS-6b and RS-11 — TDD 4F
> §24), additively.** The section above is preserved as written. Three
> corrections apply to it:
>
> 1. **"Met" describes the consumer half only.** The consumer runs in
>    production. By TDD 4F.6 §2's own definition, the production end-to-end
>    *Triggered* state is **not yet evidenced**: that requires *"a production
>    component, reachable in a deployed system without a test harness"*.
>    Neither part holds yet:
>    - `cognitive-state-engine` is not deployed;
>    - no production component promotes an Active Thought.
>
>    *Triggered* stays a system-level property, and **CF-11 stays OPEN**.
> 2. **"That surface belongs to 4F.7" is superseded.** 4F.7 is strictly
>    read-only (RS-1b). It does not promote thoughts or call `promote_thought`.
>    The production promotion driver belongs to the new slice **4F.P**, before
>    4F.8 (RS-1c; TDD 4F §18, as amended).
> 3. **The quotation at the top of this section is not TDD 4F §18's
>    wording.** §18's 4F.6 row reads *"The trigger: `cognitive-state-engine` →
>    `DecisionRequest` | CF-11's producer, under §6.2"*. The quoted phrase *"the
>    first production caller of `decide()`, and CF-11's producer under §6.2"*
>    matches master scope §17's description of TDD 4F.6 instead. The substance
>    is unaffected.

---

## 2. Category 2 — acceptance criteria: the 21 rows of TDD 4F.6 §19

Each row is the ratified requirement, then the evidence. Test paths are
relative to each package's `tests/`. **RI** marks a `real_infra` test.

| # | Requirement (§19) | Evidence | Status |
|---|---|---|---|
| 1 | A complete `ProposedAction` promoted to `IMMEDIATE` triggers; none otherwise; incomplete is invalid | `unit/test_proposed_action.py`: all 6 required fields; `test_an_incomplete_proposal_is_invalid_at_the_model_boundary`[×6]; `test_a_thought_refuses_a_partial_proposal`. `unit/test_promotion_orchestration.py`: `…with_a_complete_proposal_sends_exactly_one_request`, `test_a_thought_without_a_proposal_never_triggers`, `test_a_promotion_that_does_not_reach_immediate_never_triggers`[×3], `test_promoting_an_already_immediate_thought_…`. **RI** `test_decision_trigger_real_nats.py`: the same four cases over a real broker and real Postgres | **Met** |
| 2 | `autonomy.decision.requested`, request/reply; exactly one consumer | `nova-contracts/tests/test_autonomy_events.py::test_the_trigger_subject_is_registered`, `test_it_is_the_only_autonomy_subject`. Allow-lists: cognitive-state publishes `{autonomy.decision.requested}`; autonomy subscribes `{autonomy.decision.requested}` (§4) | **Met** |
| 3 | `subject_id = uuid5(_DECISION_TRIGGER_NAMESPACE, str(envelope.event_id))`, derived by the consumer | `unit/test_decision_orchestration.py::test_the_namespace_is_the_pinned_literal` (literal **and** its documented provenance), `test_subject_id_is_uuid5_of_the_event_id_string_and_nothing_else`, `test_the_same_event_id_derives_the_same_subject_whatever_else_differs`. **RI** `test_a_real_trigger_is_decided_by_the_production_served_handler` asserts that the suggestion id equals `uuid5(ns, event_id)`, read back by SQL | **Met** |
| 4 | No producer-supplied `subject_id` | The field is absent from the contract, and `extra="forbid"` rejects it: `test_the_payload_has_no_subject_id_field`, `test_a_producer_supplied_subject_id_is_rejected`. **RI** `test_a_producer_supplied_identity_field_is_rejected_on_the_real_bus[subject_id]` shows no rows and no dispatch | **Met** |
| 5 | Consumer: `autonomy-engine`, one `serve()` | `contract/test_autonomy_boundaries.py::test_control_6_the_only_bus_calls_are_one_request_and_one_serve` (AST pin: exactly one `serve`, in `main.py`, on `DECISION_TRIGGER_SUBJECT`). **RI**: every consumer test runs the production `create_app` lifespan | **Met** |
| 6 | Caller at the orchestration boundary: `decision_orchestration.py`, not `api/`, not `domain/` | Package root, beside `main.py`. The grep in §1.1 finds one production `decide()` caller | **Met** |
| 7 | Level, policies and grants read server-side; `user_id` from `primary_user_id` and never carried | `unit/…::test_user_id_is_resolved_server_side` (request, trust read and suggestion all equal `PRIMARY`); level tests at 0, 1 and 2 plus the unconfigured case; `test_a_producer_supplied_identity_field_is_rejected_before_decide[user_id]`. **RI**: the suggestion row's `user_id` equals the configured primary user | **Met** |
| 8 | No Layer 2 deduplication | `unit/…::test_two_event_ids_with_identical_payloads_are_two_decisions`; **RI** `test_two_event_ids_with_identical_payloads_are_two_decisions` (two dispatches, two log rows) | **Met** |
| 9 | No TTL; 4F.5's 15 s is not reused | `occurred_at` is not read by the consumer (grep: docstring only, line 104). No `ttl`/`expires`/`max_age`/`stale` in the three trigger modules. The producer's 20 s is a **reply wait**, disclosed as finding F-2 | **Met** |
| 10 | No trigger-layer retry | `unit/test_promotion_orchestration.py::test_no_outcome_is_retried`[×5]; `unit/test_decision_trigger_client.py`: every outcome, `len(calls) == 1`. **RI** `test_a_silent_consumer_is_unconfirmed_after_a_real_bounded_wait_and_not_resent` | **Met** |
| 11 | Transport failure: catch → observe → structured degraded reply; `decide()` not invoked | `unit/…::test_a_failure_before_deciding_is_degraded_and_decide_is_not_invoked` (spy on `decide`: 0 calls, no dispatch, no trust read, no row); **RI** `test_an_unreachable_database_is_a_degraded_reply_and_nothing_executes`. Producer side: `unit/test_decision_trigger_client.py::test_no_transport_exception_escapes`[×4] | **Met** |
| 12 | No execution without delivery | **RI** `test_an_undelivered_trigger_decides_nothing_and_executes_nothing`: a real `NoRespondersError` at the producer; no decision, suggestion or `action.execute`, with every Level-2 gate configured open. **RI** `test_a_real_broker_with_no_consumer_is_reported_unavailable` (producer side) | **Met** |
| 13 | No new `DecisionOutcome` | `unit/…::test_the_outcome_vocabulary_is_unchanged`: exactly the five members | **Met** |
| 14 | No new audit table, no `autonomy` migration | `contract/…::test_4f6_adds_no_autonomy_migration` (versions == `["0001_initial_schema.py"]`); **RI** `test_the_migration_creates_exactly_the_five_tables` unchanged and passing | **Met** |
| 15 | `PUBLIC_TOPICS` stays 18 | `test_control_7_public_topics_is_unchanged_at_its_eighteen_exact_strings` unchanged; the retargeted control 6 asserts the subscribe set does not intersect `PUBLIC_TOPICS` | **Met** |
| 16 | No gateway exposure | `contract/…::test_4f6_no_gateway_or_browser_surface_names_the_trigger_subject` scans `api-gateway/src`, `ws-gateway/src` and `apps/web-client/src`. `git diff 4f1602a f7b9c26` on those paths: **0 files** | **Met** |
| 17 | No `TrustMetric` subject or RPC | `contract/…::test_4f6_no_trust_metric_subject_exists` (no registered subject contains "trust"). CF-10 stays OPEN | **Met** |
| 18 | No new autonomy REST route | `integration/test_autonomy_api.py::test_the_only_routes_are_the_ones_the_tdd_names`, **unmodified** and passing. `api/` has 0 lines of diff | **Met** |
| 19 | `PermissionCategory` canonical in `nova_contracts/events/autonomy.py`, re-exported; no duplicate | `autonomy unit/test_permission_category_relocation.py` (`EngineCategory is ContractCategory`); `cognitive-state unit/test_proposed_action.py::test_no_permission_category_is_defined_in_this_engine` (AST), `test_the_category_type_is_the_contracts_own` | **Met** |
| 20 | 4F.5 untouched | `git diff --stat 4f1602a f7b9c26` on autonomy `clients/`, `domain/{levels,policy,trust,permissions,ports}.py`, `config.py`, `api/`, `repository/`, `alembic/` and 4F.5's two unit files: **empty**. `domain/decision.py`: **+11/−2**, the optional `subject_id` keyword only (§3.1 D-2). The other 13 tests in 4F.5's `test_level_two_real_postgres.py` pass unmodified; only its subscribe check was retargeted | **Met** |
| 21 | Boundaries at zero | action-engine, Stage 3, nova-eventbus-sdk, `apps/web-client/src`, `.github`: **0 files each** (§7.3) | **Met** |

**21 of 21 met.** §19's two closing constraints are also met:

- **Schema changes: exactly one.** Migration `0002` adds one nullable JSONB
  column. The real-Postgres test `test_0002_adds_exactly_one_nullable_jsonb_column`
  confirms the other columns are unchanged, and
  `test_0002_leaves_the_check_constraints_exactly_as_0001_defined_them` confirms
  the CHECK constraints are unchanged.
- **Contract changes: exactly two.** They are the payload and
  `PermissionCategory`'s new home. **Registry 119 → 120.** How this was achieved
  is finding **F-1**.

### 2.1 What this slice does not claim

- It does not close CF-9, CF-10 or CF-11.
- It does not show AC-8 in a browser (4F.8).
- It does not ship a production caller of `promote_thought` (4F.7).
- It does not implement TTL, stale-trigger semantics, Layer 2 deduplication,
  persistent lost-trigger auditability, L-17, L-18, `/v1/cognitive-state`, the
  4F.7 panel, `TrustMetric`, or Levels 3–5.
- It does not redesign `action-engine` or `nova-eventbus-sdk`.

---

## 3. Category 1 — implementation against the TDDs and ADRs

### 3.1 Implementation decisions the TDD left open, each disclosed

| # | Decision | Why, with evidence |
|---|---|---|
| **D-1** | **`extra="forbid"` on `AutonomyDecisionRequestedPayload`** | §9 says *"Producer-supplied `user_id` — **Rejected**"*, and §10 lists *"producer-supplied `user_id` rejected"* as a required negative test. Pydantic's default would **drop** the field silently instead. `autonomy-engine`'s own `api/schemas.py` `_Strict` base already uses `extra="forbid"`. A rejection is replied as `rejected=True`, and `decide()` is not invoked |
| **D-2** | **Optional `subject_id` keyword on `decide()`** | §5.5 named two shapes and ratified neither. I chose the smaller one. When the keyword is omitted, `uuid4()` is minted exactly as before, so every existing caller is byte-for-byte unchanged in behaviour. It is **not** a field on `DecisionRequest`: `test_decision_request_has_no_subject_id_field` |
| **D-3** | **A `rejected` flag on the reply**, beside `degraded` | Design A: *"`ValidationError` is handled separately and earlier: a malformed payload is a rejection, not a transport failure."* The reply needed a way to say so |
| **D-4** | **The degraded reply says how far the attempt got** | `subject_id is None` means the failure came before `decide()`, so nothing was decided or executed. `subject_id` set with `outcome is None` means `decide()` raised; 4F.5 propagates unknown dispatch faults, so execution state is then unknown. `outcome` set means a decision was reached but could not be recorded. Collapsing these into one state would let the reply claim "nothing executed" when that is not known |
| **D-5** | **`none_as_null=True` on the JSONB column** | Found by the real-Postgres tier before commit: SQLAlchemy's default wrote Python `None` as JSON `null`, not SQL `NULL`. Fixed in `repository/models.py`; negative-controlled as M12 |
| **D-6** | **`main.py` binds only the trigger port** | An earlier draft also opened a database engine and repository in the lifespan. That would have imported `nova_service_kit`, which this engine does not declare as a dependency and its Dockerfile does not copy, and it served no running caller. Removed before commit |

### 3.2 Ratified decisions, verified as built

| Decision | As built |
|---|---|
| **A-4F6-1**: internal subject | `@register_payload("autonomy.decision.requested")`. Not in `PUBLIC_TOPICS`; no gateway file changed |
| **A-4F6-2a**: `ProposedAction` | `cognitive-state-engine/domain/models.py`. Six required fields plus optional `detail`, all-or-nothing. `ActiveThought.proposed_action: ProposedAction \| None = None`. One nullable JSONB column (`0002`) |
| **A-4F6-2b**: Option A | Moved, not copied. `autonomy-engine/domain/models.py` imports it and keeps it in `__all__`. The **15** other files that import it from `domain.models` (6 in `src/`, 9 in `tests/`, counted at base with `git grep`) are unchanged. *(The first draft of this row, and the test docstring that pins the re-export, said 16. That echoed TDD revision 4's withdrawn blast-radius estimate. Both were corrected before merge, the docstring in commit `b8d22d3`.)* |
| **A-4F6-3 Layer 1** | `derive_subject_id`; the namespace is the pinned literal `0c81f3b8-e30f-5f0a-9241-8985e4b83489`, and its provenance is re-verified by test |
| **A-4F6-5**: Design A | Consumer side: three `except Exception` boundaries, each logging with `exc_info` and returning a structured reply. Producer side: `DecisionTriggerClient`. No retry anywhere; no table |
| **A-4F6-6**: amendment | The code honours D-4F-9's single internal subject. Retargeted controls pin **exactly** that set |
| **A-4F6-7** + filename | `decision_orchestration.py` at the package root |

### 3.3 Retargeted controls: none retired, all wording preserved

Each retargeted test asserts the **exact** new set, so none is weaker than the
test it replaced. Each keeps the original name, assertion or docstring in a
dated note.

- `autonomy`: `test_control_6_this_engine_publishes_action_execute_and_serves_only_the_trigger`
- `autonomy`: `test_control_6_the_only_bus_calls_are_one_request_and_one_serve`
- `autonomy`: `test_control_8_exactly_one_internal_autonomy_subject_exists`
- `autonomy` RI: `test_this_engine_subscribes_to_nothing_but_the_trigger`
- `cognitive-state`: `test_control_11_this_engine_publishes_the_trigger_and_nothing_else`
- `digital-twin-engine` (test-only): `test_control_8_no_autonomy_subject_is_registered_anywhere`, now pinned to `["autonomy.decision.requested"]`. This file is **outside TDD 4F.6 §11's listed boundary**; see finding **F-3**

### 3.4 ADRs

- **ADR-004** (engines independent): import-linter reports 7 kept, 0 broken.
  No test in either engine imports the other; they meet at the shared
  contract.
- **ADR-006** (no broker client in an engine): `NoRespondersError` is matched
  by type name, as in 4F.5.
- **ADR-025** (single trusted user): identity comes only from
  `primary_user_id`. `test_the_only_identity_is_the_configured_primary_user`
  is unchanged and passing.
- **ADR-024** (`schema_version`): both new payloads carry
  `schema_version: int = 1`.
- **ADR-033** (test tiers): the new real-infra tests are marked `real_infra`
  and excluded from the default tier.

---

## 4. Category 8 — contracts and codegen

- `git diff --stat 4f1602a f7b9c26 -- packages/nova-contracts/`: 6 files.
  - `events/autonomy.py`: new
  - `__init__.py`: re-exports
  - `codegen/generate_typescript.py`: one `MODELS` entry
  - `tests/test_autonomy_events.py`: new, 27 tests
  - `typescript/AutonomyDecisionRequestedPayload.ts`: new
  - `typescript/index.ts`: +1 line
- **Codegen:** *"Generated 118 TypeScript contract file(s)"* (was 117);
  `typescript/` holds 119 `.ts` files including the barrel. Regenerating twice
  gives identical md5 sums, so there is **zero drift**.
- **Registry:** `len(known_subjects()) == 120`. The only `autonomy.*` subject
  is `autonomy.decision.requested`. `AutonomyDecisionReplyPayload` is not
  registered (F-1).
- **Consumers of the new payload:**
  - `cognitive-state-engine`: builds it in `promotion_orchestration.trigger_payload`
  - `autonomy-engine`: validates it in `decision_orchestration`
  - Both are covered by unit and RI tests. There are no other consumers.
- **Breaking change: none.** The payload is new. The move of
  `PermissionCategory` leaves its wire form, the plain string value, unchanged
  (`test_permission_category_serializes_as_its_plain_string`).
- **Allow-lists, verified at runtime:**
  - `autonomy-engine`: publish `{action.execute}` (**unchanged**); subscribe
    `{autonomy.decision.requested}`
  - `cognitive-state-engine`: publish `{autonomy.decision.requested}`;
    subscribe `{}`
  - `action.execute` is still the only autonomy `PUBLISHABLE_SUBJECTS` entry.

---

## 5. Category 9 — tests, lint, types, imports

All commands were run at `f7b9c26`, uncached.

| Gate | Command | Result |
|---|---|---|
| Lint + types | `pnpm turbo run lint --force` | **32/32**, 0 cached |
| Typecheck (TS) | `pnpm turbo run typecheck --force` | **5/5** |
| Build | `pnpm turbo run build --force` | **32/32** |
| Tests | `pnpm turbo run test --force --continue` | **32/32**. autonomy 311 passed / 45 deselected; cognitive-state 102 / 28; nova-contracts 161; digital-twin 143 / 18; action-engine 103 / 27 (0 files changed); web-client 217; ui 29; every other package unchanged and green |
| Coverage (85% domain gate) | `pytest --cov=<mod>.domain` | **autonomy 99%**, **cognitive-state 100%**. nova-contracts: N/A (no `domain` module, and its test script has no `--cov`) |
| Import boundaries | `uv run lint-imports` | **7 kept, 0 broken** |
| Scaffolding tools | `uv run pytest tools/tests -q` | **295 passed** |
| Agent packages | per-package `mypy src && pytest tests` | **5/5** (13, 22, 13, 14, 11 passed) |
| compose | `docker compose … config --quiet` | **valid** (exit 0) |
| Codegen drift | generate + `git status` | **118 files; zero drift** |

**New tests:**

| Package | File | Tests |
|---|---|---|
| nova-contracts | `test_autonomy_events.py` | 27 |
| autonomy | `unit/test_decision_orchestration.py` | 33 |
| autonomy | `unit/test_permission_category_relocation.py` | 3 |
| autonomy | contract, three `test_4f6_*` tests | 3 |
| autonomy | RI `test_decision_trigger_real_infra.py` | 15 |
| cognitive-state | `unit/test_proposed_action.py` | 18 |
| cognitive-state | `unit/test_promotion_orchestration.py` | 17 |
| cognitive-state | `unit/test_decision_trigger_client.py` | 11 |
| cognitive-state | RI `test_decision_trigger_real_nats.py` | 9 |
| cognitive-state | RI `test_proposed_action_real_postgres.py` | 7 |

**No assertion was weakened.** Two of my new tests initially failed on their
**inputs**, not on the code: one used `risk="moderate"`, which is a real tier,
and two configured no permission grant, so the real gate correctly denied. The
inputs were corrected and the assertions kept.

`ruff format` is not a gate (protocol §9.2). Only files this slice touched
were formatted.

### 5.1 Negative controls: each property removed, its tests must fail

Mutated one at a time, run, then restored from git. The tree was confirmed
clean afterwards.

| # | Property removed | Result |
|---|---|---|
| M1 | `extra="forbid"` → `"ignore"` | 3 contract + 2 consumer tests **fail** |
| M2 | Trigger on any promotion, not only to `IMMEDIATE` | 3 **fail** |
| M3 | A second `request_decision` (a retry) | 6 **fail** |
| M4 | `subject_id` not passed to `decide()` | 2 **fail** |
| M5 | Namespace literal changed | 2 **fail** |
| M6 | Pre-decide Design A catch narrowed | 1 **fails** |
| M7 | Contract-validation catch removed | 7 **fail** |
| M8 | `serve()` on a different subject | 1 **fails** (structural control 6) |
| M9 | `decide()` ignores the supplied `subject_id` | 2 **fail** |
| M10 | A `propose` not persisted as a suggestion | 2 **fail** |
| M11 | Producer may publish `action.execute` | 2 **fail** (control 11) |
| M12 | `none_as_null` removed (real Postgres) | 2 passed unmutated → 2 **fail** mutated |
| M13 | Consumer's `serve()` removed (real NATS) | 2 passed unmutated → 2 **fail** with a real `NoRespondersError` |

M12 and M13 were first run in a batch while the local Postgres happened to be
down. The batch's non-zero exits for those two were therefore **not** counted.
Both were re-run by hand against a verified-running database, each with an
unmutated baseline first.

### 5.2 Flakiness

- The new real-infra files were run **10 consecutive times**: autonomy 15/15
  and cognitive-state 16/16 on every run. They include the real 1-second
  bounded wait, subscription timing and redelivery.
- The new unit files were run **10 times in random order** (`pytest-randomly`):
  33/33 and 46/46 every run.
- **No flake was observed.**

> **Correction, 2026-09-23 (pre-merge audit of PR #37), additively.** The
> second bullet above is **inaccurate about how the runs were made**, and is
> preserved as originally written.
>
> **`pytest-randomly` is not installed in this environment.** `import
> pytest_randomly` raises `ModuleNotFoundError`, it is not declared in any
> `pyproject.toml` or in `uv.lock`, and the only `pytest11` plugins installed
> are `anyio`, `asyncio`, `nova_testkit` and `pytest_cov`. The `-p no:randomly`
> flag used in those runs therefore did nothing.
>
> **What actually happened:**
>
> - **The original 10 repeated runs used pytest's normal order**, not a random
>   one. Each still passed every time: 33/33 for the autonomy-engine file and
>   46/46 for the three cognitive-state-engine files.
> - **The later pre-merge audit ran the tests in explicitly shuffled order.**
>   Each run shuffled the collected test ids with `shuf` and passed them to
>   pytest in that order. Each run was then checked: the first test pytest
>   actually executed had to be the first id after shuffling.
> - **All 20 shuffled runs passed.** That is 10 per engine, at 33/33 and 46/46,
>   with the randomised order confirmed on every run. They ran in an isolated
>   `git archive` export of `0b155ce`.
> - **No implementation behaviour and no test assertion changed** because of
>   this correction. Only this record's description of the method was wrong.
>   The real-infra bullet above is unaffected: it never claimed random order.

---

## 6. Category 10 — real infrastructure

1. **Docker: NOT available.** `docker ps` fails with *"failed to connect to the
   docker API at unix:///var/run/docker.sock"*.
2. **What was run instead, disclosed as such.** PostgreSQL 16.13 (the
   distribution binaries) and `nats-server` with `-js` were started locally. A
   **scratchpad-only** pytest plugin, never committed, pointed `nova-testkit`'s
   `postgres_container`/`nats_container` fixtures at them, and each run used a
   fresh database. **This is not the CI environment.** It matches its images
   in major version and JetStream mode, but CI's `postgres:16-alpine` and
   `nats:2-alpine` containers remain the authoritative evidence (§7.2).
3. **Harness fidelity.** Before any new test was added, the **pre-existing**
   suites ran green through this harness: autonomy 30 and cognitive-state 12.
   This includes 4F.5's `test_a_real_broker_with_no_responder_is_reported_unavailable`,
   which proves the local broker raises the real `NoRespondersError`.
4. **Results, local:**
   - `autonomy-engine -m real_infra`: **45 passed** (30 pre-existing + 15 new)
   - `cognitive-state-engine -m real_infra`: **28 passed** (12 + 16 new)
5. **Every real-infra test, by name.** All 73 cover code this slice changed,
   directly or through the migration chain, the ORM and the lifespan:
   - **autonomy, new** (`test_decision_trigger_real_infra.py`, 15):
     - `test_a_real_trigger_is_decided_by_the_production_served_handler`
     - `test_level_two_executes_once_through_the_real_dispatch_path`
     - `test_an_unconfigured_instance_only_observes`
     - `test_a_policy_denial_denies_and_dispatches_nothing`
     - `test_above_low_never_auto_executes[moderate|high|critical]`
     - `test_no_action_engine_degrades_to_a_proposal_that_executes_nothing`
     - `test_a_redelivered_trigger_reaches_action_engine_under_the_same_action_id`
     - `test_a_redelivered_proposal_is_not_recorded_twice`
     - `test_two_event_ids_with_identical_payloads_are_two_decisions`
     - `test_a_producer_supplied_identity_field_is_rejected_on_the_real_bus[subject_id|user_id]`
     - `test_an_unreachable_database_is_a_degraded_reply_and_nothing_executes`
     - `test_an_undelivered_trigger_decides_nothing_and_executes_nothing`
   - **autonomy, pre-existing** (`test_level_two_real_postgres.py`, 14):
     - `test_x1_level_two_is_selectable_through_the_production_route`
     - `test_x2_levels_three_to_five_are_still_refused_through_the_route[3|4|5]`
     - `test_a_level_two_decision_dispatches_over_real_nats_and_persists_execute`
     - `test_trust_unavailable_did_not_block_that_dispatch`
     - `test_absent_policy_dispatches_nothing_over_the_real_bus`
     - `test_a_missing_execution_field_dispatches_nothing_over_the_real_bus`
     - `test_a_silent_responder_produces_a_persisted_timeout_and_no_retry`
     - `test_a_real_broker_with_no_responder_is_reported_unavailable`
     - `test_that_unavailability_is_not_reported_as_a_timeout`
     - `test_no_responder_degrades_to_a_proposal_that_executes_nothing`
     - `test_the_real_bus_refuses_any_subject_but_action_execute`
     - `test_this_engine_subscribes_to_nothing_but_the_trigger` (**retargeted**)
   - **autonomy, pre-existing** (`test_repository_real_postgres.py`, 16):
     - `test_the_migration_creates_exactly_the_five_tables`
     - `test_the_migration_does_not_touch_another_engines_schema`
     - `test_the_decision_log_matches_doc_07s_column_definition`
     - `test_a_proposal_and_its_log_row_are_written_in_one_transaction`
     - `test_a_decision_and_its_log_row_are_written_in_one_transaction`
     - `test_a_log_row_cannot_reference_a_suggestion_that_does_not_exist`
     - `test_deleting_a_suggestion_cannot_erase_its_decision_record`
     - `test_pagination_is_deterministic_when_two_suggestions_share_a_timestamp`
     - `test_a_second_decision_is_refused_by_the_conditional_update`
     - `test_deciding_an_unknown_suggestion_raises_not_found`
     - `test_the_autonomy_level_round_trips`
     - `test_policies_round_trip_including_the_match_columns`
     - `test_permission_grants_upsert_by_category_and_leave_others_alone`
     - `test_policy_checks_survive_the_jsonb_round_trip`
     - `test_counts_are_scoped_by_status`
     - `test_ping_succeeds_against_a_reachable_database`
   - **cognitive-state, new** (`test_decision_trigger_real_nats.py`, 9):
     - `test_promotion_to_immediate_sends_one_real_request_carrying_the_proposal`
     - `test_a_thought_without_a_proposal_reaches_immediate_and_sends_nothing`
     - `test_a_promotion_below_immediate_sends_nothing`
     - `test_promoting_an_immediate_thought_again_sends_nothing`
     - `test_a_real_broker_with_no_consumer_is_reported_unavailable`
     - `test_a_silent_consumer_is_unconfirmed_after_a_real_bounded_wait_and_not_resent`
     - `test_a_degraded_reply_crosses_the_real_wire_as_degraded`
     - `test_the_real_bus_refuses_action_execute_and_every_other_subject`
     - `test_this_engine_cannot_consume_the_trigger_it_produces`
   - **cognitive-state, new** (`test_proposed_action_real_postgres.py`, 7):
     - `test_0002_adds_exactly_one_nullable_jsonb_column`
     - `test_0002_leaves_the_check_constraints_exactly_as_0001_defined_them`
     - `test_0002_adds_no_table`
     - `test_a_proposal_round_trips_and_is_stored_as_a_json_object`
     - `test_no_proposal_is_sql_null_not_a_json_value`
     - `test_moving_a_layer_keeps_the_proposal`
     - `test_a_proposal_can_be_withdrawn_back_to_null`
   - **cognitive-state, pre-existing** (`test_repository_real_postgres.py`, 12):
     - `test_a_historical_created_at_is_persisted_not_overwritten_by_the_column_default`
     - `test_upsert_preserves_created_at_and_advances_updated_at`
     - `test_the_three_relation_lists_round_trip_through_jsonb`
     - `test_an_absent_estimated_completion_stays_null`
     - `test_the_check_constraints_are_real[×3]`
     - `test_listing_is_deterministic_across_a_timestamp_tie`
     - `test_listing_narrows_to_one_attention_layer`
     - `test_move_layer_persists_the_transition`
     - `test_a_missing_thought_raises_rather_than_returning_none`
     - `test_the_migration_creates_exactly_one_table_in_its_own_schema`
6. **Matrix:** both `autonomy-engine` and `cognitive-state-engine` already have
   rows in `real-infra-checks.yml`. No CI change was needed, and `.github` has
   0 files changed.
7. **The decisive evidence TDD §10 names:** *"a real-infra test in which no
   test code calls `decide()` directly."* No test in
   `test_decision_trigger_real_infra.py` calls `decide()`. Every decision is
   made by the production `create_app` lifespan's `serve()` handler, using the
   production trust adapter and the production `ActionDispatchClient`.
8. **What the RI tests fake.** `action-engine` is a stand-in responder, as in
   4F.5. Its terminal-replay guard is proven by its own suite
   (`test_pipeline.py::test_idempotent_replay_of_a_terminal_action_returns_stored_result`,
   `test_repository_real_postgres.py::test_inserting_a_duplicate_action_id_raises_action_already_exists`).
   4F.6 proves what **reaches** that guard: the same `action_id` on
   redelivery. Each engine's RI tier drives the other engine as a stand-in on
   the real broker. No single test runs both engines' production code, because
   control 10 forbids cross-engine imports. The two halves meet at the shared
   contract, and the full-stack path is 4F.8's AC-8.

---

## 7. Category 11 — PR, branch, commit and CI evidence

### 7.1 Branch and commits

- **Branch:** `phase-4f6`. It tracks `origin/phase-4f6`.
- **Tree:** clean at each commit.
- **Ancestry:** `4f1602a` is an ancestor of HEAD.

Commits `4f1602a..` in order:

| Commit | Content |
|---|---|
| `9eed0b1`, `9c4e665`, `86eef93`, `dd7ae08`, `8f3e3c8`, `c6a3c01` | TDD 4F.6 and `00-master-scope.md`, docs only |
| `f7b9c26` | **The implementation**: 36 files, +3762/−80 |
| (next) | This record, plus the additive architecture notes and the autonomy-engine README (§9) |

**`f7b9c26`'s commit message, checked claim by claim:**
- *"Registry 119 → 120"*: true, §4.
- *"six distinct outcomes"*: true, `TriggerStatus` has six members.
- *"PUBLIC_TOPICS is unchanged (18)"*: true.
- *"no gateway, web-client, action-engine or SDK file changed"*: true, 0 files
  each.
- *"no autonomy migration or table"*: true.
- The retargeted-controls list: true, and complete.

### 7.2 CI at the exact implementation SHA, `f7b9c26`

PR #37's first CI run was against **`f7b9c267649909a94d5da9cd5de93ab3ec4d6482`**,
the implementation commit, before this record existed. Conclusions were read
from the PR's check runs through the GitHub API.

| Workflow (run id) | Jobs | Conclusion |
|---|---|---|
| `real-infra-checks` (35925009435) | 15 | **15/15 success**. **`real-infra (autonomy-engine)`: 45 passed, 311 deselected**; **`real-infra (cognitive-state-engine)`: 28 passed, 102 deselected**. These are the same counts as the local run in §6, now executed in the CI containers |
| `build-and-scan` (35925009341) | 23 (22 image jobs + `dependency-audit`) | **23/23 success**. Every image job builds its image and runs `aquasecurity/trivy-action@v0.34.0`; that includes `autonomy-engine` and `cognitive-state-engine`. No Dockerfile changed |
| `pr-checks` (35925009454) | 2 (`checks`, Playwright golden path) | **`checks`: success**: lint, typecheck, the full uncached turbo test suite, import-linter, tools tests, agent packages and compose validation. **Playwright golden path (staged, non-blocking): still running when this record was committed**; its conclusion is reported on PR #37 and in the slice report, not here |

**CI total at `f7b9c26` when this record was committed: 39 of 40 checks complete, all 39 successful; 1 in progress (Playwright, non-blocking).**

`b8d22d3` (a test docstring) and this record's commit came afterwards. Their
own CI runs are reported in the PR, not here: a record cannot contain the CI
result of the commit that adds it.

### 7.3 Boundary audit (`git diff --name-only 4f1602a f7b9c26`)

| Path | Files |
|---|---|
| `services/action-engine` (including Stage 3) | **0** |
| `packages/nova-eventbus-sdk` | **0** |
| `services/ws-gateway` | **0** |
| `services/api-gateway` | **0** |
| `apps/web-client` | **0** |
| `.github` | **0** |
| `infra` | **0** |
| `services/digital-twin-engine/src`, `/alembic` | **0** |
| `services/digital-twin-engine/tests` | **1** (F-3) |
| `docs` | **0** in `f7b9c26`. The TDD commits touch 2 docs files; this record's commit touches 4 (this record, plus architecture docs 07, 09 and 10), and also `services/autonomy-engine/README.md` |

### 7.4 SLOC (4E methodology; `cloc` over a `git archive` export; tests excluded)

| Scope | Base `4f1602a` | Head `f7b9c26` | Δ |
|---|---|---|---|
| Comparable | 36,718 | 37,124 | +406 |
| Wider | 42,059 | 42,465 | +406 |
| Full | 45,691 | 46,097 | +406 |
| **4F scope (the gated figure)** | **46,337** | **46,743** | **+406** |

The 50,000 gate is **not crossed**, with **3,257** of headroom remaining.
There are no other milestones between here and the gate.

---

## 8. Category 13 — findings, gaps and carry-forwards

### 8.1 Findings: OPEN, each with a recommendation. None is silently fixed

| # | Finding | Documents | Options → recommendation | Blocks? |
|---|---|---|---|---|
| **F-1** | **The reply is not a registered subject.** Every other request/reply pair registers its reply, and that convention would have put the registry at 121 | TDD 4F.6 §16 and §19 fix *"Registry 119 → 120"* and *"exactly two"* contract changes; the brief repeated 120. **The TDD error is mine**, from the ratification rounds: the reply was not counted | (a) keep it unregistered (built, and mechanically sound: the reply rides NATS's ephemeral inbox, which neither the SDK nor the registry consults); (b) register it and amend §19 to 121. **Recommend (b) at Gate Review**, for convention's sake. It is a one-line contract change and needs ratification | No |
| **F-2** | **The 20-second reply-wait bound is unratified.** `decision_trigger_timeout_seconds = 20.0` | The TDD specifies no reply bound. It must exceed 4F.5's 15 s dispatch bound, or every successful Level-2 execution would read as `unconfirmed`. It is **not** a TTL; A-4F6-4 stays OPEN | Ratify 20 s, or choose another value > 15 s. **Recommend ratifying as built** | No |
| **F-3** | **A test outside TDD §11's boundary was changed.** `digital-twin-engine/tests/contract/test_phase_4e_boundaries.py::test_control_8_no_autonomy_subject_is_registered_anywhere` asserted a **registry-wide** "no `autonomy.*`" property, which D-4F-9 now contradicts | §11 lists the files allowed to change and omits this one; that omission is my TDD error. The retarget pins exactly `["autonomy.decision.requested"]`, keeps the original assertion in a note, and changes **no** digital-twin production file | Accept the retarget, or revert it and leave CI red. **Recommend accepting**, and adding the file to §11 by additive amendment | No |
| **F-4** | **A redelivered `propose` replies `degraded`.** Same `event_id`, so the same `subject_id`. The suggestion table's **existing** primary key refuses a second row; the whole transaction rolls back, leaving one suggestion and one log row; the reply is `degraded=True, outcome="propose"` | §5.4 Q5 covered redelivery only for dispatch. The brief forbids "alternate idempotency mechanisms". `action-engine` has a precedent: `ActionAlreadyExistsError` translation | (a) keep as built, which is safe and duplicates nothing; (b) translate the PK violation into `SuggestionAlreadyExistsError` and reply as an idempotent `propose`. **Recommend (b), ratified, in a later slice**. Not done here because of the brief's prohibition | No |
| **F-5** | **`correlation_id` does not reach `action.execute`.** §8 says `correlation_id` is *"threaded through: trigger → decision → `action.execute` share one identity"*. 4F.5's dispatch uses `subject_id` as `action.execute`'s correlation id | §19 row 20 freezes 4F.5's dispatch semantics, and §19 is authoritative. The chain is still reconstructable: `event_id → subject_id` (deterministic) `→ action_id` | Amend §8, or thread the id in a ratified change to 4F.5's dispatch. **Recommend amending §8 to describe the built chain** | No |
| **F-6** | **`promote_thought` has no production caller.** Only the trigger port is bound in `main.py` | TDD 4F.6 §15.1; CF-11 claims 3–4 are owned by 4F.8 and 4F closure | None in this slice. The surface is 4F.7's | No |
| **F-7** | **The Design A log lines include `correlation_id`.** The consumer's warnings interpolate `envelope.event_id` and `envelope.correlation_id` as message arguments | TDD 4F.6 §9.1 Design A (**RATIFIED**) lists *"Information captured: Subject, `event_id`, `correlation_id`, exception type and traceback"*. §16 keeps *"Logging `correlation_id`"* **OPEN** as a possible convention: *"No log call in the repository carries one."* I followed the ratified row. No logging infrastructure, binding or structured-context mechanism was added | (a) keep; (b) drop `correlation_id` from the three lines until the convention is settled. **Recommend the Gate Review decide**; it is a three-line change either way | No |

> **Correction, 2026-09-26 (4F.7 ratification, RS-11 and RS-1c — TDD 4F
> §24), additively.** The F-6 row above and §2.1's *"It does not ship a
> production caller of `promote_thought` (4F.7)"* are preserved as written.
>
> - **Their owner attribution is superseded.** 4F.7 is **strictly read-only**
>   (RS-1b). It does not promote thoughts, call `promote_thought`, create Active
>   Thoughts or author `ProposedAction`s.
> - **F-6's owner is now the production promotion slice, 4F.P**, which comes
>   before 4F.8 (TDD 4F §18, as amended). 4F.P also owns thought ingestion,
>   `ProposedAction` authorship, the CAS transition semantics (RS-7) and
>   A-4F6-3 Layer 2.
> - **F-6 stays OPEN**, and so does CF-11.

### 8.2 CF-9, CF-10 and CF-11: all OPEN

**CF-11.** 4F.6 supplies claims 1–2 (§15.1): the trigger exists and reaches
`decide()` in production code, proven over real infrastructure. **Claims 3–4
(4F.8 end-to-end, and 4F-closure recorded evidence) stay open.**

**CF-9** and **CF-10:** 4F.6 contributes nothing. There is no `TrustMetric`
surface, and §11.4 still forbids one.

### 8.3 Other carry-forwards, unchanged

- **A-4F6-4** (TTL) and **stale-trigger semantics**: OPEN.
- **A-4F6-3 Layer 2**: DEFERRED to the slice that ratifies `ProposedAction`
  promotion semantics.
- **Persistent lost-trigger auditability**: DEFERRED.
- **`observability.py` packaging**: OPEN, and not created. The existing
  logging convention was reused.
- **Logging `correlation_id`**: OPEN as a convention. No logging
  infrastructure was introduced. The three Design A log lines do carry it as a
  message argument, per Design A's ratified *"information captured"* row;
  disclosed as **F-7**.
- **L-17** and **L-18**: OPEN, and untouched.

### 8.4 Non-blocking observation: the web-client's own `PERMISSION_CATEGORIES` (added 2026-09-23)

*Added by the pre-merge audit of PR #37. It is not one of F-1 … F-7, and it
reclassifies none of them.*

**What exists.** The web-client already keeps its own copy of the permission
vocabulary, in `apps/web-client/src/entities/autonomy.ts`:

- a hand-maintained `PERMISSION_CATEGORIES` list (line 43);
- a derived TypeScript type, `export type PermissionCategory` (line 207).

Both date from **Phase 4D**, commit `de6dbc9`. Today the list holds the same
ten values, in the same order, as the canonical
`nova_contracts.events.autonomy.PermissionCategory`; I checked this
programmatically at `0b155ce`. Because it is maintained by hand, nothing
enforces that it stays that way.

**Why 4F.6 leaves it alone:**

- **4F.6 does not modify the web-client.** `git diff --name-only 4f1602a
  0b155ce -- apps/` lists **0 files**.
- **The web-client is outside the ratified 4F.6 implementation boundary.** TDD
  4F.6 §12 lists `apps/web-client/src/` as a non-goal, and §19 row 21 requires
  it to have **0 files** changed.
- **So the web-client's copy is not reconciled with the canonical enum in this
  slice.** Whether it should import the generated TypeScript contract instead
  is a question for a later web-client / UI scope.

**What it does not change:**

- **The 4F.6 contract result is unchanged.** §19 row 19 requires one canonical
  `PermissionCategory`, living in `nova_contracts/events/autonomy.py`, with
  *"no duplicate in `cognitive-state-engine`; no second type"*. That holds:
  there is exactly one Python definition, and the web-client list is a browser
  REST-client vocabulary, not an Event Bus contract.
- **It is a follow-up item, not an implementation blocker.** It already
  existed before this slice and needs documentation follow-up. **No ledger row
  is opened for it by this correction**, so the ledger count in §1 and §10 is
  unchanged.

---

## 9. Category 14 — documentation updated by this slice

| Trigger (§14.1) | Document | Change | Additive? |
|---|---|---|---|
| New subject | `docs/architecture/09-event-bus-architecture.md` §4 | A dated note: the first `autonomy.*` subject, internal, not public; the taxonomy's two names are still unbuilt reservations | **Yes**, taxonomy line kept |
| New subject | `docs/architecture/10-inter-engine-communication.md` §2 | A dated note after the flow table describing the built initiative path | **Yes**, rows 8 and 13 kept |
| Table / migration | `docs/architecture/07-database-architecture.md` §1 | A dated correction: Active Thoughts are in Postgres `cognitive_state.active_thought` (4F.1), not Redis; `0002` adds one column; no `cog:*` key exists (grep: 0 hits) | **Yes**, Redis rows kept |
| Publisher README | `services/cognitive-state-engine/README.md` | Status update, owned events, persistence | **Yes**, originals preserved in notes |
| Subscriber README | `services/autonomy-engine/README.md` | Owned-events table filled in; the scaffold placeholder is preserved in a note | **Yes** |
| Engine boundary | TDD 4F.6 | **Not edited.** F-1, F-3 and F-5 are proposed amendments awaiting Gate Review | — |

**Inspected and found accurate, or out of this slice's scope:**
- `09`'s envelope section: accurate.
- `20-engine-responsibility-boundaries.md`: ownership is unchanged; 4F.6 adds
  no state ownership.
- `11-api-architecture.md`: N/A, since no REST route was added.
- `14-deployment-architecture.md`: N/A. No Dockerfile changed. D-6 removed the
  one dependency that would have required a change.

**SAD 15 §9.1:** N/A. 4F.6 introduces no new subsystem; it extends two
existing engines.

---

## 10. Deferred-obligations ledger (protocol §0.2)

### 10.1 Settled by this slice

**None.**

### 10.2 Still open

**L-1 … L-6, L-8 … L-11, and L-13 … L-18**, as listed in the 4F.5 record
§10.2, are carried forward **unchanged**: not closed, renamed or renumbered.
L-9 (the category-12 cross-file sweep) and L-10 (the `docs/` staleness sweep)
inherit the three 4F.6 notes in §9 as inputs.

### 10.3 L-19: opened by this slice

| | |
|---|---|
| **Row** | **L-19** |
| **Status** | **OPEN** |
| **Obligation** | `services/autonomy-engine/README.md` is still mostly the engine scaffold. The description paragraph is `TODO`, and *Owned APIs* lists only the three `/internal/*` routes, omitting the `/v1/autonomy/*` surface 4D shipped. 4F.6 filled in only the owned-events table, which is the part its own change affected |
| **Owner** | **4F closure** (together with L-6/L-16's README pass) |
| **Blocks 4F.6?** | No |

---

## 11. Final status

- **Implementation:** complete against all 21 rows of §19, including the
  exactly-one schema change.
- **Local verification:** complete, with real numbers (§5).
- **Real infrastructure:** executed locally against substitute
  PostgreSQL 16 and NATS/JetStream (§6), with **Docker unavailable**. CI
  remains the authoritative evidence (§7.2).
- **Findings:** seven, all OPEN, none blocking (§8.1).
- **Carry-forwards:** CF-9, CF-10 and CF-11 all OPEN.
- **Ledger:** 17 rows open.
- **Gate verdict:** none; this is a slice (§0).
- **`main` and `phase-4`:** untouched.
- **Next step:** completing 4F.6 does **not** authorize starting 4F.7.

### 11.1 What was not verified, and why

- **The real-infra tier in the CI containers.** It is pending until §7.2 is
  filled in. The local run used substitute binaries, not the CI images.
- **The Playwright golden path.** That is CI-only. 4F.6 adds no browser
  surface, but the stack now starts `autonomy-engine` with a live `serve()`,
  so the E2E run is still relevant evidence.
- **Docker image builds and Trivy.** CI-only. No Dockerfile changed.
- **A single test running both engines' production code together.** This is
  structurally excluded by control 10; see §6 item 8.
