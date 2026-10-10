# Phase 4F.P — Slice Completion Record
## Production promotion: thought ingestion, `ProposedAction` authorship, CAS promotion, the authored operation on `action.execute`, the real outcome, and real-execution evidence

**Date:** 2026-10-05

**Slice:** 4F.P — TDD 4F.P §1, P1 … P9. Per master scope §5, the order is 4F.7 → **4F.P** → 4F.8. This record is **P9's Slice Completion Record**.

**Branch:** `phase-4fp`.

- **Implementation SHA: `d1ae98181c9af1bec24279a0a79cd62f874d0093`.** It is the last commit that touches code, tests, CI or compose.
- This record's commit follows it, and is documentation only (§7.1).

**Base:** `phase-4` at **`9d2d63613fabf98c85dcdfa7c5a90fba4233baff`**. This slice does not change it.

**`main`:** **`7e273e62e942ecd5528ca807e65933d6bb675669`**. Untouched.

**PR:** **none.** None has been requested, and TDD 4F.P §22 step 8 and protocol §11.1 allow a PR only when asked. **Nothing is merged.**

**Protocol:** [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md).

- sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`, 1131 lines.
- Last changed on `origin/main` in `733a31d` (2026-08-30).
- Fetched from `origin/main` and read in full in this session. It is byte-identical to the copy 4F.7 used.

**TDDs:**

- [TDD 4F.P](../../design/phase-4/13-tdd-4fp-production-promotion.md) is authoritative. That includes **§30**: SD-1 … SD-6 and A-4FP-1 … A-4FP-13, RATIFIED 2026-09-29, with A-4FP-14's default (a) standing. It also includes §28.4's corrections C-1 … C-15, which §30 incorporates.
- Also used: [TDD 4F](../../design/phase-4/06-tdd-4f-companion-and-cognitive-state.md) §24, [TDD 4F.5](../../design/phase-4/09-tdd-4f5-autonomy-level-2.md), [TDD 4F.6](../../design/phase-4/10-tdd-4f6-initiative-trigger.md) and [TDD 4F.7](../../design/phase-4/11-tdd-4f7-cognitive-state-panel.md).

---

## 0. What this document is, and is not

**This is a Slice completion record. It is not a Gate Review.**

- Protocol §0.1 gives a Significant Slice categories **1, 2, 8, 9, 10, 11, 13 and 14 in full**.
- Categories **3–7 and 12** go into a deferred-obligations ledger (§10).
- So this record issues **no GO / CONDITIONAL-GO / NO-GO verdict**. 4F's Gate Review is **L-1**, owned by 4F closure after 4F.8.

**4F.P is NOT complete.** Every deliverable P1 … P8 is implemented and verified locally, and this record discharges P9's documentation and controls. Four things remain, and §11 names them:

- **No CI run exists at the implementation SHA** (§7.2). TDD 4F.P §15.1 makes CI authoritative and requires this record to cite CI's conclusions **at the exact SHA**. The only workflow that runs the P8 proof in containers is `pr-checks.yml`'s e2e job, and it runs only for a pull request.
- **Two decisions are the user's** (§8.1): F-4FP-1, V-6 (b)'s realisation; and F-4FP-2, the six-member outcome vocabulary.
- **No PR has been opened.**
- **Nothing is merged.**

**Phase 4F is NOT complete.** **4F.8 has not started.** Completing 4F.P does not authorize starting 4F.8. 4F.8 also waits for 4F.P to be **merged** (TDD 4F.P §30.9).

### 0.1 Branch shape — disclosed

- **The cut.** After the user's explicit GO, `phase-4fp` was cut from **`origin/phase-4` @ `9d2d636`** (TDD 4F.P §22 step 3).
- **The TDD history.** The ratified TDD lived in five documentation-only commits on `phase-4p-tdd`: `fbce0ff`, `58181f5`, `7140d30`, `fc20827` and `2b92682`. They were brought onto `phase-4fp` by **one normal merge, `8b22cf9`**, with the commits unchanged. So the branch carries the ratified TDD together with its implementation.
- **No rewriting.** No history was rewritten, squashed, rebased or force-pushed.
- **Ancestry, re-verified in this session.**
  - `9d2d636` is an ancestor of HEAD.
  - No 4F.P commit is an ancestor of `phase-4` or `main`.
  - `origin/phase-4fp` equals the implementation SHA.
  - The working tree was clean before this record.

### 0.2 Decisions in force

- **RATIFIED:**
  - SD-1 … SD-6 (§30.1);
  - A-4FP-1 … A-4FP-13 (§30.2).
- **Not ratified, with its default standing:** A-4FP-14 (a). The read surface does not expose `operation` or `parameters`.
- **In-session instructions** for each implementation slice (P1/P3/P5/P6, P4, P7, P8), and for this final verification.
- **One discrepancy between an instruction and the ratified text.** It was reported at the time and is listed for confirmation in §8.1, F-4FP-2.

---

## 1. Status

**Implemented, and verified locally:** every deliverable P1 … P8 in TDD 4F.P §1. P9's controls and documentation are completed by this record (§5, §9).

- **P2 is implemented**, in `c0c47f9`: the promotion policy and its production driver. The status notes on this branch list *"P1, P3 … P8"* and omit P2. §8.1 F-4FP-3 corrects that additively.
- **Real-infrastructure tests** ran against substitute local services, because Docker is unavailable here (§6): PostgreSQL 16, `nats-server` and `redis-server`.
- **The composed proof** ran against a local equivalent of the e2e stack (§6.2): the same engines and the real companion binary, as processes.
- **CI has not run at all for this branch** (§7.2).

### 1.1 The slice's exit criterion

TDD 4F.P §1:

> *"A real input produces an Active Thought carrying a complete, authored
> `ProposedAction` in production, and that thought's promotion causes a real
> execution."*

It is proven, **locally**, by the P8 driver (`tools/e2e_real_execution.py`). Every engine on the path runs production code from the implementation SHA. The driver only:

- writes a file;
- configures the stack through production routes;
- observes the bus without publishing;
- reads every store by `SELECT`-only SQL.

**This session's cold run.** It started from an empty database, run id `19b4ad89df51`, and passed **67/67 checks**. Each link below is read from that run's evidence:

| Link | What | Evidence (run `19b4ad89df51`, run A) |
|---|---|---|
| **A** | A real observation | The driver wrote `p8-19b4ad89df51-a.txt` into the shared workspace. The **real `nova-companion` binary** observed it, as sensor `companion-filesystem`. |
| **B** | `perception.workspace.observed` | Outbox row and event `aba331c1…`, dispatched by `perception-engine`. Its `user_id` is `…0001`, and its `object_id` is `ws-198388df…`, a path hash. The payload carries no path. |
| **C** | Cognitive-state ingestion | Exactly one Active Thought for that object. Its id is `uuid5(77980e9a-…, object_id)` (A-4FP-1, A-4FP-9), and it belongs to user `…0001`. |
| **D** | A real ActiveThought | `4e53cf1e-dd33-51e2-b0e6-c0625f18b52b`, read by SQL from `cognitive_state.active_thought`. |
| **E** | A real ProposedAction using T1 | `{category: read, risk: low, action_type: filesystem, execution_target: filesystem, operation: list, parameters: {}, verification_method: adapter_success}`. The title names the run's file. |
| **F** | Real CAS promotion | `attention_layer = immediate`. This is the production path: `ingestion_orchestration.py` → `promote_thought` → `compare_and_set_layer`. The CAS property itself is proven per engine: V-7 (b), and NP-7 in §5.1. |
| **G** | `autonomy.decision.requested` | Exactly one, `468294f4…`, from `cognitive-state-engine`. It carries `operation: list` and `parameters: {}`. Exactly one reply, from `autonomy-engine`, with `subject_id` `6a92acbe-9ca6-5070-9473-579fb4095f26`. |
| **H** | Real Level 2 `AUTO_EXECUTE` policy | Configured by `PUT /v1/autonomy/level` (2), `PUT /v1/autonomy/permissions` (`read` up to `low`) and `POST /v1/autonomy/policies` (`AUTO_EXECUTE`, `read`). A-4FP-11's `{"negligible": 0.0}` was set by `PUT /v1/action/identity-confidence-policy`. The decision row has `autonomy_level = 2` and the reason *"auto-executed at autonomy level 2 by policy; …"*. |
| **I** | Exactly one `action.execute` | `1ef171fa…`, from `autonomy-engine`, the one producer. Exactly one for that `action_id`: no retry and no duplicate. |
| **J** | It contains `"operation": "list"` | `parameters == {"operation": "list"}`. `requested_by` is `…0001`. |
| **K** | The real `action-engine` receives and executes it | Exactly one reply to `action.execute`, from `action-engine`: `causation_id` `1ef171fa…`, status `completed`. `action.action` has `id = subject_id`, status `completed`, risk `negligible` and the stored listing. 13 history rows cover all twelve stages, including `validate`/`success`, `check_permissions`/`success` and `execute`/`started`. |
| **L** | The real `capability-engine` receives the filesystem `list` | Exactly one `capability.invoke.request`, `8a663568…`, from `action-engine`. It names `capability_id` `19c02fdd…`, the installed `filesystem` capability, with `operation: list` and `parameters: {"operation": "list"}`. |
| **M** | The real filesystem capability runs against the real workspace | Exactly one reply, from `capability-engine`: `causation_id` `8a663568…`, outcome `success`, `result {"entries": ["p8-19b4ad89df51-a.txt"]}`. The capability's `required_resources` is the shared workspace root. `capability-engine`'s own `capability_invocation_total` rose by **exactly 1**. |
| **N** | The real `action-engine` receives the `completed` result | The capability reply's `result` equals `action.action.result`. `action-engine`'s reply is `completed` with the same listing. |
| **O** | P7 maps `completed` to `EXECUTE` | The driver's outcome table equals `autonomy-engine`'s `ACTION_STATUS_OUTCOMES`; guard G10 checks this against the source. The decision reason ends *"action-engine reported completed"*. |
| **P** | The persisted outcome is `EXECUTE` | Exactly one `autonomy.decision_log` row for the `subject_id`, with outcome `execute` and no suggestion. It was written in transaction **4316**, after `action-engine`'s terminal writes: the action row is at xid 4313, and the history maximum is below 4316. |
| **Q** | No stand-in on the positive path | See the four checks below. |

Link Q holds on four separate checks:

- Exactly one reply to each RPC (the trigger, `action.execute` and `capability.invoke`), each from the engine that owns the subject.
- `capability-engine`'s own counter.
- No stand-in process was running.
- The driver cannot serve a subject, by guard G6/G8.

**What §1's bullets add:**

- **The intended operation and parameters reach the real `action-engine`, which executes through a real capability.** Links I–N above.
- **The recorded outcome is the one `action-engine` reported.** Links O–P above.
- **Each failure mode is recorded truthfully.**

  | Failure mode | Where it is proven | Where in this record |
  |---|---|---|
  | Denial | The composed stack, V-6 (a) | §1.2 |
  | Failure | Per-engine halves, V-6 (b) | §8.1, F-4FP-1 |
  | Timeout | Per engine, V-8 (b) | §2 |
  | Unavailable executor | Per engine, V-8 (a) | §2 |
  | Transport fault | Per engine, V-8 (c) | §2 |

- **4F.P does not claim AC-8.** No AC-8 claim is made.

### 1.2 The denial control (V-6 (a)), separately

The driver removes A-4FP-11's row through the production route, `DELETE /v1/action/identity-confidence-policy`. The threshold therefore returns to stage 3's default of `1.0`. In the same run, `19b4ad89df51`, run B:

- **The real `action-engine` returned `denied`.** Its reply is `{"status": "denied", "error": "identity_confidence_denied"}`, from `action-engine`.
- **The reason is `identity_confidence_denied`.** It is a stage-3 identity-confidence denial.
- **P7 persisted `propose`.** The reason reads *"proposed for explicit user approval; nothing is executed (action-engine denied the action: identity_confidence_denied)"*. A suggestion `3746cd93…` was written with it, as A-4FP-7's proposal path requires.
- **No capability invocation occurred.** `capability_invocation_total` changed by **0**.
- **The row is restored afterwards** (`PUT` → 200). Run C then executes again.

The driver's check asserts `denied`, `propose`, the reason prefix and the zero delta. **It does not assert the error string itself.** That string is read from the evidence dump the driver prints. §8.1 F-4FP-4 records this, and it is **not changed here**, as the instruction for this verification requires.

---

## 2. Category 2 — acceptance criteria

**Sources consulted:**

- TDD 4F.P §1: the exit criterion and its bullets.
- §15: V-1 … V-10, as corrected by §28.4 **C-14**, which assigns each V-item to a tier.
- §16: NP-1 … NP-14, reported in §5.1.
- §30.2's ratified decisions, in §3.3.
- Master scope §5 and §17. They state no 4F.P criterion beyond the TDD's.
- `ENGINEERING_ROADMAP.md`: it has no 4F.P entry.
- In-session:
  - the slice instructions;
  - this verification's links A–Q and its denial control;
  - the non-goals: no new subject, `PUBLIC_TOPICS` entry or route; no change to authoring; no retry, scheduler, TTL or outbox; no change to `action-engine` or `capability-engine`; no 4F.8.

| # | Criterion | Tier (C-14) | Status | Evidence |
|---|---|---|---|---|
| X-1 | §1 exit criterion | Composed | **Met (local); CI pending** | §1.1, links A–P |
| X-2 | The real `action-engine` receives the intended operation and parameters and executes through a real capability | Composed | **Met (local); CI pending** | Links I–N |
| X-3 | `autonomy-engine` records the outcome `action-engine` actually reported | Composed + unit | **Met (local); CI pending** | Links O–P. Unit: `test_level_two_dispatch.py::test_p7_the_ratified_table_exactly` and `::test_p7_completed_is_the_only_status_that_maps_to_execute` |
| X-4 | Each failure mode is recorded truthfully | Mixed | **Met per mode, with the failure mode resting on V-6 (b)'s halves** (F-4FP-1) | V-6 (a), V-6 (b), V-8 (a)–(c) below |
| V-1 | `action-engine` receives the authored operation | Composed | **Met (local)** | Driver checks `[a] V-1/V-2` and `[a] 8`. Link J |
| V-2 | The authored parameters reach `action-engine`, key for key | Composed | **Met (local)** | `action.action.parameters == {"operation": op} ∪ authored` (`[a] V-1/V-2`) |
| V-3 | `action-engine` accepts it | Composed | **Met (local)** | `validate`/`success` and `check_permissions`/`success` in `action_execution_history` (`[a] 12`) |
| V-4 | It completes, with the adapter's `entries` | Composed | **Met (local)** | `[a] 11`. Links K, M |
| V-5 | `autonomy-engine` records the actual outcome | Composed | **Met (local)** | `[a] 12/16`, `[a] 12` and `[a] 13`. Link P |
| V-6 (a) | A real stage-3 denial is not `EXECUTE` | Composed | **Met (local)** | §1.2 |
| V-6 (b) | A failed action is not `EXECUTE` | Per-engine | **Partly met: as two halves, not as C-14's single test** | `autonomy-engine` real-infra `test_p7_failed_and_rolled_back_are_recorded_as_execution_failed[failed]` and `[rolled_back]`, with a labelled stand-in replying `failed`. `action-engine` unit `test_pipeline.py::test_execution_failure_without_rollback_strategy_reaches_failed`, which predates 4F.P. **F-4FP-1** |
| V-7 (a1) | A second real modification of the same file is still one thought, one trigger and one action | Composed | **Met (local)** | Driver checks `V-7 (a1)` (×2): new `event_id`, same `object_id`. After run C's ordered marker, one each of thought, trigger, `action.execute`, decision row and action row |
| V-7 (a2) | The same envelope delivered twice is one thought and one trigger | Per-engine | **Met (local)** | `cognitive-state-engine` `test_ingestion_real_postgres.py::test_an_observation_over_the_real_bus_becomes_one_thought_and_one_real_request`. A re-published envelope adds nothing, asserted with an ordered marker |
| V-7 (b) | Two concurrent promotions trigger once | Per-engine | **Met (local)** | `test_v7b_concurrent_promotions_of_one_thought_trigger_exactly_once`. Its in-suite control, `test_v7b_negative_control_an_unconditional_move_triggers_every_racer`, shows the race is real |
| V-7 (c) | A redelivered trigger produces one action row | Per-engine | **Met, as two halves (the 4F.6 precedent)** | `autonomy-engine` `test_a_redelivered_trigger_reaches_action_engine_under_the_same_action_id` (4F.6). `action-engine` `test_pipeline.py::test_idempotent_replay_of_a_terminal_action_returns_stored_result`, and real-infra `test_inserting_a_duplicate_action_id_raises_action_already_exists`, both from before 4F.P |
| V-8 (a) | No responder: `propose`, no `execute` | Per-engine | **Met (local)** | `test_p7_no_responder_is_recorded_as_a_proposal_never_a_timeout` |
| V-8 (b) | A silent responder: `timeout`, no `execute` | Per-engine (the one permitted stand-in) | **Met (local)** | `test_p7_no_reply_within_the_bound_is_recorded_as_timeout` |
| V-8 (c) | A transport fault: a degraded reply, no row | Per-engine | **Met (local), as realised in the TDD's 2026-10-01 note** | `test_p7_a_transport_fault_before_any_reply_records_nothing`. The bus is closed before the dispatch, because the NATS client reports an in-flight close as a timeout |
| V-9 | The trigger is production-originated | Composed + static | **Met** | The 26 guards in `tools/tests/test_e2e_real_execution.py`. They check, from the driver's AST: no `publish`/`request`/`serve`/`promote_thought`/`decide`; `SELECT`-only SQL; six production routes; tapped subjects exactly. Negative-controlled as G6–G8 and G11–G13 (§5.1). The input is a real companion observation of a real file write (link A) |
| V-10 | The boundaries are unchanged | Static | **Met** | See the V-10 checks below |
| I-1 | In-session: links A–Q | Composed | **Met (local)** | §1.1 |
| I-2 | In-session: the denial control, separately | Composed | **Met (local)** | §1.2 |
| I-3 | In-session non-goals | Static | **Met** | See the I-3 checks below |
| X-5 | AC-8 | — | **Not claimed, by design** (§1) | — |

**V-10's checks:**

- Registry **120**: `test_the_registry_holds_exactly_one_hundred_and_twenty_subjects` and `test_p13_the_registry_holds_one_hundred_and_twenty_subjects`.
- `PUBLIC_TOPICS` **18**: `test_p13_public_topics_are_unchanged_at_eighteen` and `test_control_7_public_topics_is_unchanged_at_its_eighteen_exact_strings`.
- Nine gateway prefixes: `api-gateway`'s route-table test passed in the uncached run.
- `git diff --stat 9d2d636 HEAD -- services/action-engine services/capability-engine` is **empty**, so stage 3 is byte-identical.
- The diff check is negative-controlled as NP-12 (§5.1).

**I-3's checks:**

- No subject, `PUBLIC_TOPICS` entry, gateway prefix or route was added (V-10). The driver uses six existing routes.
- No authoring change in P8: `domain/authoring.py` was last changed in `c0c47f9`, and the T1 guard is negative-controlled as G12.
- No retry, scheduler, TTL or outbox: `git diff --name-only a0b9b4f d1ae981` touches no `services/` or `packages/` file.
- Nothing from 4F.8.

**22 of 23 criteria are met on local evidence.** X-5 is excluded, because AC-8 is not claimed.

- **V-6 (b) is met only as two per-engine halves.** C-14 describes a single test in which the real adapter fails, and that test does not exist. It is for decision (F-4FP-1), and X-4's failure mode rests on it.
- **None of the 23 is verified in CI**, because no CI run exists for this branch (§7.2). The composed rows are CI-pending specifically: the e2e job is their authoritative carrier.

### 2.1 What this slice does not claim

- **AC-8**, or any Level-1 against Level-2 comparison, in a browser or otherwise (4F.8).
- **AC-7** in full: latency, revocation and project correlation (4F.8).
- **CF-11 claims 3 and 4**, and the closure of CF-9, CF-10 or CF-11. **All three stay OPEN** (§8.2).
- **That 4F.P is complete** (§0).

---

## 3. Category 1 — implementation against the TDDs and ADRs

### 3.1 Deliverables (TDD 4F.P §1)

| # | Deliverable | Commit | Verdict | Where |
|---|---|---|---|---|
| P1 | Thought ingestion (A-4FP-1) | `c0c47f9` | **Implemented as ratified** | `domain/ingestion.py:32` (`_INGESTION_NAMESPACE`), `:39` `thought_id_for`, `:45` (the field table). `ingestion_orchestration.py:71`: a foreign user is dropped at `:86`; the insert is at `:98`. `repository/postgres_cognitive_state_repository.py:170` `insert_thought_if_absent`. `events/handlers.py:124` `make_workspace_observation_handler`. `events/subscribed.py:42`, the two-subject allow-list. `main.py:116`, the one `subscribe()` |
| P2 | The promotion policy and its production driver (A-4FP-2, A-4FP-10) | `c0c47f9` | **Implemented as ratified.** Omitted from the status lists (F-4FP-3) | `ingestion_orchestration.py:98–114`: it promotes only when its own insert created the thought, and loses the initiative on a raise, with no retry (FP-15). It is the only production caller of `promote_thought` (`test_p14_promote_thought_has_exactly_one_production_caller`) |
| P3 | The authorship rule (A-4FP-3, A-4FP-4, A-4FP-5) | `c0c47f9` | **Implemented as ratified** | `domain/authoring.py:98` T1, `:118` `AUTHORING_TABLE`, `:122` `entry_for`. `domain/models.py:177` `operation` and `:183` `parameters` with their validators (`:191`, `:201`) |
| P4 | Propagation (A-4FP-6, SD-3, C-5, C-7, C-8) | `56cdee8` | **Implemented as ratified** | `nova-contracts` `events/autonomy.py:144`/`:149`, with validators at `:156` and `:172`; TypeScript regenerated. `cognitive-state-engine` `promotion_orchestration.py:126–127` (`trigger_payload`). `autonomy-engine` `decision_orchestration.py:142–143`; `domain/decision.py:150–151` (`DecisionRequest`); `:204` `_execution_payload`, with the merge at `:248` |
| P5 | CAS (A-4FP-8) | `c0c47f9` | **Implemented as ratified** | `repository/postgres_cognitive_state_repository.py:189` `compare_and_set_layer` (one `UPDATE … WHERE … RETURNING`). `promotion_orchestration.py:153` |
| P6 | Layer 2 (A-4FP-9) | `c0c47f9` | **Implemented as ratified** | The object identity as `thought_id`, plus the insert-if-absent of P1 |
| P7 | The real outcome (A-4FP-7, SD-4, C-9) | `a0b9b4f` | **Implemented as ratified**, with six members (F-4FP-2) | `domain/models.py:149` `EXECUTION_FAILED`. `domain/decision.py:255` `ACTION_STATUS_OUTCOMES`, `:294` `outcome_for_action_status`, `:545` (applied to the reply), `:524–536` (`TIMEOUT`, unchanged) |
| P8 | Real-execution evidence (A-4FP-11, A-4FP-12, A-4FP-13) | `d1ae981` | **Implemented as ratified**; its CI run is outstanding | `infra/docker/docker-compose.local.yml`: `:637` (`PERCEPTION_ENGINE_PRIMARY_USER_ID`), `:696` (`nova-companion`), `:705`/`:782` (one workspace). `pr-checks.yml`: `:200` (provision), `:690` (start), `:700` (prove), `:710` (logs). `tools/e2e_real_execution.py`. `tools/tests/test_e2e_real_execution.py`. `.gitignore` |
| P9 | Controls, documentation and this record | this commit | **Done locally** | §5, §9, this document |

**Unchanged by 4F.P, asserted.** `git diff --stat 9d2d636 HEAD -- <path>` is empty for each of:

- `services/action-engine`, `services/capability-engine`, `services/perception-engine`, `services/world-model-engine`;
- `services/ws-gateway`, `services/api-gateway`;
- `companion/`, `apps/`, `agent-os/`, `agents/`;
- every Dockerfile, every Alembic `versions/` directory;
- `uv.lock`, `pnpm-lock.yaml`;
- `build-and-scan.yml`, `real-infra-checks.yml`.

### 3.2 Implementation choices left open by the TDD, each disclosed

| # | Choice | Why | Alternative |
|---|---|---|---|
| C-1 | **The P8 services start after the golden path**, not in the e2e job's first `up` | The Cognitive State panel's spec asserts an unseeded stack in which no `perception-engine` runs, and `perception-engine` reports its sensors on startup. Starting the services afterwards keeps every spec's premise | Start them with the stack, and retarget that spec |
| C-2 | **The capability invocation is correlated to the action by the bus, by content and by a counter**, not by an audit record | `capability-engine` keeps no per-invocation record, and `action-engine` does not pass `action_id` into `capability.invoke`. Adding either would change an engine V-10 freezes | An audit record, in a later ratified change |
| C-3 | **V-8 (c) closes the bus before the dispatch** | On this stack, the NATS client reports a connection closed under an in-flight request as a timeout (TDD note, 2026-10-01) | — (realised as the TDD records) |
| C-4 | **A reply status outside `ActionStatus` is an unknown fault** (a degraded reply, no row) | SD-4 maps every `ActionStatus` value. Anything else is not `action-engine`'s contract | Map it to `EXECUTION_FAILED`. SD-4 does not say so |
| C-5 | **A denial without an error reads *"no error was reported"*** | An approval-loop denial carries no error | — |
| C-6 | **The driver restates engine constants and does not import them** (namespaces, the outcome table, T1, the twelve stages) | ADR-004 and V-9. Each restatement is guarded against its owning source (guards G9, G10, G12, G14) | Import them, which V-9's import guard forbids |

### 3.3 Ratified decisions, verified as built

| Decision | Built | Verified by |
|---|---|---|
| SD-1: `user_id` from `primary_user_id`, compared and never copied | P1 | `test_a_foreign_users_observation_writes_nothing`; the foreign-user case over the real bus |
| SD-2: no numeric parameter limit | P3, P4 | No limit exists in source |
| SD-3: absent is `None`, never `{}` | P4 | `test_p4_an_absent_execution_field_is_never_completed`, `test_p4_an_explicit_empty_object_is_present_not_absent`; NP-4 |
| SD-4: the outcome for every status | P7 | `test_p7_the_ratified_table_exactly`; NP-1, NP-2 |
| SD-5: `ingestion_orchestration.py` | P2 | File present; P-14 |
| SD-6: the trigger is awaited inline | P1, P2 | The handler awaits it, with no task, queue or retry; `test_no_trigger_outcome_is_retried` |
| A-4FP-1 … A-4FP-10 | P1 … P7 | §2, and NP-1 … NP-14 (§5.1) |
| A-4FP-11: `{"negligible": 0.0}` as disclosed test configuration | P8 | Link H; removing it gives V-6 (a)'s denial (§1.2) |
| A-4FP-12: the composed stack, one user, one workspace | P8 | Guards G1, G2; §1.1 |
| A-4FP-13: the SAD 15 §4 item 1 exception | §7.3 | Boundary audit |
| A-4FP-14 (a): no read-surface change | — | `test_cognitive_state_api_real_infra.py` excludes both fields (`_NOT_SERVED`) |

### 3.4 Retargeted controls: none retired, all wording preserved

| Test | Why it changed | How the original is kept |
|---|---|---|
| `cognitive-state-engine` `test_phase_4f7_boundaries.py::test_p14_promote_thought_has_exactly_one_production_caller` | A-4FP-10. Formerly *"…still_has_no_production_caller"* | Its wording is preserved, per §30.2 |
| `test_p13_this_engines_allow_lists_are_exactly_the_ratified_two`; `test_boundaries.py::test_the_subscribe_allow_list_is_exactly_the_two_ratified_subjects` (P-11) | A-4FP-1: two subjects | Retargeted (`c0c47f9`) |
| `test_boundaries.py`, control 11's schema check | F-4F7-1 repaired, as A-4F7-6 (a) describes (A-4FP-10) | Permits exactly the three ratified subjects; negative-controlled |
| `nova-contracts` `test_detail_is_the_only_optional_authored_field` | C-7 | Its wording is preserved |
| `autonomy-engine` `test_decision_orchestration.py::test_the_outcome_vocabulary_is_the_five_plus_execution_failed` | P7: six members | Its wording is preserved |
| `test_decision_trigger_real_nats.py` (`NOT_YET_ON_THE_WIRE` retired) | P4 put both fields on the wire | Quoted in a dated comment |
| `test_cognitive_state_api_real_infra.py` (`_NOT_SERVED`) | A-4FP-14 (a) | — |

### 3.5 ADRs

| ADR | Verdict |
|---|---|
| ADR-004 (bus only) | **Holds.** No engine imports another. Drift tests read `risk.py`, `pipeline.py`, `decision.py` and `config.py` as text. `uv run lint-imports`: **7 kept, 0 broken** |
| ADR-006 (the Event Bus) | **Holds.** One more core-NATS `subscribe()`, with no queue group, like every engine |
| ADR-024 (versioning) | **Holds.** Two optional fields; `schema_version` stays `1` |
| ADR-025 (one trusted user) | **Holds**, and is now enforced in the stack (SD-1, C-12) |
| ADR-032 (identity confidence) | **Holds.** Stage 3's code is unchanged. A-4FP-11 is test configuration only |
| ADR-033 (two-tier testing) | **Holds.** New real-infra tests carry `real_infra`, and both engines are already in `real-infra-checks.yml` |

No ADR is made false by this slice.

---

## 4. Category 8 — contracts and codegen

- **`packages/nova-contracts/` changed in `56cdee8` only.** `AutonomyDecisionRequestedPayload` gains `operation: str | None = None` and `parameters: dict | None = None`, with A-4FP-4's form and the `"operation"` refusal. It is +54/−3 lines in `events/autonomy.py`, and `AutonomyDecisionRequestedPayload.ts` gains +20.
- **Codegen.** `uv run --package nova-contracts python packages/nova-contracts/codegen/generate_typescript.py` generated **118** files, and `git status --porcelain` stayed **empty**: **zero drift**.
- **Subjects.**
  - The registry holds **120**, and `PUBLIC_TOPICS` holds **18**, before and after.
  - No subject is new.
  - `cognitive-state-engine`'s subscribe allow-list is exactly `{perception.sensor.health_changed, perception.workspace.observed}`.
- **Consumers.** `autonomy-engine` validates the payload under `extra="forbid"`, so the two engines deploy together (A-4FP-6). `AutonomyDecisionReplyPayload.outcome` stays a `str`.
- **REST: SAD 15 §4 item 4's review of the one OpenAPI change.**
  - `DecisionOutcome`'s enum widens from five values (`9d2d636`: `observe_only`, `propose`, `deny`, `execute`, `timeout`) to six, adding **`execution_failed`**. This was read from the served `create_app().openapi()`.
  - It reaches the schema through `DecisionResultResponse.outcome`, the response of `POST /v1/autonomy/suggestions/{id}/decide`. That route produces only `propose` or `deny` (`api/autonomy.py:494`).
  - The one client schema, `apps/web-client/src/entities/autonomy.ts:181`, enumerates four values. It already lacked `timeout`, and cannot receive `execution_failed` from that route.
  - **No consumer breaks** (F-4FP-10).
- **Breaking changes:** none for producers, because the fields are optional. The consumer is strict, which is the reason for the joint deployment.

---

## 5. Category 9 — tests, lint, types, imports

Run in this session at the implementation SHA, before this record's documentation edits. Those edits touch no code.

| Gate | Command | Result |
|---|---|---|
| Lint + types (uncached) | `pnpm turbo run lint --force` | **32/32 tasks successful, 0 cached** |
| Tests (uncached) | `pnpm turbo run test --force` | **32/32 tasks successful, 0 cached** |
| `cognitive-state-engine` | (in the above) | ruff clean; mypy **26** source files; **284 passed**, 57 deselected; **domain coverage 100%** |
| `autonomy-engine` | | ruff clean; mypy **28**; **379 passed**, 63 deselected; **99%** |
| `nova-contracts` | | ruff clean; mypy **20**; **171 passed** |
| `action-engine` | | mypy **24**; **103 passed**, 27 deselected; **97%** (unchanged code) |
| `capability-engine` | | mypy **28**; **83 passed**, 6 deselected; **97%** (unchanged code) |
| `perception-engine` | | mypy **39**; **208 passed**, 22 deselected; **99%** (unchanged code) |
| `web-client` | | **245 passed** |
| Import boundaries | `uv run lint-imports` | **Contracts: 7 kept, 0 broken** |
| Scaffolding tools | `uv run pytest tools/tests -q` | **326 passed**, including the 26 P8 guards |
| compose | `docker compose -f infra/docker/docker-compose.local.yml config --quiet` | **valid** (exit 0). The Compose CLI v5.1.1 is present, and the daemon is not |
| Codegen drift | generate + `git status` | **118 files; none** |
| Whitespace | `git diff --check 9d2d636 HEAD` | clean |

`ruff format` is not a gate (protocol §9.2).

### 5.1 Negative controls

**TDD 4F.P §16 (NP-1 … NP-14).** These were re-run in this session at the implementation SHA. A scratchpad-only driver applied each mutation, ran the named tests and restored every file byte for byte (`git status` unchanged afterwards). **All 14 are caught.** In the whole-suite unit runs, the real-infra items error, because their fixtures need Docker. Each verdict below rests on the named **failed** tests, not on those errors.

| # | Mutation | Failed (among others) |
|---|---|---|
| NP-1 | `failed` → `EXECUTE` | `test_p7_a_failed_reply_records_execution_failed`, `test_p7_the_ratified_table_exactly`; real-infra `test_p7_failed_and_rolled_back_are_recorded_as_execution_failed[failed]` |
| NP-2 | `denied` → `EXECUTE` | `test_p7_denied_records_a_proposal_and_its_suggestion_in_one_write`, `test_p7_a_denied_reply_records_a_proposal_through_the_proposal_path[…]` ×2; real-infra `test_p7_denied_is_recorded_as_a_proposal_with_its_suggestion` |
| NP-3 | `_execution_payload` sends `parameters={}` | 6 unit tests, incl. `test_p4_t1_dispatches_its_authored_operation_as_the_whole_parameters`; real-infra `test_p4_t1_leaves_on_the_existing_dispatch_point_as_operation_list`, `test_p4_authored_parameters_are_flattened_beside_the_operation_on_the_wire` |
| NP-4 | A missing `operation` defaults to `"list"` | `test_p4_an_absent_execution_field_is_never_completed[absent0]`, `test_invariant_6_a_missing_execution_field_yields_a_suggestion[operation]`, `test_x15_each_precondition_is_independently_load_bearing` |
| NP-5 | `"operation"` allowed in `parameters` | `test_parameters_may_never_name_the_operation`, `test_a_thought_refuses_a_proposal_whose_parameters_name_the_operation` |
| NP-6 | T1 authored `low` for `write` (classified `moderate`) | `test_rule_1_no_entry_is_authored_below_action_engines_classification` |
| NP-7 | The CAS replaced by `move_layer` | real-infra `test_v7b_concurrent_promotions_of_one_thought_trigger_exactly_once` |
| NP-8 | Insert-if-absent replaced by `upsert_thought` | 16 unit tests; real-infra `test_a_repeat_after_promotion_neither_resets_nor_repromotes`, `test_an_observation_over_the_real_bus_becomes_one_thought_and_one_real_request` |
| NP-9 | Promote on every observation | `test_a_repeated_observation_writes_nothing_and_triggers_nothing`, `test_a_duplicate_of_a_thought_still_at_active_is_not_promoted`; real-infra `test_a_repeat_after_promotion_neither_resets_nor_repromotes` |
| NP-10 | A persisted `triggered` column (in `0002`) | real-infra `test_0002_adds_exactly_one_nullable_jsonb_column` |
| NP-11 | `perception.workspace.observed` added to `PUBLIC_TOPICS` | `test_p13_public_topics_are_unchanged_at_eighteen`, `test_control_7_public_topics_is_unchanged_at_its_eighteen_exact_strings` |
| NP-12 | One line appended to an `action-engine` file | V-10's diff check: `git diff --stat 9d2d636 -- services/action-engine services/capability-engine` goes from empty to *"1 file changed"*, and is empty again after the restore |
| NP-13 | T1's `parameters` carry the label | `test_the_label_reaches_the_title_and_never_the_parameters`, `test_author_produces_the_complete_proposal` |
| NP-14 | `promote_thought` called from `api/` | `test_p14_nothing_on_the_served_path_writes_a_thought_or_promotes[api/cognitive_state.py]`, `test_p14_promote_thought_has_exactly_one_production_caller` |

**The P8 guards (G1 … G14).** All were run in this session, and all 14 are caught:

| Guards | Mutation | Caught by |
|---|---|---|
| G1 … G11 | Re-run with the scratchpad driver | The guard each one targets |
| G12 | T1's operation changed | `test_t1_is_the_ratified_authoring_entry` |
| G13 | An extra tapped subject | `test_v9_the_only_tapped_subjects_are_the_path_and_the_replies` |
| G14 | A thirteenth `ActionStage` | `test_the_twelve_stages_are_action_engines` |

G1 … G11 cover:

- the user unset;
- a second workspace;
- `perception-engine` started with the golden path;
- the workspace provisioned late;
- the proof made non-failing;
- the driver publishing;
- the driver writing SQL;
- the driver importing an engine;
- namespace drift;
- outcome-table drift;
- an executing route.

**The P8 composed-stack controls.** They were run at P8's time, earlier in this session, and their logs are kept. Each made the real driver fail:

| Control | Mutation | Failing checks |
|---|---|---|
| NC-1 | `autonomy-engine` sends `parameters={}` | 30 |
| NC-2 | `completed` mapped to `execution_failed` | 2 |
| NC-3a | A stand-in answers `action.execute` beside the real `action-engine` | 14 |
| NC-3b | A stand-in replaces it, claiming its name and listing the real workspace | 26 |
| NC-4 | The producer drops the pair | 40 |
| NC-5 | Thought identity from the event | 3 |

**Per-slice controls recorded at the time**, in the commit messages:

- P4: 13 mutations (`56cdee8`);
- P7: 12 (`a0b9b4f`).

They are not re-run individually here. NP-1 … NP-5 re-exercise the same properties.

### 5.2 Flakiness (≥ 10 runs)

| Tests | Runs, in this session | Result |
|---|---|---|
| `cognitive-state-engine -m real_infra` (57) | 10 | **10/10 green** |
| `autonomy-engine -m real_infra` (63) | 10 | **10/10 green** |
| The composed P8 proof | 4: 1 cold from an empty database + 3 warm | **4/4: 67/67 checks** |
| The composed P8 proof, at P8's time | 26 logged runs | **26/26 passed**: 1 at 59 checks, 11 at 61, 14 at 67 (the final driver), 2 of them cold. This corrects `d1ae981`'s message (§7.1) |

Every wait in the driver is bounded and polls a condition. None is a sleep that paces the proof.

---

## 6. Category 10 — real infrastructure

1. **Docker: NOT available.** `docker info` fails with *"failed to connect to the docker API at unix:///var/run/docker.sock … no such file or directory"*.
2. **What ran instead, disclosed as such.** PostgreSQL **16.13** (a throwaway cluster), `nats-server` **v2.10.7** (JetStream for the test tier) and Redis **7.0.15**.
   - **For the `real_infra` tiers:** a scratchpad-only pytest plugin, never committed, pointed `nova-testkit`'s container fixtures at them, with a fresh database per run.
   - **For the composed proof:** a scratchpad-only script ran the stack's engines from this tree as processes, with compose's environment, and the real `nova-companion` binary built from `companion/`.
   - **The local differences:**
     - processes rather than containers;
     - the workspace is a host path rather than the `/workspace` mount;
     - `world-model-engine` uses `GRAPH_STORE_BACKEND=in_memory`. Its context RPC, the one stage 3 calls, is Redis-backed either way;
     - there is no otel-collector.
   - **This is not the CI environment.** CI's containers remain authoritative.
3. **Results, local, at the implementation SHA, in this session:**

   | Package | `-m real_infra` |
   |---|---|
   | `cognitive-state-engine` | **57 passed** |
   | `autonomy-engine` | **63 passed** |
   | `perception-engine` | **22 passed** |
   | `action-engine` | **27 passed** |
   | `capability-engine` | **6 passed** |

4. **The tests 4F.P added or changed, by name.**
   - **`cognitive-state-engine`, new.** `test_ingestion_real_postgres.py` (12):
     - `test_the_first_insert_creates_the_row_and_a_repeat_writes_nothing`
     - `test_the_inserted_row_holds_every_ratified_field`
     - `test_concurrent_inserts_of_one_identity_create_exactly_one_row`
     - `test_the_compare_and_set_moves_only_from_the_expected_layer`
     - `test_a_compare_and_set_on_a_missing_thought_returns_nothing`
     - `test_concurrent_compare_and_sets_have_exactly_one_winner`
     - `test_v7b_concurrent_promotions_of_one_thought_trigger_exactly_once`
     - `test_v7b_negative_control_an_unconditional_move_triggers_every_racer`
     - `test_concurrent_ingestions_of_one_object_create_one_thought_and_one_trigger`
     - `test_a_repeat_after_promotion_neither_resets_nor_repromotes`
     - `test_an_observation_over_the_real_bus_becomes_one_thought_and_one_real_request`
     - `test_a_persisted_t1_proposal_crosses_the_real_bus_with_its_authored_execution_fields`
   - **`cognitive-state-engine`, changed.** Their data or exclusions changed, and every test name is kept:
     - `test_decision_trigger_real_nats.py` (9): the authored pair, verbatim;
     - `test_cognitive_state_api_real_infra.py` (4): `_NOT_SERVED`;
     - `test_proposed_action_real_postgres.py` (7): the pair in the test data.
   - **`cognitive-state-engine`, unchanged:** `test_repository_real_postgres.py` (12) and `test_sensor_state_real_infra.py` (13).
   - **`autonomy-engine`, new.** In `test_decision_trigger_real_infra.py`:
     - P4:
       - `test_p4_t1_leaves_on_the_existing_dispatch_point_as_operation_list`
       - `test_p4_authored_parameters_are_flattened_beside_the_operation_on_the_wire`
       - `test_p4_a_trigger_without_the_pair_stays_a_suggestion_on_the_real_path`
       - `test_p4_parameters_naming_the_operation_are_rejected_on_the_real_bus`
     - P7:
       - `test_p7_completed_is_recorded_as_execute_only_after_the_reply`
       - `test_p7_denied_is_recorded_as_a_proposal_with_its_suggestion`
       - `test_p7_failed_and_rolled_back_are_recorded_as_execution_failed`
       - `test_p7_a_non_terminal_reply_is_recorded_as_execution_failed`
       - `test_p7_no_reply_within_the_bound_is_recorded_as_timeout`
       - `test_p7_no_responder_is_recorded_as_a_proposal_never_a_timeout`
       - `test_p7_a_transport_fault_before_any_reply_records_nothing`
       - `test_p7_t1_still_leaves_as_operation_list_whatever_the_reply`
   - **`autonomy-engine`, the rest of that file:** the 4F.6 tests, now carrying T1's pair, for 33 items in all. `test_level_two_real_postgres.py` (14) gains the pair. `test_repository_real_postgres.py` (16) is unchanged.
5. **What each covers.**
   - **Every `cognitive-state-engine` and `autonomy-engine` real-infra test exercises changed code**: through the lifespan (the new subscription), the trigger payload, `decide()` and the dispatch, or the outcome mapping.
   - **`perception-engine`, `action-engine` and `capability-engine` code is unchanged.** Their tiers ran because they are the P8 path's engines.
6. **Matrix.** All five packages have rows in `.github/workflows/real-infra-checks.yml`, which lists 15 package jobs. 4F.P did not change that workflow.
7. **Per-engine stand-ins** are named here, as C-14 requires. Each is RS-8 test infrastructure and counts toward no composed V-item:

   | Stand-in | Where | Labelled |
   |---|---|---|
   | The `action.execute` responder, replying with the real `ActionResultPayload` contract | `autonomy-engine`'s P4/P7 and 4F.6 real-infra tests | In the module docstring |
   | The silent responder | V-8 (b) | Yes |
   | The `autonomy.decision.requested` responder | `cognitive-state-engine`'s `test_ingestion_real_postgres.py` and `test_decision_trigger_real_nats.py` | Yes |

   **The composed path has none** (§1.1, link Q).
8. **Unverified.** *These 175 real-infra tests (57 + 63 + 22 + 27 + 6) and the composed P8 proof have not been executed in CI's containers for this change. `Real-Infrastructure Checks` is non-blocking. The e2e job is staged and non-blocking. Neither has reported against `d1ae981`, because neither has run on this branch (§7.2).*

---

## 7. Category 11 — PR, branch, commit and CI evidence

### 7.1 Branch and commits

**Branch:** `phase-4fp`. Re-verified in this session:

- its HEAD before this record is `d1ae981`, equal to `origin/phase-4fp`;
- the tree is clean;
- `9d2d636` is an ancestor;
- nothing on it is merged into `phase-4` or `main`.

| Commit | Content |
|---|---|
| `fbce0ff`, `58181f5`, `7140d30`, `fc20827`, `2b92682` | The TDD, its audit, its ratification and the cross-TDD notes (docs only, from `phase-4p-tdd`) |
| `c0c47f9` | P1, P2, P3, P5 and P6, in `cognitive-state-engine` |
| `8b22cf9` | The merge of the TDD history (§0.1) |
| `8bf7d37` | Documentation status sync |
| `56cdee8` | P4: `nova-contracts`, `cognitive-state-engine`, `autonomy-engine` |
| `a0b9b4f` | P7: `autonomy-engine` |
| `d1ae981` | P8: compose, CI, driver, guards, `.gitignore`, docs. 12 files, +1894/−1. **The implementation SHA** |
| (next) | This record, and the documentation in §9 |

**Commit messages, checked against the diffs and the runs.**

- **`d1ae981`'s *"26 consecutive driver runs passed (12 at 61 checks, 14 at the final 67 …)"* is wrong by one.** The 26 logged runs are 1 at 59 checks (the first), 11 at 61 and 14 at 67. The total of 26, the 14 at 67 and the two cold runs are correct. The same figure appears in TDD 4F.P §30.10's 2026-10-04 note. A dated correction note follows it there (§9), and this paragraph corrects the commit message, which cannot be rewritten.
- **`c0c47f9`'s message and every status note list the slices as *"P1, P3, P5 and P6"* / *"P1, P3 … P8"*.** They omit P2's number, although the same message describes P2's content (A-4FP-2, A-4FP-10). See F-4FP-3.
- **No other factual claim was found to be false.**

### 7.2 CI

**No CI run exists for this branch, and no local result is reported as CI evidence.** These were queried through the GitHub API in this session:

- `actions/runs?branch=phase-4fp` → **0** workflow runs;
- `commits/d1ae981…/check-runs` → **0** check runs;
- `pulls?head=Tudor191:phase-4fp` → **0** PRs.

**Why the Docker e2e job has not run:**

| Workflow | Triggers on `phase-4fp`'s copy | Can it run for this branch without a PR? |
|---|---|---|
| `PR Checks`, which carries the e2e job and the P8 proof | `pull_request`; `push` to `main`; `workflow_dispatch` | **No.** `main`'s copy of `pr-checks.yml` has no `workflow_dispatch` (`grep -c` → 0), and GitHub dispatches a workflow only when its default-branch definition declares the trigger. A push to `main` is excluded |
| `Build & Scan`, which runs Trivy on the rebuilt `cognitive-state-engine` and `autonomy-engine` images | `pull_request`; `push` to `main` | **No** |
| `Real-Infrastructure Checks` | `pull_request`; `push` to `main`; nightly `schedule`; `workflow_dispatch` | Dispatchable, because `main`'s copy declares it. **It does not carry the e2e job** |

**The outstanding acceptance step.** The P8 proof's first run in containers needs a PR from `phase-4fp`. When it runs, its conclusion must be read **from the e2e job itself**. That job is *"staged, non-blocking"*, so a green PR status does not imply it passed. The P8 step has no `continue-on-error`, so its failure fails that job. The conclusions of all three workflows at the exact head SHA are then to be added to this record, additively, as 4F.7's record did.

**Known CI risk** (F-4FP-6): the existing `perception-engine` flake can redden `PR Checks` spuriously.

### 7.3 Boundary audit (`git diff --name-only 9d2d636 HEAD`, plus this record's commit)

| Area | Files | A-4FP-13 |
|---|---|---|
| `services/cognitive-state-engine` | src 10 (`domain/authoring.py`, `domain/ingestion.py` and `ingestion_orchestration.py` new), tests 14, README | **Covered by the exception** |
| `services/autonomy-engine` | src 3, tests 5, README | **Covered by the exception** |
| `packages/nova-contracts` | src 1, tests 1, TypeScript 1 | **Covered by the exception** |
| `infra/docker` | `docker-compose.local.yml`, `README.md` | **Covered by the exception** |
| `.github/workflows/pr-checks.yml` | The e2e job's P8 steps | Recorded, not governed |
| `tools/` | `e2e_real_execution.py`, `tests/test_e2e_real_execution.py` | Recorded, not governed |
| `.gitignore` | +5: `infra/docker/workspace/`, compose's default bind directory | **Not named by A-4FP-13.** A root configuration file, disclosed here. It carries no code |
| `services/perception-engine/README.md` | A documentation note (§9) | Documentation only. No `src/` change |
| `docs/` | `design/phase-4` (TDD notes), `architecture` 07/09/10/14, this record | Documentation |
| **Unchanged** | See §3.1's list | — |

**SAD 15 §4 items 2–5 stay mandatory** (A-4FP-13):

- **Item 3** (contract and codegen in the same change) is met by `56cdee8`.
- **Item 4**'s OpenAPI review is §4.
- **Items 2 and 5** are per-PR obligations. They apply when the PR is opened.

**No change-scope linter was created.**

### 7.4 SLOC

The method is the 4E methodology: `cloc` **v2.06** `--skip-uniqueness --quiet` over a pristine `git archive`, with tests excluded.

| Scope | `9d2d636` | `d1ae981` | Δ |
|---|---|---|---|
| Comparable (`services/*/src`, `packages/*/src`, `services/*/alembic/versions`) | 37,413 | 37,797 | +384 |
| Wider | 42,754 | 43,138 | +384 |
| Full | 46,787 | 47,171 | +384 |
| **4F scope (+ `companion/`, excluding its `tests/`: 646)** | **47,433** | **47,817** | **+384** |

- **The base reproduces 4F.7's recorded head exactly**, and TDD 4F.P §23's base of 47,433. The `companion/` figure excludes `companion/*/tests` (398). That is how the series' 47,433 reconciles, since the companion is unchanged.
- The +384 is inside §23's estimate of 260–520. The harness, compose and tests count **0**.
- **Headroom to 50,000: 2,183. The gate is not crossed.**

---

## 8. Category 13 — findings, gaps and decisions requiring approval

### 8.1 Findings: OPEN, each with a recommendation. None is silently fixed

**F-4FP-1. V-6 (b) is evidenced as two halves, not as C-14's single test.**

- **What C-14 describes.** The test authors a `negligible` `filesystem`/`read` of a missing file, inserts the thought and calls `promote_thought`. The **real adapter** fails, `action.status = failed`, and the log row is `execution_failed`.
- **What was built.** `autonomy-engine` maps a stand-in's `failed` reply to `execution_failed`, and `action-engine`'s own unit test reaches `failed` on an execution failure.
- **Why C-14's version is not possible as written.** A per-engine test cannot hold the real `action-engine` (control 7). The composed driver may not author a non-T1 proposal (V-9; A-4FP-3, *"adding an entry is a new ratification"*).
- **Documents.** TDD 4F.P §15 V-6 (b); §28.4 C-14 (*"per-engine `real_infra`"*, stand-ins *"permitted"*); §30.2 A-4FP-12. **C-14 is silent on how a per-engine test reads `action.action.status`.**
- **Options:**
  - **(a)** Ratify the halves as V-6 (b)'s evidence. This is 4F.6's precedent, and V-7 (c) is evidenced the same way.
  - **(b)** Add a composed run, with a test-only authoring path. That needs a ratification, and weakens V-9.
  - **(c)** Defer V-6 (b)'s composed form to 4F.8.
- **Recommendation: (a).**
- **Blocks 4F.P's completion until decided.** It blocks nothing else.

**F-4FP-2. The outcome vocabulary has six members.**

- The P7 instruction said *"exactly the ratified five members"*. A-4FP-7 (§30.2) adds `EXECUTION_FAILED` to the five that existed (`observe_only`, `propose`, `deny`, `execute`, `timeout`). §28.5 lists six.
- Six were built, and the discrepancy was reported in the P7 report. No later instruction changed it.
- **Options:** keep six, as ratified, or reduce to five, which would contradict A-4FP-7.
- **Recommendation: confirm six.**
- **Blocks:** no, because the ratified text governs. Confirmation is requested.

**F-4FP-3. Every phase-4fp status note omits P2's number.**

- They list *"P1, P3, P5 and P6"* … *"P1, P3 … P8"*. P2 is implemented in `c0c47f9`, whose message names A-4FP-2 and A-4FP-10.
- This record states P1 … P8 (§1, §3.1). L-24 carries a dated clarification of the other notes.
- **Recommendation: L-24, at the 4F closure sweep.**
- **Blocks:** no.

**F-4FP-4. The driver's V-6 (a) check does not assert the `identity_confidence_denied` error string.**

- It asserts `denied`, `propose`, the reason prefix and the zero invocation delta. The string is in the printed evidence (§1.2).
- It was **not changed**, per this verification's instruction: *"Do not modify the denial implementation unless a regression is proven"*.
- **Recommendation:** add one condition in a later, separately approved change.
- **Blocks:** no.

**F-4FP-5. P8 made a compose comment false.**

- In `docker-compose.local.yml`, the `agent-os-kernel` block (`19b33b6`, 4C.1) says *"no service in this file sets a primary user id"*. P8 sets `PERCEPTION_ENGINE_PRIMARY_USER_ID`.
- **Recommendation:** an additive comment note (L-25).
- **Blocks:** no.

**F-4FP-6. A `perception-engine` flake that predates 4F.P.**

- The tests are `test_s4_the_raw_path_is_absent_from_the_outbox_payload` (`d9d922f`, 4F.3) and `test_the_enqueued_payload_carries_the_hash_and_never_the_path` (`cc0dcad`, 4F.2).
- They assert that the substring `"ada"`, a path segment, is absent from a payload that also holds random hexadecimal UUIDs and a SHA-256. `a` and `d` are hex digits, so a random id containing `ada` fails the test.
- It was seen once during P8 and passed on re-run. **4F.P does not touch `perception-engine`.**
- **Recommendation:** use a segment that cannot be hex, in a perception-owned change.
- **Blocks:** no. It **can redden CI**; read failures by name.

**F-4FP-7. A carried-forward finding from P4.**

- `cognitive-state-engine`'s `test_detail_is_the_only_optional_field` is unchanged. It is still true for `ProposedAction`.
- **Recommendation:** keep it, as P4 recorded.
- **Blocks:** no.

**F-4FP-8. The `cognitive-state-engine` README's "Owned APIs" omits 4F.7's three `GET` routes.** This predates 4F.P (4F.7).

- **Recommendation:** fold into L-9.
- **Blocks:** no.

**F-4FP-9. `autonomy-engine`'s README is still the scaffold** (the 4F.6 ledger row).

- It now carries a 4F.P note (§9).
- **Recommendation:** as 4F.6 recorded.
- **Blocks:** no.

**F-4FP-10. The web client's `decisionResultSchema` enumerates four outcomes.** It lacks `timeout` (4F.5) and `execution_failed`.

- The only route that uses it produces `propose`/`deny`, so nothing breaks (§4).
- **Recommendation:** widen it at 4F closure, or document why not.
- **Blocks:** no.

### 8.2 CF-9, CF-10 and CF-11: all OPEN

TDD 4F.P §30.7 stands:

- **CF-9:** the composed run is the first real stage-3 pass. It settles at 4F closure.
- **CF-10:** nothing. Trust stays `UNAVAILABLE`.
- **CF-11:** 4F.P evidences the production mechanism. **Claim 3 is 4F.8's** and **claim 4 is 4F closure's.**

### 8.3 Deferred, and not implemented here

TDD 4F.P §30.8 stands unchanged. This includes:

- AC-7 and AC-8 (4F.8);
- TTL and stale-trigger semantics (A-4F6-4);
- lost-trigger auditability (the FP-7 and FP-15 windows);
- `observability.py` packaging;
- automatic demotion;
- K-5;
- further ingestion sources and authoring entries, each a new ratification;
- FP-8, FP-13 and FP-18;
- A-4FP-14 (b).

**None was implemented as a side effect.** No retry, scheduler, TTL, outbox, route or subject was added.

### 8.4 Obligations outside this slice

| Obligation | Status |
|---|---|
| TDD 4F.P §22 step 4 / §30.6 item 2: TDD 4F.8's re-verification | **After 4F.P is merged** (L-26) |
| §30.6 item 3: the FP-24 ledger row, TDD 4D §4.3's *"exactly four outcomes"* (now six) | **L-23** |

---

## 9. Category 14 — documentation updated by this slice

| Trigger (§14.1) | Document | Change | Additive? |
|---|---|---|---|
| Changed event payload; new subscription | `docs/architecture/09-event-bus-architecture.md` §4 | Dated note: `perception.workspace.observed`'s second consumer; the two optional fields on `autonomy.decision.requested`; 120/18 | **Yes** (before: nothing at that point) |
| Same | `10-inter-engine-communication.md` §2 | Dated note: the path, built end to end; ADR-004 holds | **Yes** |
| Stored data (no migration) | `07-database-architecture.md` §1 | Dated note: the two JSONB keys, the two new statements, `execution_failed` | **Yes** |
| Deployment surface | `14-deployment-architecture.md` §2 | Dated note: the `nova-companion` service, one workspace, one user, the e2e job | **Yes** |
| | `infra/docker/README.md` | Dated P8 paragraph (in `d1ae981`) | **Yes** |
| Publisher README | `services/cognitive-state-engine/README.md` | *Status update — 4F.P*. The 4F.6/4F.7 statements it supersedes are kept and named. A note on the second Subscribe entry and the Request payload | **Yes** |
| Subscriber README | `services/autonomy-engine/README.md` | Note: the pair on the wire; the outcome mapping | **Yes** |
| Producer README | `services/perception-engine/README.md` | Note: the second consumer; the stack's user | **Yes** |
| Design documents | TDD 4F.P, 4F, 4F.5, 4F.6, 4F.7; master scope | Dated per-slice status notes (P1 … P8 commits). In this commit: one 2026-10-05 note each in TDD 4F.P §30.10 and §22, and in master scope §5 and §17 | **Yes** |

**Before/after.** Every change is an inserted, dated note at the place named. No existing sentence was edited. The *before* at each location is the unchanged surrounding text, and the *after* is that text plus the note (see this commit's diff).

**Inspected and found accurate, or N/A:**

- **`11-api-architecture.md`:** it does not document `POST /v1/autonomy/suggestions/{id}/decide`'s response schema. The enum widening is reviewed in §4. No change needed.
- **`17-cicd-pipeline.md`:** it describes `pr-checks.yml` at file level only (*"lint, unit, contract, integration"*), and not the e2e job's steps. No gate was added. No change needed. The same holds for `15-development-workflow.md` §4.
- **`20-engine-responsibility-boundaries.md`:** it does not mention `cognitive-state-engine`. Ownership is unchanged: thoughts are `cognitive-state-engine`'s, observations `perception-engine`'s, execution `action-engine`'s. It is covered by L-20 (4F.7).
- **`companion/nova-companion/README.md`:** it already describes the internal Docker network. No change needed.
- **`02-repository-and-folder-structure.md`, workspace globs, `[tool.importlinter]`:** N/A. There is no new package or engine.
- **`16-testing-strategy.md`, ADR-033:** N/A. There is no new tier or marker.
- **The observability docs:** N/A. No metric was added. P8 reads the existing `capability_invocation_total`.
- **`build-and-scan.yml`:** the `nova-companion` image is already in its matrix (line 116), and its Dockerfile is unchanged since `d9d922f`.

**SAD 15 §9.1:** no new subsystem is introduced. For the new surfaces:

| Item | Status |
|---|---|
| Architecture documentation | Present: the TDD and the notes above |
| Sequence | Present: TDD §5, and doc 10's note |
| Unit and integration tests | Present |
| Failure scenarios | Present: V-6 … V-8; FP-15 |
| Logging | Present: the handler's and the orchestration's decision points |
| Performance benchmarks | **None.** None was ratified. SD-6 discloses up to 20 s per promoted observation |
| Observability metrics | **None added** |

---

## 10. Deferred-obligations ledger (protocol §0.2)

### 10.1 Settled by this slice

**None.**

### 10.2 Still open

**L-1 … L-6, L-8 … L-11 and L-13 … L-22** are carried forward **unchanged**, as the 4F.7 record §10 left them. L-9 and L-10 inherit F-4FP-8 and F-4FP-10 as inputs.

### 10.3 Opened by this slice

| Row | Status | Obligation | Owner | Blocks 4F.P? |
|---|---|---|---|---|
| **L-23** | OPEN | TDD 4D §4.3's *"exactly four outcomes"* is stale. The vocabulary is now six (FP-24; §30.6 item 3) | 4F closure (L-9 sweep) | No |
| **L-24** | OPEN | A dated clarification of every status note on this branch, covering two points. First, they omit P2's number (F-4FP-3). Second, *"P9's Slice Completion Record does not exist"* is superseded by this record, in the notes not given a 2026-10-05 note here: TDD 4F.P's header, §27, §28 and §30.6 notes, and TDDs 4F, 4F.5, 4F.6 and 4F.7 | 4F closure | No |
| **L-25** | OPEN | The compose comment that P8 made false (F-4FP-5) | 4F closure, or the PR | No |
| **L-26** | OPEN | TDD 4F.8's re-verification against merged 4F.P (§22 step 4; §30.9) | 4F.8, after merge | No |
| **L-27** | OPEN | Project Health, roadmap and top-level README status for 4F.P (categories 4, 5 and 7). `ENGINEERING_ROADMAP.md` has no 4F.P entry | 4F closure | No |

---

## 11. Final status

- **Implementation:** P1 … P8 complete against TDD 4F.P §30, as ratified.
- **P9:** controls (§5), documentation (§9) and this record. Done locally.
- **Local verification:** complete, with real numbers (§5, §6).
- **The exit criterion:** proven locally on the composed stack, with no stand-in (§1.1). The denial control is proven separately (§1.2).
- **Negative controls:** caught in every case.
  - NP-1 … NP-14: 14/14;
  - P8 guards: 14/14;
  - composed controls: 6/6, at P8's time.
- **Flakiness:** real-infra 20/20; composed 4/4 in this session and 26/26 at P8's time.
- **Real infrastructure:** substitute local services. **Docker is unavailable.**
- **CI: no run exists for this branch.** The e2e job, which carries the P8 proof, can run only for a PR (§7.2).
- **For decision:** F-4FP-1 (V-6 (b)) and F-4FP-2 (six outcomes).
- **CF-9, CF-10, CF-11:** OPEN.
- **Gate verdict:** none. This is a slice (§0).
- **`main` and `phase-4`:** untouched. **No PR. Nothing merged.**
- **4F.P is NOT complete.** It stays incomplete until four things hold:
  - CI's conclusions at the exact head SHA are recorded here, with the e2e job's P8 step green in containers;
  - F-4FP-1 is decided;
  - the PR is reviewed;
  - the merge is authorized.
- **Completing 4F.P does not authorize starting 4F.8.**

### 11.1 What was not verified, and why

- **The P8 proof in the e2e job's containers.** No Docker daemon here, and no CI run on this branch (§7.2).
- **The real-infra tiers in CI's containers.** They were executed only on local substitute binaries.
- **Image builds and Trivy** for the changed `cognitive-state-engine` and `autonomy-engine` images. CI-only.
- **V-6 (b) as one test with the real adapter.** It is not possible under control 7 and V-9 as written (F-4FP-1).
- **SAD 15 §4 items 2 and 5.** Per-PR, and no PR exists.
