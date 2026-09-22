# TDD 4F.6 — The initiative trigger: Level 2's *Triggered* state

**Revision 4 — 2026-09-22. Final decision analysis.** Revision 1 reported a
blocking architectural contradiction (§0); revision 2 ratified **A-4F6-1** and
**A-4F6-7**; revision 3 made the TDD ratification-ready. This revision adds the
**full `PermissionCategory` ownership analysis** (§4.6), the **final
`ProposedAction` spec** (§4.7), both **duplicate-identity layers with the seven
identity questions answered** (§5), the **two lost-trigger designs** (§9.1), the
**stale-trigger semantic** (§6), and the **final matrix** (§16) with
**blocking vs non-blocking** blockers (§17).

> **It also corrects a factual error in revision 3.** Revision 3 claimed *"no
> `serve()` handler in the repository catches anything."* **Four engines do** —
> see §9.1. The corrected evidence changes the A-4F6-5 analysis, and the
> original claim is quoted there rather than quietly dropped.

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

### 4.6 **A-4F6-2b — `PermissionCategory` ownership. Full option analysis**

**The most important unresolved issue.** `ProposedAction` needs both `risk`
and a permission category. `RiskLevel` is in `nova-contracts` and usable;
`PermissionCategory` is in `autonomy-engine`'s `domain/models.py`, and
**ADR-004's `independence` contract forbids `cognitive-state-engine` importing
it**.

#### 4.6.1 Evidence gathered for this analysis

| Fact | Evidence at `4f1602a` |
|---|---|
| Who uses `PermissionCategory` | **Two places only**: `services/autonomy-engine` (16 files) and `apps/web-client` (1 file) |
| **The vocabulary is already duplicated** | `apps/web-client/src/entities/autonomy.ts:43` hand-maintains `PERMISSION_CATEGORIES` with the comment *"Bible Part 14's ten permission categories, verbatim and in its order"*, and derives a `zod` enum and a TS type from it |
| The web client **does** consume generated contracts elsewhere | `realtime/reconcile.ts`, `entities/health.ts`, `entities/planning.ts`, `entities/approvals.ts`, `entities/pulse.ts` all `import … from "@nova/nova-contracts"` |
| Enums referenced by a contracts payload **are** code-generated | `PlanningTaskGraphCreatedPayload.ts` contains `export type RiskLevel = "negligible" \| "low" \| "moderate" \| "high" \| "critical";` — generated, not hand-written |
| `RiskLevel`'s own docstring | *"the one canonical risk-tier scale anywhere in this project"* |
| Persistence | `autonomy.permission_grant` is keyed `PRIMARY KEY (user_id, category)`, column type **`TEXT`** |
| Vocabulary sizes | `PermissionCategory` **10** members; `action.execute`'s `action_type` **2** literals. **Neither derives from the other** |

#### 4.6.2 The options

**Option A — move `PermissionCategory` into `nova-contracts`.**

| | |
|---|---|
| **Files affected** | `packages/nova-contracts/src/nova_contracts/**` (new home); `autonomy-engine`'s `domain/models.py` (re-export or import); potentially the **16** autonomy-engine files; `apps/web-client/src/entities/autonomy.ts` could then import the generated type |
| **Import-linter** | **Satisfied.** Both engines import a shared package, neither imports the other |
| **Contracts** | The vocabulary becomes a first-class shared contract, like `RiskLevel` |
| **API** | **None** — the wire form is already the string value |
| **Bus serialization** | **None** — `StrEnum` serializes to the same strings |
| **Migration** | **None.** `permission_grant.category` is `TEXT`; no CHECK constraint |
| **Tests** | Import sites update; behaviour unchanged |
| **Existing consumers change?** | **Yes** — autonomy-engine's import sites, and optionally the web client |
| **Semantic duplication** | **Removes** the existing one: the web client could import the generated type instead of hand-maintaining ten strings |
| **Violates ADR-004?** | **No** |
| **Additive or breaking?** | **Additive in behaviour, broad in touch.** Moves a type out of the engine that owns the concept |

**Option B — a new shared contract type in `nova-contracts` for initiative/action requests.**

| | |
|---|---|
| **Files affected** | `packages/nova-contracts/**` only — the `autonomy.decision.requested` payload, which **must exist regardless** under A-4F6-1 |
| **Import-linter** | **Satisfied** |
| **Contracts** | The payload declares its own category vocabulary (a `Literal` or enum) |
| **API** | **None** |
| **Bus serialization** | **Native** — it *is* the wire contract |
| **Migration** | **None** |
| **Tests** | A contract test asserting the payload vocabulary and `PermissionCategory` **agree member-for-member** |
| **Existing consumers change?** | **No.** `autonomy-engine` keeps its enum untouched |
| **Semantic duplication** | **Yes — a second authority for the vocabulary**, requiring a drift test |
| **Violates ADR-004?** | **No** |
| **Additive or breaking?** | **Purely additive.** Smallest touch of the four |

**Option C — keep `PermissionCategory` in `autonomy-engine`; carry a transport-safe primitive.**

| | |
|---|---|
| **Files affected** | `packages/nova-contracts/**` (payload with `category: str`); the consumer validates |
| **Import-linter** | **Satisfied** |
| **Contracts** | The contract is **weaker**: `str` admits any value, and the vocabulary is enforced only at the consumer |
| **API / serialization / migration** | **None** |
| **Tests** | Negative tests for unknown categories at the consumer boundary |
| **Existing consumers change?** | **No** |
| **Semantic duplication** | **No duplication — but no shared vocabulary either.** The producer cannot validate what it emits |
| **Violates ADR-004?** | **No** |
| **Additive or breaking?** | **Additive.** But it pushes a **security-relevant** vocabulary check to runtime, and a typo becomes a rejected trigger rather than a type error |

**Option D — `cognitive-state-engine` emits no category; `autonomy-engine` derives it.**

| | |
|---|---|
| **Feasibility** | **Not repository-supported.** `PermissionCategory` (10) does not derive from `action_type` (2); 4F.5 established exactly this. Deriving would mean **inventing** the mapping |
| **Assessment** | **Rejected on evidence**, and it would also move a producer responsibility §6.2 assigns to `cognitive-state-engine` |

#### 4.6.3 Assessment

**Option D is excluded by evidence.** Of the remaining three:

- **B** is the smallest and purely additive, and the payload it needs **must be
  written anyway** — but it creates a second authority for a security-relevant
  vocabulary, mitigated by a drift test (the repository already has drift tests,
  e.g. `tools/tests/test_identity_confidence_ceiling_drift.py`).
- **A** is the only option that **removes** an existing duplication, and
  `RiskLevel`'s precedent — a Bible Part 14 vocabulary living in
  `nova-contracts` as *"the one canonical scale"* — is a direct parallel. **But
  it touches 16 autonomy-engine files and the web client**, which 4F.6's
  non-goals exclude.
- **C** keeps the blast radius smallest but **weakens a security-relevant
  contract** to `str`.

**No option is clearly supported by repository evidence over the others**: A has
the better precedent, B the better blast radius, and they point in opposite
directions. Per this round's instruction, **the decision is marked OPEN rather
than recommended on convenience.**

**What would settle it:** whether `PermissionCategory` is considered *Bible Part
14 vocabulary* (→ **A**, like `RiskLevel`) or *`autonomy-engine`'s internal
domain* (→ **B**). That is a judgement about the concept's ownership, not about
the code.

#### 4.6.4 **A-4F6-2c — does `ProposedAction` belong in 4F.6?**

**It is larger than "a trigger":** a domain structure, a vocabulary decision and
a migration, in an engine whose read surface is 4F.7's.

| Option | Consequence |
|---|---|
| **(a) Inside 4F.6** | 4F.6 stays one slice that actually delivers *Triggered*. **Cost:** a migration in a slice named for the trigger |
| **(b) Its own slice first** | Cleaner boundaries. **Cost:** inserts a slice before 4F.6 and delays CF-11 |

**Not chosen.** It affects sequencing rather than correctness, so §17 classifies
it **non-blocking**.


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
| **Namespace** | One module-private `UUID` constant in `autonomy-engine`'s orchestration module, mirroring `_ATTENTION_NAMESPACE`. A fixed literal, **never generated at runtime** |
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

## 7. **A-4F6-7 — the caller. Boundary RATIFIED, filename resolved on evidence**

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

**Resolved: `decision_orchestration.py`.** Moved from OPEN to PROPOSED on this
evidence, and the move is recorded explicitly rather than made silently. **The
module is not created.** This is a naming decision with **low architectural
weight** — §17 classifies it as non-blocking.


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

### 9.1 **A-4F6-5 — transport failure and the lost trigger. PROPOSED**

> **Correction, 2026-09-22 — revision 3 was wrong on this point.** Revision 3
> stated *"no `serve()` handler in the repository catches anything,"* based on
> inspecting `action-engine` alone. **That is false.** A second pass found
> **four** engines whose serve handlers catch:
>
> | Engine | Behaviour |
> |---|---|
> | **`capability-engine`** | `except Exception as exc:  # noqa: BLE001 -- structured reply, never a crash (TDD 3C §8)` → increments a metric → returns `CapabilityInvokeReplyPayload(outcome="failure", error=str(exc))` |
> | **`knowledge-engine`** | `except Exception: logger.warning("knowledge.traverse.request degraded", exc_info=True)` → returns an empty-but-valid reply |
> | **`personality-engine`**, **`world-model-engine`** | Same shape |
> | **`action-engine`** | **No catch** — the exception propagates |
>
> **The dominant convention is therefore catch → observe → return a structured
> degraded reply, never crash**, and `capability-engine` cites a TDD for it.
> `action-engine` is the exception, not the rule. The analysis below is
> re-derived on the corrected evidence.

**Observability mechanisms that exist:**

| Mechanism | Evidence |
|---|---|
| **`observability.py` per engine** | **13 engines have one**, with OpenTelemetry `Counter`s. **`autonomy-engine` and `cognitive-state-engine` do not** (nor do `api-gateway`, `nova-core`, `ws-gateway`) |
| **Structured logging** | `logger.warning(..., exc_info=True)` and `logger.exception(...)` are established |
| **`correlation_id` in logs** | **Never.** A repository-wide search finds **no** log call carrying `correlation_id`. Logging it would be a **new convention** |
| **An audit table outside a decision log** | **`memory.audit_log`** — `id`, `memory_record_id`, `action`, `actor`, `changed_at`, `detail JSONB`. The precedent for Design B |

#### Design A — catch + structured observability, degraded reply

| | |
|---|---|
| **Location** | The `serve()` handler in `autonomy-engine`'s orchestration module |
| **Data captured** | Subject, `event_id`, exception type and traceback via `exc_info=True`; optionally a counter if an `observability.py` is added |
| **`correlation_id`** | **Would be logged** — deliberately extending a convention that does not exist today. Without it a lost trigger cannot be tied to its producer |
| **Exception handling** | `except Exception` at the handler boundary, matching `capability-engine`/`knowledge-engine` |
| **Persistence impact** | **None** |
| **Schema impact** | **None** |
| **Test impact** | Assert `decide()` is not called, **no** `decision_log` row, no retry, and that the failure is observable |
| **Failure behaviour** | **Nothing executes.** The producer receives a **structured reply** rather than a timeout |
| **Auditability** | **Logs only.** No queryable record. **A lost trigger leaves no durable trace** |

#### Design B — catch + a persistent audit record outside `decision_log`

| | |
|---|---|
| **Location** | Same handler; writes to a new append-only table, e.g. `autonomy.trigger_audit`, shaped on `memory.audit_log` |
| **Data captured** | `id`, `event_id`, `subject`, `correlation_id`, `occurred_at`, `failure_reason`, `detail JSONB` |
| **`correlation_id`** | **Persisted**, so a lost trigger is joinable to its producer |
| **Exception handling** | As Design A |
| **Persistence impact** | **A new table.** **This requires a new migration** |
| **Schema impact** | **Yes — stated plainly**: a new table in the `autonomy` schema, which 4F.6's non-goals currently exclude |
| **Test impact** | Design A's, plus a `real_infra` test reading the audit row back with independent SQL |
| **Failure behaviour** | Identical to A |
| **Auditability** | **Durable and queryable.** A lost trigger is a record, not a log line |

**Neither design introduces a new `DecisionOutcome`.** Design B deliberately
records **outside** `decision_log`, precisely because no `DecisionOutcome`
means *"the trigger failed before a decision"* — and inventing one is what 4F.5
refused to do for `ActionDispatchUnavailable`.

**Stated clearly, as required: Design B requires new persistence — a new table
and a new migration. It does not require a new outcome.**

**In both designs:** `decide()` is **never invoked** on trigger-layer transport
failure; **no `DecisionLogEntry` exists**; **trigger-layer retry is forbidden**
(it would reintroduce D-4F5-3's double-execution risk one level up); and the
producer **receives a reply** rather than being left to time out.

**Not recommended here.** Design A matches the dominant convention and adds no
schema; Design B is the only one that makes a lost trigger auditable. **The
choice is a safety position — whether an unaudited lost trigger is acceptable —
and belongs to ratification, not to this document.**


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

## 16. 4F.6 FINAL RATIFICATION MATRIX

**Every 4F.6 architectural decision appears in exactly one category.** Category
changes since revision 3 are marked **[moved]** with their justification —
none is silent.

### RATIFIED

| Decision | Statement |
|---|---|
| **Trigger subject** (**A-4F6-1**) | **`autonomy.decision.requested`.** `cognitive-state-engine` → `autonomy-engine`. **Internal only**, exactly **one** server-side consumer, **never in `PUBLIC_TOPICS`**, never browser-reachable, not a public API, **no gateway prefix**. Registry **119 → 120** |
| **Caller boundary** (**A-4F6-7**) | The `decide()` caller lives at the **application/orchestration boundary** in `autonomy-engine` — **not `api/`, not `domain/`** |

### PROPOSED

| Decision | Proposal |
|---|---|
| **Trigger condition** (**A-4F6-2**) | A thought carrying a **complete `ProposedAction`**, **promoted to `IMMEDIATE`**, deterministic through the existing `next_layer`/`move_layer` mechanism. **A thought without one never triggers** |
| **`ProposedAction` schema** (**A-4F6-2a**) | §4.7's final spec: 6 required fields + optional `detail`; **all-or-nothing**; `risk` **authored, never derived**; **one nullable JSONB column**, additive, **no existing column altered**, **no API surface affected** |
| **Duplicate identity — Layer 1** (**A-4F6-3**) | `subject_id = uuid5(_DECISION_TRIGGER_NAMESPACE, str(envelope.event_id))`, **derived by the consumer, never payload-supplied**, so `action-engine`'s **existing** guard suppresses duplicate execution. **No constraint, no migration** |
| **Duplicate identity — Layer 2** | `thought_id` + the five `ProposedAction` semantic fields; **not** title/detail/timestamps. **Blocked on A-4F6-2a** |
| **`decide()` signature** | Must accept a consumer-derived `subject_id`. **Changes a 4F.5 signature** |
| **Transport error behaviour** (**A-4F6-5**) | **Design A or Design B** (§9.1). Both: `decide()` never invoked, no log entry, no retry, **no new `DecisionOutcome`**, producer gets a reply. **B requires a new table and migration** |
| **Module filename** | **`decision_orchestration.py`** — **[moved from OPEN]**, because the revision-3 collision concern is disproven by `communication-engine` and the convention is `<inbound artifact>_orchestration.py` |
| **§11.4 / §13 amendment** (**A-4F6-6**) | §14's exact text, appended additively to TDD 4F as **D-4F-9**; historical wording **quoted, not edited** |

### OPEN

| Item | Why |
|---|---|
| **`PermissionCategory` ownership** (**A-4F6-2b**) | **[moved from PROPOSED]** — revision 3 recommended option (a); this round's full analysis (§4.6) finds **A has the better precedent and B the better blast radius, pointing in opposite directions**. **No option is clearly supported**, so it is marked OPEN rather than chosen on convenience. **Blocks the payload contract entirely** |
| **Slice placement** (**A-4F6-2c**) | Whether `ProposedAction` belongs in 4F.6 or its own slice |
| **TTL** (**A-4F6-4**) | **No value exists to adopt.** No number selected |
| **Stale-trigger behaviour** | **Undefined by design**: "stale" may mean **age** or **supersession**, and §6.3 argues supersession is the one that matters. Currently processed normally |
| **Auditability of a lost trigger** | Design A leaves **no durable record**; Design B needs a table and migration. **Unresolved** |
| **`autonomy-engine` `observability.py`** | The engine has none; 13 others do |
| **Logging `correlation_id`** | **No log call in the repository carries one.** Design A would establish a new convention |
| **CF-9** | **OPEN.** Conditions 1, 3, 4 evidenced by 4F.4; 2 answered by **D-4F4-1** awaiting citation; **5 unmet**. **4F.6 contributes nothing.** No evidence resolves it |
| **CF-10** | **OPEN, structurally blocked.** Needs a Trust read surface §11.4 **still forbids**. **4F.6 contributes nothing.** No evidence resolves it |
| **CF-11** | **OPEN.** 4F.6 can evidence **claims 1 and 2**; **claim 3** is 4F.8's, **claim 4** is 4F closure's. No evidence resolves it |

### DEFERRED

| Item | Owner |
|---|---|
| CF-11 claim 3 — end-to-end trigger-to-action | **4F.8** (AC-8) |
| CF-11 claim 4 — recorded closure evidence | **4F closure / Gate Review (L-1)** |
| CF-9 condition 5, and condition 2's citation | **4F closure** |
| CF-10 | **Beyond 4F** |
| **L-17** (web-client policy-effect enum) | Later UI scope — **OPEN**, untouched |
| **L-18** (SDK `NoRespondersError`) | `nova-eventbus-sdk` — **OPEN**, untouched. **4F.6 must not fix it** |
| Cognitive-state panel and `/v1/cognitive-state` | **4F.7** |
| Whether 4F.7 renders `proposed_action` | **4F.7** |

---

## 17. IMPLEMENTATION BLOCKERS

**A decision is BLOCKING only when implementation would require inventing a
semantic or security property without it.**

### BLOCKING ARCHITECTURE

| # | Decision | Why it blocks |
|---|---|---|
| **1** | **A-4F6-2a — `ProposedAction`** | Without it there is **no safe trigger condition**. A `DecisionRequest` needs a permission category and risk tier `ActiveThought` does not carry; supplying them would **invent the security semantics every gate is evaluated against**. If rejected, **4F.6 must be re-scoped** |
| **2** | **A-4F6-2b — `PermissionCategory` ownership** | **ADR-004 forbids the import.** Until the vocabulary has a ratified home, **the payload contract cannot be written at all** — not a detail, a prerequisite |
| **3** | **A-4F6-5 — the auditability position** | Choosing Design A means **accepting that a lost trigger leaves no durable record**. That is a **safety property**, and Design B's table cannot be added later without a migration |
| **4** | **A-4F6-6 — the amendment** | Until applied, the ratified subject **remains contradicted by TDD 4F §11.4 and §13**. Implementing first would leave the architecture self-contradictory in the repository |
| **5** | **A-4F6-3 — consumer-derived `subject_id`** | The bus is **at-least-once**, so idempotency is **required**. It works only if the orchestrator supplies `subject_id`, which changes a 4F.5 signature — and the field must be **impossible to set from the payload**, a **security** property |

### NON-BLOCKING ARCHITECTURE

| Decision | Why it does not block |
|---|---|
| **Module filename** (`decision_orchestration.py`) | Naming. Resolved on evidence; no semantic or security property depends on it |
| **`autonomy-engine` `observability.py`** | A packaging choice **once A-4F6-5's behaviour is ratified** — a metric can be added later without changing semantics |
| **Logging `correlation_id`** | A logging convention, not a semantic |
| **A-4F6-2c — slice placement** | Affects sequencing, not correctness |
| **Layer 2 duplicate identity** | Layer 1 covers the at-least-once property the bus requires; Layer 2 addresses producer bugs and can follow |
| **TTL / stale-trigger** | **Only because "no TTL" is the safe default**: every gate still runs, so a stale trigger cannot execute anything a fresh one could not. **If the answer were "stale means superseded", it would become blocking** |


---

## 18. Status

**RATIFIED: A-4F6-1 (trigger subject) and A-4F6-7 (caller boundary).**
**Everything else is PROPOSED, OPEN or DEFERRED per §16.**

**Implementation remains blocked on the five BLOCKING ARCHITECTURE items in
§17**, principally **A-4F6-2a** and **A-4F6-2b** — the latter now **OPEN**
rather than recommended, because §4.6's full analysis found no option clearly
supported by repository evidence.

**CF-9, CF-10 and CF-11 all remain OPEN.** No evidence in this revision proves
otherwise, and this document closes none of them.
