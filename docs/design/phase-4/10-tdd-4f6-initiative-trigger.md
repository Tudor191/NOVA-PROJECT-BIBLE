# TDD 4F.6 — The initiative trigger: Level 2's *Triggered* state

**Revision 3 — 2026-09-22. Ratification-ready.** Revision 1 reported a
blocking architectural contradiction (§0); revision 2 ratified **A-4F6-1** and
**A-4F6-7**. This revision makes **A-4F6-3** and **A-4F6-5**
implementation-grade, resolves the four residual questions individually (§13),
and adds the **ratification checklist** (§16) and the **implementation
blockers** (§17).

**§16 is the authority on what is RATIFIED, PROPOSED, OPEN or DEFERRED.**
Nothing is ratified merely because a proposal for it exists here.

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

## 4. **A-4F6-2 / A-4F6-2a — the trigger condition and `ProposedAction`**

### 4.1 Why the repository alone is insufficient — re-verified

`ActiveThought` carries `description`, `priority`, `confidence`,
`dependencies`, `estimated_completion`, `related_memories`,
`related_projects`, `current_progress`, `attention_layer`, `created_at`,
`updated_at`. `AttentionAction` is `Literal["promote", "demote"]` — an
attention-layer transition, **nothing executable**.

A search across the engine's `src/` for `risk`, `PermissionCategory`,
`action_type`, `execution_target` and `verification` returns **only**
`FocusSignal.CURRENT_RISKS` and `FocusInputs.current_risks` — **a 0.0–1.0
focus-ranking weight, not a `RiskLevel`**, never to be coerced into one.

**A thought is a reasoning process, not a proposed action.** Supplying the
permission category and risk tier that every downstream gate is evaluated
against would be inventing security-relevant semantics.

### 4.2 The `ProposedAction` design, evaluated

| | |
|---|---|
| **Ownership** | **`cognitive-state-engine`.** D-4F-3 gives it the trigger; §6.2 already lists *"an action type"*, *"subject / context"* and *"a rationale"* among what it **MAY produce**. `ProposedAction` makes that explicit rather than inferred |
| **Attachment** | **Optional, on `ActiveThought`.** A thought is still a thought without one |

**Fields, and which are required:**

| Field | Required | Type | Note |
|---|---|---|---|
| `category` | **Yes** | see §4.4 | The permission category every gate is evaluated against |
| `risk` | **Yes** | `RiskLevel` | **`nova-contracts`**, shared — available |
| `title` | **Yes** | `str`, non-empty | Mirrors `description`'s non-empty rule |
| `action_type` | **Yes** | `str` | `action.execute` accepts only `Literal["terminal","filesystem"]` |
| `execution_target` | **Yes** | `str` | |
| `verification_method` | **Yes** | `str` | |
| `detail` | **No** | `str`, default `""` | `DecisionRequest.detail` already defaults to `""` |

**Validation rules:**

1. **All-or-nothing.** A partial `ProposedAction` is **invalid at the model
   boundary**, not silently completed. A thought either carries a complete one
   or none.
2. **A thought without `ProposedAction` never triggers.** Absence is never a
   low-risk default — the same fail-closed reading as *"absent policy means
   approval"*.
3. **`risk` is authored, never derived.** Deriving it from `confidence`,
   `priority` or `current_progress` is **forbidden**: `current_risks` is a
   ranking weight, and using it as a risk tier would be exactly the coercion
   §22.7 forbids for Trust.
4. **No `user_id` on `ProposedAction`.** Resolved server-side (§8).

**Trigger condition:** a thought carrying a **complete** `ProposedAction`,
**promoted to `IMMEDIATE`** — Part 6's *"critical events requiring instant
action"*, the one layer whose Bible definition is about acting.

**Determinism:** **yes.** `next_layer(current, action)` is a pure function over
a fixed transition table built by `_build_transitions()`, and promotion runs
through the existing `move_layer` repository operation. **4F.6 adds no new
transition mechanism.**

**Invalid states:** no `ProposedAction`; partial one; `attention_layer !=
IMMEDIATE`; a demotion; a thought already triggered for the same promotion
(§5).

### 4.3 The smallest concrete schema change

`cognitive_state.active_thought` already stores structured values as **JSONB**
— `dependencies`, `related_memories`, `related_projects`. The smallest change
follows that existing pattern exactly:

```
ALTER TABLE cognitive_state.active_thought
    ADD COLUMN proposed_action JSONB NULL;
```

| | |
|---|---|
| **Shape** | **One nullable JSONB column.** Additive |
| **Existing columns** | **None altered.** No type change, no backfill, no destructive step |
| **CHECK constraints** | The schema has **3**; this column adds none and conflicts with none |
| **Nullability** | `NULL` is the honest *"this thought proposes no action"* |
| **API surface affected** | **None.** `cognitive-state-engine` exposes **only `api/health.py`** at `4f1602a`. The read surface is **4F.7's**, and 4F.7 decides whether to render this |
| **Other persistence** | **None.** No `autonomy` schema change, no ORM change there |

### 4.4 **A contract dependency that must be settled — evidence**

| Enum | Home | Usable by `cognitive-state-engine`? |
|---|---|---|
| **`RiskLevel`** | **`nova_contracts.events.planning`** — shared | **Yes** |
| **`PermissionCategory`** | **`autonomy-engine`'s own `domain/models.py`** — an engine internal | **NO** |

**ADR-004 forbids it.** The first import-linter contract is *"Engines are
independent (ADR-004): no engine imports another engine's internals directly"*,
type `independence` — **7 contracts kept, 0 broken** today, and importing
`PermissionCategory` would break it.

`PermissionCategory` has **10 members** (`read`, `analyze`, `recommend`,
`create`, `modify`, `delete`, `execute`, `deploy`, `purchase`, `communicate`);
`action.execute`'s `action_type` is `Literal["terminal", "filesystem"]` — **2**.
**Neither derives from the other**, which 4F.5 already established.

**Two ways out, both requiring ratification:**

| Option | Consequence |
|---|---|
| **(a) The category vocabulary lives in the subject's `nova-contracts` payload** — which that subject needs regardless | No engine imports another. **But the vocabulary then has two homes**, and they must be kept in step |
| **(b) `PermissionCategory` moves to `nova-contracts`** | One home, shared properly. **Touches `autonomy-engine`'s domain**, which is a wider change than a trigger slice |

**Recommendation: (a)**, since the payload contract must exist anyway. **Not
chosen — see A-4F6-2b.**

### 4.5 Does this belong in 4F.6?

**Argued honestly: it is larger than "a trigger."** It adds a domain structure,
a contract vocabulary decision and a migration to an engine whose read surface
is 4F.7's.

| Option | Consequence |
|---|---|
| **(a) Inside 4F.6** | 4F.6 stays one coherent slice that actually delivers *Triggered*. **Cost:** a migration and a domain structure in a slice whose title is the trigger |
| **(b) A separate slice first** | Cleaner boundaries. **Cost:** inserts a slice before 4F.6 and delays CF-11 |

**Recommendation: (a)**, because splitting leaves 4F.6 with nothing to
deliver. **Not chosen — this is part of A-4F6-2a.**

---

## 5. **A-4F6-3 — duplicate identity. Two distinct layers**

### 5.1 The established pattern — verified, and it is exactly this

`digital-twin-engine/events/handlers.py` already does this:

```python
_ATTENTION_NAMESPACE = UUID("6f9d4a52-1c3f-5b8e-9f21-0a7d2c4e6b10")
observation_id=uuid5(_ATTENTION_NAMESPACE, str(envelope.event_id))
```

with the reasoning stated in its own docstring:

> *"One is derived deterministically from the envelope's own `event_id`
> (`uuid5`), which makes a redelivery of the **same event** idempotent — **the
> property the at-least-once bus actually requires** — without pretending two
> genuinely distinct observations are one."*

**`uuid5` with a module-private namespace constant is therefore an established
repository pattern, not an invention.**

### 5.2 Delivery semantics — **resolved by repository evidence**

**The bus is at-least-once.** The docstring above states it directly, and the
backend is **NATS + JetStream** (`backends/nats.py` line 1: *"NATS JetStream
`EventBus` backend — the default implementation (ADR-006)"*).

**Consequence: redelivery must be assumed, and idempotency is required, not
optional.** This is no longer OPEN.

### 5.3 The two layers, kept distinct

**Layer 1 — redelivery idempotency. Available today, no dependency.**

| | |
|---|---|
| **Namespace** | One module-private `UUID` constant in the consumer, e.g. `_DECISION_TRIGGER_NAMESPACE`, mirroring `_ATTENTION_NAMESPACE` |
| **Input** | **`str(envelope.event_id)` and nothing else** |
| **Canonical form** | `str(UUID)` — lowercase, hyphenated, Python's canonical form. **No JSON, no field ordering, no normalization needed** — a single UUID string |
| **Identical** | Two deliveries carrying the **same `event_id`** — i.e. a redelivery |
| **Distinct** | Any two envelopes with different `event_id`s, **even if every payload field matches** |
| **Timestamps** | **No.** `occurred_at` does not participate |
| **`correlation_id`** | **No.** It groups related work; it is not an identity |
| **`title` / `detail`** | **No.** Payload content never participates |

**Layer 2 — logical duplicate suppression. Depends on A-4F6-2a.**

Two *genuinely distinct* triggers for the same promotion (a producer bug, or a
restart re-emitting) carry different `event_id`s, so Layer 1 does **not**
suppress them. Suppressing those needs a **trigger identity**:
`uuid5(namespace, f"{thought_id}:{promotion-identity}")` — and **the promotion
identity does not exist** until A-4F6-2a defines it. `updated_at` is the
nearest candidate and is **not** stable enough to key on.

### 5.4 The connection to `action-engine`'s guard

`_idempotent_reply_if_terminal(action_id)` runs *"before any stage runs, and
before the Action row is even inserted, so a genuine retry never re-triggers
any side effect, **including the approval loop**"*, replaying the stored
terminal result; `ActionORM`'s PK gives `ActionAlreadyExistsError` underneath.

**The guard is sound and is keyed on the `action_id` it is handed.** Today
`subject_id = uuid4()` (`decision.py:480`), so **two deliveries of the same
trigger produce two different `action_id`s and the guard never fires.**

**Proposal:** on the trigger path, derive `subject_id` from Layer 1 — so a
redelivered trigger yields the **same** `action_id`, and `action-engine`'s
**existing** guard suppresses the duplicate execution.

| | |
|---|---|
| **New mechanism** | **None** |
| **Database constraint** | **None.** No repository evidence requires one: the guard already lives at the execution boundary, which is where double-execution is actually prevented |
| **Migration** | **None** |
| **Required change** | `decide()` must accept a caller-supplied `subject_id`, or the orchestrator must derive it before calling. **That is a change to a 4F.5 signature** and must be explicit |
| **Residual** | Two `decision_log` rows may still exist for one logical trigger — consistent with *"the decision log records every attempt"*, but a conscious acceptance |

---

## 6. **A-4F6-4 — TTL. Not implemented, and no value invented**

### 6.1 Why no TTL exists today

A repository-wide search for `ttl`, `expires_at`, `expiry`, `max_age` and
`stale` across every engine's `src/` returns **exactly one** numeric lifetime:
`session_cookie_max_age_seconds` in `api-gateway` — **an auth cookie**, not a
request lifecycle. **No request-shaped payload in this repository carries an
expiry, a TTL or a maximum age.** `EventEnvelope` carries `occurred_at`, and
**nothing consumes it as a deadline.**

### 6.2 Why 4F.5's 15-second bound is not reusable

**It bounds a different thing.** D-4F5-3's 15 seconds bounds **how long
`autonomy-engine` waits for `action-engine`'s reply** — it is a *reply* timeout,
chosen against `action-engine`'s 300-second approval loop. A trigger TTL would
bound **how old a request may be before it is refused** — an unrelated
quantity, with unrelated inputs.

Reusing the number would imply the two are related, and **§22.3 already
forbids the analogous conflation**: a timeout must stay distinguishable from
other conditions rather than becoming a general-purpose number.

### 6.3 The exact future decision, if a TTL is ever introduced

| | |
|---|---|
| **Decision required** | A ratified maximum trigger age, with its evidential basis — **not a round number chosen for comfort** |
| **Authoritative clock** | **`EventEnvelope.occurred_at`** — producer-side, UTC, already on every envelope. **Not** the consumer's wall clock, which would make expiry depend on which instance received it |
| **Clock-skew** | Must be addressed explicitly: producer and consumer clocks are not guaranteed aligned |
| **Expired behaviour** | **Refused without invoking `decide()`** |
| **Persisted or discarded?** | **A ratification in itself.** `DecisionLogEntry` requires a `DecisionOutcome`, and **no member means "expired before a decision"**. Persisting one would mean inventing an outcome — which 4F.5 deliberately refused to do for `ActionDispatchUnavailable`. **Discarding is therefore the lower-cost default, at the price of an unaudited drop** |

**4F.6 implements no TTL.**

---

## 7. **A-4F6-7 — the caller. Boundary RATIFIED, filename OPEN**

**Ratified:** the production `decide()` caller lives at the
**application/orchestration boundary** inside `autonomy-engine` — **not
`api/`, not `domain/`.**

**Package placement — established precedent.** Orchestration modules sit at the
**package root**, beside `main.py`, outside both `api/` and `domain/`:

- `perception-engine/…/observation_orchestration.py`
- `communication-engine/…/conversation_orchestration.py`

`observation_orchestration.py` is the closest analogue — it takes an inbound
payload and drives an existing-but-uncalled domain chain, which is exactly
4F.6's shape.

| Candidate | Assessment |
|---|---|
| **`decision_orchestration.py`** | Matches `<noun>_orchestration.py` exactly. **But `decision` is already the name of the `domain/decision.py` module**, and two modules differing only by suffix may read as duplicates |
| **`trigger_orchestration.py`** | Names what the module *is for* — the trigger path — and collides with nothing. Slightly narrower if other callers of `decide()` appear later |
| **`initiative_orchestration.py`** | Matches the project's own vocabulary (*"the initiative trigger"*, *"the Initiative Engine is the natural owner"*, CF-11) and collides with nothing |

**No recommendation is forced.** The boundary is ratified; **the filename stays
OPEN** pending the final repository-evidence review. **The module is not
created.**

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

## 13. The four residual questions, resolved individually

### 13.1 Duplicate delivery semantics

| | |
|---|---|
| **Repository evidence** | The SDK backend is **NATS + JetStream** (`backends/nats.py` line 1, ADR-006). `digital-twin-engine`'s handler docstring states the property directly: deriving a deterministic id *"makes a redelivery of the **same event** idempotent — **the property the at-least-once bus actually requires**"*, and uses `uuid5(_ATTENTION_NAMESPACE, str(envelope.event_id))` |
| **Proposed answer** | **At-least-once. Redelivery must be assumed.** Layer 1 (§5.3) derives the trigger's identity from `envelope.event_id` via `uuid5`, and the trigger path uses it as `subject_id` so `action-engine`'s **existing** guard suppresses the duplicate execution |
| **Implementation consequence** | One namespace constant; one `uuid5` call; `decide()` must accept a caller-supplied `subject_id`. **No new mechanism, no constraint, no migration** |
| **Test consequence** | A `real_infra` test delivering the **same envelope twice** and asserting: two log rows are acceptable, **exactly one execution occurs**, and the second dispatch replays the stored terminal result rather than re-running the pipeline |
| **Requires ratification?** | **Yes** — for the `subject_id` derivation and the 4F.5 signature change. **The at-least-once fact itself is evidence, not a decision** |

### 13.2 Stale-trigger semantics

| | |
|---|---|
| **Repository evidence** | **No request-shaped payload carries an expiry.** The only numeric lifetime anywhere is an `api-gateway` auth cookie. `EventEnvelope.occurred_at` exists and **nothing consumes it as a deadline** |
| **Proposed answer** | **No TTL in 4F.6.** A stale trigger is processed normally; every gate still runs, so a stale trigger cannot execute anything a fresh one could not |
| **Implementation consequence** | **None** — no code, no field, no comparison |
| **Test consequence** | A test asserting that **age alone changes nothing**, so the absence is deliberate and visible rather than an oversight |
| **Requires ratification?** | **Yes**, to accept "no TTL" as the position. Introducing one later needs its own ratification (§6.3) |

### 13.3 Unexpected transport error semantics

| | |
|---|---|
| **Repository evidence** | **No `serve()` handler in the repository catches anything.** `action-engine`'s `action.execute` handler calls `model_validate` and the domain function with **no `try`/`except`**; the SDK's `_callback` has none either. An exception propagates, **no reply is published**, and the requester times out. Separately, **`autonomy-engine` has no `observability.py`** — other engines do, with OpenTelemetry `Counter`s — and its `main.py` uses a plain `logger` |
| **Proposed answer** | **Propagate, plus observability (§9.1).** `decide()` is not invoked; no `DecisionLogEntry` exists; no trigger-layer retry; **no new `DecisionOutcome`** |
| **Implementation consequence** | Either a structured `logger` call at the boundary using the existing logger, **or** a new `observability.py` for `autonomy-engine` — **the latter is a new module and a scope question** |
| **Test consequence** | A test asserting `decide()` is **not** called when the handler raises, that **no** log row is written, and that **no retry** occurs |
| **Requires ratification?** | **Yes**, on two points: accepting an **unaudited** lost trigger, and whether `autonomy-engine` gains an `observability.py` |

### 13.4 TTL policy

| | |
|---|---|
| **Repository evidence** | As §13.2. Additionally, 4F.5's 15-second bound is a **reply** timeout measured against `action-engine`'s 300-second approval loop — a different quantity with different inputs (§6.2) |
| **Proposed answer** | **No TTL. No value invented.** If one is ever introduced: `EventEnvelope.occurred_at` is authoritative, clock skew must be addressed, expired requests are refused **without** invoking `decide()`, and **whether they are persisted is itself a ratification** because no `DecisionOutcome` means "expired" |
| **Implementation consequence** | **None in 4F.6** |
| **Test consequence** | **None in 4F.6**, beyond §13.2's deliberate-absence test |
| **Requires ratification?** | **Yes** — to accept the absence now, and again in full if a TTL is ever added |

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

## 16. 4F.6 RATIFICATION CHECKLIST

**Every 4F.6 architectural decision appears in exactly one category.**

### RATIFIED

| Decision | Statement |
|---|---|
| **Trigger subject** (**A-4F6-1**) | **`autonomy.decision.requested`.** `cognitive-state-engine` → `autonomy-engine`. **Internal only**, exactly **one** server-side consumer, **never in `PUBLIC_TOPICS`**, never browser-reachable, not a public API, **no gateway prefix**. Registry **119 → 120** permitted |
| **Caller boundary** (**A-4F6-7**) | The production `decide()` caller lives at the **application/orchestration boundary** inside `autonomy-engine` — **not `api/`, not `domain/`** |

### PROPOSED

| Decision | Proposal | Depends on |
|---|---|---|
| **Trigger condition** (**A-4F6-2**) | A thought carrying a **complete `ProposedAction`**, **promoted to `IMMEDIATE`**. Deterministic through the existing `next_layer` / `move_layer` mechanism. **A thought without one never triggers** | **A-4F6-2a** |
| **`ProposedAction` schema** (**A-4F6-2a**) | Optional structure on `ActiveThought`; 6 required fields + optional `detail`; **all-or-nothing** validation; `risk` **authored, never derived**. Smallest change: **one nullable JSONB column** `proposed_action`, additive, **no existing column altered**, **no API surface affected** | — |
| **Category vocabulary** (**A-4F6-2b**) | `RiskLevel` is shared and usable; **`PermissionCategory` is an `autonomy-engine` internal** that ADR-004 forbids importing. Recommend **(a)** the vocabulary lives in the subject's `nova-contracts` payload; alternative **(b)** move `PermissionCategory` to `nova-contracts` | — |
| **Slice placement** (**A-4F6-2c**) | Recommend `ProposedAction` **inside 4F.6**, because splitting leaves 4F.6 with nothing to deliver | — |
| **Duplicate identity** (**A-4F6-3**) | **Layer 1**, available now: `uuid5(namespace, str(envelope.event_id))`, used as the trigger's `subject_id` so **`action-engine`'s existing guard** suppresses duplicate execution. **No new mechanism, no constraint, no migration.** Requires `decide()` to accept a caller-supplied `subject_id`. **Layer 2** (logical duplicates) depends on A-4F6-2a | Layer 2 → **A-4F6-2a** |
| **Transport error behaviour** (**A-4F6-5**) | **Propagate + observability.** `decide()` never invoked; **no** log entry; **no** retry; **no new `DecisionOutcome`**. Open sub-point: whether `autonomy-engine` gains an `observability.py` | — |
| **§11.4 / §13 amendment** (**A-4F6-6**) | The exact text in §14, appended additively to TDD 4F as **D-4F-9**. Historical wording **quoted, not edited** | — |

### OPEN

| Item | Why it is open |
|---|---|
| **TTL** (**A-4F6-4**) | **No value exists to adopt** — the only lifetime constant in the repository is an auth cookie's, and 4F.5's 15-second bound measures a different quantity. **No TTL in 4F.6**; accepting that absence is itself a ratification |
| **Stale-trigger behaviour** | Follows the TTL decision. Currently: **processed normally; every gate still runs** |
| **Module filename** | `decision_orchestration.py` / `trigger_orchestration.py` / `initiative_orchestration.py`. **Package root**, per precedent. Deliberately unresolved pending the final evidence review |
| **`decide()` signature change** | Whether it may accept a caller-supplied `subject_id` — required by A-4F6-3 Layer 1 |
| **Unaudited lost trigger** | Whether propagate-without-a-log-row is acceptable (§13.3) |
| **`autonomy-engine` `observability.py`** | The engine has none today; adding one is a new module |
| **CF-9** | **OPEN.** Conditions 1, 3, 4 evidenced by 4F.4; condition 2 answered by **D-4F4-1** awaiting citation; **condition 5 unmet** — a category 3–5 documentation obligation. **4F.6 contributes nothing.** No evidence proves otherwise |
| **CF-10** | **OPEN, and structurally blocked.** Closure needs a Trust read surface that §11.4 **still forbids**, unamended by §14. **4F.6 contributes nothing.** No evidence proves otherwise |
| **CF-11** | **OPEN.** 4F.6 can evidence **claims 1 and 2** (a production caller exists; trigger delivery works). **Claim 3** (end-to-end trigger-to-action) is **4F.8's**; **claim 4** (recorded closure evidence) is **4F closure's**. §6.1: *"implementing a producer does not close CF-11 by implication."* No evidence proves otherwise |

### DEFERRED

| Item | Owner |
|---|---|
| End-to-end Level 2 trigger-to-action — **CF-11 claim 3** | **4F.8** (AC-8) |
| Recorded CF-11 closure — **claim 4** | **4F closure / the Gate Review (L-1)** |
| **CF-9** condition 5, and condition 2's citation | **4F closure** |
| **CF-10** — blocked by §11.4 | **Beyond 4F** |
| **L-17** (web-client policy-effect enum) | A later policy-authoring / UI scope — **OPEN**, untouched |
| **L-18** (SDK `NoRespondersError`) | `nova-eventbus-sdk` / later maintenance — **OPEN**, untouched. **4F.6 must not fix the SDK** |
| The cognitive-state panel and `/v1/cognitive-state` prefix | **4F.7** |
| Whether 4F.7 renders `proposed_action` | **4F.7** |

---

## 17. IMPLEMENTATION BLOCKER

**Implementation cannot start. These decisions are architecture, not detail,
and none is hidden inside an implementation choice.**

| # | Blocker | Why it blocks |
|---|---|---|
| **1** | **A-4F6-2a — `ProposedAction`** | **The primary blocker.** Without it there is **no safe trigger condition**: a `DecisionRequest` needs a permission category and a risk tier that `ActiveThought` does not carry, and inventing them would fabricate the security semantics every downstream gate is evaluated against. **If rejected, 4F.6 must be re-scoped.** |
| **2** | **A-4F6-2b — the category vocabulary** | **ADR-004's import-linter contract forbids** `cognitive-state-engine` importing `PermissionCategory` from `autonomy-engine`. Without a ratified home, the payload contract **cannot be written at all** |
| **3** | **A-4F6-3 — `decide()`'s `subject_id`** | The bus is **at-least-once**, so idempotency is required, not optional. It works **only** if the trigger path supplies `subject_id`, which changes a 4F.5 signature |
| **4** | **A-4F6-6 — the amendment** | The subject in A-4F6-1 stays **contradicted by TDD 4F §11.4 and §13 until the amendment is applied.** Implementing first would leave the architecture self-contradictory in the repository |
| **5** | **A-4F6-5 — the unaudited lost trigger** | Accepting that a transport failure leaves **no audit row** is a deliberate safety position, not an implementation detail |

**Not blockers** — these may be settled during implementation without changing
the architecture: the module filename (§7), and whether `autonomy-engine` gains
an `observability.py` (§13.3), provided the *behaviour* in A-4F6-5 is ratified.

---

## 18. Status

**RATIFIED: A-4F6-1 (trigger subject) and A-4F6-7 (caller boundary).**
**Everything else is PROPOSED, OPEN or DEFERRED per §16.**

**Implementation remains blocked on the five items in §17**, principally
**A-4F6-2a**.

**CF-9, CF-10 and CF-11 all remain OPEN.** No evidence in this revision proves
otherwise, and this document closes none of them.
