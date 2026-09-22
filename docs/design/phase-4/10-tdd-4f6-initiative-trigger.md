# TDD 4F.6 — The initiative trigger: Level 2's *Triggered* state

**Status: PROPOSED. Nothing here is ratified.** This document is the
preparation deliverable for Phase 4F.6 and exists to be reviewed. It contains
**one blocking architectural finding** (§3.3) that must be settled before any
implementation begins.

Subordinate to [TDD 4F](06-tdd-4f-companion-and-cognitive-state.md) §6, §6.1,
§6.2, §11.4, §12, §13, §18 and D-4F-3 · [TDD
4F.5](09-tdd-4f5-autonomy-level-2.md) in full ·
[TDD 4D](04-tdd-4d-autonomy-engine.md) §8.1, §13 ·
[PROJECT_PHASE_COMPLETION_PROTOCOL.md](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md)
(read from `origin/main`, sha256 `21185dd1…`).

Prepared at `phase-4` = **`4f1602ac086c421fc1a6beb54b7effb10f3ef6d9`**, the
merge commit of 4F.5 (PR #36). Every repository fact below was verified against
that tree, not recalled.

---

## 0. The headline, before anything else

**TDD 4F's own ratified constraints, read together, leave 4F.6 with no legal
transport for the trigger.** Three of them:

| Source | Constraint |
|---|---|
| §13, `cognitive-state-engine` row | **"Event Bus: Subscribes to existing subjects; publishes nothing (§11.3)"** |
| §11.4 | **"No `autonomy.*` subject."** |
| §12 | **"`autonomy-engine` gains no new route."** |

…and yet §13's *Produces* row for the same engine reads: **"Cognitive state …
and `DecisionRequest`s into `autonomy-engine` (§6.2)."**

A producer that publishes nothing, on a bus with no subject it may use, into an
engine that gains no route, **cannot deliver anything**. This is not a gap in
my reading — §7 records the repository evidence, and there is no fourth
mechanism in this codebase.

**This is the same class of finding as 4F.5's Trust contradiction**, which was
surfaced during branch preparation rather than resolved unilaterally, and it is
surfaced the same way here. **§3.3 states the options; A-4F6-1 is the decision.
No implementation may begin until it is ratified.**

---

## 1. Scope

### 1.1 What 4F.6 owns

| # | Deliverable |
|---|---|
| **1** | **State 4, *Triggered*** — the only one of Level 2's five states still unbuilt (§2) |
| **2** | **The trigger producer** in `cognitive-state-engine`: what makes it fire, and what it emits |
| **3** | **The trigger transport** — pending **A-4F6-1** |
| **4** | **The first production caller of `decide()`** in `autonomy-engine`, including loading level, policies and grants, and persisting the outcome |
| **5** | **Fail-safe behaviour** for every malformed, missing, duplicate, stale or unavailable trigger condition (§5) |
| **6** | **Duplicate/idempotency behaviour** — pending **A-4F6-3** |
| **7** | **The evidence CF-11 closure requires** — gathered, but **CF-11 is not closed by 4F.6 alone** (§8) |

### 1.2 What 4F.6 does not own

- **Anything 4F.5 already built.** Selectability, `AUTO_EXECUTE`, the seven
  §22.4 preconditions, the 15-second bound, `ActionDispatchUnavailable`, the
  Trust contract. 4F.6 **calls** that machinery; it does not reinterpret one
  line of it.
- **The cognitive-state panel and `/v1/cognitive-state` prefix** — **4F.7**.
- **AC-7 / AC-8 end-to-end acceptance** — **4F.8**.
- **The 4F Gate Review** — category 3, **L-1**, owned by 4F.8.
- **CF-9** (§9.1) and **CF-10** (§9.2).

---

## 2. The Level 2 state machine — what 4F.5 left

TDD 4F §6's five states, at `4f1602a`. **4F.6 changes exactly one row.**

| # | State | Status at `4f1602a` | 4F.6 |
|---|---|---|---|
| **1** | **Defined** | **Done** — `DEFINED_LEVELS == {0, 1, 2}` | Nothing |
| **2** | **Selectable** | **Done by 4F.5** — `SELECTABLE_LEVELS == {0, 1, 2}`; `PUT /v1/autonomy/level {"level": 2}` returns 200 | Nothing |
| **3** | **Policy-permitted** | **Done by 4F.5** — `PolicyEffect.AUTO_EXECUTE`, affirmative, LOW-only | Nothing |
| **4** | **Triggered** | **NOT DONE. CF-11.** Re-verified at `4f1602a`: **zero** production callers of `decide()` | **All of it** |
| **5** | **Executing** | **Done by 4F.5** — `ActionDispatchClient`, one bounded request/reply, no retry | Nothing |

**Verified, not assumed:** `grep` for `decide(` across
`services/autonomy-engine/src/` at `4f1602a` returns **only** the definition and
docstring references. **Zero production callers.**

### 2.1 What *Triggered* means, precisely

**A production component, reachable in a deployed system without a test
harness, causes `decide()` to run with a `DecisionRequest` it constructed from
real evidence.**

Three clauses, each load-bearing:

- **"production component"** — not a test, not a script, not a fixture. 4F.5's
  real-infra tests call `decide()` directly and say so; that is deliberately
  **not** a trigger.
- **"reachable in a deployed system"** — the path exists in the running
  topology, not only in code. CF-11's closure language is *"production-reachable
  and demonstrated end to end."*
- **"from real evidence"** — the request is derived from cognitive state, not
  from a constant. A hardcoded `DecisionRequest` on a timer would satisfy the
  letter of *Triggered* and none of its purpose.

**Triggered ≠ Executing.** A trigger that produces a `PROPOSE` outcome has
still triggered. Conflating the two would make the trigger's correctness depend
on policy configuration, which §6.6's single-dispatch rule exists to prevent.

---

## 3. The trigger source

### 3.1 What the repository actually provides — verified

| Question | Answer at `4f1602a` |
|---|---|
| Does `cognitive-state-engine` publish anything? | **No.** `PUBLISHABLE_SUBJECTS == frozenset()` |
| Does it subscribe to anything? | **No.** `SUBSCRIBABLE_SUBJECTS == frozenset()` |
| Does it have any non-health route? | **No.** Only `api/health.py` |
| Does it have an outbound client of any kind? | **No.** No `clients/` directory |
| Does `autonomy-engine` have an intake route? | **No.** 11 routes; `POST /suggestions/{id}/decide` decides an **existing** suggestion |
| Does `autonomy-engine` subscribe to anything? | **No.** `SUBSCRIBABLE_SUBJECTS == frozenset()` with a `TODO` comment |
| Is there an `autonomy.*` subject? | **No.** Registry has 119 subjects; **zero** match `autonomy`, `cognitive`, `decision-request`, `initiative` or `suggestion` |
| Do any Python engines call each other over HTTP? | **No.** Only `ai-model-orchestration-engine` (external LLM providers), `api-gateway` (its job) and `capability-engine` (external tools) import `httpx` |
| How *do* engines reach each other? | **The Event Bus, exclusively** — `clients/*_client.py` + `BoundEventBus.request()`, in six engines |

**Conclusion: the established engine→engine mechanism in this repository is
Event Bus request/reply, and nothing else.** `POST /v1/perception/observations`
(D-4F-5) is real and internal, but its client is **`nova-companion`, an
out-of-process Rust OS agent** — it is the established pattern for an *external
producer*, not for one engine calling another.

### 3.2 What TDD 4F forbids — verified verbatim

- §11.4: *"No `autonomy.*` subject. No `TrustMetric` subject or RPC (CF-10 stays
  open). No new `memory.*` or `digital_twin.*` subject. No wildcard widening."*
- D-4F-6 / §11.3: *"**No cognitive-state Event Bus subject is added.**"*
- §12: *"**`autonomy-engine` gains no new route**: selecting Level 2 is an
  existing operation whose 422 stops being returned for `2`."*
- §13: *"Event Bus: Subscribes to existing subjects; **publishes nothing**."*
- TDD 4F.5 §5: *"`autonomy-engine`'s `SUBSCRIBABLE_SUBJECTS` is empty and
  **stays empty**"* — asserted by `test_this_engine_still_subscribes_to_nothing`.

### 3.3 **A-4F6-1 — the blocking decision: what carries the trigger?**

Every option violates at least one ratified statement. **There is no compliant
path**, which is why this needs ratification rather than a judgement call.

| Option | Mechanism | What it costs |
|---|---|---|
| **(a) A new internal subject, e.g. `autonomy.decision.requested`** — `cognitive-state-engine` publishes; `autonomy-engine` serves | Follows the **established** engine→engine pattern exactly, and 4F.5 already proved that pattern end to end on real NATS | Violates **§11.4** ("no `autonomy.*` subject"), **§13** ("publishes nothing") and 4F.5's *"stays empty"*. Registry 119 → 120. **Three disclosed retirements.** `PUBLIC_TOPICS` stays 18 — the subject is internal and never browser-reachable |
| **(b) A new internal REST intake route on `autonomy-engine`** — `cognitive-state-engine` gains an HTTP client | Mirrors D-4F-5's `POST /v1/perception/observations` shape; no subject, registry stays 119; both allow-lists stay empty | Violates **§12** ("gains no new route"). **Invents a Python engine→engine HTTP pattern that does not exist**, with its own retry/timeout/auth questions the bus has already answered |
| **(c) `autonomy-engine` subscribes to an existing subject** and derives the request itself | No new subject; registry stays 119 | **Violates D-4F-3**: the producer becomes `autonomy-engine`, not `cognitive-state-engine`. Also breaks 4F.5's *"stays empty"*. **Reverses the ratified ownership** — worst of the four |
| **(d) Defer the trigger and re-scope 4F.6** | Honest about the contradiction | **Leaves CF-11 open with no owner** and blocks 4F.8's AC-8, which needs both levels demonstrated |

**Recommendation: (a)**, with all three retirements disclosed and replaced by
tighter properties — exactly the precedent 4F.5 set when
`"action.execute"` entered `PUBLISHABLE_SUBJECTS` and retired 4D's control 8
(*"this engine never calls the bus at all"*), replaced by *"may publish
`action.execute` and nothing else."*

**Why (a) rather than (b):** §11.4's prohibition was written in the context of
§11.3, which is about **browser-reachable and consumer-less** subjects. The
subject proposed here is **internal, consumed by exactly one server-side
engine, and never added to `PUBLIC_TOPICS`** — the same shape as
`action.execute`, which §11.2 explicitly permitted in the same document. **But
that is an interpretation, and I will not act on it unratified.** If §11.4 is
meant absolutely, (b) is the fallback and §12 needs the amendment instead.

**Nothing below assumes an answer.** §3.4 specifies the trigger *content*,
which is identical under (a) and (b).

### 3.4 The trigger's content — transport-independent

| | |
|---|---|
| **Producer** | `cognitive-state-engine` (D-4F-3), under §6.2's eight prohibitions |
| **What makes it fire** | **A-4F6-2.** A cognitive-state condition — an Active Thought reaching a threshold, a Focus transition, an Attention-layer move. **The repository does not establish which, and I have not chosen one** |
| **Payload** | A `DecisionRequest`-shaped contract: `category`, `risk`, `title`, `detail`, `capability_class`, `priority`, plus 4F.5's `action_type`, `execution_target`, `verification_method`, plus the rationale and cognitive-state evidence §6.2 permits |
| **`user_id`** | **Never carried by the producer.** §12: *"Identity resolved server-side from `primary_user_id` … so 4F never creates a caller-supplied-`user_id` route."* The existing decide route already does this. **A producer-supplied `user_id` would be a privilege-escalation surface** |
| **Validation** | The contract validates at the boundary; a payload that fails validation is **rejected without invoking `decide()`** (§5) |
| **Correlation ID** | The SDK already generates one per envelope and `ActionDispatchClient` already passes the decision's `subject_id` as the dispatch correlation id. 4F.6 **threads the trigger's correlation id through to the decision**, so trigger → decision → `action.execute` share one traceable identity |
| **Authorization boundary** | **Unchanged.** Every gate 4F.5 built still runs: Policy Engine, Permission Matrix, Trust, and all seven §22.4 preconditions. **The trigger is an input, never an authorization** |
| **Deduplication** | **A-4F6-3** (§6) |
| **Where `decide()` is invoked** | A new application-service function in `autonomy-engine` — **not** in the API layer and **not** in `domain/` — that loads level, policies and grants from the repository, calls `decide()`, and persists the result |

---

## 4. Decision invocation

`decide()`'s signature is fixed by 4F.5 and **4F.6 must not change it**:

```
decide(request, *, level, policies, grants, trust_source, dispatcher, now)
```

| Input | Where 4F.6 gets it | Note |
|---|---|---|
| `request` | Built from the trigger payload + server-side `primary_user_id` | **Never** the producer's `user_id` |
| `level` | `repository.get_level(user_id)`, defaulting as the decide route already does | Level 2 is not assumed; a Level-0/1 trigger is valid and must propose or observe |
| `policies` | `repository.list_policies(user_id)` | |
| `grants` | `repository.list_permission_grants(user_id)` | |
| `trust_source` | The wired `ConversationalTrustSource` — `UnavailableConversationalTrustSource` under CF-10 | **Unchanged.** §22.7 holds |
| `dispatcher` | `app.state.dispatcher`, wired in 4F.5 | |
| `now` | Default | |

**Outcome handling.** Each of `decide()`'s five outcomes already has defined
meaning; 4F.6 **persists** them and adds none:

| Outcome | Trigger path behaviour |
|---|---|
| `EXECUTE` | Persist the decision log entry. The action already ran through `action-engine` |
| `PROPOSE` | Persist the suggestion **and** the log entry — the existing `insert_suggestion` path, which today has zero production callers |
| `DENY` / `OBSERVE_ONLY` | Persist the log entry. No suggestion |
| `TIMEOUT` | Persist the log entry. **No retry** — D-4F5-3 |

**Timeout behaviour is 4F.5's and unchanged**: 15 seconds, one attempt,
`TIMEOUT` recorded, never retried. **4F.6 must not add a retry at the trigger
layer either** — that would reintroduce the double-execution risk D-4F5-3
forbids, one level up.

---

## 5. Safety — fail-safe behaviour for every path

**The rule: a trigger is an input, never an authorization.** Nothing below may
weaken a gate.

| Condition | Required behaviour | Established? |
|---|---|---|
| **Malformed trigger** | Rejected at the contract boundary. `decide()` **not** invoked | **Yes** — contract validation is repo-wide |
| **Missing trigger fields** | Same, if a required field. Optional execution fields absent → `decide()` runs and **precondition 5 yields a suggestion** | **Yes** — 4F.5 X-14 |
| **Unavailable trigger source** | No trigger, no decision. The system stays at its prior state. **Absence of a trigger is never execution** | **Yes** — by construction |
| **Duplicate trigger** | **A-4F6-3** | **NO** |
| **Stale trigger** | **A-4F6-4.** Is there a maximum age after which a request is refused? The repository establishes no TTL for any request-shaped payload | **NO** |
| **Invalid autonomy level** | Level is read server-side from the repository, never from the trigger, so an "invalid level" cannot originate in the trigger | **Yes** |
| **Policy denial** | `DENY` outcome, log entry, no dispatch | **Yes** — 4F.5 X-7 |
| **Trust denial** | Precondition 4 blocks dispatch | **Yes** — §22.7, X-16 |
| **Trust unavailable** | **Non-blocking, never a PASS.** Not coerced | **Yes** — §22.7, CF-10 |
| **Missing execution fields** | Suggestion, no RPC | **Yes** — X-14 |
| **Dispatch unavailable** | `ActionDispatchUnavailable` → precondition 6 fails → `PROPOSE`, no retry | **Yes** — §22.8 |
| **Dispatch timeout** | `TIMEOUT` outcome, no retry | **Yes** — §22.3 |
| **Unexpected transport error** | **A-4F6-5.** 4F.5 deliberately lets unknown transport errors keep their own identity rather than be relabelled. **What the trigger layer does with one is undefined** — propagate, or record and drop? | **NO** |

**Four of fourteen are undefined.** They are flagged, not invented.

---

## 6. Duplication and idempotency — **A-4F6-3**

### 6.1 What already exists

- **`DecisionLogEntry.subject_id`** — the decision's own identity, persisted as
  the `action_id` column, and passed as the dispatch correlation id.
- **`action-engine`'s idempotency guard**, keyed on the caller-supplied
  `action_id`. 4F.5's TDD notes that re-sending the same id would be *"a
  deliberate retry rather than an accident."*
- **Envelope correlation ids**, generated per bus request.

### 6.2 What does not exist

**No trigger-level dedup key, and no uniqueness constraint that would stop two
identical `DecisionRequest`s becoming two decisions and two dispatches.** The
`decision_log` table has no unique index beyond its primary key — verified in
`0001_initial_schema.py`.

### 6.3 The decision

**Is duplicate suppression required, and if so, keyed on what?**

| Option | Consequence |
|---|---|
| **(a) None** — every trigger is a decision | Simplest, and consistent with *"the decision log records every attempt."* **But a producer bug or an at-least-once redelivery becomes repeated LOW-risk auto-execution** |
| **(b) Reuse `action-engine`'s existing `action_id` guard** — the trigger derives a deterministic `subject_id` from its own identity | **No new mechanism**, which is what the brief prefers. Requires a deterministic derivation to be ratified |
| **(c) A new idempotency key and a uniqueness constraint** | A migration, a new column, new semantics. **Requires ratification and probably does not belong in a slice** |

**Recommendation: (b), if a deterministic derivation can be agreed; otherwise
(a) with the redelivery risk stated explicitly.** I have not chosen.

**Note under option (a):** whether the bus delivers at-most-once or
at-least-once for the chosen transport is itself a fact to establish before
accepting (a).

---

## 7. Event Bus

| | At `4f1602a` | After 4F.6 |
|---|---|---|
| Registered subjects | **119** | **119** under (b)/(c)/(d); **120** under (a) — **proposed, not approved** |
| `PUBLIC_TOPICS` | **18** | **18, unchanged under every option.** No browser exposure |
| `autonomy-engine` `PUBLISHABLE_SUBJECTS` | `{"action.execute"}` | **Unchanged** |
| `autonomy-engine` `SUBSCRIBABLE_SUBJECTS` | **empty** | **empty** under (b)/(d); **one entry** under (a) — retires a 4F.5 property |
| `cognitive-state-engine` `PUBLISHABLE_SUBJECTS` | **empty** | **empty** under (b)/(c)/(d); **one entry** under (a) — retires a §13 property |

### 7.1 Proposed new subject — **NOT APPROVED**

Listed only so the decision is concrete. **Do not implement.**

| Field | Proposed |
|---|---|
| **Name** | `autonomy.decision.requested` |
| **Shape** | Request/reply, mirroring `action.execute`'s proven shape |
| **Producer** | `cognitive-state-engine` |
| **Consumer** | `autonomy-engine`, via `serve()` |
| **Public?** | **No.** Never added to `PUBLIC_TOPICS`; internal, server-side only |
| **Status** | **PROPOSED under A-4F6-1(a). Blocked by §11.4 until ratified** |

---

## 8. CF-11 — what closure actually requires

**CF-11 is not closed by 4F.6 writing a trigger.** TDD 4F §6.1 is explicit:

> *"4F implementing a producer does not close CF-11 by implication. Closure
> requires that the producer be **production-reachable** and **demonstrated end
> to end**; until that is verified and recorded, CF-11 stays OPEN."*

| # | Closure condition | Who can evidence it |
|---|---|---|
| 1 | A production component constructs a `DecisionRequest` from real evidence | **4F.6** |
| 2 | It reaches `decide()` through a deployed path, no test harness | **4F.6** |
| 3 | The path is demonstrated **end to end** in a running system | **Likely 4F.8**, which owns AC-8 in a browser |
| 4 | Verified and **recorded** in the closing document | **4F closure / the Gate Review (L-1)** |

**Expected status after 4F.6: OPEN**, with conditions 1 and 2 evidenced and 3–4
outstanding. **4F.6 must not record CF-11 as closed**, and this TDD does not
close it.

---

## 9. CF-9 and CF-10

### 9.1 CF-9 — **not 4F.6's**

Conditions 1, 3 and 4 are evidenced by 4F.4; condition 2 is answered by
ratification **D-4F4-1** and awaits citation; **condition 5 is unmet** and is a
category 3–5 documentation obligation that protocol §0.1 defers for a slice.
**4F.6 contributes nothing and must not close it. Expected after 4F.6: OPEN.**

### 9.2 CF-10 — **not 4F.6's**, and structurally blocked

Closing CF-10 needs a Trust read surface — a served `digital_twin.*` subject or
an HTTP route — and **§11.4 forbids exactly that** (*"No `TrustMetric` subject
or RPC (CF-10 stays open)"*). The trigger path must keep Trust `UNAVAILABLE`,
non-blocking and never a PASS, per §22.7. **Expected after 4F.6: OPEN.**

---

## 10. Test strategy

| Tier | Coverage |
|---|---|
| **Unit** | Trigger construction from cognitive state; the §6.2 prohibitions as properties; payload validation; server-side `user_id` resolution; outcome→persistence mapping for all five outcomes |
| **Integration** | Trigger → `decide()` → repository, with fakes for bus and trust; every §5 row that is *established*; Level 0/1/2 producing observe / propose / execute respectively from the **same** trigger |
| **`real_infra`** | **The load-bearing tier.** Real Postgres + real NATS: a real trigger from a real producer reaching a real `decide()`, with the decision and its log row read back by **independent SQL**; a real dispatch to a real responder; `ActionDispatchUnavailable` degradation with no responder; duplicate-trigger behaviour once A-4F6-3 is settled |
| **Contract** | `PUBLIC_TOPICS` still 18; `action.execute` still not public; both engines' allow-lists exactly as ratified; **no engine imports another**; §6.2's eight prohibitions asserted structurally |
| **Negative** | Malformed payload; missing required field; producer-supplied `user_id` **rejected**; trigger at Level 0/1 never executing; policy-denied trigger; trust-denied trigger; above-LOW risk trigger never auto-executing; trigger with missing execution fields |
| **Duplicate** | Pending **A-4F6-3** |
| **E2E** | **Not 4F.6's.** AC-8 in a browser is 4F.8's |

**Evidence required for the trigger → `decide()` → outcome path:** a real-infra
test in which **no test code calls `decide()` directly** — the production
trigger path does, and the assertion reads the persisted result. Anything
weaker re-proves 4F.5 rather than proving 4F.6.

---

## 11. Boundaries — what may change

| Allowed | Why |
|---|---|
| `services/cognitive-state-engine/src/**` | The trigger producer. D-4F-3 |
| `services/autonomy-engine/src/**` | The first production caller of `decide()` |
| `services/cognitive-state-engine/tests/**`, `services/autonomy-engine/tests/**` | Evidence |
| `packages/nova-contracts/**` | **Only under A-4F6-1(a)**, and only to add the one internal subject |
| `docs/**` | This TDD, the completion record, the master-scope index |
| A `real-infra` CI matrix row for `cognitive-state-engine` | **Only if one does not already exist** — verify before touching CI |

---

## 12. Non-goals — what must not change

- **`action-engine`** — execution/approval boundary owner. Zero files.
- **Stage 3** (`nova_action_engine/domain/pipeline.py`) — zero files.
- **`nova-eventbus-sdk`** — **L-18** is open and is not 4F.6's.
- **`apps/web-client/src/`** — **L-17** is open; the panel is 4F.7's.
- **Migrations and ORM** — zero, unless A-4F6-3 resolves to (c), which would
  itself need ratification.
- **`PUBLIC_TOPICS`** — 18, unchanged. No browser exposure of any trigger.
- **The gateway** — no new prefix. `/v1/cognitive-state` is 4F.7's.
- **4F.5's dispatch semantics** — `TIMEOUT`, `ActionDispatchUnavailable`, the
  seven preconditions, the 15-second bound, no retry: **all unchanged**.
- **The Trust contract** — §22.7 holds exactly.
- **CI workflow policy** — no global change.
- **`main`** — untouched.

---

## 13. Ratification checklist

**Nothing may be implemented until every one of these is decided.**

| ID | Decision | Blocking? |
|---|---|---|
| **A-4F6-1** | **The trigger transport.** New internal subject (a), internal REST route (b), autonomy subscribes (c), or defer (d). **Every option violates a ratified statement; the decision is which to amend, additively.** Recommendation: **(a)** | **YES — blocks everything** |
| **A-4F6-2** | **What makes the trigger fire** — which cognitive-state condition. The repository establishes none | **YES** |
| **A-4F6-3** | **Duplicate suppression** — none (a), reuse `action_id` (b), or a new key (c). Recommendation: **(b)** if a deterministic derivation is agreed | **YES** |
| **A-4F6-4** | **Stale-trigger TTL** — is there a maximum age, and what happens past it? | **YES** |
| **A-4F6-5** | **Unexpected transport errors at the trigger layer** — propagate, or record and drop? | **YES** |
| **A-4F6-6** | **Which 4F statements are amended**, and their replacement properties: §11.4, §12, §13's *"publishes nothing"*, and 4F.5's *"`SUBSCRIBABLE_SUBJECTS` stays empty"*. Additive, per protocol principle 4 | **YES, if (a) or (b)** |
| **A-4F6-7** | **Whether `decide()`'s caller is an application-service module**, and where it lives — not `api/`, not `domain/` | No — but should be settled |

---

## 14. Completion evidence — what the 4F.6 record must prove

Per protocol §0.1, a Significant Slice gets categories **1, 2, 8, 9, 10, 11, 13,
14 in full** and **3–7, 12 as a ledger**. **Category 3 is the Gate Review, so
4F.6 issues no verdict.**

The record must prove:

1. **State 4 is built** — a production trigger exists and reaches `decide()`.
2. **Every acceptance criterion** with named evidence, and every negative case.
3. **`decide()` has a production caller**, named, with the call path traced.
4. **No test calls `decide()` directly** in the evidence for the trigger path.
5. **Real-infra evidence, executed**, with counts — and, if Docker is
   unavailable locally, **protocol §10.1's disclosure obligation honoured with
   every delegated test enumerated by name**. 4F.5's first CI run found four
   real defects precisely because that obligation was honoured.
6. **Every §5 safety row** evidenced or explicitly deferred.
7. **Duplicate behaviour** as ratified under A-4F6-3.
8. **Event Bus state**: `PUBLIC_TOPICS` 18; subject count stated; both
   allow-lists stated exactly.
9. **Every boundary in §12 at zero files.**
10. **CF-9 OPEN, CF-10 OPEN, CF-11 OPEN** — with CF-11's conditions 1 and 2
    evidenced and 3–4 named as outstanding.
11. **L-17 and L-18 still OPEN**, plus any row 4F.6 opens.
12. **Every A-4F6 ratification cited** where it was applied.
13. **SLOC** on the 4F scope, with headroom to the 50,000 gate.
14. **Any retired 4F/4F.5 property disclosed**, not silent, with its replacement
    named — the precedent 4F.5 set with 4D's control 8.

---

## 15. Status

**PROPOSED — NOT RATIFIED. No implementation authorized.**

**A-4F6-1 blocks everything**, and it is a genuine contradiction in TDD 4F
rather than an ambiguity I can resolve by reading more carefully. The
recommendation is **(a)**; the decision is not mine.
