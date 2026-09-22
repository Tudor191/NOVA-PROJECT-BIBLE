# TDD 4F.6 — The initiative trigger: Level 2's *Triggered* state

**Revision 2 — 2026-09-22.** Revision 1 reported a blocking architectural
contradiction (§0). **That finding was accepted, and A-4F6-1 and A-4F6-7 are
now ratified.** A-4F6-2 … A-4F6-5 carry **proposals backed by a second
repository analysis**; none is ratified, and **§16 is the authority on which is
which.**

Subordinate to [TDD 4F](06-tdd-4f-companion-and-cognitive-state.md) §6, §6.1,
§6.2, §11.2, §11.3, §11.4, §12, §13, §18 and D-4F-3 · [TDD
4F.5](09-tdd-4f5-autonomy-level-2.md) in full · [TDD
4D](04-tdd-4d-autonomy-engine.md) §8.1, §13 ·
[PROJECT_PHASE_COMPLETION_PROTOCOL.md](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md)
(read from `origin/main`, sha256 `21185dd1…`, 1131 lines).

Prepared at `phase-4` = **`4f1602ac086c421fc1a6beb54b7effb10f3ef6d9`**, 4F.5's
merge commit. Every repository fact below was verified against that tree.

---

## 0. The finding that produced this revision — preserved

Revision 1 reported that three ratified statements in TDD 4F, read together,
left no legal transport for the trigger:

| Source | Constraint |
|---|---|
| §13, `cognitive-state-engine` row | *"Event Bus: Subscribes to existing subjects; **publishes nothing** (§11.3)"* |
| §11.4 | *"**No `autonomy.*` subject.**"* |
| §12 | *"**`autonomy-engine` gains no new route.**"* |

…against §13's own *Produces* row: *"Cognitive state … and **`DecisionRequest`s
into `autonomy-engine`** (§6.2)."*

**The finding was accepted as genuine and blocking.** §14 is the additive
amendment that resolves it. **This section is preserved rather than deleted**,
per protocol principle 4 — the contradiction was real, and the record of it is
what justifies the exception §14 grants.

---

## 1. Scope

### 1.1 What 4F.6 owns

| # | Deliverable |
|---|---|
| **1** | **State 4, *Triggered*** — the last unbuilt state of Level 2 (§2) |
| **2** | The **trigger producer** in `cognitive-state-engine` |
| **3** | The **transport**: `autonomy.decision.requested` (§3, **RATIFIED**) |
| **4** | The **first production caller of `decide()`** (§7, **RATIFIED** boundary) |
| **5** | **Fail-safe behaviour** for every path in §9 |
| **6** | **Duplicate behaviour** (§5) and **stale-trigger behaviour** (§6), as ratified |
| **7** | **Evidence toward CF-11**, which **4F.6 does not close** (§15) |

### 1.2 What 4F.6 does not own

Everything 4F.5 built — selectability, `AUTO_EXECUTE`, the seven §22.4
preconditions, the 15-second bound, `ActionDispatchUnavailable`, the Trust
contract. 4F.6 **calls** that machinery and reinterprets none of it. The
cognitive-state panel and `/v1/cognitive-state` prefix are **4F.7's**; AC-7/AC-8
acceptance is **4F.8's**; the Gate Review is **L-1**.

---

## 2. The Level 2 state machine — one row changes

| # | State | At `4f1602a` | 4F.6 |
|---|---|---|---|
| **1** | **Defined** | **Done** — `DEFINED_LEVELS == {0,1,2}` | Nothing |
| **2** | **Selectable** | **Done by 4F.5** — `SELECTABLE_LEVELS == {0,1,2}` | Nothing |
| **3** | **Policy-permitted** | **Done by 4F.5** — `AUTO_EXECUTE`, affirmative, LOW-only | Nothing |
| **4** | **Triggered** | **NOT DONE. CF-11.** Re-verified: **zero** production callers of `decide()` | **All of it** |
| **5** | **Executing** | **Done by 4F.5** — one bounded request/reply, no retry | Nothing |

**Triggered means:** a production component, reachable in a deployed system
without a test harness, causes `decide()` to run with a `DecisionRequest` it
built from real evidence. **Triggered ≠ Executing** — a trigger yielding
`PROPOSE` has still triggered.

---

## 3. Transport — **A-4F6-1, RATIFIED**

```
cognitive-state-engine  →  autonomy.decision.requested  →  autonomy-engine
```

| Property | Value |
|---|---|
| **Subject** | **`autonomy.decision.requested`** |
| **Shape** | Request/reply, mirroring `action.execute`'s proven shape |
| **Producer** | `cognitive-state-engine` — gains `PUBLISHABLE_SUBJECTS = {"autonomy.decision.requested"}` |
| **Consumer** | **`autonomy-engine`, and exactly one** — gains `SUBSCRIBABLE_SUBJECTS = {"autonomy.decision.requested"}` and one `serve()` |
| **Visibility** | **Internal only. Never in `PUBLIC_TOPICS`. Never browser-reachable. Not a public API** |
| **Registry** | **119 → 120**, permitted |
| **Gateway** | **No prefix.** No route, no proxy entry |

**This is an exception granted specifically for 4F.6**, not a general
relaxation. §14 carries the amendment text and its reasoning.

### 3.1 The boundary properties that replace the retired ones

Each retirement is **disclosed and replaced by something tighter** — the
precedent 4F.5 set when `action.execute` retired 4D's control 8:

| Retired | Replacement property, test-enforced |
|---|---|
| `cognitive-state-engine` *"publishes nothing"* | **"publishes `autonomy.decision.requested` and nothing else"** |
| `autonomy-engine`'s `SUBSCRIBABLE_SUBJECTS` *"stays empty"* | **"subscribes to `autonomy.decision.requested` and nothing else"** |
| §11.4 *"no `autonomy.*` subject"* | **"exactly one `autonomy.*` subject exists, it is internal, and it is not in `PUBLIC_TOPICS`"** |

---

## 4. **A-4F6-2 — the trigger condition. PROPOSED, and the repository is insufficient**

### 4.1 The honest answer first

**The repository does not contain enough information to define this condition
safely, and I will not invent one.**

Second analysis of `cognitive-state-engine` at `4f1602a`:

| Structure | Fields |
|---|---|
| **`ActiveThought`** | `thought_id`, `user_id`, `description`, `priority` (int ≥ 0), `confidence` (0–1), `dependencies`, `estimated_completion`, `related_memories`, `related_projects`, `current_progress` (0–1), `attention_layer`, `created_at`, `updated_at` |
| **`AttentionLayer`** | `IMMEDIATE`, `ACTIVE`, `PASSIVE`, `DORMANT`, `ARCHIVED` |
| **`AttentionAction`** | `Literal["promote", "demote"]` — **an attention-layer transition, nothing executable** |
| **`FocusInputs` / `FocusedThought`** | Seven 0–1 ranking signals; a score and the signals used |
| **Repository ops** | `upsert_thought`, `get_thought`, `list_thoughts`, `move_layer` |

**`DecisionRequest` requires `category` (`PermissionCategory`), `risk`
(`RiskLevel`), `title`, `detail`, and 4F.5's `action_type`,
`execution_target`, `verification_method`.**

**None of those exist anywhere in `cognitive-state-engine`.** Verified: a
case-insensitive search for `risk`, `PermissionCategory`, `action_type`,
`execution_target` and `verification` across its `src/` returns **only**
`FocusSignal.CURRENT_RISKS` and `FocusInputs.current_risks` — a **0.0–1.0
focus-ranking weight**, which is **not** a `RiskLevel` and must never be
coerced into one.

**An `ActiveThought` is a reasoning process, not a proposed action.** Mapping
one to a `DecisionRequest` means supplying a permission category, a risk tier
and three execution fields **that the thought does not carry**. Any rule for
doing so would be invented — precisely the *"AI thinks an action would help"*
condition this round forbids. A wrong guess here is a **security** error: it
picks the category and risk tier that every downstream gate is evaluated
against.

### 4.2 The smallest additional ratification — **A-4F6-2a**

**A thought must be able to carry an explicit, author-supplied action
proposal.** The smallest form:

| | |
|---|---|
| **New structure** | `ProposedAction`, attached optionally to `ActiveThought` |
| **Fields** | `category: PermissionCategory`, `risk: RiskLevel`, `action_type`, `execution_target`, `verification_method`, `title`, `detail` |
| **Rule** | **A thought without a `ProposedAction` never triggers.** Absence is not a low-risk default |
| **Condition** | **Deterministic**: a thought that (1) carries a complete `ProposedAction` and (2) is **promoted to `IMMEDIATE`** — Part 6's *"critical events requiring instant action"*, the one layer whose Bible definition is about acting — emits exactly one trigger per promotion |
| **Invalid states** | No `ProposedAction`; partial `ProposedAction`; a thought already triggered for this promotion; `attention_layer != IMMEDIATE`; a demotion |
| **Why cognitive-state-engine** | D-4F-3 and §6.2 give it the *"MAY produce: a `DecisionRequest`, an action type, subject/context, a rationale"* — §6.2 already presumes it holds action-shaped data. `ProposedAction` is that presumption made explicit rather than inferred |
| **Cost** | A domain structure **and a schema addition**, which is larger than "a trigger" and may belong in its own slice |

**Is the condition deterministic?** Yes — promotion to `IMMEDIATE` is an
observable state transition through `move_layer`, and `next_layer` is a pure
function over a fixed transition table. **Is it already represented?** The
*transition* is. **The action semantics are not.**

**If A-4F6-2a is rejected, 4F.6 has no safe trigger condition and must be
re-scoped.** That is the honest position.

---

## 5. **A-4F6-3 — duplicate suppression. PROPOSED: reuse, conditionally**

### 5.1 What exists — verified

| Mechanism | Reality at `4f1602a` |
|---|---|
| **`action-engine`'s idempotency guard** | **Real and strong.** `_idempotent_reply_if_terminal(action_id)` runs *"before any stage runs, and before the Action row is even inserted, so a genuine retry never re-triggers any side effect, **including the approval loop**"*. A terminal action replays its stored result |
| **DB uniqueness** | `ActionORM` PK on `action.id` → `IntegrityError` → `ActionAlreadyExistsError` |
| **`DecisionLogEntry.subject_id`** | Persisted as the `action_id` column; passed as the dispatch correlation id, so decision and action share one identity |
| **`autonomy.decision_log` constraints** | **PK only.** No unique index on `action_id` — verified in `0001_initial_schema.py` |
| **`subject_id` generation** | **`uuid4()`**, `decision.py:480` — **non-deterministic** |
| **Envelope `correlation_id`** | Generated per bus request; **not** a dedup key |

### 5.2 Why reuse does not work as-is

Two identical triggers produce two `uuid4()` `subject_id`s → two different
`action_id`s → **`action-engine`'s guard never fires**, because it is keyed on
the id it is *given*. The guard is sound; the caller currently hands it a fresh
key every time.

### 5.3 The proposal

**Reuse `action-engine`'s existing guard by making the trigger's `subject_id`
deterministic.** Derive it as a **UUIDv5 over a stable trigger identity** —
under A-4F6-2a, `(thought_id, the promotion that produced the trigger)`.

| | |
|---|---|
| **New mechanism** | **None.** No column, no constraint, no migration |
| **Effect** | A duplicate trigger produces the **same** `action_id`; `action-engine` replays the stored terminal result and **executes nothing twice** |
| **Cost** | `decide()` must accept a caller-supplied `subject_id` on the trigger path, or derive it before calling. **That is a change to a 4F.5 signature and needs to be explicit** |
| **Residual** | Two `decision_log` rows may still be written for one logical trigger. That is **consistent** with *"the decision log records every attempt"*, but it should be a conscious acceptance |

**This proposal depends on A-4F6-2a**, because the stable identity it hashes
does not exist until a `ProposedAction` and its promotion do.

**Fallback if A-4F6-2a is rejected:** no suppression, and the at-least-once
question below must be answered first.

### 5.4 An open sub-question

**Whether the chosen transport delivers at-most-once or at-least-once is not
established in this repository.** Core NATS request/reply is at-most-once with
no redelivery, which would make duplicates a *producer* concern only — but that
should be confirmed rather than assumed.

---

## 6. **A-4F6-4 — stale-trigger TTL. PROPOSED: no TTL, because nothing justifies a number**

### 6.1 What exists — verified

A repository-wide search for `ttl`, `expires_at`, `expiry`, `max_age` and
`stale` across every engine's `src/` returns **exactly one** numeric lifetime:
`session_cookie_max_age_seconds` in `api-gateway` — an **auth cookie**, not a
request lifecycle.

**No request-shaped payload in this repository carries a TTL, an expiry or a
maximum age.** `EventEnvelope` has `occurred_at`; nothing consumes it as a
deadline. The only bounded wait anywhere on this path is 4F.5's **15-second
dispatch timeout**, which bounds *waiting for a reply*, not *request freshness*.

### 6.2 The proposal

**No TTL in 4F.6**, because there is no justified number and inventing one
would be arbitrary.

| Option | Trade-off |
|---|---|
| **(a) No TTL — recommended** | Nothing invented. **Risk:** a trigger delayed by a slow consumer or a restart is acted on later than intended. Bounded in practice by request/reply's own timeout, which fails the *producer* rather than executing late |
| **(b) A TTL equal to the 15-second dispatch bound** | Uses a number the project has already ratified — but **for a different purpose**. Reusing it implies the two are related when they are not |
| **(c) A new ratified TTL** | Honest, but the number has no evidential basis today |

**If a TTL is later ratified:** `EventEnvelope.occurred_at` is the authoritative
clock (producer-side, already on every envelope); an expired request is
**refused without invoking `decide()`**; and — per the *"records every
attempt"* principle — **whether an expired request is persisted is itself a
ratification**, since no decision was made and `DecisionLogEntry` requires an
outcome. Tests would drive a synthetic `occurred_at` past the bound and assert
no dispatch, no execution, and the ratified persistence behaviour.

---

## 7. **A-4F6-7 — the `decide()` caller. RATIFIED boundary, module proposed from precedent**

**Ratified:** the caller lives at the **application/orchestration boundary**
inside `autonomy-engine`. **Not `api/`. Not `domain/`.**

**Proposed module — from the existing architecture, not invented:**

```
services/autonomy-engine/src/nova_autonomy_engine/decision_orchestration.py
```

**The precedent is established and consistent:** package-root orchestration
modules exist as `<noun>_orchestration.py`, beside `main.py`, outside both
`api/` and `domain/` —

- `perception-engine/…/observation_orchestration.py`
- `communication-engine/…/conversation_orchestration.py`

`observation_orchestration.py` is the closest analogue: it is the module that
takes an inbound payload and drives an existing-but-uncalled domain chain —
exactly 4F.6's shape.

**Responsibilities:** validate the payload; resolve `user_id` **server-side**;
load level, policies and grants; call `decide()`; persist the outcome. **It
contains no gate logic** — every gate stays in `domain/`.

---

## 8. The payload contract

| Field | Source | Note |
|---|---|---|
| `category` | `ProposedAction` (**A-4F6-2a**) | `PermissionCategory` |
| `risk` | `ProposedAction` | `RiskLevel` — **never** derived from `current_risks` |
| `title`, `detail` | `ProposedAction` / thought `description` | |
| `action_type`, `execution_target`, `verification_method` | `ProposedAction` | Absent → suggestion, never a guess (X-14) |
| `priority` | `ActiveThought.priority` | |
| `rationale` / evidence | The thought and its focus signals | §6.2 permits |
| `correlation_id` | Producer-set, threaded through | trigger → decision → `action.execute` share one identity |
| **`user_id`** | **NEVER carried.** Resolved server-side from `primary_user_id` | §12: *"4F never creates a caller-supplied-`user_id` route."* A producer-supplied `user_id` is a **privilege-escalation surface** |

---

## 9. Safety

| Condition | Behaviour | Established? |
|---|---|---|
| Malformed trigger | Rejected at contract validation; `decide()` **not** invoked | Yes |
| Missing required field | Same | Yes |
| Missing execution fields | `decide()` runs; precondition 5 → suggestion | Yes — X-14 |
| Producer-supplied `user_id` | **Rejected** | Yes — §12 |
| Unavailable trigger source | No trigger, no decision. **Absence is never execution** | Yes |
| Duplicate trigger | **A-4F6-3** | Proposed |
| Stale trigger | **A-4F6-4** | Proposed |
| Invalid autonomy level | Impossible from the trigger — level is read server-side | Yes |
| Policy denial | `DENY`, logged, no dispatch | Yes — X-7 |
| Trust denial | Precondition 4 blocks | Yes — §22.7 |
| Trust unavailable | **Non-blocking, never a PASS** | Yes — §22.7 |
| Dispatch unavailable | Precondition 6 fails → `PROPOSE`, no retry | Yes — §22.8 |
| Dispatch timeout | `TIMEOUT`, no retry | Yes — §22.3 |
| Unexpected transport error | **A-4F6-5** | Proposed |

### 9.1 **A-4F6-5 — unexpected transport errors. PROPOSED**

**The repository's actual convention, verified:** **no `serve()` handler
catches anything.** `action-engine`'s `action.execute` handler calls
`model_validate` and the domain function with **no `try`/`except`**, and the
SDK's `_callback` has none either. An exception therefore propagates, **no
reply is published**, and the requester experiences a **timeout**.

**Consequences for 4F.6, stated plainly:** an error raised before persistence
means **no `DecisionLogEntry` is written** and the trigger is **silently lost** —
fail-safe with respect to *execution* (nothing runs), but **not** with respect
to *auditability*.

| Option | Trade-off |
|---|---|
| **(a) Propagate — matches the existing convention exactly** | Consistent with every other consumer; no new pattern. **The trigger vanishes with no audit row** |
| **(b) Record-and-drop** — catch, persist a non-executing outcome, return a reply | Auditable. **But `DecisionLogEntry` requires a `DecisionOutcome`, and no member means "the trigger failed before a decision"** — adding one is a new outcome, which 4F.5 deliberately refused to do for `ActionDispatchUnavailable` |
| **(c) Propagate, plus observability** — no reply, but a metric/log at the boundary | Keeps the convention, makes the loss visible without inventing an outcome. **Recommended** |

**In all three: `decide()` is not invoked; no retry is added at the trigger
layer** — a trigger-level retry would reintroduce the double-execution risk
D-4F5-3 forbids, one level up. **Acknowledgement** is not applicable to core
request/reply: there is no ack, only a reply or its absence.

**Related, and already open:** **L-18** — the SDK does not translate
`NoRespondersError`. If `autonomy-engine` is not subscribed, the **producer**
receives a raw `nats.errors.NoRespondersError`. 4F.6 must decide what the
producer does with that; **it must not fix the SDK** (L-18 is not 4F.6's).

---

## 10. Test strategy

| Tier | Coverage |
|---|---|
| **Unit** | Trigger construction; the §6.2 prohibitions as properties; payload validation; server-side `user_id` resolution; outcome→persistence for all five outcomes; deterministic `subject_id` derivation if A-4F6-3 is ratified |
| **Integration** | Trigger → `decide()` → repository with fakes; Level 0/1/2 producing observe/propose/execute from the **same** trigger |
| **`real_infra`** | **Load-bearing.** Real Postgres + real NATS: a real producer publishing `autonomy.decision.requested`, a real `serve()` consumer, a real `decide()`, read back by **independent SQL**; real dispatch to a real responder; `ActionDispatchUnavailable` degradation; duplicate-trigger behaviour |
| **Contract** | `PUBLIC_TOPICS` **still 18**; `autonomy.decision.requested` **not** public; registry **120**; both engines' allow-lists **exactly** as ratified; no engine imports another; §6.2's eight prohibitions structural |
| **Negative** | Malformed payload; missing field; **producer-supplied `user_id` rejected**; Level 0/1 never executing; policy-denied; trust-denied; above-LOW never auto-executing; missing execution fields |
| **E2E** | **Not 4F.6's** — AC-8 in a browser is 4F.8's |

**The decisive evidence:** a real-infra test in which **no test code calls
`decide()` directly**. Anything weaker re-proves 4F.5.

---

## 11. Boundaries — what may change

`services/cognitive-state-engine/src/**` · `services/autonomy-engine/src/**` ·
both test trees · `packages/nova-contracts/**` (**the one subject only**) ·
`docs/**` · a `real-infra` CI matrix row for `cognitive-state-engine` **only if
absent** · a `cognitive_state` schema addition **only under A-4F6-2a**.

---

## 12. Non-goals

`action-engine` · Stage 3 · **`nova-eventbus-sdk` (L-18 is not 4F.6's)** ·
`apps/web-client/src/` (L-17; the panel is 4F.7's) · `autonomy` migrations and
ORM · **`PUBLIC_TOPICS` (18, unchanged)** · the gateway · 4F.5's dispatch
semantics · the §22.7 Trust contract · CI workflow policy · **`main`**.

---

## 13. Residual open questions

- **A-4F6-2a** — does a thought gain an explicit `ProposedAction`? **If not,
  4F.6 must be re-scoped.**
- At-most-once vs at-least-once delivery for the chosen transport (§5.4).
- Whether `decide()` may accept a caller-supplied `subject_id` (§5.3).
- Whether an expired request is persisted, if a TTL is ever ratified (§6.2).
- What the **producer** does with a raw `NoRespondersError` while **L-18** is
  open (§9.1).

---

## 14. **A-4F6-6 — the architecture amendment, exact text**

**To be appended additively to TDD 4F. Historical wording is preserved, not
rewritten.**

> ### 11.5 D-4F-9 — one internal `autonomy.*` subject, for the 4F.6 trigger. **RATIFIED 2026-09-22.**
>
> §11.4 reads *"No `autonomy.* ` subject."* §13 records that
> `cognitive-state-engine` *"publishes nothing."* §12 records that
> *"`autonomy-engine` gains no new route."* **All three stand as written, and
> none is deleted.** This section adds a bounded exception to the first two.
>
> **Why the exception is needed.** §13's own *Produces* row requires
> `cognitive-state-engine` to deliver **`DecisionRequest`s into
> `autonomy-engine`** (§6.2), and 4F.6's preparation established that the three
> statements above leave **no mechanism** by which it can: the engine has both
> allow-lists empty, only a health route and no outbound client;
> `autonomy-engine` has no intake route and an empty `SUBSCRIBABLE_SUBJECTS`;
> the registry contains no subject that fits; and **no Python engine in this
> repository calls another over HTTP** — engine-to-engine is the Event Bus,
> exclusively. The constraints were jointly unsatisfiable.
>
> **What §11.4's prohibition was protecting.** It sits beside §11.3, whose
> subject is **browser-reachable and consumer-less** subjects: *"a subject
> exists to be consumed, not to be complete"*, and *"`PUBLIC_TOPICS` is the sole
> browser realtime allow-list."* The prohibition guards the **public surface**
> and against subjects **nobody consumes**. **It was not written against an
> internal, server-side subject with exactly one consumer** — the same document
> permitted `action.execute` in §11.2 on precisely that basis.
>
> **The exception, and its bounds.** **One** subject,
> **`autonomy.decision.requested`**, is approved **for 4F.6 specifically**:
>
> - **Internal only.** **Never** added to `PUBLIC_TOPICS`, which stays at
>   **18**. Never browser-reachable. Not a public API. No gateway prefix.
> - **Exactly one server-side consumer**, `autonomy-engine`.
> - Registry **119 → 120**.
> - **This is not a general relaxation.** §11.4 otherwise stands: no
>   `TrustMetric` subject or RPC (**CF-10 stays open**), no new `memory.*` or
>   `digital_twin.*` subject, no wildcard widening, no `perception.*` in
>   `PUBLIC_TOPICS`.
>
> **The two statements this amends, and their replacements.** Each retirement is
> **disclosed and replaced by a tighter, test-enforced property** — the
> precedent §11.2 set when `action.execute` retired 4D's control 8:
>
> | Amended | Original wording | Replacement property |
> |---|---|---|
> | §13, Event Bus row | *"publishes nothing (§11.3)"* | *"publishes `autonomy.decision.requested` and **nothing else**"* |
> | §11.4, first clause | *"No `autonomy.* ` subject."* | *"**Exactly one** `autonomy.* ` subject exists; it is internal, server-side, single-consumer, and **not** in `PUBLIC_TOPICS`"* |
>
> **§12 is not amended.** *"`autonomy-engine` gains no new route"* remains true
> and is now **strengthened** by this decision: the trigger arrives over the
> bus, so no route is added. Its original sentence stands unqualified.
>
> **§13's *Produces* row is unchanged** — it already said
> `cognitive-state-engine` produces `DecisionRequest`s into `autonomy-engine`.
> This amendment supplies the mechanism that sentence always presupposed.
>
> *(Preserved per protocol principle 4: the original clauses of §11.4 and §13
> are quoted above verbatim and are not edited in place. This section is the
> dated note that explains what changed and why.)*

---

## 15. CF-9, CF-10 and CF-11 — all remain OPEN

**4F.6 closes none of them, and this TDD closes none of them.**

### 15.1 CF-11 — four distinct things, not one

| # | Claim | Who evidences it | After 4F.6 |
|---|---|---|---|
| **1** | **A production caller of `decide()` exists** | **4F.6** | **Expected: evidenced** |
| **2** | **Trigger delivery works** — a real producer's message reaches that caller over real infrastructure | **4F.6** | **Expected: evidenced** |
| **3** | **End-to-end Level 2 trigger-to-action behaviour** — trigger → decision → `action.execute` → `action-engine`, demonstrated in a running system | **4F.8** (AC-8) | **NOT evidenced by 4F.6** |
| **4** | **Final Phase 4 closure evidence** — verified and **recorded** in the closing document | **4F closure / the Gate Review (L-1)** | **NOT evidenced by 4F.6** |

**These must not be conflated.** §6.1: *"4F implementing a producer does not
close CF-11 by implication."* **1 and 2 are necessary and not sufficient.
Expected status after 4F.6: OPEN.**

### 15.2 CF-9 — **OPEN. Not 4F.6's**

Conditions 1, 3, 4 evidenced by 4F.4; condition 2 answered by **D-4F4-1**,
awaiting citation; **condition 5 unmet** — a category 3–5 documentation
obligation protocol §0.1 defers for a slice. 4F.6 contributes nothing.

### 15.3 CF-10 — **OPEN, and structurally blocked. Not 4F.6's**

Closure needs a Trust read surface — a served `digital_twin.*` subject or an
HTTP route — which §11.4 **still forbids**, unamended by §14. The trigger path
keeps Trust `UNAVAILABLE`, non-blocking, never a PASS.

---

## 16. RATIFICATION STATUS

### RATIFIED

| ID | Decision |
|---|---|
| **A-4F6-1** | **Internal Event Bus subject `autonomy.decision.requested`.** `cognitive-state-engine` → `autonomy-engine`. Internal only, one server-side consumer, never in `PUBLIC_TOPICS`, never browser-reachable, not a public API. Registry 119 → 120 permitted. An additive amendment, explained in §14 |
| **A-4F6-7** | **The production `decide()` caller lives at the application/orchestration boundary inside `autonomy-engine` — not `api/`, not `domain/`.** The module is proposed in §7 from existing precedent; **the boundary is ratified, the filename is not** |

### PROPOSED — REQUIRES USER RATIFICATION

| ID | Proposal | Confidence |
|---|---|---|
| **A-4F6-2** | **The repository is insufficient.** No trigger condition can be defined safely without **A-4F6-2a** — an explicit `ProposedAction` on `ActiveThought`. Proposed condition: *a thought carrying a complete `ProposedAction`, promoted to `IMMEDIATE`* | **The insufficiency is established. The proposed remedy is not ratified** |
| **A-4F6-2a** | Add `ProposedAction` to the cognitive-state domain (and schema). **May belong in its own slice** | Not ratified |
| **A-4F6-3** | **Reuse `action-engine`'s existing `action_id` guard** by deriving `subject_id` deterministically (UUIDv5 over a stable trigger identity). **No new mechanism.** **Depends on A-4F6-2a** | Mechanism verified; derivation not ratified |
| **A-4F6-4** | **No TTL.** Nothing in the repository justifies a number — the only lifetime constant is an auth cookie's | Not ratified |
| **A-4F6-5** | **Propagate, plus observability (c)** — matching the repository's actual convention, without inventing a `DecisionOutcome` | Not ratified |
| **A-4F6-6** | **The §14 amendment text**, as written | **Text proposed; not yet applied to TDD 4F** |

**None of A-4F6-2 … A-4F6-5 is ratified merely because a proposal exists here.**

### DEFERRED

| Item | Owner |
|---|---|
| End-to-end Level 2 trigger-to-action (CF-11 condition 3) | **4F.8** |
| CF-11 conditions 3 and 4; **CF-11 stays OPEN** | **4F.8 / 4F closure** |
| **CF-9** condition 5 and condition 2's citation | **4F closure** |
| **CF-10** — structurally blocked by §11.4 | **Beyond 4F** |
| **L-17** (web-client enum), **L-18** (SDK `NoRespondersError`) | Unchanged, both **OPEN** |
| The cognitive-state panel and `/v1/cognitive-state` | **4F.7** |
| At-most-once vs at-least-once delivery (§5.4) | Open sub-question |

---

## 17. Status

**A-4F6-1 and A-4F6-7 are RATIFIED. A-4F6-2 … A-4F6-6 are PROPOSED.**

**Implementation remains blocked** — principally on **A-4F6-2a**, without which
there is no safe trigger condition and 4F.6 must be re-scoped.
