# TDD 4F.6 — The initiative trigger: Level 2's *Triggered* state

**Revision 6 — 2026-09-22. RATIFIED.** Revisions 1–5 found the blocking
contradiction (§0) and produced the full decision analysis. **This revision
applies the ratifications: A-4F6-1, A-4F6-2a, A-4F6-2b Option A, A-4F6-3
Layer 1, A-4F6-5 Design A, A-4F6-6, A-4F6-7 and the module filename are
RATIFIED.** A-4F6-3 Layer 2 and persistent lost-trigger auditability are
**DEFERRED**; TTL and stale-trigger semantics remain **OPEN**.

**There are no remaining BLOCKING ARCHITECTURE decisions (§17), and §19 is the
Implementation Contract the implementation branch must satisfy.**

> **Corrections carried forward, not dropped.** Revision 3 claimed *"no
> `serve()` handler in the repository catches anything"* — **false**. Revision 4
> then said **four** engines had degraded-reply serve handlers — **also wrong**:
> `personality-engine`'s catch is at **startup**, not in a handler. **The
> correct count is three.** Revision 4 also estimated Option A's blast radius at
> 16 files; **re-export makes it ~2**, which is what changed that
> recommendation. All are quoted in place rather than quietly amended.

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

> **Added 2026-09-26 (4F.7 ratification, RS-6a and RS-6b — TDD 4F §24.7),
> additively.** The table and the definition above are preserved.
>
> - **Row 4's "All of it" describes the mechanism 4F.6 built.** Both the
>   producer and the consumer exist, and the consumer runs in production.
> - **Against the definition above, the production end-to-end *Triggered* state
>   is not yet evidenced.** The definition requires *"a production component,
>   reachable in a deployed system without a test harness"*. Neither half of
>   that holds yet:
>   - `cognitive-state-engine` is not deployed;
>   - no production component promotes an Active Thought.
> - **What makes it evidenceable.** The production promotion driver belongs to
>   the new slice **4F.P** (TDD 4F §18, as amended). Deploying the engine in
>   4F.7 does not change this status on its own.
> - ***Triggered* stays a system-level property.** There is no per-thought
>   triggered state, enum, field or persisted outcome.
> - **CF-11 stays OPEN.**

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
| `category` | **Yes** | see §4.6 | The permission category every gate is evaluated against |
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

### 4.6 **A-4F6-2b — `PermissionCategory` ownership. RATIFIED: Option A**

#### 4.6.1 The decisive precedent

`RiskLevel` lives in `nova_contracts/events/planning.py`, and its docstring
states why, verbatim:

> *"**Bible Part 14's** risk classification scale
> (`docs/bible/part-14-autonomy-engine.md:271-279`), reused verbatim — **the one
> canonical risk-tier scale anywhere in this project, rather than a second,
> `planning-engine`-specific scale that `action-engine` (TDD 3D) would otherwise
> have to reinterpret or map**."*

Three facts make this decisive rather than merely suggestive:

1. **`RiskLevel` comes from `part-14-autonomy-engine.md` — `autonomy-engine`'s
   own Bible part.** A vocabulary owned conceptually by autonomy was already
   placed in `nova-contracts` **because another engine would otherwise have to
   map it.** That is precisely the situation `PermissionCategory` is now in.
2. **`PermissionCategory` is from the same Bible part.** The web client's own
   comment calls it *"Bible Part 14's ten permission categories, verbatim and in
   its order."* **Two vocabularies, one source document; one is already
   canonical in contracts and the other is not.**
3. **`autonomy-engine/domain/models.py:29` already reads
   `from nova_contracts.events.planning import RiskLevel`** — in the very file
   that defines `PermissionCategory`. The pattern is already in place there.

**Supporting structure:** every domain with bus contracts has an
`events/<domain>.py` in `nova-contracts` carrying its enums — `perception`,
`memory`, `communication`, `personality`, `executive_cognition`, `world_model`,
`system`, `agent_os`, `planning`. **There is no `events/autonomy.py` only
because autonomy had no bus contract.** A-4F6-1 creates one, so that module will
exist, and it is where this vocabulary belongs.

**Both engine patterns exist** — `ConversationState` and `MemoryType` are
**imported** from contracts; `ConfidenceTier` is **duplicated** in
`personality-engine` (whose docstring notes the value is *"caller-supplied,
never re-derived by this engine"*). So duplication is tolerated **where the
engine merely receives the value**. `autonomy-engine` does **not** merely
receive it: it evaluates gates against it, which is the case for canonical
ownership.

#### 4.6.2 Impact tables

**Option A — move `PermissionCategory` into `nova-contracts`.**

| Dimension | Impact |
|---|---|
| **Source files affected** | **2**: new/extended `nova_contracts/events/autonomy.py`; `autonomy-engine/domain/models.py` |
| **Imports added** | One: `from nova_contracts.events.autonomy import PermissionCategory` in `domain/models.py`, **re-exported through the existing `__all__`** |
| **Imports removed** | **None** |
| **Engines affected** | **1** (`autonomy-engine`), and only at the definition site |
| **Contract files affected** | 1 new/extended module + its generated TS |
| **Serialization impact** | **None.** `StrEnum` → identical wire strings |
| **Import-linter impact** | **None broken.** Both engines import a shared package |
| **Tests affected** | **None expected** — the re-export keeps every existing import path valid |
| **Migration impact** | **None.** `permission_grant.category` is `TEXT`, no CHECK |
| **API impact** | **None** |
| **Event Bus impact** | **None beyond A-4F6-1's subject** |
| **Semantic duplication risk** | **Reduced.** The web client could import the generated type instead of hand-maintaining ten strings |
| **Breaking-change risk** | **Low.** Behaviour-preserving; values identical |
| **Blast radius** | **~2 files** — *not* the 16 estimated in revision 4, because **re-export leaves all 16 call sites unchanged**. This correction is what changes the recommendation |
| **ADR-004 compatibility** | **Compatible** |

**Option B — a parallel vocabulary in `nova-contracts`, engine enum preserved.**

| Dimension | Impact |
|---|---|
| **Source files affected** | 1 (`nova_contracts/events/autonomy.py`) + a drift test |
| **Imports added** | None in engines |
| **Imports removed** | **None** |
| **Engines affected** | **0** |
| **Contract files affected** | 1 + generated TS |
| **Serialization impact** | **None** |
| **Import-linter impact** | **None broken** |
| **Tests affected** | **A new drift test is mandatory**, binding the two vocabularies member-for-member |
| **Migration impact** | **None** |
| **API impact** | **None** |
| **Event Bus impact** | **None beyond A-4F6-1's subject** |
| **Semantic duplication risk** | **High and permanent — two authorities for a security-relevant vocabulary**, plus the web client's third copy |
| **Breaking-change risk** | **None** |
| **Blast radius** | **~1 file + a test** — the smallest |
| **ADR-004 compatibility** | **Compatible** |

#### 4.6.3 Recommendation

**RATIFIED 2026-09-22: Option A.**

The evidence is specific, not general: **the sibling vocabulary from the same
Bible part already lives in `nova-contracts`, for the stated reason that another
engine would otherwise have to map it** — and `autonomy-engine` already imports
it from there. Option B would create the *second vocabulary* that `RiskLevel`'s
docstring exists to argue against, for a value on which **every permission gate
is evaluated**.

Revision 4 left this OPEN on a blast-radius estimate of 16 files. **That
estimate was wrong**: a re-export through the existing `__all__` leaves every
call site untouched, so Option A costs ~2 files. With that corrected, the two
considerations no longer point in opposite directions and **the evidence
supports A clearly.**

**Ratified 2026-09-22.** `PermissionCategory` moves to
`nova_contracts/events/autonomy.py`, with call-site compatibility preserved
through the repository's established **re-export** pattern. **The vocabulary
stays canonical: no duplicate in `cognitive-state-engine`, and no second
`PermissionCategory` type.** **The source move is not performed by this
document** — it is TDD ratification only.


#### 4.6.4 **A-4F6-2c — does `ProposedAction` belong in 4F.6? RESOLVED: yes**

**It is larger than "a trigger":** a domain structure, a vocabulary decision and
a migration, in an engine whose read surface is 4F.7's.

| Option | Consequence |
|---|---|
| **(a) Inside 4F.6** | 4F.6 stays one slice that actually delivers *Triggered*. **Cost:** a migration in a slice named for the trigger |
| **(b) Its own slice first** | Cleaner boundaries. **Cost:** inserts a slice before 4F.6 and delays CF-11 |

**RESOLVED 2026-09-22: option (a) — inside 4F.6.** No separate slice is created
solely for `ProposedAction`. This is subsumed by **A-4F6-2a's ratification** and
no longer appears as an independent decision in §16.


### 4.7 **A-4F6-2a — the final implementation-grade `ProposedAction` spec**

| | |
|---|---|
| **Type name** | **`ProposedAction`** |
| **Ownership** | **`cognitive-state-engine`**, `domain/models.py`. D-4F-3 gives it the trigger; §6.2 lists *"an action type"*, *"subject / context"* and *"a rationale"* among what it MAY produce |
| **Attachment** | **`ActiveThought.proposed_action: ProposedAction \| None = None`** — optional |

**Fields:**

| Field | Type | Required | Semantics |
|---|---|---|---|
| `category` | **pending A-4F6-2b** | **Yes** | **The permission category every gate is evaluated against.** Authored, never inferred from the thought |
| `risk` | `RiskLevel` (`nova-contracts`) | **Yes** | **Authored, never derived.** Deriving from `confidence`, `priority`, `current_progress` or `current_risks` is **forbidden** — `current_risks` is a 0–1 ranking weight, and coercing it is the error §22.7 forbids for Trust. Above `low` **cannot** auto-execute (4F.5 X-6), so an honest high value simply yields a suggestion |
| `action_type` | `str` | **Yes** | What `action-engine` will execute. `action.execute` accepts only `Literal["terminal","filesystem"]`; a value outside it is **rejected by the contract at dispatch**, not silently mapped. **Does not derive from `category`** — 10 vs 2, established by 4F.5 |
| `execution_target` | `str`, non-empty | **Yes** | *What* the action acts on. **Never defaulted** — a missing target yields a suggestion (X-14), never a guess |
| `verification_method` | `str`, non-empty | **Yes** | How the result is verified. **Never defaulted**, same reasoning |
| `title` | `str`, non-empty | **Yes** | Becomes `DecisionRequest.title`; surfaces in the suggestion a user approves. Non-empty mirrors `description`'s existing rule |
| `detail` | `str` | **No**, default `""` | Becomes `DecisionRequest.detail`, which already defaults to `""` |

**Validation rules:**

1. **All-or-nothing.** `ProposedAction` is either **absent** or **complete**.
   A partial instance is **invalid at the model boundary** — Pydantic required
   fields — and is never silently completed.
2. **Absence never triggers.** No `ProposedAction` → no trigger. The same
   fail-closed reading as *"absent policy means approval"*.
3. **No `user_id`.** Resolved server-side from `primary_user_id` (§8).
4. **No `subject_id`.** Decision identity is **consumer-derived** (§5.4 Q1).
5. **Non-empty strings** for `title`, `execution_target`, `verification_method`.

**Is JSONB still the smallest schema change? — Yes.**

```
ALTER TABLE cognitive_state.active_thought
    ADD COLUMN proposed_action JSONB NULL;
```

| | |
|---|---|
| **Precedent** | `dependencies`, `related_memories`, `related_projects` are **already JSONB** on this table |
| **Existing columns** | **None altered.** No type change, no backfill, no destructive step |
| **CHECK constraints** | The schema has **3**; this adds none and conflicts with none |
| **Alternative considered** | A separate `proposed_action` table with a FK — **larger**: a second table, a join, and a lifecycle to keep in step with the thought |
| **Does the existing persistence model support it unchanged?** | **Yes.** `ActiveThoughtORM` already maps JSONB columns; `upsert_thought` / `get_thought` / `list_thoughts` / `move_layer` need no signature change |
| **API surface affected** | **None.** `cognitive-state-engine` exposes only `api/health.py`; the read surface is **4F.7's** |
| **`autonomy` schema** | **Untouched** |


---

## 5. **A-4F6-3 — subject identity. Two layers, resolved separately**

### 5.1 The established pattern, and the delivery fact

`digital-twin-engine/events/handlers.py` already derives a deterministic id:

```python
_ATTENTION_NAMESPACE = UUID("6f9d4a52-1c3f-5b8e-9f21-0a7d2c4e6b10")
observation_id=uuid5(_ATTENTION_NAMESPACE, str(envelope.event_id))
```

> *"…which makes a redelivery of the **same event** idempotent — **the property
> the at-least-once bus actually requires** — without pretending two genuinely
> distinct observations are one."*

**The bus is at-least-once** (backend: NATS + JetStream, ADR-006). Idempotency
is therefore **required, not optional**. This is repository evidence, not a
decision.

### 5.2 Layer 1 — transport duplicate identity

**Exact mapping:**

```
subject_id = uuid5(_DECISION_TRIGGER_NAMESPACE, str(envelope.event_id))
```

| | |
|---|---|
| **Namespace** | **`_DECISION_TRIGGER_NAMESPACE = UUID("0c81f3b8-e30f-5f0a-9241-8985e4b83489")`** — a module-private constant in `decision_orchestration.py`, mirroring `digital-twin-engine`'s `_ATTENTION_NAMESPACE`. **A fixed literal, never generated at runtime.** Its provenance is reproducible — `uuid5(NAMESPACE_DNS, "autonomy.decision.requested.nova")` — but the **literal is what is pinned**, exactly as the precedent pins one |
| **Input** | **`str(envelope.event_id)` and nothing else** |
| **Canonical form** | Python's canonical `str(UUID)` — lowercase, hyphenated. **No JSON, no field ordering, no normalization** — the input is one UUID string |
| **Owner of generation** | **The consumer, `autonomy-engine`.** Derived from the envelope it received |
| **Identical** | Two deliveries carrying the same `event_id` — a redelivery |
| **Distinct** | Different `event_id`s, **even if every payload field matches** |
| **Non-participants** | `occurred_at`, `correlation_id`, `causation_id`, `title`, `detail`, and all payload content |

### 5.3 Layer 2 — logical duplicate identity

Two *genuinely distinct* envelopes representing the same initiative (a producer
restart re-emitting) carry different `event_id`s, so Layer 1 does **not**
suppress them.

**Participating fields, if Layer 2 is ratified:**

```
uuid5(_INITIATIVE_NAMESPACE, f"{thought_id}|{proposed_action_digest}")
```

| Field | Participates? | Why |
|---|---|---|
| `thought_id` | **Yes** | The stable identity of the thought that proposed the action |
| `category`, `risk`, `action_type`, `execution_target`, `verification_method` | **Yes** | They define *what* is proposed; a change is a different initiative |
| `title`, `detail` | **No** | Human-readable text; an edited wording is not a new initiative |
| `attention_layer` | **No** | The trigger already requires `IMMEDIATE` |
| `updated_at`, `created_at` | **No** | **Not stable enough to key on** |
| `priority`, `confidence`, `current_progress` | **No** | They change continuously without changing the proposal |
| `correlation_id`, `event_id` | **No** | Layer 1's concern |

**Canonical serialization** would need ratifying: a `|`-joined ordered field
list, lowercased enum values, with a fixed field order. **This layer is blocked
on A-4F6-2a**, since `proposed_action` does not exist yet.

### 5.4 The seven questions, answered explicitly

| # | Question | Answer |
|---|---|---|
| **1** | **Does caller-supplied `subject_id` become part of `DecisionRequest`?** | **No — and this is the important answer.** `subject_id` must **not** be a producer-supplied payload field. It is **derived by the consumer** from the envelope. Putting it in `DecisionRequest` as a caller input would let a producer choose a decision's identity |
| **2** | **Where is it validated?** | It is never validated because it is never received. The consumer derives it, so it is well-formed by construction |
| **3** | **Who owns generation?** | **`autonomy-engine`**, in the orchestration module, from `envelope.event_id` |
| **4** | **What prevents arbitrary callers creating collisions?** | **The allow-list and the derivation together.** `PUBLISHABLE_SUBJECTS` admits exactly one producer; `event_id` is SDK-generated per envelope; and since the consumer derives the id, a malicious payload **cannot** name an existing decision. A caller that forged an `event_id` could only collide with its *own* prior trigger — which is the idempotent case, not an escalation |
| **5** | **Same event redelivered?** | Same `event_id` → same `subject_id` → same `action_id` → **`action-engine`'s guard replays the stored terminal result. Nothing executes twice** |
| **6** | **Two distinct events, same logical initiative?** | Different `event_id`s → different `subject_id`s → **two decisions and two dispatches**. Layer 1 does not help. **Layer 2 is the only remedy, and it is blocked on A-4F6-2a** |
| **7** | **Is `action-engine`'s guard still sufficient?** | **Sufficient for redelivery (case 5), not for case 6.** It is keyed on the `action_id` it is handed, and `_idempotent_reply_if_terminal` runs *"before any stage runs, and before the Action row is even inserted"* — so it is the correct and sufficient place for duplicate **execution**. It cannot know that two differently-keyed requests are the same initiative |

### 5.5 Consequence for `decide()`

`decide()` currently sets `subject_id = uuid4()` internally
(`decision.py:480`). Layer 1 requires the **orchestrator** to supply it.

**Two shapes, both requiring ratification:** an optional `subject_id`
keyword on `decide()`, or derivation inside the orchestrator with `decide()`
refactored to accept it. **Either changes a 4F.5 signature**, and the field
must remain **impossible to set from the payload**.

**No database constraint and no migration.** No repository evidence requires
one: duplicate *execution* is already prevented at the execution boundary, and
`decision_log` is deliberately append-only with *"every attempt"* recorded.


---

### 5.6 **Layer 2 — resolved: DEFERRED, with a named owner**

**A. Two events, different `event_id`, identical `ProposedAction` semantics —
what are they?**

**Unresolved by evidence, and therefore deliberately deferred.** The repository
cannot answer it, and the two readings are both defensible:

- **Same initiative** — if the producer re-emitted after a restart, acting twice
  on one intention is wrong.
- **Different initiatives** — if the same thought legitimately re-reached
  `IMMEDIATE` after being demoted and re-promoted, that is a **new** intention
  about the same subject, and suppressing it would silently drop real work.

**Nothing in the repository distinguishes the two cases**, because the
distinguishing fact — whether a promotion is *new* — lives in `ProposedAction`
and its promotion history, **neither of which exists yet**.

**B. If logical deduplication is required, the canonical identity is:**

```
uuid5(_INITIATIVE_NAMESPACE, "thought_id|category|risk|action_type|execution_target|verification_method")
```

| Participates | Excluded |
|---|---|
| `thought_id` | `title`, `detail` — human text; an edit is not a new initiative |
| `category`, `risk` | `created_at`, `updated_at` — **not stable enough to key on** |
| `action_type` | `priority`, `confidence`, `current_progress` — change continuously |
| `execution_target`, `verification_method` | `attention_layer` — the trigger already requires `IMMEDIATE` |
| | `event_id`, `correlation_id` — Layer 1's concern |

Canonical form: fields in the order above, `|`-joined, enum values lowercased,
no whitespace normalization beyond each field's own validation.

**C. Layer 2 is NOT required for 4F.6. It is DEFERRED.**

**Why deferral is safe, on evidence:**

1. **Layer 1 covers what the bus actually requires.** The bus is at-least-once,
   and `digital-twin-engine`'s precedent states the needed property exactly:
   deterministic derivation *"makes a redelivery of the **same event**
   idempotent — the property the at-least-once bus actually requires."* **Layer
   1 discharges that property in full.**
2. **Layer 2 addresses a producer defect, not a transport property.** Two
   distinct `event_id`s mean the producer genuinely emitted twice.
3. **Every gate still runs on the second trigger.** Policy, Permission Matrix,
   Trust and all seven §22.4 preconditions are re-evaluated. A duplicate
   initiative **cannot execute anything the first could not** — the exposure is
   *repetition*, not *escalation*.
4. **Deferring invents nothing.** Implementing Layer 2 now would require
   choosing between the two readings in (A) **with no evidence**, which is
   exactly what this TDD refuses to do elsewhere.

**Future owner: the slice that ratifies `ProposedAction`'s promotion
semantics** — A-4F6-2a's owner if `ProposedAction` lands in 4F.6, otherwise the
slice that introduces it. **Recorded as a deferred obligation in the 4F.6
completion record**, not silently dropped.

**D. Is `action-engine`'s guard sufficient for Layer 1? — Yes.**

`_idempotent_reply_if_terminal(action_id)` runs *"before any stage runs, and
before the Action row is even inserted, so a genuine retry never re-triggers any
side effect, **including the approval loop**"*, replaying the stored terminal
result; `ActionORM`'s primary key backs it with `ActionAlreadyExistsError`.

Given Layer 1, a redelivered envelope yields the **same** `subject_id` →the
**same** `action_id` → the guard fires → **nothing executes twice**. **Sufficient
for Layer 1, and by construction insufficient for Layer 2**, since it cannot
know two differently-keyed requests are one initiative.

**No new database constraint is proposed, and none is required.**


---

## 6. **A-4F6-4 — stale triggers. The semantic, not a number**

### 6.1 Why no TTL exists

A repository-wide search for `ttl`, `expires_at`, `expiry`, `max_age` and
`stale` returns **exactly one** numeric lifetime: `session_cookie_max_age_seconds`
in `api-gateway` — **an auth cookie**. **No request-shaped payload carries an
expiry.** `EventEnvelope.occurred_at` exists and **nothing consumes it as a
deadline**.

### 6.2 Why 4F.5's 15 seconds is not reusable

It bounds **how long `autonomy-engine` waits for `action-engine`'s reply**,
chosen against that engine's 300-second approval loop. A trigger TTL would
bound **how old a request may be before it is refused** — a different quantity
with different inputs. §22.3 already forbids the analogous conflation.

### 6.3 The exact unresolved semantic

| Question | Position |
|---|---|
| **What does "stale" mean?** | **Undefined, and that is the decision.** Two candidate meanings: *(i)* **age** — the request was emitted more than *N* ago; *(ii)* **supersession** — the cognitive state that justified it has since changed, so the thought is no longer in `IMMEDIATE` or its `ProposedAction` has changed. **(ii) is the meaning that actually matters for safety**, and it is not a clock question at all |
| **Which timestamp is authoritative?** | **`EventEnvelope.occurred_at`** — producer-side, UTC, already on every envelope. Not the consumer's wall clock, which would make expiry depend on which instance received the message. **Clock skew must be addressed explicitly** |
| **At which layer is freshness evaluated?** | **The orchestration module in `autonomy-engine`**, before `decide()` — the same boundary that validates the payload. **Not** in `domain/`, which must stay free of transport concerns |
| **What must be ratified first?** | **(1)** Which meaning of stale applies — age, supersession, or neither. **(2)** If age: a number **with its evidential basis**. **(3)** Whether an expired trigger is persisted, which is itself a ratification because **no `DecisionOutcome` means "expired"** |
| **What happens to a stale trigger today?** | **It is processed normally.** Every gate still runs, so a stale trigger cannot execute anything a fresh one could not. **The risk is not privilege — it is acting on a stale intention** |

**4F.6 implements no TTL, and no number is selected.**


---

## 7. **A-4F6-7 — the caller. Boundary and filename both RATIFIED**

**Ratified:** the production `decide()` caller lives at the
**application/orchestration boundary** inside `autonomy-engine` — **not
`api/`, not `domain/`.**

**Package placement — established.** Orchestration modules sit at the **package
root**, beside `main.py`:

- `perception-engine/…/observation_orchestration.py`
- `communication-engine/…/conversation_orchestration.py`

**The naming convention is `<inbound artifact>_orchestration.py`** — an
*observation* arrives at `POST /v1/perception/observations`; a *conversation*
drives session lifecycle.

| Candidate | Assessment |
|---|---|
| **`decision_orchestration.py`** | The inbound artifact is a **decision request** (`autonomy.decision.requested`), so the noun matches the convention exactly |
| `trigger_orchestration.py` | Names the mechanism rather than the artifact — no precedent does this |
| `initiative_orchestration.py` | Matches project vocabulary (*"the initiative trigger"*, CF-11) but **not** the subject name |

**The collision concern raised in revision 3 is disproven.**
`communication-engine` has **both** `conversation_orchestration.py` **and**
`domain/conversation_memory.py`, so an orchestration noun that also appears
under `domain/` is already accepted. (`perception-engine` has no
`domain/observation*.py`, so the convention does not require the pairing
either.)

**RATIFIED 2026-09-22: `decision_orchestration.py`**, on the naming precedent
above. **The module is not created by this document.**


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

### 9.1 **A-4F6-5 — transport failure. RATIFIED: Design A**

> **Correction, 2026-09-22 — two corrections, one to revision 3 and one to
> revision 4.**
>
> **Revision 3** claimed *"no `serve()` handler in the repository catches
> anything."* **False** — see the table below.
>
> **Revision 4** then listed **four** engines with degraded-reply serve
> handlers, including `personality-engine`. **Also wrong**:
> `personality-engine`'s `except` is at **startup**, loading Core Identity
> (`logger.exception("personality-engine failed to load Core Identity at
> startup")`) — **not a serve handler.** The correct count is **three**.

| Engine | Serve-handler behaviour |
|---|---|
| **`capability-engine`** | `except Exception as exc:  # noqa: BLE001 -- structured reply, never a crash (TDD 3C §8)` → metric → `CapabilityInvokeReplyPayload(outcome="failure", error=str(exc))` |
| **`world-model-engine`** | `except Exception:` → `context_degraded_total` + duration metric → `logger.warning("world_model.context.request degraded", exc_info=True)` → **`ContextReplyPayload(user_id=…, degraded=True)`** |
| **`knowledge-engine`** | `except Exception:` → `logger.warning("knowledge.traverse.request degraded", exc_info=True)` → empty-but-valid reply, **no explicit flag** |
| **`action-engine`** | **No catch.** The exception propagates; no reply; the caller times out |
| **The SDK** | `_callback` has **no** `try`/`except` — it does not convert anything |

**The dominant convention is: catch at the handler boundary, observe, and
return a structured reply that says it is degraded.** `capability-engine` cites
a TDD for it; `world-model-engine` carries **`degraded: bool` in the reply
contract itself**. `action-engine` is the sole exception.

#### Design A — catch → observe → structured degraded reply → no `decide()`

| | |
|---|---|
| **Exception boundary** | The `serve()` handler in `autonomy-engine`'s orchestration module — the same boundary all three precedents use |
| **Exception classes** | `except Exception` at the boundary, matching `capability-engine`/`world-model-engine`/`knowledge-engine`. **`ValidationError` is handled separately and earlier**: a malformed payload is a rejection, not a transport failure |
| **Mechanism reused** | Structured logging (`logger.warning(..., exc_info=True)`) — established; **plus a reply field**, following `ContextReplyPayload.degraded` |
| **Information captured** | Subject, `event_id`, `correlation_id`, exception type and traceback |
| **Identifiers available** | `envelope.event_id`, `envelope.correlation_id`, `envelope.occurred_at` — all present before any failure |
| **Persistence changes** | **None** |
| **Migration** | **None** |
| **Tests** | `decide()` not called; **no** `decision_log` row; no retry; the reply carries the degraded signal |
| **`NoRespondersError`** | **Not applicable on this side** — it is a *producer-side* failure, raised in `cognitive-state-engine` when nothing serves the subject. **L-18 is open**, so the producer receives the raw `nats` error; **4F.6 must not fix the SDK** |
| **Timeout** | Also producer-side: if the consumer is slow, the producer's `request()` raises the SDK-translated `TimeoutError`. **The consumer may still complete**, so the producer must not assume nothing happened |
| **Unexpected transport exception** | Caught here; logged; degraded reply |
| **Retry** | **Forbidden** at the trigger layer — it would reintroduce D-4F5-3's double-execution risk one level up |

#### Design B — Design A **plus** a persistent audit record

Everything in Design A, and additionally a row in a **new** append-only table
(shaped on `memory.audit_log`: `id`, `event_id`, `subject`, `correlation_id`,
`occurred_at`, `failure_reason`, `detail JSONB`).

| | |
|---|---|
| **Persistence changes** | **A new table** |
| **Migration** | **REQUIRED.** A new migration in the `autonomy` schema |
| **Tests** | Design A's, plus a `real_infra` test reading the row back with independent SQL |
| **Auditability** | **Durable and queryable** — a lost trigger becomes a record |
| **Everything else** | Identical to Design A |

**Neither design creates a new `DecisionOutcome`.** Design B deliberately
records **outside** `decision_log` precisely because no outcome member means
*"failed before a decision"*, and inventing one is what 4F.5 refused to do for
`ActionDispatchUnavailable`.

#### Recommendation

**RATIFIED 2026-09-22: Design A.**

Three independent reasons, each from evidence:

1. **It is the established convention**, used by all three catching serve
   handlers, one of which cites a TDD for it.
2. **It requires no new persistence and no migration** — and the instruction
   for this round is not to create an audit table unless repository evidence
   supports it. **`memory.audit_log` proves such tables exist; it does not
   establish that a transport failure warrants one.**
3. **The reply itself carries the signal.** `ContextReplyPayload.degraded` shows
   the repository's answer to *"how does a caller know this failed?"* is **a
   field in the reply contract**, not a database row. The producer therefore
   learns of the failure directly, which is the auditability that matters most.

**The residual is stated rather than hidden:** under Design A a transport
failure leaves **no durable, queryable record** — only logs and the producer's
reply. **That was accepted on ratification**, and **persistent auditability of a
lost trigger is DEFERRED** (§16), not forgotten. **No audit table is
introduced.**

**Ratified behaviour, restated for the implementation contract:** `decide()` is
**not invoked**; there is **no trigger-layer retry**; **no new
`DecisionOutcome`**; **no new persistence table**; existing observability
conventions are reused; `NoRespondersError` is handled at the **producer-side**
application boundary (it is raised there, not here); a timeout follows the
**existing transport convention** and the producer must not assume the consumer
did nothing; unexpected transport errors are observed and converted into the
established **degraded reply** representation; and **action execution never
occurs when the trigger was not successfully delivered to `autonomy-engine`.**


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

## 14. **A-4F6-6 — the architecture amendment, exact text. RATIFIED**

**RATIFIED 2026-09-22**, and to be appended additively to TDD 4F. **Historical
wording is preserved, not rewritten.** The amendment applies **specifically to
the internal engine-to-engine Event Bus surface** and to nothing else: the
**browser/public** surface is untouched, `PUBLIC_TOPICS` stays at **18**, and
**no `TrustMetric` subject, no `TrustMetric` RPC and no new autonomy REST route**
is introduced.

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

## 16. 4F.6 FINAL RATIFICATION MATRIX

**Ratified 2026-09-22.** Every decision appears in **exactly one** category.
Moves into RATIFIED are marked **[ratified]**.

> **One clarification, so nothing reads as double-listed.** A carry-forward
> finding's **status** and the **obligation to close it** are different objects.
> **CF-9, CF-10 and CF-11 are OPEN** — that is their status. Their **closure
> conditions** are **DEFERRED** to named owners. The status is listed once under
> OPEN; the obligation is listed once under DEFERRED. No decision appears twice.

### RATIFIED

| Decision | Statement |
|---|---|
| **A-4F6-1 — trigger subject** | **`autonomy.decision.requested`.** Internal, server-side, **exactly one consumer**, producer `cognitive-state-engine`, consumer `autonomy-engine`. **Never in `PUBLIC_TOPICS`, never browser-visible, never gateway-exposed.** Registry **119 → 120** |
| **A-4F6-2a — `ProposedAction`** **[ratified]** | **Part of 4F.6.** Owned by **`cognitive-state-engine`**. Stored as **one nullable JSONB column** on `ActiveThought`. Required: `category`, `risk`, `action_type`, `execution_target`, `verification_method`, `title`. Optional: `detail`. **All-or-nothing**; incomplete is **invalid**; **missing never triggers**; **`risk` is authored, never derived**; **no guessing, no coercion**; **promotion to `IMMEDIATE` required**; transition stays deterministic through the existing attention-layer mechanism. **No separate slice** (supersedes A-4F6-2c) |
| **A-4F6-2b — Option A** **[ratified]** | **`PermissionCategory` moves to `nova_contracts/events/autonomy.py`.** Call-site compatibility preserved via the repository's established **re-export** pattern through `autonomy-engine`'s existing `__all__`. **The vocabulary stays canonical — no duplicate in `cognitive-state-engine`, no second `PermissionCategory` type** |
| **A-4F6-3 Layer 1 — transport identity** **[ratified]** | **The producer never supplies `subject_id`.** The consumer derives `subject_id = uuid5(_DECISION_TRIGGER_NAMESPACE, str(envelope.event_id))`; namespace documented in §5.2. **`event_id` is the transport identity.** **`action-engine`'s existing idempotency guard is reused. No database constraint. No migration** |
| **A-4F6-5 — Design A** **[ratified]** | **catch → observe → structured degraded reply.** `decide()` **not invoked**; **no trigger-layer retry**; **no new `DecisionOutcome`**; **no new persistence table**; existing observability conventions reused; **action execution never occurs when the trigger was not successfully delivered** |
| **A-4F6-6 — architecture amendment** **[ratified]** | §14's **D-4F-9**, applied formally to the **internal engine-to-engine** Event Bus surface only. Historical wording **preserved verbatim**. **No `TrustMetric` subject, no `TrustMetric` RPC, no new autonomy REST route** |
| **A-4F6-7 — caller boundary** | The `decide()` caller lives at the **application/orchestration layer** in `autonomy-engine` — **not `api/`, not `domain/`** |
| **Module filename** **[ratified]** | **`decision_orchestration.py`**, on the `<inbound artifact>_orchestration.py` precedent |

### PROPOSED

**None.** Every proposal has been ratified, deferred or left open.

### OPEN

| Item | Status |
|---|---|
| **A-4F6-4 — TTL** | **No TTL is introduced.** 4F.5's 15-second dispatch timeout is **not reused** — it bounds a reply, not freshness. **`EventEnvelope.occurred_at` remains the freshness reference** if a TTL is later introduced. **No numeric value selected** |
| **Stale-trigger semantics** | **OPEN.** "Stale" may mean **age** or **supersession**; a stale trigger is processed normally today, and every gate still runs |
| **`observability.py` packaging** | Whether `autonomy-engine` gains one. **Packaging only**: the *behaviour* is already ratified above, and this row decides nothing about it |
| **Logging `correlation_id`** | No log call in the repository carries one; adopting it would establish a convention *(the first clause is factually wrong — corrected 2026-09-23 in the note below this table; the row stays OPEN)* |
| **CF-9** | **OPEN** — status. 4F.6 contributes nothing |
| **CF-10** | **OPEN** — status. Structurally blocked by §11.4, which **§14 does not amend** |
| **CF-11** | **OPEN** — status. 4F.6 evidences claims 1–2 only |

> **Correction, 2026-09-23 (pre-merge audit of PR #37), additively.** The
> *"Logging `correlation_id`"* row above says *"No log call in the repository
> carries one."* **That is factually wrong.** The row is preserved as ratified.
>
> At `4f1602a`, the base 4F.6 was built on, log calls already carry
> `correlation_id`:
>
> - **`agent-os/supervisors/src/nova_agent_os_supervisors/clients/decision_memory_client.py:33`**:
>   `logger.info(...)`, passing it as a message argument (`… correlation_id=%s`).
> - **`services/planning-engine/src/nova_planning_engine/events/handlers.py:83`**:
>   `logger.warning("decomposition failed", extra={… "correlation_id": …})`.
> - **`services/planning-engine/src/nova_planning_engine/events/handlers.py:118`**:
>   `logger.info("decomposition succeeded and persisted", extra={… "correlation_id": …})`.
>
> The pre-merge audit identified those three. **A fourth was found while this
> correction was prepared**, by an AST scan of all 145 log calls under `src/`
> at `4f1602a`:
>
> - **`services/api-gateway/src/nova_api_gateway/api/forward.py:113`**:
>   `logger.warning("upstream unavailable", extra={… "correlation_id": …})`.
>
> All four files are unchanged by 4F.6.
>
> **What this correction does not change:**
>
> - **The row stays OPEN.** The existing calls use two different mechanisms, a
>   message argument and structured `extra`, across three components, with no
>   shared rule. That is unratified practice, not a convention. **Their
>   existence does not ratify a project-wide logging standard.**
> - **4F.6 introduces no new logging convention** and no logging
>   infrastructure. Its three Design A log lines carry `correlation_id` as a
>   message argument because §9.1's ratified Design A lists it under
>   *"Information captured"*. The 4F.6 completion record discloses this as
>   **F-7**, which stays open.
> - **Whether and how `correlation_id` logging should be standardized remains
>   an open concern.** The second clause of the row, that adopting it would
>   establish a convention, still describes that decision.
> - **No production logging code is changed** by this correction.

### DEFERRED

| Item | Owner |
|---|---|
| **A-4F6-3 Layer 2 — logical duplicate semantics** | **The slice that ratifies `ProposedAction` promotion semantics.** Two different `event_id` values are **distinct transport identities**; **no logical initiative deduplication is invented, and no second deduplication mechanism is added** |
| **Persistent auditability of a lost trigger** | A later slice. **No audit table is introduced** |
| **CF-11 closure claims 3 and 4** | **4F.8** (end-to-end) / **4F closure** (recorded evidence) |
| **CF-9 condition 5** (and condition 2's citation) | **4F closure** |
| **CF-10 closure** | **Beyond 4F** — needs a Trust read surface §11.4 still forbids |
| **L-17** — web-client policy-effect enum | A later policy-authoring / UI scope |
| **L-18** — SDK `NoRespondersError` translation | `nova-eventbus-sdk` / later maintenance. **4F.6 must not fix the SDK** |
| **4F.7 panel and `/v1/cognitive-state`** | **4F.7** |

> **Added 2026-09-26 (4F.7 ratification, RS-1c and RS-7 — TDD 4F §24),
> additively.** The table above is preserved.
>
> - **The owner of A-4F6-3 Layer 2 now has a name.** *"The slice that ratifies
>   `ProposedAction` promotion semantics"* is **4F.P**, added before 4F.8 in
>   TDD 4F §18.
> - **4F.P's TDD must also ratify** the CAS semantics of the promotion
>   transition, before any production caller of `promote_thought` exists.
> - **4F.7 is strictly read-only (RS-1b).** It owns none of these rows except
>   its own.

---

## 17. IMPLEMENTATION BLOCKERS — recalculated after ratification

**A decision blocks only if implementation would require inventing a security,
identity, persistence or externally visible semantic.** All four of revision
5's blockers are now ratified:

| Former blocker | Resolution |
|---|---|
| **A-4F6-2a** | **RATIFIED.** The trigger condition and every field are fixed; nothing is invented |
| **A-4F6-2b** | **RATIFIED (Option A).** The vocabulary has a canonical home, so the payload contract can be written |
| **A-4F6-3 Layer 1** | **RATIFIED.** Identity is consumer-derived and payload-supplied `subject_id` is prohibited |
| **A-4F6-6** | **RATIFIED.** The amendment is applied, so the subject is no longer contradicted |

### **BLOCKING ARCHITECTURE: none.**

**No architectural decision now prevents implementation from starting.**

### NON-BLOCKING

| Item | Why it does not block |
|---|---|
| **A-4F6-4 / stale-trigger** | **"No TTL" is the ratified behaviour for 4F.6.** Every gate still runs, so a stale trigger cannot execute anything a fresh one could not. Only the *future* semantic is open |
| **A-4F6-3 Layer 2** | **DEFERRED.** Layer 1 discharges the at-least-once property the bus requires |
| **Persistent auditability** | **DEFERRED.** Design A's behaviour is fully specified without it |
| **`observability.py` packaging** | A packaging choice; the ratified behaviour is reuse of existing conventions |
| **Logging `correlation_id`** | A logging convention |
| **CF-9 / CF-10 / CF-11** | Carry-forward findings. **4F.6 closes none**, and none blocks it |

**The remaining open items are future semantics and packaging choices, not
prerequisites.** Per this round's instruction, none is classified as a blocker.


---

## 18. Status

**RATIFIED, 2026-09-22.** A-4F6-1, A-4F6-2a, A-4F6-2b Option A, A-4F6-3
Layer 1, A-4F6-5 Design A, A-4F6-6, A-4F6-7 and `decision_orchestration.py`.

**No PROPOSED items remain. No BLOCKING ARCHITECTURE decisions remain.**

**DEFERRED:** A-4F6-3 Layer 2 · persistent lost-trigger auditability · CF-11
claims 3–4 · CF-9 condition 5 · CF-10 closure · L-17 · L-18 · the 4F.7 panel.

**OPEN:** TTL · stale-trigger semantics · `observability.py` packaging ·
logging `correlation_id` · **CF-9, CF-10 and CF-11 statuses** — **4F.6 closes
none of them.**

**§19 is the Implementation Contract.** Implementation may begin against it on
a separate branch; **this document creates no code.**

---

## 19. 4F.6 Implementation Contract

**The exact behaviour the implementation branch must satisfy.** Every line is
ratified; none is a proposal. Where a line says *never*, a test must be able to
fail on it.

| # | Requirement |
|---|---|
| **1 — Trigger** | A thought carrying a **complete `ProposedAction`**, **promoted to `IMMEDIATE`**. A thought without one **never** triggers. An incomplete `ProposedAction` is **invalid at the model boundary** |
| **2 — Transport** | **`autonomy.decision.requested`**, request/reply. Producer `cognitive-state-engine`; consumer `autonomy-engine`, **exactly one** |
| **3 — Identity** | `subject_id = uuid5(_DECISION_TRIGGER_NAMESPACE, str(envelope.event_id))`, derived **by the consumer**. **`event_id` is the transport identity** |
| **4 — No producer-supplied `subject_id`** | The field is **absent from the payload contract**, so a producer **cannot** name a decision's identity |
| **5 — Consumer** | **`autonomy-engine`**, via one `serve()` |
| **6 — Decision caller** | The **application/orchestration boundary** — `decision_orchestration.py`. **Not `api/`, not `domain/`** |
| **7 — Level** | The trigger enters the **existing** autonomy decision flow. Level, policies and grants are read **server-side** from the repository; `user_id` is resolved from `primary_user_id` and **never carried by the producer** |
| **8 — No Layer 2 deduplication** | Two different `event_id` values are **distinct transport identities**. **No logical initiative deduplication, and no second deduplication mechanism** |
| **9 — No TTL** | No freshness check. 4F.5's 15-second bound is **not** reused |
| **10 — No retry** | **No trigger-layer retry**, ever |
| **11 — Transport failure** | **catch → observe → structured degraded reply.** `decide()` is **not invoked** |
| **12 — No execution without delivery** | **Action execution never occurs when the trigger was not successfully delivered to `autonomy-engine`** |
| **13 — No new `DecisionOutcome`** | The five existing members are unchanged |
| **14 — No new audit table** | No new table, no new migration in the `autonomy` schema |
| **15 — No `PUBLIC_TOPICS` exposure** | **`PUBLIC_TOPICS` stays at 18** |
| **16 — No gateway exposure** | No prefix, no route, no proxy entry |
| **17 — No `TrustMetric` surface** | **No `TrustMetric` subject, no `TrustMetric` RPC.** CF-10 stays open |
| **18 — No new autonomy REST route** | §12's statement stands unqualified |
| **19 — `PermissionCategory` canonical** | Lives in `nova_contracts/events/autonomy.py`, re-exported for call-site compatibility. **No duplicate in `cognitive-state-engine`; no second type** |
| **20 — 4F.5 untouched** | Dispatch semantics, the seven §22.4 preconditions, the 15-second bound, `ActionDispatchUnavailable`, the §22.7 Trust contract: **all unchanged** |
| **21 — Boundaries at zero** | `action-engine`, Stage 3, `nova-eventbus-sdk`, `apps/web-client/src/`, CI workflows: **0 files** |

**Schema changes permitted by this contract: exactly one** — the nullable JSONB
column on `cognitive_state.active_thought`. **No `autonomy` schema change.**

**Contract changes permitted: exactly two** — the
`autonomy.decision.requested` payload, and `PermissionCategory`'s new home.
**Registry 119 → 120.**
