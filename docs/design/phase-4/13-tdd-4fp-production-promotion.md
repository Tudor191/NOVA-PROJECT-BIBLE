# TDD 4F.P — The production promotion slice
## From a real observation to a real, truthfully recorded execution

**Status: PREPARED 2026-09-27. NOT RATIFIED. NOT implementation-ready.**

- **What this is.** The implementation contract for **4F.P**, the slice RS-1c
  added **before 4F.8** (TDD 4F §18, as amended by §24). It defines NOVA's
  first production initiative path, end to end:

  ```
  ActiveThought → ProposedAction → promotion → autonomy decision →
  action.execute → action-engine → real execution result → decision/audit outcome
  ```

- **Why it is now load-bearing.** Preparing 4F.8's TDD found that **a real
  Level-2 action cannot execute on today's production path**. That finding is
  **authoritative** (user direction, 2026-09-27) and is restated in §3.
  - `autonomy-engine` sends `action.execute` with **`parameters={}`**.
  - `action-engine` rejects any request without **`parameters["operation"]`**.
  - 4F.5's and 4F.6's real-infrastructure evidence used an **`action-engine`
    stand-in**, so it never tested this boundary.
  - `autonomy-engine` records **`EXECUTE` whatever `action-engine` replies.**

  This document resolves the incompatibility. It does not work around it.
- **Blocking before implementation.** Thirteen decisions, **A-4FP-1 …
  A-4FP-13** (§8), must be ratified first. **A-4FP-14** has a recommended
  default and does not block.
  - Each candidate that would **change an existing ratification** names that
    decision, the proposed change, the reason, the affected components and
    criteria, and whether implementation must wait. **No existing ratified
    contract is changed silently.**
  - A-4FP-4, -5, -6 and -7 **determine A-4F8-3**, which is proposed in 4F.8's
    TDD and not ratified there. **A-4F8-3 is not ratified here either** (§9).
- **Order.** **4F.P → 4F.8 → 4F closure → the Phase 4 Gate Review** (§20). 4F.8
  must not start before 4F.P is ratified, implemented and merged.
- **No implementation exists.** This document was prepared on the documentation
  branch `phase-4p-tdd`. No 4F.P or 4F.8 implementation branch exists, and no
  production file, test, migration, Dockerfile, workflow, contract or package
  was modified to prepare it.
- **CF-9, CF-10 and CF-11 stay OPEN.** 4F.P closes none of them (§18).

| | |
|---|---|
| **Date** | 2026-09-27 |
| **Prepared against** | `phase-4` = **`9d2d63613fabf98c85dcdfa7c5a90fba4233baff`** (the merge of PR #38, 4F.7). `main` = **`7e273e62e942ecd5528ca807e65933d6bb675669`**. Every repository fact below was read at this tree |
| **Protocol** | [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md), sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`, 1131 lines, read from `origin/main`; byte-identical on `phase-4` |
| **Subordinate to** | [TDD 4F](06-tdd-4f-companion-and-cognitive-state.md), especially §6, §6.2, §10, §11, §13, §14, §16, §18 as amended, and §24 (RS-1 … RS-11). Also [TDD 4F.5](09-tdd-4f5-autonomy-level-2.md) §22, [TDD 4F.6](10-tdd-4f6-initiative-trigger.md) §4.7, §5, §9.1, §15, §16 and §19, and [TDD 4F.7](11-tdd-4f7-cognitive-state-panel.md) §28. **Where this document and TDD 4F disagree, TDD 4F governs**, and the disagreement belongs in §8 |
| **Related, not yet on `phase-4`** | TDD 4F.8, `docs/design/phase-4/12-tdd-4f8-acceptance-verification.md`, **PREPARED and NOT RATIFIED**, on the documentation branch **`phase-4f8-tdd` at `5a95475`**. It is cited here by branch and commit, because it is not on this branch's base |
| **Bible** | [Part 6](../../bible/part-06-nova-cognitive-state-engine.md) (Active Thoughts, Attention Layers); [Part 12](../../bible/part-12-action-engine.md) (the Action Principle lifecycle); [Part 14](../../bible/part-14-autonomy-engine.md) l.101–107 (*"Level 2 · Assisted. Low risk actions execute automatically."*) |

---

## 0. How to read this document

- **§1–§2:** the exact scope and non-goals.
- **§3:** the incompatibility, restated from source.
- **§4:** the verified baseline.
- **§5:** the production execution flow, step by step.
- **§6:** the reconciliation of the twenty subjects this preparation was asked
  to cover.
- **§7:** the findings this preparation made.
- **§8:** the ratification candidates. **Nothing in §8 is decided.**
- **§9:** A-4F8-3, specifically.
- **§10–§16:** the contract:
  - §10: `ProposedAction`;
  - §11: operation and parameters;
  - §12: result semantics;
  - §13: duplicate and CAS semantics;
  - §14: persistence, subjects and API;
  - §15: how real execution evidence is collected;
  - §16: negative controls.
- **§17–§21:** classification, carry-forwards, 4F.8's blocked decisions, the
  dependency chain, and what stays deferred.
- **§22–§25:** SLOC, risks, SAD 15 §9.0, and the consistency audit.
- **Wherever a section rests on a §8 candidate,** it states what holds under the
  recommended option. If the user ratifies a different option, that section is
  amended additively before implementation.

---

## 1. Exact 4F.P scope

**RS-1c, ratified:**

> *"The production promotion driver, thought ingestion and `ProposedAction`
> authorship belong to a **new implementation slice inside milestone 4F, before
> 4F.8**. … **Its future TDD must explicitly ratify:** the promotion policy; the
> thought-ingestion mapping; the `ProposedAction` authorship rule; the CAS
> transition semantics; Layer 2 logical deduplication."*

To those five, the real-execution incompatibility adds what makes the path
**honest end to end**: the operation and its parameters, and the recording of
what actually happened.

| # | Deliverable | Owner | Decided by |
|---|---|---|---|
| **P1** | **Thought ingestion**: `cognitive-state-engine` subscribes to one **existing** subject and maps each accepted input to an Active Thought, idempotently | `cognitive-state-engine` | **A-4FP-1** |
| **P2** | **The promotion policy and its production driver**: which thoughts are promoted, when, and by what. **The first production caller of `promote_thought`** (4F.6 finding F-6) | `cognitive-state-engine` | **A-4FP-2**, **A-4FP-10** |
| **P3** | **The `ProposedAction` authorship rule**: a closed, ratified authoring table. Every field, **including the operation and its parameters**, is authored from it, never derived | `cognitive-state-engine` | **A-4FP-3**, **A-4FP-4**, **A-4FP-5** |
| **P4** | **Propagation**: the operation and its parameters travel from the thought through the trigger and `DecisionRequest` into `action.execute`'s `parameters`, which is where `action-engine` requires them | `nova-contracts`, `cognitive-state-engine`, `autonomy-engine` | **A-4FP-6** |
| **P5** | **CAS on the promotion transition**, so one promotion fires at most one trigger | `cognitive-state-engine` | **A-4FP-8** |
| **P6** | **Duplicate-trigger handling** (Layer 2): at most one initiative per ingested input | `cognitive-state-engine` | **A-4FP-9** |
| **P7** | **Real result handling**: `autonomy-engine` records the outcome `action-engine` actually reports. **`EXECUTE` means completed, and nothing less** | `autonomy-engine` | **A-4FP-7** |
| **P8** | **Real-execution evidence**: the composed production path proven against the real `action-engine` and `capability-engine`, never a stand-in, read back by independent SQL (§15) | tests, `tools/`, the e2e job | **A-4FP-11**, **A-4FP-12**, **A-4FP-13** |
| **P9** | **Controls, documentation and the 4F.P Slice Completion Record.** The record is not a Gate Review | — | — |

**The slice's exit criterion.** A real input produces an Active Thought
carrying a complete, authored `ProposedAction` in production, and that
thought's promotion causes a real execution.

- The real `action-engine` receives the intended operation and parameters, and
  executes the action through a real capability.
- `autonomy-engine` records the outcome `action-engine` actually reported.
- Each failure mode is recorded truthfully: a denial, a failure, a timeout, an
  unavailable executor or a transport fault.
- **4F.P does not claim AC-8.** AC-8's Level-1/Level-2 acceptance run, in a
  browser, is **4F.8's** (§20).

---

## 2. Non-goals

| Excluded | Why |
|---|---|
| **AC-7's and AC-8's acceptance runs**: the latency measurement, revocation, the Level-1/Level-2 comparison and the browser specs | 4F.8 (TDD 4F §18; TDD 4F.8) |
| Revocation detection (RS-3b) and known-project correlation (L-13) | 4F.8's A-4F8-1 and A-4F8-2. **4F.P's ingestion does not require a `project_id`** (A-4FP-1) |
| **Any change to `action-engine`**: its twelve stages, the `operation` requirement, risk classification, stage 3, the approval loop, `ActionStatus` or `ActionResultPayload` | TDD 4F §7.3; TDD 4F.4 W-6; TDD 4F.5 §18. **The fix is on the producing side** (§3) |
| Any change to `capability-engine` | Its built-in adapters are used as they are |
| **A new Event Bus subject**; any `PUBLIC_TOPICS` change; any gateway prefix or route | TDD 4F §11.4, §16.1 control 2; RS-5. 4F.P uses **existing** subjects (§14) |
| A write route under `/v1/cognitive-state` | RS-1b. **Ingestion is Event Bus–driven**, and the read surface stays `GET`-only |
| Exposing the operation and parameters on the read surface or in the panel | A-4FP-14 (default: no change) |
| A per-thought triggered state, enum, column or persisted trigger outcome | RS-6a |
| A trigger TTL, stale-trigger semantics, a trigger retry, an outbox for the trigger, or persistent lost-trigger audit | RS-7; TDD 4F.6 §16 (OPEN or DEFERRED) |
| **Executing an approved Level-1 suggestion** | `POST /v1/autonomy/suggestions/{id}/decide` executes nothing by 4D's design (`api/autonomy.py` l.413–432). Not in 4F.P's ratified scope (§7, FP-8) |
| Additional ingestion sources, or model-based (LLM) authoring | Not ratified. A-4FP-1 and A-4FP-3 admit exactly one of each |
| Automatic demotion, and Part 6 INTERRUPTIONS semantics | Deferred (§21) |
| Focus-signal computation | OPEN (K-5) |
| `TrustMetric`; CF-10; Levels 3–5 | TDD 4F §2.1, §11.4 |
| Closing CF-9, CF-10 or CF-11 | TDD 4F §5.3, §6.1; TDD 4F.6 §15 |

---

## 3. The production incompatibility, restated from source

| Link | What the code does at `9d2d636` | Evidence |
|---|---|---|
| The trigger payload | `AutonomyDecisionRequestedPayload` carries `category`, `risk`, `action_type`, `execution_target`, `verification_method`, `title`, `detail`, `priority`, `thought_id`, `requesting_engine` and `correlation_id`. **It has no operation and no parameters**, and is `extra="forbid"` | `nova_contracts/events/autonomy.py` l.83–128, l.112 |
| `DecisionRequest` | Built from the payload field by field. **No operation, no parameters** | `decision_orchestration.py` l.119–129 |
| The dispatch payload | `_execution_payload` builds `ActionExecuteRequestPayload(..., parameters={}, ...)` | `domain/decision.py` l.180–215, l.211 |
| `action-engine`, stage 2 | `operation = str(request.parameters.get("operation", "")).strip()`. If it is empty, the action is `failed` with *"parameters['operation'] is required"*, **before** risk, identity, capability or execution | `action-engine/domain/pipeline.py` l.128–135 |
| **Therefore** | **Every real Level-2 dispatch ends `failed` at stage 2.** No real action has ever executed through this path | — |
| The outcome recorded | `_dispatch_or_propose` records **`DecisionOutcome.EXECUTE`** for **any** reply, `failed` and `denied` included. The reply status appears only in the reason text, *"action-engine reported {status}"* | `domain/decision.py` l.426–447 |
| Why evidence missed it | 4F.5's real-infrastructure tier: *"The one stand-in — a real NATS responder for `action.execute`"*. 4F.6's: *"`action-engine` is a stand-in responder, as in 4F.5."* TDD 4F.5 §16 R-5 directed that *"tests that assert dispatch assert the RPC, not the outcome"* | 4F.5 record §6.3; 4F.6 record §6 item 8 |
| The contract `action-engine` already offers | `ActionStatus` separates `denied` from `failed` deliberately: *"TDD 3D §4 point 5 requires a calling agent instance be able to tell these apart, not receive one opaque failure outcome."* | `events/action.py` l.82–95 |
| `DecisionOutcome.TIMEOUT` already anticipates a distinct failure | *"Distinct from `DENY` and from an execution failure, deliberately. A denial means the gates refused; **a failure means `action-engine` reported one**."* No outcome member expresses that failure | `autonomy-engine/domain/models.py` l.111–141 |

**The resolution has two halves, and both are needed:**

1. **Author and carry the operation and parameters**, so that `action-engine`
   can execute: P3, P4 and A-4FP-4 … A-4FP-6.
2. **Record what `action-engine` actually reports**, so that `EXECUTE` is never
   the record of a mere request: P7 and A-4FP-7.

**Both halves sit on the producing side.** `action-engine` is not changed.

---

## 4. Baseline — verified at `9d2d636`

| Fact | Value | Evidence |
|---|---|---|
| Registry | **120** subjects; the only `autonomy.*` subject is `autonomy.decision.requested` | `len(_REGISTRY)` after importing every `nova_contracts.events` module |
| `PUBLIC_TOPICS` | **18** | AST parse of `ws-gateway/domain/protocol.py` |
| `cognitive-state-engine`'s allow-lists | Publish `{autonomy.decision.requested}`; subscribe `{perception.sensor.health_changed}` | 4F.7 record §4; P-11 |
| `promote_thought` | **No production caller** | 4F.7 P-14 (`test_p14_promote_thought_still_has_no_production_caller`) |
| Production Active Thoughts | **None.** No production writer of `active_thought` has ever existed | RS-2a; TDD 4F.7 K-4 |
| `move_layer` | Reads the row inside a transaction and overwrites `attention_layer` **unconditionally**. `promote_thought` reads the thought **before** that transaction. **It is not a compare-and-set** | `postgres_cognitive_state_repository.py`, `move_layer`; `promotion_orchestration.py` l.112–120 |
| `upsert_thought` | Replaces **every** mutable column on conflict, including `attention_layer` and `proposed_action` | same file, `upsert_thought` |
| The attention ladder | Adjacent moves only. Promoting `IMMEDIATE` returns `None`, which is a no-op | `domain/attention.py` l.38–64 |
| `ProposedAction` | The six required fields plus `detail`; all-or-nothing | `domain/models.py` l.131–160 |
| Trigger reply wait | 20 s (4F.6 F-2, unratified) | `cognitive-state-engine/config.py` l.47 |
| Delivery semantics of the trigger and `action.execute` | **Core NATS request/reply.** `request()` is `nc.request` and `serve()` a core `nc.subscribe`; **no JetStream** on either. **At-most-once: no bus redelivery** | `nova_eventbus_sdk/backends/nats.py` l.122, l.158 |
| `action.execute` parameters | One free `dict` (`events/action.py` l.172). **The whole dict** is validated against the capability's `input_schema`, and **the whole dict** reaches the adapter | `pipeline.py` l.272–281, l.296; `capability-engine/main.py` l.72–105 |
| Built-in `input_schema` | `{"operation": str, "parameters": object}`, `required: ["operation"]`; extra keys allowed | `capability-engine/domain/builtin_capabilities.py` l.20–27 |
| Built-ins, all bootstrap-installed | `filesystem` (`read`, `write`, `list`; `list` defaults to the sandbox root), `terminal` (`execute`), `git`, `http`. Sandbox root default `/workspace` | `builtin_capabilities.py`; `filesystem_adapter.py` l.21–50; `config.py` l.26 |
| `execution_target` in `action-engine` | **Resolved as a capability name** (stage 5) | `pipeline.py` l.234 |
| `action-engine` risk | `classify_risk(action_type, operation)`: `read`/`list`/`status`/`log`/`diff` are `negligible`; `write` is `moderate`; `terminal`+`execute` is `high`; `delete`/`remove`/`format` are `critical`; anything else is `low` | `risk.py` l.26–41 |
| `decision_log` | Append-only. `action_id` is indexed, **not unique**; `outcome` is `TEXT` with **no CHECK** | `autonomy/alembic/versions/0001_initial_schema.py` |
| **SLOC, 4F scope** | **47,433**; headroom to 50,000 **2,567** | Measured at `9d2d636` with `cloc` v2.06 (4E methodology) during 4F.8's preparation |

---

## 5. The production execution flow

Under the recommended options. **Every step names its owner and the evidence
that proves it (§15).**

```mermaid
sequenceDiagram
    participant C as nova-companion
    participant PE as perception-engine
    participant N as Event Bus (NATS)
    participant CS as cognitive-state-engine
    participant AE as autonomy-engine
    participant AX as action-engine
    participant CE as capability-engine

    C->>PE: real filesystem observation (internal intake, existing)
    PE->>N: perception.workspace.observed (outbox, existing, internal)
    N-->>CS: subscribed (A-4FP-1)
    CS->>CS: ingestion identity; insert-if-absent Active Thought at ACTIVE,<br/>ProposedAction authored from the ratified table (A-4FP-3/4/5)
    CS->>CS: promotion driver: CAS ACTIVE → IMMEDIATE, winner only (A-4FP-2/8/9)
    CS->>AE: autonomy.decision.requested + operation + parameters (A-4FP-6)
    AE->>AE: level, policies, grants server-side; Policy → Permission → Trust;<br/>single dispatch point; seven §22.4 preconditions + operation present
    AE->>AX: action.execute{parameters: {"operation": op, ...params}} (15 s, once)
    AX->>AX: validate (operation) → risk → stage 3 → stage 5 resolve capability
    AX->>CE: capability.invoke.request
    CE-->>AX: success | failure | sandbox_violation
    AX-->>AE: ActionResultPayload{status}
    AE->>AE: outcome from the real status (A-4FP-7); append decision_log
    AE-->>CS: AutonomyDecisionReplyPayload{outcome, subject_id}
    CS->>CS: log only — nothing persisted about the trigger (RS-6a)
```

| # | Step | Owner | Rule | Failure behaviour |
|---|---|---|---|---|
| 1 | A real observation is published | `perception-engine` | Existing, 4F.2/4F.3 | — |
| 2 | **Ingest** | `cognitive-state-engine` | Validate the payload. Derive the **ingestion identity**. **Insert-if-absent** an Active Thought at `ACTIVE`, carrying the authored `ProposedAction`. A repeat is a no-op (A-4FP-1, A-4FP-9) | An invalid payload is logged and dropped, with nothing written. A store failure is logged, with nothing promoted |
| 3 | **Promote** | `cognitive-state-engine` | Only the **creator** of the thought promotes it, once: a **CAS** `ACTIVE → IMMEDIATE` (A-4FP-2, A-4FP-8) | The CAS loser does nothing. A store failure means no trigger |
| 4 | **Trigger** | `cognitive-state-engine` | The existing `promote_thought` condition (A-4F6-2a); the payload is copied verbatim, now including the operation and parameters (A-4FP-6) | 4F.6's `TriggerDelivery`: `unavailable`, `unconfirmed`, `failed`, `rejected` or `degraded`. **No retry** (4F.6 §19 row 10) |
| 5 | **Decide** | `autonomy-engine` | Unchanged: server-side level, policies and grants; deny-only gates; Trust `UNAVAILABLE`, which is never a pass; the single dispatch point. **The operation joins D-4F5-2's execution fields**: absent means a suggestion | 4F.6 Design A: a degraded reply, `decide()` not invoked |
| 6 | **Dispatch** | `autonomy-engine` → `action-engine` | One request/reply, 15 s, no retry (D-4F5-3). `parameters = {"operation": op, **params}` | Timeout: `TIMEOUT`. Unavailable: `PROPOSE` (§22.8). Unknown fault: degraded reply, **no `EXECUTE`** |
| 7 | **Execute** | `action-engine` → `capability-engine` | **Unchanged** twelve-stage lifecycle | `denied`, `failed` or `rolled_back`, reported in `ActionResultPayload.status` |
| 8 | **Record** | `autonomy-engine` | **The outcome is chosen from the real status** (A-4FP-7). `EXECUTE` only for `completed` | §12 |
| 9 | **Reply to the producer** | `autonomy-engine` → `cognitive-state-engine` | The outcome actually recorded | The producer logs it and **persists nothing** (RS-6a) |

---

## 6. Reconciliation — the twenty subjects

| # | Subject | Position | Where |
|---|---|---|---|
| 1 | Promotion policy | Only the creator of an ingested thought promotes it, once, `ACTIVE → IMMEDIATE`, by CAS. **No automatic demotion in 4F.P** | A-4FP-2; §13 |
| 2 | Thought ingestion | One existing internal subject, `perception.workspace.observed`. One thought per ingestion identity. Insert-if-absent, **never** an overwriting upsert | A-4FP-1; FP-5 |
| 3 | `ProposedAction` authorship | A **closed, ratified authoring table** in `cognitive-state-engine`'s domain. Every field is authored; none is derived from the thought's numbers or from free text | A-4FP-3; §10 |
| 4 | Operation authorship | **An authored field of `ProposedAction`**, taken from the table | A-4FP-4; §11 |
| 5 | Parameters authorship | **An authored, bounded field of `ProposedAction`**, taken from the table. **It never carries a raw path** (D-4F3-2) | A-4FP-4; §11 |
| 6 | Propagation into `action.execute` | Additive fields on the **existing** trigger payload and `DecisionRequest`. `_execution_payload` merges them into `parameters` | A-4FP-6; §11 |
| 7 | CAS on promotion | A conditional `UPDATE … WHERE attention_layer = :expected`, on `decide_suggestion`'s precedent | A-4FP-8; §13 |
| 8 | Layer 2 deduplication | **The ingestion identity is the initiative identity.** At most one trigger per identity, with no persisted trigger state | A-4FP-9; §13 |
| 9 | A production caller of `promote_thought` | The ingestion handler's orchestration, registered in `main.py`'s lifespan | A-4FP-10 |
| 10 | Real `action-engine` execution | Proven in the composed stack against the real `action-engine` and `capability-engine` | A-4FP-12; §15 |
| 11 | Real result handling | `ActionResultPayload.status` is read and **decides the outcome** | A-4FP-7; §12 |
| 12 | Decision-log semantics on rejection, failure and unavailability | `denied` becomes `PROPOSE`, with a specific reason. `failed`/`rolled_back` become the **new `EXECUTION_FAILED`**. Unavailable stays `PROPOSE` (§22.8). Timeout stays `TIMEOUT` | A-4FP-7; §12 |
| 13 | No `EXECUTE` merely because execution was requested | `EXECUTE` requires `status == "completed"`, asserted by tests that read `action-engine`'s own row | A-4FP-7; §15 V-5, V-6 |
| 14 | Timeout and transport failure | **Unchanged**: D-4F5-3, §22.8, A-4F6-5 Design A. The crash window between dispatch and recording is disclosed (FP-7) | §12.3 |
| 15 | Permission and policy boundaries (4F.5) | **Unchanged.** `AUTO_EXECUTE` is LOW-bounded, `DENY` wins, absence means approval, and the seven preconditions hold, with the operation added to precondition 5 | §6.1 |
| 16 | The Level-2 lifecycle (4F.5, 4F.6) | States 1–3 and 5 unchanged. State 4 gains its production caller. **State 5's evidence becomes a real execution** | §6.2 |
| 17 | `autonomy.decision.requested` semantics (4F.6) | Unchanged: identity, consumer, Design A, no TTL, no retry. **Two additive payload fields** | A-4FP-6 |
| 18 | The existing `action.execute` contract | **Unchanged.** `parameters: dict` already carries the operation | §11 |
| 19 | `action-engine`'s stage requirements, especially `operation` | **Met, not changed.** The operation is authored and carried | §11 |
| 20 | Persistence changes | **No migration and no new table.** New JSONB keys in `proposed_action`, one new `TEXT` outcome value, and two conditional statements | §14 |

### 6.1 The 4F.5 permission and policy boundaries — unchanged

| 4F.5 property | Under 4F.P |
|---|---|
| D-4F5-1: `AUTO_EXECUTE` affirmative, LOW-bounded, `DENY` wins, absence means approval | **Unchanged** |
| D-4F5-2: execution fields required at the dispatch branch only; absence means a suggestion; no defaults, no guessing | **Extended by one field, the operation**, with the same rules (A-4FP-6) |
| D-4F5-3: 15 s, one request, no retry, a distinguishable `TIMEOUT` | **Unchanged** |
| D-4F5-4: `permits_execution` is eligibility; the seven preconditions | **Unchanged.** Precondition 5 now includes the operation |
| §22.7 Trust contract | **Unchanged**: `UNAVAILABLE` is non-blocking and never a pass |
| §22.8 dispatch availability | **Unchanged**: no responder means `PROPOSE` |
| Stage 3 in `action-engine` | **Unchanged**, and always run |

### 6.2 The Level-2 lifecycle (TDD 4F §6) — before and after 4F.P

| # | State | At `9d2d636` | After 4F.P |
|---|---|---|---|
| 1 | Defined | Done (4D) | Unchanged |
| 2 | Selectable | Done (4F.5) | Unchanged |
| 3 | Policy-permitted | Done (4F.5) | Unchanged |
| 4 | Triggered | Consumer done (4F.6). **The production end to end is not evidenced** (RS-6b) | **Mechanism complete**: a production component triggers from a real input. It is **evidenced in 4F.P's composed stack**, and **accepted in 4F.8** (CF-11 claim 3) |
| 5 | Executing | Dispatch done (4F.5). **Real execution: impossible** (§3) | **A real execution, recorded truthfully** |

---

## 7. Findings of this preparation

Each finding is verified at `9d2d636`. None is fixed here.

| # | Finding | Evidence | Goes to |
|---|---|---|---|
| **FP-1** | **No real Level-2 dispatch can execute** (= 4F.8's F-4F8-1, now authoritative) | §3 | A-4FP-4, A-4FP-5, A-4FP-6 |
| **FP-2** | **`EXECUTE` is recorded for any reply** (= F-4F8-2) | §3 | A-4FP-7 |
| **FP-3** | **`execution_target` means two things.** A-4F6-2a calls it *"what the action acts on"*. `action-engine` resolves it as a **capability name** (stage 5, TDD 3D §5.1) | `pipeline.py` l.234; TDD 4F.6 §4.7 | A-4FP-5 |
| **FP-4** | **`promote_thought` is not race-safe.** It reads the thought, then `move_layer` overwrites the layer unconditionally. Two concurrent promotions of one `ACTIVE` thought can **both** reach `IMMEDIATE` and **both** fire, with different `event_id`s. That means two decisions, two `action_id`s and **two executions** | `promotion_orchestration.py` l.112–130; `move_layer` | A-4FP-8 |
| **FP-5** | **`upsert_thought` is unsafe for ingestion.** It overwrites `attention_layer` and `proposed_action` on conflict, so re-ingesting a known input would reset a promoted thought | `upsert_thought` | A-4FP-1, A-4FP-9 |
| **FP-6** | **The trigger and `action.execute` are at-most-once, not at-least-once.** TDD 4F.6 §5.1 and §13.1 state *"the bus is at-least-once (NATS + JetStream)"*. As built, both subjects use core NATS request/reply, so **the bus never redelivers them**. **A duplicate can only originate at the producer** (FP-4, FP-5). Layer 1 (4F.6) stays a correct safety net | `backends/nats.py` l.122, l.158 | Documentation. A-4FP-9 |
| **FP-7** | **Dispatch happens before the decision is recorded.** `decide()` awaits the RPC and the orchestrator records afterwards. A crash in between leaves an executed action with **no autonomy log row**. `action-engine`'s own `action` and `action_execution_history` rows still record it | `decision.py`; `decision_orchestration.py` l.132–215 | **Disclosed.** Stays with the DEFERRED persistent lost-trigger auditability (§21) |
| **FP-8** | **Approving a Level-1 suggestion executes nothing** (by 4D's design) | `api/autonomy.py` l.413–432 | Documentation only. Out of 4F.P's scope |
| **FP-9** | **A proposal cannot target the observed file.** D-4F3-2 keeps the raw path inside `perception-engine`, and `perception.workspace.observed` carries only a hash and a final segment. Authored parameters may therefore name only **capability-sandbox-relative** targets | TDD 4F.3 §9.1; 4F.2 contract | Constraint in A-4FP-3 |
| **FP-10** | **Risk is classified twice** (= F-4F8-3). An authored risk **below** `action-engine`'s own classification would let the policy gate admit an action that `action-engine` rates higher | `risk.py` | A-4FP-3's rule: **authored ≥ classified**, drift-guarded |
| **FP-11** | **4F.7's P-14 pins the absence this slice must create.** `test_p14_promote_thought_still_has_no_production_caller` fails the moment 4F.P succeeds | 4F.7 record §2 P-14 | A-4FP-10: a disclosed retargeting |
| **FP-12** | **The e2e stack cannot produce a real input.** It starts no `perception-engine`, worker or companion, and `perception-engine`'s `primary_user_id` is unset in compose (= F-4F8-8) | `pr-checks.yml` l.253–266; `perception-engine/config.py` l.55 | A-4FP-12 |
| **FP-13** | **An "already in flight" reply reads as `failed`.** If a second `action.execute` for the same `action_id` arrived while the first was executing, `action-engine` would reply `failed`. Under A-4FP-7 that would be recorded as `EXECUTION_FAILED` while the action completes. **It is unreachable in production**, where the bus does not redeliver (FP-6) and the producer never re-sends (4F.6 row 10), but a harness could provoke it | `pipeline.py` l.159–173 | **Disclosed** as a known limitation (§12.4) |

---

## 8. Ratification candidates

**A-4FP-1 … A-4FP-13 block implementation. A-4FP-14 has a default.**

- **"New"** candidates answer questions nobody has ratified. The five RS-1c
  requires are among them.
- **"Amends"** candidates would change an existing ratification. Each names the
  decision, the proposed change, the reason, the affected components and
  criteria, and whether implementation must wait.

**Nothing in this section is decided.**

### A-4FP-1 — Thought ingestion (RS-2b's mapping). **New, and amends RS-3a's allow-list clause. BLOCKING**

**Question.** Which existing subject feeds thought creation, how is an input
mapped to an Active Thought, and how does ingestion stay idempotent?

| Option | Consequence |
|---|---|
| **(a) `perception.workspace.observed` only** (internal, existing). One thought per **ingestion identity** `thought_id = uuid5(NS_INGEST, payload.object_id)`. It is **inserted if absent** (`INSERT … ON CONFLICT DO NOTHING RETURNING`), at `ACTIVE`, with authored fields: `description` from the label; `priority`, `confidence` and `current_progress` as constants named in the table; `related_projects = [project_id]` only when the payload carries one. **A repeat observation writes nothing** | Provider-free, reproducible in CI from a real companion event. Matches TDD 4F §13's *"Consumes: Perception observations"*. **Needs no `project_id`**, so no dependency on 4F.8's L-13. Idempotent under outbox re-publication. Cost: one subscription and one insert-if-absent statement |
| (b) `world_model.object.created`/`.updated` | One further outbox hop (world-model's worker, not in the e2e stack). The payload carries no `project_id` |
| (c) `world_model.context.changed` | Produced by fused identity and presence signals, **which CI cannot produce without fabrication**. It would also settle TDD 4F §24.13 item 2's doc-10 row |
| (d) `planning.task_graph.created` / `reasoning.process.completed` | **LLM-dependent**, with no provider in the stack (master scope §1.1, AC-4's note) |
| (e) `memory.long_term.created` | Real, but produced only by a memory write driver in CI (4E's `tools/` precedent). No product rule links a memory to an action |

**Recommendation: (a).** The authored constants — `priority`, `confidence`,
`current_progress` and the description template — are ratified **with** the
authoring table (A-4FP-3). Proposed values: `priority 1`, `confidence 1.0` (a
directly observed fact), `current_progress 0.0`.

**Amends RS-3a's allow-list clause:**

- **Existing decision (RS-3a):** `cognitive-state-engine`'s subscribe
  allow-list *"changes from **empty** to **exactly this existing subject**"*
  (`perception.sensor.health_changed`).
- **Proposed change:** it becomes exactly **two** existing subjects,
  `perception.sensor.health_changed` and `perception.workspace.observed`. Both
  are internal inputs; no subject is added, and `PUBLIC_TOPICS` is untouched.
  4F.7's P-11 is retargeted, not retired, with its wording preserved.
- **Reason:** RS-2b assigns ingestion from existing subjects to this slice.

**Affected components:** `cognitive-state-engine` (`events/subscribed.py`, a
handler, an ingestion orchestration module, the repository's insert-if-absent,
`main.py`). **Affected criteria:** AC-8 (the trigger's input). **Implementation
must wait: yes.**

### A-4FP-2 — The promotion policy (RS-1c). **New. BLOCKING**

**Question.** Which thoughts are promoted to `IMMEDIATE`, when, by what, and
what happens afterwards?

| Option | Consequence |
|---|---|
| **(a) Creation-time promotion, once.** The ingestion step that **created** a thought, and only that step, promotes it `ACTIVE → IMMEDIATE` through the CAS (A-4FP-8). Re-ingestion never promotes. **No automatic demotion in 4F.P**: a triggered thought stays `IMMEDIATE`, and Focus's capacity bounds what is shown | Deterministic. One trigger per ingested identity. No persisted trigger state (RS-6a). **Consequence, disclosed:** `IMMEDIATE` accumulates, and demotion is deferred (§21) |
| (b) Creation-time promotion, with demotion `IMMEDIATE → ACTIVE` after the trigger reply | Needs a rule for re-promotion, which re-opens Layer 2 (A-4FP-9), and a demotion trigger that reads the decision outcome, which is **close to RS-4b's line** (*"does not read autonomy data"*) |
| (c) A periodic driver promoting by Focus score | Focus signals are all `None` in production (K-5). A score of priority alone would be an invented urgency |
| (d) Promotion by a user action | A write route. **Forbidden** (RS-1b) |

**Recommendation: (a).**

**Recommended wording:**

> *"A thought is promoted to `IMMEDIATE` exactly once, by the ingestion step
> that created it, through a compare-and-set transition. Nothing else promotes
> in production, and nothing demotes in this slice."*

**Affected components:** `cognitive-state-engine`. **Affected criteria:**
AC-8. **Implementation must wait: yes.**

### A-4FP-3 — The `ProposedAction` authorship rule (RS-1c, RS-2b). **New. BLOCKING**

**Question.** How are a proposal's fields chosen, including the operation and
its parameters, without deriving, defaulting or guessing?

| Option | Consequence |
|---|---|
| **(a) A closed authoring table**: data in `cognitive-state-engine`'s domain, keyed by ingestion input kind, **ratified entry by entry**. An input with no entry yields a thought with **no** proposal, which **never triggers** (A-4F6-2a rule 2). **One entry, T1, is proposed for ratification** (below) | Nothing is derived at runtime. Every value is a ratified constant or a ratified pass-through. Adding an entry is a new ratification |
| (b) Rule-based derivation from the thought's fields | Derives security-relevant values. **Forbidden** by A-4F6-2a's *"authored, never derived"* |
| (c) Model-based (LLM) authoring | No provider in the stack; not provider-free; not ratifiable as a deterministic rule |
| (d) No proposal at all in 4F.P | Nothing ever triggers in production, so CF-11 stays unevidenceable. That contradicts RS-1c's rationale |

**The proposed entry T1**, for `perception.workspace.observed`:

| Field | Proposed value | Why |
|---|---|---|
| `category` | `read` | Part 14's category for a read-only action |
| `risk` | **`low`** (authored) | AC-8's *"low-risk case"* (TDD 4F §4.2). It is **not below** `action-engine`'s own classification of `(filesystem, list)`, which is `negligible` |
| `action_type` | `filesystem` | `ActionType` |
| `execution_target` | `filesystem` | **The built-in capability's name**, which is what `action-engine` resolves (A-4FP-5) |
| `operation` | `list` | Supported by the `filesystem` adapter; read-only; `negligible` in `action-engine` |
| `parameters` | `{}` | `list` without a `path` lists the capability's **configured sandbox root**. **No path from the observation** (FP-9, D-4F3-2) |
| `verification_method` | `adapter_success` | Names exactly what `action-engine`'s stage 10 does: *"a successful adapter invocation is itself treated as satisfying verification"* (`pipeline.py` l.340–346) |
| `title` | *"Review the workspace after activity in {label}"* | `label` is the observation's final path segment, already public in the World Model |
| `detail` | *"NOVA noticed activity in the watched workspace and proposes listing it."* | — |

**Two binding rules for every entry, now and later:**

1. **Authored risk ≥ classified risk.** An entry's authored `risk` is never
   below `action-engine`'s `classify_risk(action_type, operation)`. A contract
   test parses `action-engine/domain/risk.py` **as text**, with no import (the
   4F.7 P-22 precedent), and fails if any entry violates this.
2. **No raw path, and no value from free text.** Parameters are constants of
   the entry or ratified pass-throughs of non-sensitive payload fields. T1 has
   none.

**Recommendation: (a) with T1.** Alternatives for T1 exist: `git`/`status`, or
a table with no entry, which would mean no production trigger. Each is the
user's to choose. **Deployment note, not a decision:** under A-4FP-12,
`capability-engine`'s sandbox root can be the same workspace the companion
watches, so T1 lists the directory where the activity happened, with no path
on the bus.

**Affected components:** `cognitive-state-engine` (the domain table, a drift
test). **Affected criteria:** AC-8 (*"the same action category"*, *"a low-risk
case"*). **Implementation must wait: yes.**

### A-4FP-4 — The `operation` and `parameters` fields on `ProposedAction`. **Amends A-4F6-2a. BLOCKING**

| | |
|---|---|
| **Existing decision** | **A-4F6-2a** (TDD 4F.6 §4.7): `ProposedAction` has exactly the required fields `category`, `risk`, `action_type`, `execution_target`, `verification_method` and `title`, plus the optional `detail`; all-or-nothing |
| **Proposed change** | Add **`operation: str`**, required, non-empty, part of all-or-nothing. Add **`parameters: dict[str, JSON]`**, required with an explicit `{}` allowed. It is **bounded** (a key count, value depth and serialized size, named in the implementation contract) and **may not contain the key `"operation"`**. Both are **authored** under A-4FP-3 and never derived |
| **Reason** | `action-engine` requires `parameters["operation"]` (stage 2), and adapters read their inputs from `parameters`. Without these fields no proposal can execute (FP-1) |
| **Why a separate `operation` field** rather than a key inside `parameters` | It is the one value `action-engine` requires and classifies risk from, so it is typed, non-empty and drift-checked (A-4FP-3 rule 1). A second `"operation"` inside `parameters` is refused so that there is exactly one source |
| **Persistence** | **No migration.** `proposed_action` is JSONB. No production row exists (RS-2a; K-4), so there is no old-shape row to migrate. The model rejects an old-shape row, which would be a defect |
| **Affected components** | `cognitive-state-engine` (`domain/models.py`, repository mapping); 4F.7's read surface is unaffected (A-4FP-14) |
| **Affected criteria** | AC-8 |
| **Implementation must wait** | **Yes** |

### A-4FP-5 — What `execution_target` means. **Amends (clarifies) A-4F6-2a. BLOCKING**

| | |
|---|---|
| **Existing decision** | A-4F6-2a's field table: `execution_target` is *"*What* the action acts on. Never defaulted"* |
| **Proposed change** | `execution_target` is **the name of the capability `action-engine` resolves at stage 5**, as TDD 3D §5.1 and `pipeline.py` l.234 define it. **What the action acts on travels in `parameters`.** Still never defaulted |
| **Reason** | FP-3. Authored as *"what it acts on"* (for example a path), stage 5 would fail with *"capability not found"*, and FP-9 forbids carrying a path anyway |
| **Affected components** | `cognitive-state-engine` (docstring, authoring table); documentation of TDD 4F.6 (an additive note, at ratification) |
| **Affected criteria** | AC-8 |
| **Implementation must wait** | **Yes** |

### A-4FP-6 — Carrying the operation and parameters into `action.execute`. **Amends D-4F5-2, the 4F.6 trigger contract and 4F.5's dispatch builder. BLOCKING**

| | |
|---|---|
| **Existing decisions** | **D-4F5-2** (TDD 4F.5 §22.2): `DecisionRequest` gains exactly `action_type`, `execution_target` and `verification_method`, required only at the dispatch branch. **TDD 4F.6 §19**: *"Contract changes permitted: exactly two"* (the payload and `PermissionCategory`'s home), and **row 20** *"4F.5 untouched — dispatch semantics …"*. **A-4F6-2a**: the trigger payload copies `ProposedAction` verbatim. 4F.5's `_execution_payload` sends `parameters={}` |
| **Proposed change** | (1) `AutonomyDecisionRequestedPayload` gains **`operation: str | None = None`** and **`parameters: dict = {}`**. These are **additive** (ADR-024: `schema_version` stays `1`), and both engines are deployed together because the consumer is `extra="forbid"`. (2) `DecisionRequest` gains **`operation`** and **`parameters`**. **`operation` joins D-4F5-2's execution fields**: required only at the dispatch branch, and **absent means a suggestion, never a guess**. (3) `_execution_payload` builds **`parameters = {"operation": operation, **parameters}`**; nothing else in the payload changes. (4) `promote_thought`'s `trigger_payload` copies both fields verbatim. (5) **Codegen is regenerated.** The registry stays **120**, and **no subject is added** |
| **Reason** | FP-1. `action.execute`'s existing `parameters: dict` already has the right shape. Only the producer side is missing the values. **This is the smallest change that makes the existing contract executable** |
| **Rejected alternatives** | Deriving the operation from `verification_method` or `action_type` (guessing, forbidden by D-4F5-2); defaulting it in `action-engine` (changes stage 2, TDD 4F §7.3); a new subject (no need, D-4D-1) |
| **Affected components** | `nova-contracts` (`events/autonomy.py`; generated TypeScript); `cognitive-state-engine` (`promotion_orchestration.trigger_payload`); `autonomy-engine` (`DecisionRequest`, `decision_orchestration.decision_request`, `_execution_payload`) |
| **Affected criteria** | AC-8 |
| **Implementation must wait** | **Yes** |

### A-4FP-7 — The decision outcome follows the real execution result. **Amends TDD 4F.5 §10's audit row and X-11, and TDD 4F.6 §19 row 13. BLOCKING**

**D-4F5-3 itself is not changed.** The timeout, its bound and `TIMEOUT` stay as
ratified. This candidate supplies the *"ordinary execution failure"* outcome
that D-4F5-3's wording already distinguishes a timeout from.

| | |
|---|---|
| **Existing decisions** | **TDD 4F.5 §10:** *"Every Level-2 decision writes a `DecisionLogEntry` with `outcome=EXECUTE`"*. **X-11:** *"The decision log records the Level-2 execution … `outcome=EXECUTE`"*. **D-4F5-3:** a timeout distinct *"from a policy denial **and from an ordinary execution failure**"*. As built, `EXECUTE` is recorded for every reply. **TDD 4F.6 §19 row 13:** *"No new `DecisionOutcome` — The five existing members are unchanged."* **4F.5 §22.8.3:** no new outcome for unavailability, which reuses `PROPOSE` |
| **Proposed change** | The outcome is chosen from `ActionResultPayload.status` (table below). **`EXECUTE` is recorded only for `completed`.** One **new** member, **`EXECUTION_FAILED`**, is added to `DecisionOutcome`. That needs no migration: `outcome` is `TEXT` with no CHECK. The reason names `action-engine`'s status and error. The reply to the producer carries the recorded outcome |
| **Reason** | FP-2. `ActionStatus` separates `denied` from `failed` *"so a calling agent can tell these apart"*, and `TIMEOUT`'s docstring already assumes an execution-failure outcome exists. **No existing member honestly expresses "dispatched, and `action-engine` did not complete it"**: `PROPOSE` would falsely claim nothing ran, `EXECUTE` that it succeeded, and `TIMEOUT` that no reply came |
| **Why only one new member** | 4F.5's precedent is to reuse `PROPOSE` for a **provably non-executing** result (unavailable). **`denied` is provably non-executing**: stage 3 and the approval loop both precede execution. So it follows that precedent, and the new member is confined to the one case no existing member can state |
| **Alternatives** | (b) Two new members, `EXECUTION_DENIED` and `EXECUTION_FAILED`: a clearer audit, at one more member. (c) A separate `execution_status` column, with `EXECUTE` meaning "dispatched and answered": **rejected**, because it keeps `EXECUTE` on failures, and it needs a migration |
| **Affected components** | `autonomy-engine` (`DecisionOutcome`, `_dispatch_or_propose`, reason texts). Consumers of the outcome string: `cognitive-state-engine` (logs only); the web client's `decisionResultSchema` enum (`entities/autonomy.ts` l.181), **which is reached only by the suggestion-decision route, and that route never produces the new member** |
| **Affected criteria** | AC-8 (*"auto-executes"* is evidenced by `EXECUTE` **and** `action-engine`'s `completed`) |
| **Implementation must wait** | **Yes** |

| `action-engine` reply | Recorded outcome | Suggestion? | What it claims |
|---|---|---|---|
| `completed` | **`EXECUTE`** | No | Executed and completed |
| `denied` (stage 3, or approval refused) | **`PROPOSE`**, reason *"action-engine denied the action: {error}; it was not executed"* | **Yes**, as §22.8's path | **Provably not executed.** It remains available to the user's explicit decision |
| `failed` | **`EXECUTION_FAILED`** | No | `action-engine` received it and did not complete it. **Whether any side effect happened is recorded in `action-engine`'s history, and never inferred here** |
| `rolled_back` | **`EXECUTION_FAILED`**, reason names the rollback | No | Same |
| No reply in 15 s | `TIMEOUT` (unchanged) | No | Unknown; it may have executed |
| No responder | `PROPOSE` (unchanged, §22.8) | Yes | Provably not executed |
| Unknown transport fault | **No row**; degraded reply (unchanged, Design A) | No | Unknown. **Never `EXECUTE`** |

### A-4FP-8 — CAS on the promotion transition (RS-7). **New. BLOCKING**

**Question.** How is the `ACTIVE → IMMEDIATE` move made race-safe?

| Option | Consequence |
|---|---|
| **(a) A conditional transition.** A repository method sets `attention_layer = :target, updated_at = now` `WHERE thought_id = :id AND attention_layer = :expected`, in **one statement**, returning the row. `rowcount == 1` means **this caller moved it** and may trigger. `rowcount == 0` means someone else did, so the caller does nothing. `promote_thought` uses it; `next_layer` still decides the target | `decide_suggestion`'s conditional-`UPDATE` precedent, which RS-7 names. No migration. FP-4 is closed |
| (b) `SELECT … FOR UPDATE` then update | Correct, but a row lock where one statement suffices; no precedent in these engines |
| (c) A version column | A migration, for no gain over (a) |

**Recommendation: (a).** `move_layer`'s unconditional form stays for callers
that do not trigger. **Whether it keeps any production caller is recorded at
implementation.**

**Affected components:** `cognitive-state-engine` (repository, port,
`promote_thought`). **Affected criteria:** AC-8 (no duplicate execution).
**Implementation must wait: yes.**

### A-4FP-9 — Duplicate triggers: Layer 2 (A-4F6-3, deferred to 4F.P). **New; resolves a deferral. BLOCKING**

**Question.** When are two triggers the same initiative, and what prevents a
duplicate execution?

**The facts that make it tractable (FP-6):**

- the trigger and `action.execute` are **not redelivered** by the bus;
- the producer never re-sends;
- so duplicates can come only from producer-side re-promotion (FP-4) or
  re-ingestion (FP-5).

| Option | Consequence |
|---|---|
| **(a) The ingestion identity is the initiative identity.** One thought per identity (A-4FP-1), promoted once, at creation (A-4FP-2), by CAS (A-4FP-8). So **at most one trigger per identity**, with **no persisted trigger state** (RS-6a) and **no second deduplication mechanism**. A genuinely new input has a new identity and is a new initiative. **Layer 1 (4F.6) is unchanged** and remains the safety net at the execution boundary | Closes both producer-side duplicate sources structurally. It matches 4F.6 §5.6's reading that a new input is *"a new intention"* |
| (b) 4F.6 §5.6's `uuid5(thought_id|proposal digest)`, checked by the consumer | Needs a persisted initiative table in `autonomy` (a migration). It de-duplicates what (a) already makes impossible |
| (c) A producer-side "already triggered" marker | **A persisted trigger outcome. Forbidden** (RS-6a) |

**Recommendation: (a).** 4F.6 §5.1 and §13.1's *"at-least-once"* premise is
corrected by an additive note at ratification (FP-6). The Layer 1 mechanism is
kept exactly.

**Affected components:** `cognitive-state-engine`. **Affected criteria:** AC-8.
**Implementation must wait: yes.**

### A-4FP-10 — The production caller of `promote_thought`, and 4F.7's P-14. **Amends 4F.7's P-14 control. BLOCKING**

| | |
|---|---|
| **Existing decision** | **RS-1b** made **4F.7** strictly read-only. It still holds for the read surface. **4F.7's P-14** includes `test_p14_promote_thought_still_has_no_production_caller`, and `test_p14_nothing_on_the_served_path_writes_a_thought_or_promotes` covers `api/` and `main.py` |
| **Proposed change** | An **ingestion orchestration module** at the package root (the `<inbound artifact>_orchestration.py` convention, A-4F6-7), invoked by the `perception.workspace.observed` handler, becomes the **one** production caller of `promote_thought`. `main.py` only subscribes the handler. **P-14's "no production caller" test is retargeted** to *"exactly one production caller, the ingestion orchestration"*, with its wording preserved. **The `api/` half of P-14 is unchanged: the read surface still never writes or promotes** |
| **Reason** | F-6; RS-1c |
| **Also in scope, recommended** | **Repair F-4F7-1**, control 11's vacuous schema check, using A-4F7-6 (a)'s ratified recommendation, **because 4F.P changes exactly what that control guards** (the subscribed subject strings). The effective check permits exactly the three ratified subject strings, and is negative-controlled |
| **Affected components** | `cognitive-state-engine` (`main.py`, `events/`, the orchestration module, contract tests) |
| **Affected criteria** | AC-8 (CF-11 claim 3's prerequisite) |
| **Implementation must wait** | **Yes** |

### A-4FP-11 — The stage-3 configuration for 4F.P's real-execution evidence. **Answers 4F.8's A-4F8-5 once. BLOCKING**

**Question.** The real stage 3 reads identity confidence that CI cannot produce
honestly (4F.8's F-4F8-4). What may 4F.P's composed evidence configure?

**Recommendation: A-4F8-5's option (a), proposed for ratification once, as
this candidate.** Nothing is ratified by this document. The harness writes
`minimum_confidence_by_risk = {<tier>: 0.0}` through the production
`PUT /v1/action/identity-confidence-policy`, for **exactly** the tier
`action-engine` assigns to the executed action (`negligible` for T1). It is
disclosed test configuration, not a production default (D-4F4-4). A negative
control shows the gate denying without it, and that denial becomes `PROPOSE`
under A-4FP-7, which is itself evidence.

**Affected components:** the harness only. **Affected criteria:** AC-8.
**Implementation must wait: yes.**

### A-4FP-12 — Where the real-execution evidence runs. **Moves 4F.8's proposed D4 forward. BLOCKING**

- **Question.** Where is the composed path proven against real engines, with a
  real input, given that control 12 forbids fabricated sensor readings and
  injected messages anywhere in 4F?
- **Existing (proposed, not ratified) assignment:** TDD 4F.8's D4 and A-4F8-10
  put `perception-engine`, its worker, the companion service and
  `perception-engine`'s `primary_user_id` into the e2e stack **in 4F.8**.

| Option | Consequence |
|---|---|
| **(a) The composed stack in 4F.P.** The e2e job gains `perception-engine`, `perception-engine-worker`, a `nova-companion` service watching a bind-mounted workspace, and `perception-engine`'s `primary_user_id`. `capability-engine`'s sandbox root is that workspace. A `tools/` harness writes a real file, configures Level 2 through production routes, and reads **every** engine's database by independent SQL | A real input, a real trigger and a real execution, with **no stand-in anywhere in the chain**. 4F.8's D4 moves into 4F.P, and 4F.8 reuses it |
| (b) Per-engine halves only (the 4F.6 and 4F.7 precedent), with composition deferred to 4F.8 | Repeats the gap that hid FP-1: **no single run would ever hold the real `action-engine` on the other side of the real `autonomy-engine`** |
| (c) A multi-process real-infrastructure test in one package's suite | Engines spawned as processes (not imported, per control 7), against one database. Heavy, with no precedent |

**Recommendation: (a).** 4F.P **does not claim AC-8.** It has no Level-1
comparison, no browser and no latency measurement (§20).

**Affected components:** `infra/docker`, `.github/workflows/pr-checks.yml` (the
e2e service list), `tools/` (a harness and the stack-completeness test).
**Affected criteria:** AC-8's evidence path; AC-7's deployment. **Implementation
must wait: yes.**

### A-4FP-13 — SAD 15 §4 item 1 for the 4F.P PR. **New (RS-9's precedent). BLOCKING (process)**

- **Question.** The PR touches `nova-contracts`, `cognitive-state-engine`,
  `autonomy-engine`, `infra/docker`, `tools/` and `pr-checks.yml`. Is an RS-9
  exception granted, scoped to exactly those surfaces, with SAD 15 §4 items
  2–5 mandatory and the exception recorded in the Slice Completion Record?
- **Recommendation:** yes, scoped after A-4FP-1 … A-4FP-12.
- **Implementation must wait: yes.**

### A-4FP-14 — The read surface and the new fields. **Default: no change. NOT BLOCKING**

- **Question.** Does 4F.7's `/v1/cognitive-state/thoughts` expose `operation`
  and `parameters`?
- **Default: (a) no.** `ProposedActionResponse.of` maps field by field
  (`api/cognitive_state.py` l.72–94), so nothing breaks. The panel's strict
  schema is untouched. The docstring's *"verbatim"* gains an additive note.
- **Alternative: (b)**, extend the response, the strict zod schema and the
  panel. That changes 4F.7's contract, with P-9's controls re-checked.
- **Affected components:** none under (a). **Affected criteria:** none.

---

## 9. A-4F8-3 — determined, not ratified

**4F.8's A-4F8-3 asked:** where `action.execute`'s `operation` and adapter
parameters come from, and which action is AC-8's low-risk case. It recommended
that the extension be **owned by 4F.P's TDD**. This section answers the two
questions it was asked to determine. **It does not ratify A-4F8-3.**

| Question | Determination |
|---|---|
| **Does 4F.P define the required `ProposedAction` fields?** | **Yes.** `operation` and `parameters` (A-4FP-4), authored by the closed table (A-4FP-3), under the `execution_target` meaning `action-engine` uses (A-4FP-5) |
| **Should they become part of the existing 4F.5/4F.6 execution contract?** | **Yes, additively.** They extend the **existing** subject's payload (no new subject) and D-4F5-2's execution fields (`operation` required at dispatch; absent means a suggestion), and they fill `action.execute`'s **existing** `parameters` (A-4FP-6). Because each touches a ratified decision, each is an explicit **Amends** candidate |
| **Which action is AC-8's low-risk case?** | Whatever the ratified table's entry is. **T1 is proposed**: authored `low`; classified `negligible` by `action-engine`; `filesystem`/`list`; executable by a bootstrap-installed built-in; its effect, the listed `entries`, is observable by independent SQL on `action.action.result` (V-4). That meets all four parts of A-4F8-3's low-risk constraint. **Its choice is A-4FP-3's, not 4F.8's** |
| **What becomes of A-4F8-3** | **If A-4FP-3 … A-4FP-6 are ratified as recommended, A-4F8-3 has no remaining question**, and 4F.8's TDD records it as settled by 4F.P's ratification in an additive update (§22 step 4). If a different option is ratified, A-4F8-3 is re-derived from it |

---

## 10. `ProposedAction` — the fields after 4F.P

Under A-4FP-4 and A-4FP-5.

| Field | Type | Required | Semantics | Source |
|---|---|---|---|---|
| `category` | `PermissionCategory` | Yes | The category every gate is evaluated against | Authored (table) |
| `risk` | `RiskLevel` | Yes | **Authored**, never derived; **≥ `action-engine`'s classification** | Authored (table), drift-guarded |
| `action_type` | `ActionType` (`terminal` \| `filesystem`) | Yes | `action.execute`'s own literal | Authored (table) |
| `execution_target` | `str`, non-empty | Yes | **The capability name** `action-engine` resolves (A-4FP-5) | Authored (table) |
| **`operation`** | `str`, non-empty | **Yes (new)** | The adapter operation. **The value `action-engine` requires** | Authored (table) |
| **`parameters`** | bounded `dict[str, JSON]` | **Yes (new)**; `{}` allowed | The adapter inputs. **Never contains `"operation"`**; **never a raw path** | Authored (table) |
| `verification_method` | `str`, non-empty | Yes | How the result is verified | Authored (table) |
| `title` | `str`, non-empty | Yes | Shown on a suggestion | Authored template |
| `detail` | `str` | No, `""` | — | Authored template |

**Rules, unchanged from A-4F6-2a and extended:**

- all-or-nothing;
- absence never triggers;
- no `user_id`;
- no `subject_id`;
- non-empty strings;
- **every value from the ratified table.**

---

## 11. Operation and parameters — ownership and propagation

| Stage | Owner | Carries | Rule |
|---|---|---|---|
| Authored | `cognitive-state-engine` | `ProposedAction.operation`, `.parameters` | A-4FP-3: from the table only |
| Stored | `cognitive-state-engine` | `active_thought.proposed_action` (JSONB) | No migration |
| Triggered | `cognitive-state-engine` → `autonomy-engine` | `AutonomyDecisionRequestedPayload.operation`, `.parameters` | Copied verbatim (A-4FP-6) |
| Decided | `autonomy-engine` | `DecisionRequest.operation`, `.parameters` | `operation` required at dispatch; absent means a suggestion (D-4F5-2, extended) |
| Dispatched | `autonomy-engine` → `action-engine` | `ActionExecuteRequestPayload.parameters = {"operation": op, **params}` | **The existing contract, unchanged** |
| Executed | `action-engine` → `capability-engine` | `parameters["operation"]` → `operation`; the whole dict → the adapter | **Unchanged** stages |

**No engine derives, defaults, rewrites or drops either value.** A mutation of
any stage is caught by V-1 and V-2 (§15).

---

## 12. Real `action-engine` result semantics

### 12.1 The mapping

The mapping is A-4FP-7's table. In summary:

- `EXECUTE` means **completed**.
- `PROPOSE` means **provably not executed**: `action-engine` denied it, or
  nobody was listening.
- `EXECUTION_FAILED` means **received, and not completed**.
- `TIMEOUT` means **unknown**.
- A transport fault is **not recorded, and is never `EXECUTE`**.

### 12.2 What is never recorded

`EXECUTE` is never recorded:

- for `denied`, `failed` or `rolled_back`;
- for a timeout, for no responder, or for a transport fault;
- **because a request was sent.**

A test reads `action-engine`'s own row for the same `action_id` and fails if the
two disagree (V-5, V-6).

### 12.3 Timeout and transport — unchanged

| Condition | Behaviour | Decision |
|---|---|---|
| No reply in 15 s | `TIMEOUT`; no retry; *"may still have executed"* | D-4F5-3 |
| No responder | `PROPOSE` plus a suggestion; *"not executed"*; no retry | TDD 4F.5 §22.8 |
| Unknown fault during dispatch | `decide()` raises; the orchestrator returns a degraded reply; **no log row, and no `EXECUTE`** | A-4F6-5 Design A |
| A crash after dispatch, before recording | The executed action is recorded by `action-engine` alone | **FP-7: disclosed and deferred** |
| Trigger undelivered | Nothing is decided or executed | 4F.6 §19 row 12 |

### 12.4 Known limitation

**FP-13.** An "already in flight" reply is recorded as `EXECUTION_FAILED`.
It is unreachable in production, and it is disclosed rather than engineered
around. Changing `action-engine`'s reply vocabulary is a non-goal.

---

## 13. Duplicate and CAS semantics

| Duplicate source | Prevented by | Result |
|---|---|---|
| The outbox re-publishes one `perception.workspace.observed` | Ingestion identity + insert-if-absent (A-4FP-1) | One thought; the repeat writes nothing and promotes nothing |
| Two concurrent deliveries of the same input | Insert-if-absent: exactly one `RETURNING` row | Only the creator promotes |
| Two concurrent promotions of one thought | **CAS** (A-4FP-8) | Exactly one `rowcount == 1`; exactly one trigger |
| A re-observation of the same object later | Creation-time promotion only (A-4FP-2) | No second trigger |
| The same trigger envelope delivered twice | Not produced by the bus (FP-6). If provoked: Layer 1, same `subject_id`, same `action_id`, `action-engine`'s replay | One execution. Possibly two log rows, as 4F.6 §13.1 accepted |
| A genuinely new input | A new identity | A new initiative (A-4FP-9) |

**RS-6a holds.** Nothing records that a thought *has triggered*. Uniqueness
comes from **identity and transition**, not from a marker.

---

## 14. Persistence, subjects and API

| Area | Change | Migration? |
|---|---|---|
| `cognitive_state.active_thought.proposed_action` | Two new JSONB keys (`operation`, `parameters`) | **No**. No production row exists |
| `cognitive_state.active_thought` | Insert-if-absent; a CAS transition | **No**. Statements only |
| `autonomy.decision_log.outcome` | One new value, `execution_failed` | **No**. `TEXT`, no CHECK |
| `action.*`, `capability.*`, `perception.*`, `world_model.*` | **None** | — |
| **Subjects** | **None new.** `cognitive-state-engine` subscribes to the existing **internal** `perception.workspace.observed`. `autonomy.decision.requested` gains two additive payload fields. Registry **120**, `PUBLIC_TOPICS` **18** | — |
| **API** | **None.** No gateway prefix, no route. The read surface is unchanged (A-4FP-14) | — |

---

## 15. How real execution evidence is collected

**Principle.** A successful dispatch request is **not** evidence. Every claim
below is read from **the engine that owns the fact**, by **independent SQL on
its own connection**, in a run where **every engine on the path is the real
one**: the composed stack (A-4FP-12). The per-engine tiers remain, and **no
stand-in counts toward any V-item**.

| # | Must eventually prove | How |
|---|---|---|
| **V-1** | The real `action-engine` receives the intended **operation** | `action.action.parameters->>'operation'` equals the authored `operation` for the row whose `id` is the decision's `subject_id` (`action-engine` stores `ActionExecuteRequestPayload.action_id` as `action.action.id`). `action_type` and `execution_target` equal the authored values |
| **V-2** | The intended **parameters** reach `action-engine` | `action.action.parameters` equals `{"operation": op} ∪ authored parameters`, key for key |
| **V-3** | `action-engine` **accepts** the request | `action_execution_history` holds `validate`/`success` and `check_permissions`/`success` for that `action_id` |
| **V-4** | The action **completes, or reports the appropriate failure** | `action.action.status` is terminal. For T1 it is `completed`, with `action.action.result` holding the adapter's `entries` for the real sandbox root |
| **V-5** | `autonomy-engine` **records the actual outcome** | `autonomy.decision_log` for `action_id = subject_id` holds the outcome A-4FP-7 maps from V-4's status: `completed` gives `execute` |
| **V-6** | A **rejected or failed** action is **not** `EXECUTE` | (a) **Denied:** with A-4FP-11's row removed, stage 3 denies, so `action.status = denied` and the log has `propose` with *"action-engine denied"*; **no `execute` row**. (b) **Failed:** a test-authored proposal (RS-8 test data, labelled) with an operation the adapter refuses is promoted **by the production path's CAS**, so `action.status = failed` and the log has `execution_failed`; **no `execute` row** |
| **V-7** | **Duplicate triggers do not create duplicate execution** | (a) The same real observation re-published (an outbox redelivery): one thought, one trigger, one `action` row. (b) **Two concurrent `promote_thought` calls** on one thought against real Postgres: exactly one trigger and one `action` row. (c) The same trigger envelope sent twice by a bus bound as `cognitive-state-engine` (the 4F.6 precedent): one `action` row, and `action-engine`'s replay |
| **V-8** | A **failed transport** creates **no false success** | (a) **No responder** on `action.execute`: `propose`, no `action` row, no `execute`. (b) **A silent responder** (a bound stand-in that never replies; the one permitted stand-in, for this case only): `timeout`, no `execute`. (c) **A transport fault** (the bus closed under the dispatch): a degraded reply, **no** log row, **no** `execute` |
| **V-9** | The trigger is **production-originated** | No test code on the V-1 … V-5 path calls `promote_thought` or `decide()`, or publishes `autonomy.decision.requested` (AST check). The input is a **real** companion observation of a **real** file write |
| **V-10** | The boundaries are unchanged | Registry 120; `PUBLIC_TOPICS` 18; nine gateway prefixes; `action-engine` and `capability-engine` diffs **empty**; stage 3 byte-identical |

### 15.1 The tiers

| Tier | What |
|---|---|
| **Unit** | The authoring table (every entry complete; authored ≥ classified, by parsing `risk.py` as text); `ProposedAction`'s new validation; `_execution_payload`'s merge (`operation` joined; `"operation"` in `parameters` refused); the outcome mapping over **every** `ActionStatus` value; the ingestion mapping |
| **Contract** | Payload additivity and `extra="forbid"`; codegen with zero drift; allow-lists exactly as ratified; F-4F7-1's control repaired (A-4FP-10); P-14 retargeted; no cross-engine import |
| **`real_infra`, per engine** | `cognitive-state-engine`: insert-if-absent and CAS races against real Postgres (V-7 (b)); ingestion from a bus **bound as `perception-engine`** (4F.7 P-15's precedent) through to a real trigger request. `autonomy-engine`: the mapping against a real bus, with a bound responder for `failed`/`denied`/silent (the halves) |
| **Composed stack** (A-4FP-12) | **V-1 … V-9**, with every engine real and a real input. The harness only writes a file, configures through production routes, and reads by SQL |

**CI is authoritative.** Docker is unavailable in the preparation environment.
Both carrying workflows are non-blocking by design (4F.8's F-4F8-12), so the
Slice Completion Record cites their conclusions **at the exact SHA**.

---

## 16. Negative controls

Protocol §9.2: each mutation must fail a named test.

| # | Mutation | Must fail |
|---|---|---|
| NP-1 | Record `EXECUTE` for a `failed` reply | V-6 (b); the unit mapping |
| NP-2 | Record `EXECUTE` for a `denied` reply | V-6 (a) |
| NP-3 | Drop `parameters` in `_execution_payload` (back to `{}`) | V-1, V-2 |
| NP-4 | Default a missing `operation` | Unit: absence means a suggestion; the structural no-default check |
| NP-5 | Allow `"operation"` inside `parameters` | `ProposedAction` validation |
| NP-6 | Author a risk below `action-engine`'s classification | The drift-guarded contract test |
| NP-7 | Replace the CAS with `move_layer` | V-7 (b) |
| NP-8 | Replace insert-if-absent with `upsert_thought` | V-7 (a); the repeat resets the layer |
| NP-9 | Promote on every observation, not only at creation | V-7 (a) |
| NP-10 | Persist a "triggered" marker | RS-6a's schema control |
| NP-11 | Add a subject, or a `PUBLIC_TOPICS` entry | V-10 |
| NP-12 | Change any `action-engine` file | V-10's diff check |
| NP-13 | Author a proposal whose parameters carry a path from the payload | The authoring-table test (FP-9) |
| NP-14 | Call `promote_thought` from `api/` | P-14's retained `api/` half |

**Flakiness:** every real-infrastructure and composed-stack test is run ≥ 10
times and reported.

---

## 17. Classification of the existing 4F.P deferred items

The four requested classes:

- **Req** — required for 4F.P;
- **Def** — explicitly deferred beyond 4F.P;
- **Doc** — documentation or verification only;
- **Rat** — requiring ratification.

| Item | Source | Class | Where |
|---|---|---|---|
| The promotion policy | RS-1c | **Req + Rat** | A-4FP-2 |
| The thought-ingestion mapping | RS-1c, RS-2b | **Req + Rat** | A-4FP-1 |
| The `ProposedAction` authorship rule | RS-1c, RS-2b | **Req + Rat** | A-4FP-3 |
| CAS on the promotion transition | RS-1c, RS-7 | **Req + Rat** | A-4FP-8 |
| Layer 2 logical deduplication | A-4F6-3 (DEFERRED to this slice) | **Req + Rat** | A-4FP-9 |
| A production caller of `promote_thought` (F-6) | 4F.6 §8.1, RS-11 | **Req + Rat** | A-4FP-10 |
| Operation and parameters authorship and propagation | FP-1 (new) | **Req + Rat** | A-4FP-4, A-4FP-5, A-4FP-6 |
| Real result handling and decision-log semantics | FP-2 (new) | **Req + Rat** | A-4FP-7 |
| K-4 — no Active Thought in production | TDD 4F.7 §15 | **Req** (resolved by P1) | V-4's composed run |
| Stage-3 configuration for real execution | A-4F8-5 | **Req + Rat** | A-4FP-11 |
| Composed-stack deployment (4F.8's D4) | A-4F8-10 | **Req + Rat** (moved forward) | A-4FP-12 |
| F-4F7-1 — control 11's vacuous schema check | 4F.7 §8.1 | **Req + Rat** (because 4F.P changes what it guards) | A-4FP-10 |
| 4F.6 F-2 — the 20 s reply wait | 4F.6 §8.1 | **Rat** (non-blocking: ratify as built at the Gate Review; it exceeds the 15 s dispatch bound, as required) | Gate Review |
| 4F.6 F-5 — `correlation_id` not reaching `action.execute` | 4F.6 §8.1 | **Doc** (amend §8 to the built chain, as recommended there; unchanged by 4F.P) | Gate Review |
| 4F.6 F-1 (reply registration), F-3, F-7 | 4F.6 §8.1 | **Doc** / Gate Review | — |
| 4F.6 F-4 — a redelivered `propose` replies degraded | 4F.6 §8.1 | **Def** (unreachable on core NATS, FP-6) | — |
| 4F.6's *"at-least-once"* premise | TDD 4F.6 §5.1, §13.1 | **Doc** (an additive correction at ratification, FP-6) | A-4FP-9 |
| TTL and stale-trigger semantics (A-4F6-4) | 4F.6 §16 | **Def** (every gate still runs; a stale trigger cannot escalate) | §21 |
| Persistent lost-trigger auditability, and FP-7's crash window | 4F.6 §16 | **Def** | §21 |
| `observability.py` packaging; the `correlation_id` logging convention; F-4F7-7 | 4F.6 §16; 4F.7 | **Def** | §21 |
| Part 6 INTERRUPTIONS promotion semantics; automatic demotion | TDD 4F §24.12; A-4FP-2 | **Def** | §21 |
| Focus-signal computation (K-5) | TDD 4F.7 §15 | **Def** | §21 |
| K-6 — no pagination on `/thoughts` | TDD 4F.7 §15 (*"revisit with 4F.P"*) | **Doc** (the thought count is recorded in the composed run; pagination is deferred unless the count demands it) | §21 |
| Doc 10's `world_model.context.changed → re-evaluate Focus` row | TDD 4F §24.13 item 2 | **Doc** (under A-4FP-1 (a), no such subscription is created; corrected at 4F closure, L-9) | L-9 |
| Exposing operation and parameters on the read surface | New | **Def** (A-4FP-14 default) | A-4FP-14 |

---

## 18. CF-9, CF-10 and CF-11

| | Status | 4F.P's contribution |
|---|---|---|
| **CF-9** | **OPEN** | The first **real** stage-3 pass through the policy surface (V-3). **Not closure evidence**: conditions 2 (citation) and 5 (documents) settle at 4F closure (TDD 4F §5.3) |
| **CF-10** | **OPEN** | **None.** Trust stays `UNAVAILABLE`, non-blocking and never a pass |
| **CF-11** | **OPEN** | **The production mechanism, and its composed evidence (V-9).** **Claim 3** (the end-to-end trigger-to-action acceptance) is **4F.8's**, run as AC-8. **Claim 4** is 4F closure's. **4F.P closes nothing by itself** (RS-1c) |

---

## 19. 4F.8 decisions that remain blocked until this contract is ratified

The candidates are proposed in TDD 4F.8 on `phase-4f8-tdd` @ `5a95475`. None is
ratified.

| 4F.8 candidate | Status relative to 4F.P |
|---|---|
| **A-4F8-3** (executability; the low-risk action) | **Blocked, and becomes settled** by A-4FP-3 … A-4FP-6 if they are ratified as recommended (§9) |
| **A-4F8-4** (the AC-8 trigger source: production only) | **Its decision can be ratified independently. Its execution is blocked** until 4F.P's production caller (A-4FP-10) is merged |
| **A-4F8-5** (the stage-3 configuration) | **Blocked, and answered once** by A-4FP-11. 4F.8 reuses it |
| **A-4F8-7** (the AC-8 evidence surface) | **Blocked.** What the decision log says for a Level-2 execution depends on A-4FP-7 |
| **A-4F8-8** (4F.8's SAD 15 exception) | **Blocked.** Its scope shrinks if A-4FP-12 moves D4 into 4F.P |
| **A-4F8-10** (deployment) | **Blocked, and largely absorbed** by A-4FP-12 |
| **4F.8's §11** (interface requirements on 4F.P) | Met by the recommended options: (1) a production-reachable promotion (A-4FP-10); (2) a CI-reproducible input (A-4FP-1); (3) an executable, low-risk proposal (T1); (4) two runs of one category, from two distinct files, because each creates a new identity (A-4FP-9); (5) no autonomy data read (RS-4b) |
| **A-4F8-1, A-4F8-2, A-4F8-6, A-4F8-9** (AC-7 and 4F scope) | **Not blocked by 4F.P.** A-4FP-1 (a) needs no `project_id`, so L-13 stays 4F.8's |

---

## 20. The dependency chain

```
4F.P  ratify A-4FP-1…13 → implement → composed real-execution evidence → merge into phase-4
  ↓   (4F.8's A-4F8-3/-5/-7/-8/-10 settle or rescope from 4F.P's ratification)
4F.8  re-verify its TDD against merged 4F.P → ratify A-4F8-* → AC-7 and AC-8 acceptance
  ↓   (CF-11 claim 3 evidenced here)
4F closure  L-1 Gate Review, L-2…L-22, CF-11 claim 4, CF-9 checked against §5.3, A-4F8-9
  ↓
Phase 4 Gate Review  AC-1…AC-8, CF-1…CF-11 dispositioned → GO / CONDITIONAL-GO / NO-GO
  ↓
one PR phase-4 → main, by merge commit, only after GO (master scope §16)
```

**Why 4F.P must precede 4F.8** (RS-1c, and now also FP-1):

- **Without 4F.P, AC-8 cannot honestly pass.** The trigger has no production
  producer. And even with a stand-in, no real action can execute and the log
  would say `EXECUTE` regardless.
- **4F.8 is an acceptance slice.** It must measure a path that exists, not
  build it.

---

## 21. What remains deferred after 4F.P

- **To 4F.8:**
  - AC-7 in full: latency, revocation (RS-3b), known-project correlation
    (L-13);
  - AC-8's acceptance run: Level 1 vs Level 2, in a browser;
  - CF-11 claim 3.
- **To 4F closure:**
  - L-1 … L-22;
  - CF-9's §5.3 check; CF-11 claim 4;
  - the 4F.6 F-1/F-2/F-3/F-5/F-7 Gate Review decisions;
  - the doc-10 row;
  - the unassigned 4F deliverables (4F.8's A-4F8-9).
- **Beyond 4F.P, OPEN or DEFERRED:**
  - TTL and stale-trigger semantics;
  - persistent lost-trigger auditability, including FP-7's crash window;
  - `observability.py` and the `correlation_id` logging convention;
  - automatic demotion and INTERRUPTIONS;
  - Focus signals;
  - further ingestion sources and authoring entries (each a new
    ratification);
  - model-based authoring;
  - executing approved Level-1 suggestions (FP-8);
  - exposing the new fields on the read surface (A-4FP-14);
  - `/thoughts` pagination;
  - F-4 and FP-13.
- **Beyond Phase 4:** CF-10; L-15, L-17, L-18.

---

## 22. Implementation and closure sequence

**Nothing here starts without the user's explicit GO.**

1. **Ratify A-4FP-1 … A-4FP-13**, and confirm or change A-4FP-14.
2. At ratification, add the **additive notes** each Amends candidate requires,
   each dated and with the original wording preserved:
   - TDD 4F.6 §4.7 (A-4FP-4, A-4FP-5);
   - §5.1/§13.1 (FP-6);
   - §19 (A-4FP-6, A-4FP-7);
   - TDD 4F.5 §10/§22.2 (A-4FP-6, A-4FP-7);
   - TDD 4F.7's P-14 and P-11 (A-4FP-10, A-4FP-1);
   - TDD 4F §24 (RS-3a's allow-list, A-4FP-1).
3. **Cut the 4F.P implementation branch** from the then-current `phase-4` head
   (master scope §16). **Not created by this document.**
4. **Update TDD 4F.8 additively** for §19's settlements. That is 4F.8's
   re-verification step, **not** part of this change.
5. Build layer by layer: contracts → `cognitive-state-engine` (model, table,
   ingestion, CAS, driver) → `autonomy-engine` (fields, merge, mapping) →
   composed stack → tests → controls.
6. Run the negative controls, the flakiness runs and the full protocol gate set.
7. Write the **Slice Completion Record**, with its ledger and the A-4FP-13
   exception.
8. **A PR only when asked.**
9. **Merge on explicit authorization**, then 4F.8 (§20).

---

## 23. SLOC budget

**Base: 47,433** (4F scope, at `9d2d636`). **Headroom 2,567.**

| Component | Estimate (not measured) |
|---|---|
| `nova-contracts` payload fields | 10 – 30 |
| `cognitive-state-engine`: model fields, authoring table, ingestion mapping and orchestration, insert-if-absent, CAS, handler, wiring | 200 – 380 |
| `autonomy-engine`: `DecisionRequest` fields, the merge, outcome mapping, one member | 50 – 110 |
| Compose, harness, tests | **0** (outside every scope) |
| **4F.P total** | **260 – 520** |

After 4F.P, and 4F.8's estimate of 180 – 450, **the projected 4F scope is
47,873 – 48,403, under 50,000.** If it is crossed, TDD 4F §17's hard gate
applies unchanged.

---

## 24. Risks

| Risk | Mitigation |
|---|---|
| The first real composition surfaces defects beyond FP-1 | That is its purpose. Each is reported, not absorbed (4F.5 §12's precedent) |
| **NOVA acts in production for the first time** | Only through the ratified table. T1 is **read-only** and `negligible` in `action-engine`, and every 4F.5 gate and stage 3 still run |
| An authoring entry understates risk | Rule 1 (authored ≥ classified), drift-guarded |
| `IMMEDIATE` accumulates, with no demotion | Disclosed (A-4FP-2). Focus capacity bounds the display; demotion is deferred |
| At-most-once ingestion (as K-1): an observation dispatched while `cognitive-state-engine` is down is missed | Disclosed. No replay or durable stream is decided here |
| The composed stack is non-blocking in CI | Conclusions are cited at the exact SHA |
| The contract change reaches a stale consumer | Both engines are deployed together. The consumer is `extra="forbid"`, so a mismatch is a loud rejection, never a silent drop |

---

## 25. SAD 15 §9.0 — the 33 required contents

| # | Item | Where |
|---|---|---|
| 1 | Overall architecture | §5 |
| 2 | Core responsibilities | §1 |
| 3 | What does not belong here | §2 |
| 4 | Internal execution flow | §5, §11 |
| 5 | Complete data flow | §5 |
| 6 | Domain model | §10 |
| 7 | State transitions | §13 (CAS); attention ladder unchanged |
| 8 | APIs | §14 (none) |
| 9 | Event Bus RPCs | `autonomy.decision.requested` (+2 fields); `action.execute` (unchanged) |
| 10 | Published events | None new |
| 11 | Consumed events | `perception.workspace.observed` (new consumer) |
| 12 | Database schema | §14 (no migration) |
| 13 | Repository layer | A-4FP-1, A-4FP-8 |
| 14 | Dependency boundaries | §5, §6.1 |
| 15 | ADR compliance | ADR-004 (no import; the text-parse drift test); ADR-024 (additive fields); ADR-025 (server-side identity); ADR-032 (stage 3 unchanged) |
| 16 | Bible compliance | Part 6 (layers, adjacent moves); Part 12 (unchanged stages); Part 14 l.101–107 |
| 17 | Human Interaction Principles | No new UI. A suggestion's title and detail are authored text |
| 18 | Personality Specification | **N/A** |
| 19 | Failure handling | §12 |
| 20 | Recovery mechanisms | None added; no retry anywhere |
| 21 | Observability | Existing loggers (packaging OPEN) |
| 22 | Logging strategy | Each ingestion, promotion, trigger and recorded outcome |
| 23 | Metrics | None added |
| 24 | Performance goals | None ratified |
| 25 | Security considerations | §6.1; A-4FP-3 rules; FP-9; A-4FP-11 |
| 26 | Scalability | Single user (ADR-025); §24 |
| 27 | Testing strategy | §15, §16 |
| 28 | Future extension points | New authoring entries or ingestion sources, each ratified |
| 29 | Known limitations | FP-7, FP-13; §24 |
| 30 | Technical debt | FP-7; no demotion |
| 31 | Architectural risks | §24 |
| 32 | Tradeoffs | §8 |
| 33 | Explicit implementation order | §22 |

---

## 26. Consistency audit — before commit

Checked against `9d2d636`, and against TDD 4F.8 at `phase-4f8-tdd` @
`5a95475`. **An Amends candidate is a disclosed proposal, not a conflict.**

| Checked against | Result |
|---|---|
| **Master scope** §1.1, §5 (4F slice registration: *"4F.P … owns … production promotion driver, thought ingestion … `ProposedAction` authorship … must ratify five things"*), §6, §13, §15, §16 | **Consistent.** All five RS-1c items are candidates (§17). No AC is reworded. The milestone set is unchanged. No panel is added. The branch rules are respected: a documentation branch only |
| **D-1 … D-8** | Consistent. No prefix (D-6); no auth path (D-3) |
| **D-4D-1, D-4D-2** | Consistent. No subject without need; CF-9 not closed |
| **D-4F-1 … D-4F-9; RS-5** | Consistent. Outbox unchanged; no gateway prefix; no cognitive-state subject (D-4F-6); `cognitive-state-engine` publishes only the trigger (D-4F-9); §6.2's prohibitions intact, since the proposal still flows only through `autonomy-engine` |
| **TDD 4F §7.3, §13, §14** | Consistent. No `action-engine` bypass. Consumes perception *"via the Event Bus only"*. Writes only its own schema |
| **4F.5: D-4F5-1, D-4F5-3, D-4F5-4, §22.7, §22.8** | **Unchanged** |
| **4F.5: D-4F5-2** | **Amended by A-4FP-6** (the operation joins the execution fields, with the same absence rule). Disclosed |
| **4F.5: §10's audit row, X-11** | **Amended by A-4FP-7** (`EXECUTE` only for `completed`). Disclosed |
| **4F.6: A-4F6-1, A-4F6-3 Layer 1, A-4F6-5, A-4F6-7, §19 rows 1–12, 14–18** | **Unchanged**: no TTL, no retry, no audit table, no new autonomy route |
| **4F.6: A-4F6-2a** | **Amended by A-4FP-4** (two fields) **and A-4FP-5** (`execution_target`'s meaning). Disclosed |
| **4F.6: §19's contract count, row 13, row 20** | **Amended by A-4FP-6 and A-4FP-7.** Disclosed. Those rows bounded 4F.6's own implementation |
| **4F.6: A-4F6-3 Layer 2 (DEFERRED to 4F.P)** | **Resolved by A-4FP-9**, as the deferral required |
| **4F.6: §5.1, §13.1's at-least-once premise** | **Contradicted by source (FP-6).** Corrected additively at ratification. Layer 1 is kept |
| **4F.7: RS-1b, RS-4a–RS-4d, RS-6a, RS-7, RS-8, A-4F7-1, A-4F7-2** | Consistent. The read surface stays read-only (A-4FP-14). No triggered state. CAS is proposed here for ratification (A-4FP-8), as RS-7 required. Stand-ins appear only as labelled test data (V-6 (b), V-8 (b)) and never count toward CF-11 |
| **4F.7: RS-3a's allow-list "exactly"** | **Amended by A-4FP-1** (two subjects). Disclosed |
| **4F.7: P-14** | **Retargeted by A-4FP-10.** Disclosed; the `api/` half is kept |
| **TDD 4F.8 (PREPARED)** | Consistent with its §11 interface requirements. **It settles, or rescopes, A-4F8-3, -5, -7, -8 and -10 by proposal only** (§19). No A-4F8 candidate is ratified |
| **The `action-engine` contract** | **Unchanged**: `ActionExecuteRequestPayload`, `ActionResultPayload`, `ActionStatus`, all twelve stages, the `operation` requirement, risk classification, stage 3 and the approval loop. **4F.P only supplies what the contract already requires, and reads what it already reports** |
| **Protocol** §0.3.4, §0.3.6, §13.3 | Every change is additive. No scope is narrowed. Every ambiguity is stopped and reported (§8) |

**No unreported conflict remains.** **Six candidates amend existing
ratified text.** Each is disclosed above and named in §22 step 2, and none
takes effect without ratification:

- A-4FP-1 (RS-3a's allow-list);
- A-4FP-4 and A-4FP-5 (A-4F6-2a);
- A-4FP-6 (D-4F5-2; 4F.6 §19's contract count and row 20; 4F.5's builder);
- A-4FP-7 (4F.5 §10 and X-11; 4F.6 §19 row 13);
- A-4FP-10 (4F.7's P-14).

**Two further candidates touch 4F.8 proposals, which are not ratifications:**
A-4FP-11 answers A-4F8-5, and A-4FP-12 moves 4F.8's proposed D4 and A-4F8-10
forward. Neither changes any ratified text.

**Scope-index note.** This change adds this document's row to master scope §17.
TDD 4F.8's branch (`phase-4f8-tdd` @ `5a95475`) also appends to §17 and to §5,
and neither branch is on `phase-4`. **When both land, both rows are kept**, and
the textual overlap is resolved by keeping every added line. No existing wording
on either side is changed.

---

## 27. Status

**PREPARED 2026-09-27. NOT RATIFIED. NOT implementation-ready.**

- **Blocking:** A-4FP-1 … A-4FP-13. **A-4FP-14** has a default.
- **A-4F8-3 is determined (§9), not ratified.**
- **CF-9, CF-10 and CF-11 stay OPEN.**
- **4F.P is not started, and 4F.8 is not started.** No implementation branch
  exists. **No production file, test, migration, Dockerfile, workflow,
  contract or package was modified** to prepare this document.
