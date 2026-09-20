# TDD 4F.5 — Autonomy Level 2
## Selectable, policy-permitted, single dispatch, and `action.execute`'s first producer

**Status:** **DESIGN PREPARATION. NOT RATIFIED.** §20 lists **four** questions
that must be answered before implementation begins; three of them change what
gets built and one changes a security semantic.
**Date:** 2026-09-20
**Branch:** `phase-4f5-tdd`, cut from `phase-4` at `9ec221fc00c8a96a3189cd34b7e6df2fdfe78bc9`
(the 4F.4 merge commit). **`phase-4f.5` does not exist and must not be created
before ratification.**
**Protocol:** [`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md),
sha256 `21185dd1b2a43e87eac0a52aa5e53c8e8bbb01223014dc2a48408bbb0478de6a`,
1131 lines, read from `origin/main` and verified in this session.

**This is a slice TDD, subordinate to
[TDD 4F](06-tdd-4f-companion-and-cognitive-state.md).** 4F is one milestone with
eight slices (TDD 4F §18); this document does not replace it, restate its
ratified decisions, or reopen anything it settled. Where the two disagree, TDD 4F
governs and the disagreement is recorded in §20 rather than resolved here.

**Every claim below about current behaviour was verified against the repository
at `9ec221f` in this session** — a file read, a grep, or a schema inspection.
Nothing is taken from the roadmap description (protocol §0.3 principle 1).

---

## 1. Purpose and scope

TDD 4F §18's row for this slice, verbatim:

> **4F.5** | Level 2: selectable, policy-permitted, single dispatch,
> `action.execute` publication | *Proves:* **The five states, separately**

### 1.1 The five states, and which ones 4F.5 owns

TDD 4F §6 decomposes Autonomy Level 2 into five separable states. **Verified at
`9ec221f`**, each is in exactly the condition §6 predicted:

| # | State | Verified current condition at `9ec221f` | Owner |
|---|---|---|---|
| **1** | **Defined** | **Already true.** `DEFINED_LEVELS = {0, 1, 2}` (`domain/models.py:86`) | Nothing to do |
| **2** | **Selectable** | **False.** `SELECTABLE_LEVELS = {0, 1}` (`models.py:92`); `require_selectable()` raises `LevelNotSelectableError` → **422** | **4F.5** |
| **3** | **Policy-permitted** | **Machinery exists, unreachable.** `PolicyEffect` has exactly `DENY` and `REQUIRE_APPROVAL`; `evaluate_gates()` **hardcodes `requires_approval=True`** on the pass path and discards `policy_result.requires_approval` | **4F.5 — see §20's A-4F5-1** |
| **4** | **Triggered** | **Nothing. CF-11.** Re-verified: **zero** production callers of `decide()`, zero of `insert_suggestion`, and no create-suggestion route | **4F.6 — NOT 4F.5** |
| **5** | **Executing** | **Nothing.** `permits_execution()` returns `False` unconditionally; `_forbid_execution()` raises if it ever returns `True`; `PUBLISHABLE_SUBJECTS` is **empty** | **4F.5** |

**4F.5 owns states 2, 3 and 5. It does not own state 4.**

### 1.2 The consequence that must be stated plainly

**After 4F.5, the Level-2 execution path will have no production caller.** State
4 is CF-11 and belongs to 4F.6. `decide()` has zero production callers today and
will still have zero after this slice.

This is **not** a defect and **not** a scope shortfall — TDD 4F §18 assigns this
slice *"the five states, separately"*, and separability is precisely the point.
But it dictates how 4F.5's evidence is obtained: the dispatch path is exercised
by driving `decide()` **directly** against real infrastructure, not through a
production trigger. **AC-8's end-to-end run is 4F.8's**, and no document produced
by this slice may claim otherwise.

### 1.3 What 4F.5 is not

**4F.5 does not close CF-11**, does not close CF-9, does not close CF-10, and
does not run AC-8. See §18 and §19.

---

## 2. Dependencies

### 2.1 On completed 4F slices

| Slice | Dependency | State |
|---|---|---|
| **4F.4** | **CF-9's write surface.** Stage 3 of `action-engine`'s pipeline denies every action at threshold 1.0 unless an `IdentityConfidencePolicy` row exists. **A Level-2 `action.execute` that reaches `action-engine` is denied at stage 3 without one** | **Merged** at `9ec221f`. `GET`/`PUT`/`DELETE /v1/action/identity-confidence-policy` exists and is real-Postgres proven |
| 4F.1 | `cognitive-state-engine` domain + persistence | Merged. **Not on this slice's path** — the trigger is 4F.6's |
| 4F.2 | Perception extension, `perception.workspace.observed` | Merged. **Not on this slice's path** |
| 4F.3 | `nova-companion` | Merged. **Not on this slice's path** |

**Only 4F.4 is a genuine dependency.** The other three are named so that their
absence from the dependency list is a stated finding rather than an oversight.

**4F.5's own tests must write an identity-confidence policy through 4F.4's
production API** to get past stage 3 — they must not insert the ORM row
directly, for the same reason 4F.4's own evidence could not (ADR-032).

### 2.2 On existing architecture — all pre-existing, verified at `9ec221f`

| Dependency | State |
|---|---|
| `AutonomyLevel`, `DEFINED_LEVELS`, `SELECTABLE_LEVELS` | **Exist** — `domain/models.py:57, 86, 92` |
| `require_selectable`, `permits_execution`, `_forbid_execution` | **Exist** — `domain/levels.py:66, 95`; `domain/decision.py:119` |
| `evaluate_gates`, `GateReport`, `decide` | **Exist** — `domain/decision.py:161, 135, 218` |
| `GateReport.requires_approval` | **Exists**, defaults `True`, *"recorded for the log now so that when 4F enables Level 2 the signal is already being carried"* |
| `DecisionOutcome.EXECUTE` | **Declared and unreachable** — `models.py:102`. 4F.5 makes it reachable |
| `PolicyEffect` | **Exists** with exactly `DENY`, `REQUIRE_APPROVAL`. **No `ALLOW`**, deliberately |
| `action.execute` contract | **Exists** — `ActionExecuteRequestPayload`, `@register_payload("action.execute")`, `nova_contracts/events/action.py:151` |
| `action.execute` consumer | **Exists** — `action-engine` serves it as a **request/reply RPC**; `SUBSCRIBABLE_SUBJECTS` contains it; `main.py:147` |
| `PUBLISHABLE_SUBJECTS` (autonomy) | **Exists but empty**, carrying a `TODO` placeholder. `BoundEventBus` is constructed and *"never used"* |
| `/v1/autonomy` gateway prefix | **Exists** — `api-gateway/domain/routing.py`, forwarded 1:1 (D-6). **No gateway change needed** |
| `PUT /v1/autonomy/level` | **Exists**, identity from `settings.primary_user_id`, returns 422 for Level 2 |
| `autonomy-engine` real-infra tier | **Exists** — `real-infra-checks.yml` matrix, line 98 |

### 2.3 Data sources — Digital Twin, Memory, Perception

**None of the three is a data source for 4F.5, and none is read.**

| Source | 4F.5's relationship |
|---|---|
| **Digital Twin** (Bible Part 16, `digital-twin-engine`) | **Not read.** No domain, evidence row or confidence score is consulted. Level-2 admission is decided by the Policy Engine and Permission Matrix only |
| **Memory** (`memory-engine`, `MemoryRecord.project_id`) | **Not read.** `known_projects` correlation is **L-13** and belongs to the trigger path, not the dispatch path |
| **Perception** (`perception-engine`, `perception.*`) | **Not read.** `autonomy-engine`'s `SUBSCRIBABLE_SUBJECTS` is empty and **stays empty** |

**This is a deliberate boundary, not an omission.** TDD 4F §6.2 confines the
evidence-bearing inputs to the *trigger* (`cognitive-state-engine`, 4F.6);
`autonomy-engine` is the control plane and decides on the `DecisionRequest` it is
handed. **Reading Digital Twin, Memory or Perception state inside
`autonomy-engine` would collapse an ownership boundary** and is forbidden here.

`action-engine`'s stage 3 does consult identity confidence — but it does so
**inside `action-engine`**, over its existing `IdentityPort` RPC, exactly as it
does today. 4F.5 changes nothing about that.

---

## 3. Authoritative source mapping

| Requirement | Source |
|---|---|
| The slice's contents and proof | TDD 4F **§18**, 4F.5 row |
| The five states and their separability | TDD 4F **§6** |
| `cognitive-state-engine` is the trigger owner, not this slice | TDD 4F **§6.2**, **D-4F-3** |
| Where each gate applies; deny-only; Trust after | TDD 4F **§6.3** |
| Where approval remains required | TDD 4F **§6.4** |
| What Level 2 actually permits | TDD 4F **§6.5** |
| The single-dispatch rule | TDD 4F **§6.6** |
| `action.execute` gains its first producer; `PUBLISHABLE_SUBJECTS`; control 8 retired | TDD 4F **§11.2** |
| No new subject, no `PUBLIC_TOPICS` change, no `autonomy.*` subject | TDD 4F **§11.4** |
| `autonomy-engine` gains no new route | TDD 4F **§12** |
| Negative and security controls 3, 4, 5, 6, 7, 12, 13 | TDD 4F **§16.1** |
| *"Enabling Level 2 is milestone 4F (decision D-1) and requires an execution path, not a flag"* | TDD 4D **D-1**, quoted in `levels.py` and `decision.py` |
| Deny wins; an empty policy set is not permissive; no `allow` effect | TDD 4D **§6**, `domain/policy.py` doctrine items 1–4 |
| AC-8's clauses and their dependencies | TDD 4F **§4.2** |
| Slice produces a completion record with a ledger, not a Gate Review | Protocol **§0.1**, **§0.2** |

---

## 4. Deliverables

| # | Deliverable | Where |
|---|---|---|
| 1 | **Level 2 becomes selectable** — add `AutonomyLevel.ASSISTED` to `SELECTABLE_LEVELS`; `PUT /v1/autonomy/level` stops returning 422 for `2` | `domain/models.py` |
| 2 | **`permits_execution` becomes level-aware** — returns `True` for Level 2 and above, `False` below; `_forbid_execution` is **replaced**, not deleted, by the guard §16 control 3 requires | `domain/levels.py`, `domain/decision.py` |
| 3 | **A policy effect that affirmatively permits auto-execution** — bounded to LOW risk, opt-in, fail-closed by absence | `domain/models.py`, `domain/policy.py` — **subject to §20's A-4F5-1** |
| 4 | **The single dispatch point** — one read of `GateReport.requires_approval`; `True` → suggestion (unchanged Level-1 path), `False` → `action.execute` | `domain/decision.py` |
| 5 | **`action.execute`'s first producer** — an outbound RPC port and its Event Bus adapter; `"action.execute"` added to `PUBLISHABLE_SUBJECTS` | `domain/ports.py`, new `clients/` module, `events/published.py`, `main.py` |
| 6 | **`DecisionRequest` carries what the payload requires** — the execution fields `ActionExecuteRequestPayload` mandates | `domain/decision.py` — **subject to §20's A-4F5-2** |
| 7 | **Tests** — unit, integration, and real-Postgres/real-NATS evidence §12 requires | `autonomy-engine/tests/` |

**Seven deliverables. No migration, no new table, no new ORM model, no new Event
Bus subject, no `PUBLIC_TOPICS` change, no gateway change, no new REST route.**

---

## 5. Architectural boundaries and ownership

| Boundary | 4F.5's position |
|---|---|
| **Control plane** | `autonomy-engine` remains the decision owner. It decides; it never executes |
| **Execution boundary** | `action-engine` remains the execution/approval owner. Every Level-2 action runs its **unchanged** lifecycle — risk estimation, the ADR-032 identity gate, approval where required, the append-only log |
| **Trigger** | **`cognitive-state-engine`, and not this slice.** 4F.5 adds no caller of `decide()` |
| **Trust** | CF-10 unchanged. The Trust Engine stays **unavailable**; `score=None`, status `UNAVAILABLE`, never coerced to `0.0` or a default |
| **Gate order** | Unchanged and binding: Policy → Permission → Trust → Decide. Deny-only gates stay deny-only |
| **Ownership of policy state** | `autonomy-engine` keeps sole ownership of `Policy`. **No duplicate policy store**, and `action-engine`'s `IdentityConfidencePolicy` is a different thing with a different owner — the two are not merged, mirrored or cross-read |
| **Event Bus** | **No new subject.** `action.execute` is an existing registered contract acquiring its first producer. `SUBSCRIBABLE_SUBJECTS` stays **empty** |
| **`PUBLIC_TOPICS`** | **No change. Exactly 18** |
| **Browser** | **No new browser exposure.** No `autonomy.*` subject, no ws-gateway change, no new gateway prefix |
| **Cross-engine** | **No engine-to-engine import and no engine-to-engine HTTP.** The only cross-engine contact is the `action.execute` RPC over the bus (ADR-004, ADR-006) |
| **Identity** | Server-derived from `Settings.primary_user_id` everywhere it already is. **No new caller-supplied `user_id` route**, and single-user trusted-local is preserved |

### 5.1 The one disclosed retirement

Adding `"action.execute"` to `PUBLISHABLE_SUBJECTS` **necessarily retires 4D's
control 8** in its present form — *"this engine never calls the bus at all."*

TDD 4F §11.2 anticipated and authorised this: **"Disclosed, not silent"**, and
§16 control 6 replaces it with the tighter property: ***`autonomy-engine` may
publish `action.execute` and nothing else.*** 4F.5 must implement that
replacement control, not merely delete the old one.

---

## 6. Data flow

```
[4F.6's trigger — NOT THIS SLICE]
   → DecisionRequest
   → autonomy-engine decide()                      [control plane]
        _require_execution_path(level)             [replaces _forbid_execution]
        evaluate_gates():
            Policy Engine      (deny-only; deny wins; may PERMIT auto-execute)
            Permission Matrix  (deny-only)
        → GateReport{denied, requires_approval, ...}
        Trust read             (CF-10: UNAVAILABLE, never a number)
        ── THE SINGLE DISPATCH POINT ──
        reads GateReport.requires_approval, once
             ├── True  → Suggestion + DecisionOutcome.PROPOSE      [Level 1, unchanged]
             └── False → action.execute RPC + DecisionOutcome.EXECUTE   [Level 2, new]
   → action-engine                                 [execution boundary owner]
        stage 3: ADR-032 identity gate  ← needs 4F.4's policy row
        → executed | denied | pending approval
   → reply recorded on the decision log            [subject to A-4F5-3]
```

**Everything upstream of the dispatch point is identical between a Level-1 and a
Level-2 run** — same request shape, same gate order, same trust read, same log
entry construction. §16 control 4 asserts the two runs produce the same call
sequence up to that point. That is what makes AC-8's *"no code path differs"*
literally true rather than rhetorically true.

---

## 7. API contracts

**No new route. No changed route shape. No new gateway prefix.**

| Surface | Change |
|---|---|
| `PUT /v1/autonomy/level` | **Behaviour only**: `{"level": 2}` returns **200** instead of **422**. No schema change — `SetLevelRequest.level` is already an `int` |
| `GET /v1/autonomy/level` | **Behaviour only**: Level 2's entry in the levels list reports `selectable: true` |
| `POST`/`PATCH /v1/autonomy/policies` | **Vocabulary only**: `PolicyCreateRequest.effect` is typed `PolicyEffect`, so a new effect value widens the accepted enum **without a route or schema-shape change** (subject to A-4F5-1) |
| `api-gateway` | **Unmodified.** `/v1/autonomy` already forwards the whole subtree 1:1 |
| `ws-gateway` | **Unmodified** |

**Identity stays server-derived.** Every route above already resolves
`state.settings.primary_user_id`; 4F.5 adds no parameter, body field or header
through which a caller could name a different user.

---

## 8. Event Bus contracts

| Invariant | Required at closure |
|---|---|
| **New subjects** | **0** |
| Registered subjects | **119**, unchanged — counted from the runtime registry, not by grepping decorators (TDD 4F.3 §21.1) |
| `PUBLIC_TOPICS` | **exactly 18**, byte-identical |
| `autonomy-engine` `PUBLISHABLE_SUBJECTS` | **`{"action.execute"}` — exactly one entry, and nothing else** |
| `autonomy-engine` `SUBSCRIBABLE_SUBJECTS` | **empty**, unchanged |
| `world-model-engine`, `ws-gateway`, `api-gateway`, `nova-contracts` | **0 files changed** |

### 8.1 `action.execute` is an RPC, and `PUBLISHABLE_SUBJECTS` is the right list

Verified, because the distinction matters and the word *"publish"* in TDD 4F
§11.2 could be read either way:

- `action.execute` is **request/reply**. `nova_contracts/events/action.py:13`:
  *"`action.execute` is the request/reply RPC `action-engine` serves now"*, with
  `ActionResultPayload` as the reply.
- `PUBLISHABLE_SUBJECTS` governs **both** `.publish()` and `.request()`.
  `action-engine`'s own `events/published.py` says so explicitly: *"listed here
  because `BoundEventBus.publish()` enforces this same allow-list, identically to
  how `.request()` does for outbound RPCs."*

So 4F.5 uses **`.request()`**, and `"action.execute"` belongs in
`PUBLISHABLE_SUBJECTS`. TDD 4F §11.2's instruction is correct as written; this
section records *why*, so the implementation does not reach for `.publish()` and
silently lose the reply. **How the reply is handled is A-4F5-3.**

### 8.2 What 4F.5 must not do

No `autonomy.*` subject. No `TrustMetric` subject or RPC — **CF-10 stays open**.
No new `memory.*`, `digital_twin.*` or `perception.*` subject. No wildcard
widening. **No `PUBLIC_TOPICS` entry of any kind.**

---

## 9. Persistence, migrations and ORM

**No migration. No new table. No new ORM model. No ORM column change.**

This is not an aspiration — it is a verified property of the existing schema:

| Fact | Verified at `9ec221f` |
|---|---|
| `autonomy.policy.effect` | **`TEXT NOT NULL`** (`alembic/versions/0001_*.py:48`). The ORM comment states it directly: *"`effect` is `TEXT` holding a `PolicyEffect` value … no CHECK constraint pins the"* vocabulary |
| `autonomy.decision_log.outcome` | **`TEXT`** (line 121) |
| CHECK constraints in the `autonomy` schema | **Zero.** `grep -n "CHECK" services/autonomy-engine/alembic/versions/*.py` → no matches |

**Therefore a new `PolicyEffect` value and a newly-reachable
`DecisionOutcome.EXECUTE` both persist through the existing columns with no
schema change whatsoever.** Any implementation that reaches for a migration has
misread the schema.

`autonomy.autonomy_level_setting.level` is `SMALLINT`; Level 2 already fits, and
`DEFINED_LEVELS` already contains it.

---

## 10. Security, identity and fail-closed behaviour

**This is the most security-sensitive slice in 4F.** It is the one that makes
NOVA act without being asked. Every control below exists for that reason.

| Concern | Position |
|---|---|
| **Fail-closed on absence** | **Absent policy means approval, never execution** (TDD 4F §6.4). An empty policy set must produce `requires_approval = True`. This is the central property, and **A-4F5-1 exists because the current code cannot express it without a decision** |
| **Risk ceiling** | **LOW risk only.** Level 2 must never auto-execute at `negligible`… wait — see §10.1. Above LOW, approval is required **at any policy setting and any level** (§16 control 5) |
| **Deny still wins** | A matching `DENY` policy ends the pipeline before any auto-execute consideration. No effect, new or existing, may overturn a deny |
| **Flag alone is never enough** | §16 control 3: making `permits_execution` return `True` while the dispatch publication is removed **must still fail**. The replacement guard must assert the execution path exists, not merely that the flag is set |
| **Identity** | Server-derived `primary_user_id` throughout. Single-user trusted-local preserved. `DecisionRequest.user_id` is set by the caller *inside the trust boundary*, never from an HTTP body |
| **`action-engine` stage 3** | **Byte-identical** (§16 control 13). Absent identity-confidence policy still denies at 1.0. 4F.5 does not touch `action-engine` at all |
| **Trust** | CF-10 unchanged: `UNAVAILABLE`, `score=None`, never a default number, never a gate |
| **Browser reachability** | None added. No new prefix, no new public topic, no socket |
| **Audit** | Every Level-2 decision writes a `DecisionLogEntry` with `outcome=EXECUTE`, the policy checks that permitted it, and the level. **The decision log is the audit trail**, and it already exists |

### 10.1 A precision the Bible's wording requires

Bible Part 14 names Level 2 *"Low risk actions execute automatically."* `RiskLevel`
has five values: `negligible`, `low`, `moderate`, `high`, `critical`.
*"Low risk"* in the Bible's sense covers **`negligible` and `low`** — the tiers at
or below `low` — not `low` alone. `risk_at_least`/`risk_at_most` already exist in
`domain/risk.py` to express this.

**The ceiling is `low`, inclusive, and `moderate` and above always require
approval.** This is stated here because reading *"low"* as an equality test would
leave `negligible` requiring approval while `low` did not — an incoherence, and
the reading a careless implementation would fall into.

---

## 11. Acceptance criteria

Measurable, defined before implementation. Each is a claim with a stated proof.
Numbered `X-n` to avoid collision with 4F.4's `W-n`.

| # | Claim | Proof required |
|---|---|---|
| **X-1** | **Level 2 is selectable.** `PUT /v1/autonomy/level {"level": 2}` returns **200** and persists, in real Postgres | Real-infra test through the production route; `GET` reads back `2` |
| **X-2** | **Level 3–5 still return 422**, with the reason distinguishing "defined but not enabled" from "no defined semantics" | The existing distinction must survive; a test per level |
| **X-3** | **A policy-permitted LOW-risk request at Level 2 dispatches `action.execute`** | Real-infra test: real `decide()` → real Event Bus → the RPC is observed with the correct payload |
| **X-4** | **An identical request at Level 1 produces a suggestion and no RPC** | Same request, same policies, level changed. **The negative half of AC-8** |
| **X-5** | **Absent policy at Level 2 requires approval and dispatches nothing** | **The fail-closed control, and it is mandatory.** Empty policy set → suggestion, not execution |
| **X-6** | **`moderate` and above never auto-execute**, at any policy setting, at Level 2 | Parametrized over every tier above `low`, with a permitting policy present |
| **X-7** | **A `DENY` policy beats an auto-execute policy** | Both match the same request; the outcome is `DENY` and no RPC is made |
| **X-8** | **No code path differs up to the dispatch point** | Level-1 and Level-2 runs recorded through a spy and asserted to produce the **same call sequence** up to the single read of `requires_approval` |
| **X-9** | **Level 2 cannot execute by flag alone** | With the dispatch publication removed, forcing `permits_execution` `True` **still fails** |
| **X-10** | **`autonomy-engine` publishes `action.execute` and nothing else** | `PUBLISHABLE_SUBJECTS == {"action.execute"}`, asserted; plus a bus-level rejection test for any other subject |
| **X-11** | **The decision log records the Level-2 execution** | `outcome=EXECUTE`, the permitting policy checks, and the level — read back from real Postgres |
| **X-12** | **CF-10 is still unresolved** | 4E's five sub-properties re-asserted verbatim; trust is `UNAVAILABLE`, never `0.0` |

**X-5, X-6, X-7 and X-9 are the ones that matter most.** A Level-2 implementation
that auto-executed slightly too eagerly would satisfy X-1, X-3 and X-11 and still
be a serious security defect.

### 11.1 Negative and security tests — defined before implementation

1. Empty policy set at Level 2 → approval, no RPC (X-5).
2. Policy set containing only a non-matching permit → approval, no RPC.
3. `moderate`, `high`, `critical` with a permitting policy → approval, no RPC (X-6).
4. `DENY` + permit, both matching → `DENY`, no RPC (X-7).
5. Permission-gate denial at Level 2 → deny, no RPC.
6. A policy evaluation that raises → deny, no RPC (the existing fail-closed path).
7. Flag-only Level 2 with dispatch removed → fails (X-9).
8. Any subject other than `action.execute` → `SubjectNotAllowedError` (X-10).
9. `SUBSCRIBABLE_SUBJECTS` still empty; registry still 119; `PUBLIC_TOPICS` still 18.
10. `action-engine`, `perception-engine`, `world-model-engine`, `ws-gateway`,
    `api-gateway`, `nova-contracts` diffs **empty**.
11. No migration file added; no ORM model added or altered.

---

## 12. Real-infrastructure requirements

`autonomy-engine` is **already** in `real-infra-checks.yml`'s matrix (line 98),
so this slice adds no CI matrix row.

| Requirement | |
|---|---|
| **Mandatory tier** | X-1, X-3, X-5, X-11 are **only decidable against real Postgres and a real Event Bus**. A fake repository and a fake bus would prove the fakes agree with each other |
| Fixtures | The established `postgres_container` + `run_alembic_upgrade` pattern already used by `test_repository_real_postgres.py` |
| **The level change must go through the production route** | Not by writing the settings row directly |
| **The RPC must cross a real bus** | A real NATS connection, as 4F.3's workspace E2E already does. An in-memory bus is acceptable **only** for the pure-unit dispatch-ordering tests, never for X-3 |
| **Stage 3 must not be faked** | Any test that asserts the action was *executed* rather than merely *dispatched* must write 4F.4's identity-confidence policy **through its production API** and let the real stage 3 run |
| **The `postgres_session_factory` rollback fixture is wrong here** | It binds sessions to one connection inside a rolled-back transaction, so writes never commit and are invisible to another connection — both wrong when the claim is persistence. Compose the production `create_engine`/`create_session_factory` instead, as 4F.3 and 4F.4 both did |

---

## 13. Test strategy

**Three tiers, all three populated** — the requirement 4F.4's D-2 discrepancy
established as non-negotiable.

| Tier | What it decides | Location |
|---|---|---|
| **Unit** | Level semantics, policy effect evaluation, the dispatch decision as a pure function, the risk ceiling | `tests/unit/` |
| **Contract / integration** | Routes, status codes, the levels listing, policy CRUD with the new effect, the app wiring | `tests/integration/` |
| **Real Postgres + real NATS** | X-1, X-3, X-5, X-11 — persistence, the real RPC, the real decision log | `tests/integration/*_real_*.py`, `@pytest.mark.real_infra` |

**The unit tier does not replace the others**, and no test may assert that a
function was called, that an RPC client returned success, or that a mocked bus
received a message, as evidence for X-3.

---

## 14. CI requirements for closure

| Evidence | Required |
|---|---|
| Real GitHub Actions run at the **exact implementation SHA** | Protocol §11.1 |
| `Build & Scan` | 22/22 built **and** Trivy-scanned; no new image expected |
| `Real-Infrastructure Checks` | 15/15, with `autonomy-engine`'s job carrying the new tests |
| `PR Checks` | `checks` green — lint, mypy, import-linter, codegen zero drift, full suite |
| Skipped / cancelled | **Zero** |
| A PR | Opened only when the user asks (protocol §11.1) |

---

## 15. SLOC budget

**Current: 46,125 on the 4F scope. Headroom to the 50,000 hard gate: 3,875.**
Measured at `9ec221f` in this session with the unchanged methodology: `cloc` v2.06
`--skip-uniqueness` over a pristine `git archive`; Comparable 36,506, Wider
41,847, Full 45,479, 4F scope 46,125.

| | |
|---|---|
| TDD 4F §17's estimate for *"Autonomy Level 2 + dispatch + publisher"* | **150–300** |
| Projected after 4F.5 | **~46,275–46,425** |
| Projected headroom | **~3,575–3,725** |

**The gate is not projected to be crossed by this slice.** Tests are outside every
scope (TDD 4F §17), so the test tiers contribute **0**.

**F-2's open question** — whether `companion/`'s `Cargo.toml`/`Dockerfile`/
`README.md` belong in the count, a 142-line difference — **does not change that**,
and remains **L-5's** to settle at 4F closure.

**Code is never moved or reduced to game the metric** (TDD 4F §17).

---

## 16. Risks

| # | Risk | Mitigation |
|---|---|---|
| **R-1** | **Fail-open policy semantics.** The most dangerous outcome of this slice: wiring `requires_approval` so that *absence* of a policy permits execution | **A-4F5-1 must be ratified before implementation.** X-5 is the mandatory negative control, asserted before any admission test |
| **R-2** | **The RPC blocks the decision.** `action-engine`'s lifecycle includes an approval loop whose default timeout is **300s**; awaiting the reply could stall `decide()` | **A-4F5-3.** A bounded timeout, and a recorded timeout outcome rather than a retry |
| **R-3** | **Silent scope creep into CF-11.** Adding "just a small trigger" to demonstrate the path end to end | 4F.6 owns the trigger. 4F.5's evidence drives `decide()` directly and says so |
| **R-4** | **Control 8's retirement read as a licence.** Retiring *"never calls the bus"* could be taken as permission to publish more | §16 control 6's replacement is **implemented**, not merely documented: exactly one publishable subject, asserted |
| **R-5** | **Stage 3 denial mistaken for a dispatch failure.** Without 4F.4's policy row every dispatched action is denied, which looks like the RPC failed | Tests that assert *execution* write the policy through 4F.4's production API; tests that assert *dispatch* assert the RPC, not the outcome |

---

## 17. Deferred obligations

### 17.1 Owned by 4F.5

| # | Obligation | Why it is 4F.5's |
|---|---|---|
| **Level 2's three states** | Selectable, policy-permitted, executing | TDD 4F §18's 4F.5 row and §6 |
| **4D control 8's replacement** | The tighter *"publishes `action.execute` and nothing else"* property | TDD 4F §11.2, §16 control 6 |

**No new ledger row is proposed by this slice as designed.** If implementation
reveals one, it must be surfaced explicitly and numbered only on ratification —
the precedent set by L-15 and L-16.

### 17.2 Explicitly NOT 4F.5's — every existing row, ownership unchanged

**Fourteen open rows**, carried forward from the [4F.4 completion record](../../roadmap/architecture-reviews/phase-4f4-identity-confidence-policy-completion-record.md) §11.
**4F.5 settles none of them.**

| # | Obligation | Owner, unchanged | 4F.5's relationship |
|---|---|---|---|
| **L-1** | 4F Gate Review (category 3) | **4F closure, after 4F.8** | None |
| **L-2** | `docs/project-health/phase-4f.md` | **4F closure** | None |
| **L-3** | `project-health-master.md` 4F row | **4F closure** | None |
| **L-4** | `ENGINEERING_ROADMAP.md` 4F row | **4F closure** | None |
| **L-5** | `00-master-scope.md` §17 SLOC table + §2 methodology — **F-2's owner** | **4F closure** | None |
| **L-6** | `README.md` — *"a new engine now exists"* | **4F closure** | None |
| **L-8** | `ws-gateway/README.md` — the `perception.*` narrowing | **4F closure** | None |
| **L-9** | Cross-file consistency sweep | **4F closure** | None |
| **L-10** | `docs/` staleness sweep, incl. `11-api-architecture.md` | **4F closure** | **Possible dependency — see below** |
| **L-11** | Fusion for workspace signals | **4F closure** | None |
| **L-13** | `known_projects` population | **4F closure or later** | None — correlation is the trigger's problem, 4F.6's |
| **L-14** | Filesystem consent policy | **4F closure** | None |
| **L-15** | `IdentityConfidencePolicy` mutations unaudited | **`action-engine`** | None — 4F.5 writes no policy of that kind |
| **L-16** | `action-engine/README.md` Owned APIs list | **`action-engine` / 4F closure** | None |

**L-10, stated precisely:** 4F.5 changes no route and adds no path, so
`docs/architecture/11-api-architecture.md` does **not** become newly stale by
this slice. But `autonomy-engine/README.md` describes level semantics, and
enabling Level 2 makes any *"Level 2 is not enabled"* statement stale. **This must
be checked at implementation time**, and if a statement is found stale it is
reported as a finding — not silently fixed, and not silently absorbed.

### 17.3 Carry-forwards — all three remain OPEN

| | Status | 4F.5's contribution |
|---|---|---|
| **CF-9** | **OPEN.** Conditions 1, 3, 4 evidenced by 4F.4; 2 answered by D-4F4-1 awaiting citation; **5 unmet** | **None.** 4F.5 *consumes* CF-9's surface; it adds no closure evidence and must not record any |
| **CF-10** | **OPEN**, Trust Engine unavailable / fails closed | **None.** Re-asserted unresolved by X-12 |
| **CF-11** | **OPEN**, the initiative trigger's producer | **None.** **4F.6's.** 4F.5 adds no caller of `decide()`, so it cannot contribute closure evidence even incidentally |

---

## 18. Non-goals

Each is named because it is adjacent enough to be assumed.

| Not in 4F.5 | Owning slice |
|---|---|
| The initiative trigger / CF-11 / any caller of `decide()` | **4F.6** |
| `/v1/cognitive-state` and the panel | **4F.7** |
| The AC-7 / AC-8 acceptance run | **4F.8** |
| Downstream world-model E2E | **4F.8** |
| Autonomy Levels 3, 4, 5 — selectable or defined | **Not in 4F at all** |
| A `TrustMetric` surface, or resolving CF-10 | **Outside 4F** |
| Any change to `action-engine` | **Never in this slice** |
| Changing stage 3, the approval loop or the fail-closed default | **Never.** Explicitly forbidden |
| A policy *authoring* UI | Not in 4F — no slice row names one |
| Reading Digital Twin, Memory or Perception state in `autonomy-engine` | **Never** — §2.3 |
| A retry, queue or scheduler for dispatched actions | Not in scope; `action-engine` owns retry |
| Closing CF-9, CF-10 or CF-11 | **Not 4F.5's** |

---

## 19. Documentation and closure requirements

At the end of 4F.5, protocol §0.1 requires categories 1, 2, 8, 9, 10, 11, 13 and
14 in full and categories 3–7 and 12 as a ledger. Concretely:

1. A **4F.5 Slice Completion Record** with a deferred-obligations ledger —
   **not a Gate Review**; category 3 is deferred and 4F's Gate Review is 4F.8's.
2. **CF-9, CF-10 and CF-11 each recorded as still OPEN**, with 4F.5's
   contribution to each stated as *none*.
3. All fourteen existing ledger rows carried forward unchanged.
4. CI evidence at the exact implementation SHA, 40/40.
5. SLOC measured and recorded with headroom.
6. The `autonomy-engine` README staleness check of §17.2 performed and reported
   either way.

**Phase 4F is not complete at the end of 4F.5.** 4F.6, 4F.7 and 4F.8 remain.

---

## 20. Ambiguities requiring ratification

**Four. None is resolved in this document.** Three change what gets built; one
changes a security semantic. **Implementation must not begin until each is
answered.**

### A-4F5-1 — How may a policy lower `requires_approval` without making absence permissive?

**This is the security-critical one, and the tension is textual and real.**

**The requirement**, TDD 4F §6, state 3, verbatim:

> Machinery exists; **no `allow` effect and none added** | A policy may lower
> `requires_approval` for a bounded LOW-risk category

**The requirement it must not break**, TDD 4F §6.4, verbatim:

> Every risk **above LOW**, at any level. Every denied gate. Every case where
> policy leaves `requires_approval = True`. **Absent policy means approval**,
> never execution.

**The current implementation boundary**, verified at `9ec221f`:

- `PolicyEffect` has exactly `DENY` and `REQUIRE_APPROVAL`. Its docstring:
  *"**There is deliberately no `ALLOW`** … An `allow` effect can only matter
  where something would otherwise happen automatically — Level 2+, which 4D does
  not enable."*
- `PolicyEvaluation.requires_approval` **defaults to `False`** and becomes `True`
  only when a matching `REQUIRE_APPROVAL` policy fires (`policy.py:110, 133`).
- `evaluate_gates()` **hardcodes `requires_approval=True`** on the pass path
  (`decision.py:213`) and **discards `policy_result.requires_approval` entirely**.
- `policy.py`'s own doctrine, item 3: *"**An empty policy set is not
  permissive.**"*

**The conflict.** The only mechanism the existing vocabulary offers for *lowering*
`requires_approval` is to stop discarding `policy_result.requires_approval` and
let it flow into `GateReport`. But that field is `False` **by default** — so an
**empty policy set would yield `requires_approval = False` and auto-execute.**
That is fail-open, and it contradicts §6.4 and `policy.py`'s doctrine directly.

The `PolicyEffect` docstring's own reasoning also points the other way from §6's
instruction: it says an allow effect *"can only matter … Level 2+, which 4D does
not enable"* — which is an argument for **deferring** the effect to 4F, not for
never having one.

| Option | Consequence |
|---|---|
| **(a) Add an affirmative, opt-in effect** — e.g. `PolicyEffect.AUTO_EXECUTE`, matched only at or below the `low` ceiling, which sets `requires_approval = False`; **absence leaves the `True` default untouched** | Fail-closed **by construction**: no policy → approval. Deny still wins. **No migration** (the column is `TEXT`, unconstrained). Contradicts the *letter* of §6's *"none added"* while honouring §6.4, §6.5 and `policy.py`'s doctrine. **Recommended** |
| (b) Wire `policy_result.requires_approval` into `GateReport` unchanged | **Fail-open.** An empty policy set auto-executes. Violates §6.4 explicitly. **Must not be chosen** |
| (b′) Wire it through, but invert the default so `PolicyEvaluation.requires_approval` defaults `True` | Avoids fail-open, but makes a `REQUIRE_APPROVAL` policy meaningless (it would set `True` on a field already `True`) and provides no way to *lower* it — state 3 stays unreachable |
| (c) Defer Level-2 dispatch to a later slice | 4F.5 ships states 2 and 5 only; AC-8 slips past 4F.8. Contradicts §18's row |

**Recommendation: (a)**, with three bindings ratified alongside it:

1. **The effect is named for what it does** — `AUTO_EXECUTE`, not `ALLOW`. An
   `ALLOW` effect reads as something that could overturn a `DENY`; this one
   cannot, and the name should not suggest it.
2. **Deny beats auto-execute unconditionally**, regardless of policy order.
3. **The effect is inert above the `low` ceiling** — a matching `AUTO_EXECUTE`
   policy on a `moderate` request lowers nothing.

**But this is a security-semantics ratification, not an implementation detail,
and I will not make it silently.** It changes the policy vocabulary, the API's
accepted enum values, and the conditions under which NOVA acts unattended.

### A-4F5-2 — Where do `action.execute`'s mandatory fields come from?

**The requirement.** `ActionExecuteRequestPayload` mandates `action_id`,
`action_type`, `priority`, `source`, `requested_by`, `execution_target`,
`verification_method`, `requesting_engine`, `correlation_id`.

**The current boundary.** `DecisionRequest` carries `user_id`, `category`, `risk`,
`title`, `detail`, `capability_class`, `priority: int`. It carries **none** of
`action_type`, `execution_target` or `verification_method`.

**The conflict.** There is no derivation available:

- `ActionType = Literal["terminal", "filesystem"]` — **two** values.
- `PermissionCategory` — **ten** values (`read`, `analyze`, `recommend`,
  `create`, `modify`, `delete`, `execute`, `deploy`, `purchase`, `communicate`).

A ten-to-two mapping would be invented, not derived, and `execution_target` and
`verification_method` have no analogue at all. `DecisionRequest.priority` is an
`int` while `ActionExecuteRequestPayload.priority` is an `ActionPriority`.

| Option | Consequence |
|---|---|
| **(a) Add the execution fields to `DecisionRequest`**, optional, and **required only when the dispatch branch is reached** — a request that cannot be executed is rejected at dispatch, not silently defaulted | Explicit, and pushes the knowledge to the trigger that actually has it (4F.6). Widens `DecisionRequest`, which is an internal domain type, not an HTTP contract. **Recommended** |
| (b) Derive from `capability_class` | `capability_class` is a free-form `str | None` with no registry behind it. Would invent a second capability vocabulary |
| (c) Hardcode defaults in the dispatcher | Silently fabricates `execution_target` and `verification_method` for a **security-sensitive** payload. Rejected |
| (d) Map `PermissionCategory` → `ActionType` | Ten-to-two, no natural mapping, invents semantics |

**Recommendation: (a)**, with the dispatch branch **failing closed** — a
`DecisionRequest` lacking execution fields at Level 2 produces a **suggestion**,
not a guessed action.

### A-4F5-3 — Does `decide()` await the RPC reply, and what is the timeout?

**The requirement.** TDD 4F §11.2 says `autonomy-engine` becomes `action.execute`'s
first producer. §8.1 above establishes it is a **request/reply RPC**.

**The current boundary.** `decide()` is an `async` function returning a
`DecisionResult` synchronously to its caller. `action-engine`'s lifecycle includes
an approval loop whose default timeout is **`approval_timeout_seconds = 300.0`**.
A LOW-risk policy-permitted action should not reach that loop — but a stage-3
denial, a capability failure or a misconfiguration could make the call slow.

| Option | Consequence |
|---|---|
| **(a) Await with a bounded timeout**, record the `ActionResultPayload` status on the decision log; a timeout is **recorded as a timeout**, never retried | The outcome is auditable, and the decision log tells the truth about what happened. Needs a ratified timeout value. **Recommended** |
| (b) `.publish()` fire-and-forget | Loses the reply on a subject that *has* one; nothing consumes `ActionResultPayload`; the decision log would record "executed" without evidence. Rejected |
| (c) Dispatch in a background task | `decide()` returns before the outcome is known; the log records intent, not result; introduces a task lifecycle this engine does not have |

**Recommendation: (a)**, and **the timeout value needs ratifying**. The natural
candidate is a new `Settings` field defaulting well below `action-engine`'s 300s —
something on the order of **10–30 seconds** — so a Level-2 dispatch that stalls
degrades to a recorded timeout rather than hanging the control plane. **A number
must be chosen deliberately; I have not chosen one.**

### A-4F5-4 — Does `permits_execution` become level-aware, or does the dispatch read the level directly?

**The requirement.** §16 control 3: *"Level 2 cannot execute by flag alone —
`permits_execution` returning `True` with §11.2's publication removed must still
fail."*

**The current boundary.** `permits_execution()` returns `False` unconditionally.
`_forbid_execution()` raises if it ever returns `True`, and its message is
*"Enabling Level 2 is milestone 4F (decision D-1) and requires an execution path,
not a flag."* **That guard is what §16 control 3 currently fails against**, and
4F.5 necessarily changes it.

| Option | Consequence |
|---|---|
| **(a) `permits_execution` becomes `level >= ASSISTED`; `_forbid_execution` is replaced by a guard asserting the execution path is wired** — e.g. that the dispatch port is present and `"action.execute"` is publishable | Keeps the single-read discipline and keeps control 3 meaningful: the flag alone still fails, now because the *path* is checked rather than the flag being banned. **Recommended** |
| (b) Delete `_forbid_execution` | Retires control 3 with nothing in its place. The exact failure mode D-1 warned about |
| (c) Leave `permits_execution` `False` and have the dispatcher read the level directly | Two places would then know the rule, and `permits_execution` becomes a lie |

**Recommendation: (a).** The guard changes from *"no level may execute"* to
*"no level may execute without a wired path"*, which is the same protection
against the same mistake.

---

## 21. Implementation and closure sequence

1. **Ratify §20's four questions.** A-4F5-1, A-4F5-2 and A-4F5-4 change what is
   built; A-4F5-3 changes runtime behaviour and needs a number.
2. **Merge this TDD into `phase-4`** and verify the resulting HEAD.
3. **Create `phase-4f.5` from that fresh `phase-4` HEAD.** It does not exist yet
   and must not be created before steps 1 and 2.
4. Implement deliverables 1–7. `action-engine` is not touched.
5. Verify locally: full suite, lint, mypy, import-linter, codegen drift, SLOC.
6. Real-infra evidence for X-1, X-3, X-5 and X-11 against real Postgres and a
   real Event Bus.
7. Open a PR **only if the user asks**, to obtain exact-SHA CI evidence
   (protocol §11.1).
8. Produce the **4F.5 slice completion record with a deferred-obligations
   ledger** — protocol §0.1 and §0.2. **Not a Gate Review.**
9. **Record CF-9, CF-10 and CF-11 as still OPEN**, each with 4F.5's contribution
   stated as none.

**Phase 4F is not complete at the end of 4F.5.** 4F.6, 4F.7 and 4F.8 remain.
