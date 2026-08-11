# Phase 2D-D — Personal Companion: Research & Design Proposal

**Status: Research/Design proposal — awaiting approval. No production code has
been written or modified to produce this document.** Every claim below was
verified directly against the current source tree in this session (file
paths and line-anchored evidence throughout), not recalled from prior
documentation or task-tracker status. Where documentation and code disagree,
code is treated as ground truth, matching this project's own standing rule
(the same discipline the Phase 2D-C closure document was held to).

This document does not begin implementation. Per instruction, it stops at
every genuine design fork rather than resolving it, and does not reopen any
decision already approved in Phase 2D-A/B/C unless current code evidence
proves a concrete blocker (none was found — see §11).

---

## 0. Executive summary

Phase 2D-D builds `digital-twin-engine` — a new, minimal-form engine — plus
small, precedented extensions to `communication-engine` and
`personality-engine`. The architecture is unusually well-prepared for this:
**the wire contracts for both of digital-twin-engine's integration points
already exist in `nova-contracts`**, defined and disclosed as dormant since
Phase 2D-A/2D-C, exactly per Master Blueprint §13.6's "Progressive
capability" principle. Nothing needs to be invented at the contract level;
what's missing is the engine itself and a small number of call sites.

However, direct verification surfaced a real, previously-undocumented gap:
**the data digital-twin-engine would need to actually learn from does not
yet exist in a form it can consume.** `communication.session.completed` —
the event Master Blueprint §6 names as digital-twin-engine's learning
input — carries only `session_id, user_id, objective, turn_count,
closed_at`; none of `ConversationMemory`'s `corrections`/`preferences`/
`feedback`/`decisions`/`questions` fields, which is where the actual
evidence lives. This is not a Phase 2D-D design question so much as an
unresolved Phase 2D-C-era gap this phase now depends on closing (§4, §11).
Two smaller, related evidence gaps were also found for two of the three
named trust-development inputs (§6.3).

Four genuine design forks require a decision before implementation (§10).
No fork reopens any Phase 2D-A/B/C decision — all four are new questions
specific to 2D-D's own integration surface.

---

## 1. Current-state verification (Rule: code over docs)

### 1.1 What exists and is genuinely wired

| Component | Status | Evidence |
|---|---|---|
| `digital_twin.preferences.get.request`/`.reply` payloads | Defined in `nova-contracts`, unused | `packages/nova-contracts/src/nova_contracts/events/communication.py:237-251` |
| `personality.memory.update` payload | Defined in `nova-contracts`, unused | `packages/nova-contracts/src/nova_contracts/events/personality.py:105-116` |
| `personality-engine`'s `MemoryProfile.source` field (`"static_default"` vs `"digital_twin"`) | Exists, always `"static_default"` today | `services/personality-engine/src/nova_personality_engine/domain/models.py:100-110` |
| `personality-engine`'s `PersonalityRepository.update_memory_profile` | Exists, fully correct (fixed this session, Phase 2D-C Closure Priority 6), **no caller anywhere** | `services/personality-engine/src/nova_personality_engine/domain/ports.py:30-33` |
| `communication.session.completed` publish | **Real, wired, fires on every session close** | `services/communication-engine/src/nova_communication_engine/domain/session_lifecycle.py:235-236` |
| `communication-engine`'s `Notification` model + `POST /v1/communication/notifications` | Exists, persists only — no delivery channel | `services/communication-engine/src/nova_communication_engine/domain/models.py:192-201`, `api/notifications.py` |
| ADR-030 (personality/digital-twin boundary) | Filed, accepted | `docs/architecture/adr/ADR-030-personality-stores-digital-twin-learns.md` |
| `digital-twin-engine` itself | **Does not exist** | `services/` directory listing — 10 engines, no `digital-twin-engine` |
| `DigitalTwinPort` in `communication-engine` | **Does not exist** | `domain/ports.py:1-11`'s own docstring: "No `DigitalTwinPort`/`PerceptionPort` exists this phase" |
| `personality.memory.update` subscription in `personality-engine` | **Does not exist** | `events/subscribed.py:10-13`'s own docstring: "no handler exists to subscribe to it until Phase 2D-D" |
| `communication.session.completed` subscription anywhere | **Does not exist** | Grep of every engine's `events/subscribed.py`, zero hits outside `communication-engine`'s own `published.py` |
| Trust-development metric, Habit Detection, Preference Evolution logic | **Does not exist anywhere** | Repo-wide grep for `trust.develop|TrustEngine|trust_metric` — zero hits |
| Proactive-communication boundary policy | **Does not exist anywhere** | Repo-wide grep for `proactive` — zero relevant hits (only incidental matches in unrelated docstrings/caches) |

### 1.2 Verified vs. inferred — applied throughout this document

Following the same four-way classification the 2D-C closure document used
(its own §14):

- **Fully verified**: read directly, current session, cited by file:line.
- **Contract/fake verified**: a payload/port/protocol exists and is
  internally consistent, but nothing calls it against a real counterpart.
- **Documented but unconfirmed**: stated in a design doc/ADR, not
  independently re-derived from code this session.
- **Absent**: searched for directly, not found.

Every finding in §1.1 is **fully verified**. Bible Part 16's domain list and
ADR-030's boundary decision are **documented**, cross-checked against code
where code exists to check against (personality-engine's `source` field,
`nova-contracts`' dormant payloads) and found consistent.

---

## 2. Phase 2D-D objective and scope (per the Master Blueprint, §4.4, §9.3)

**Builds:** `digital-twin-engine`, minimal form — exactly two of Bible Part
16's eleven domains.

**In scope:**
1. **Communication Profile domain** (Bible Part 16: response length,
   technical depth, preferred terminology, explanation style, conversation
   pacing) — populated only from real 2D-A/2D-C session evidence, never
   synthetic.
2. **Conversation-scoped Preference Evolution + Habit Detection slice** —
   interaction-*timing* patterns only (e.g., terse during working hours,
   detailed in the evening) — explicitly not workflow/project habits.
3. **Trust-development metric** — tracked from correction frequency,
   clarification-question acceptance, and proactive-suggestion
   acceptance/dismissal rates (Master Blueprint §4.4).
4. **Proactive-communication boundary policy** — user-configurable
   frequency/topic limits on NOVA-*initiated speech*, never action.

**Explicitly out of scope** (Master Blueprint §3.2, §9.3): the other nine
Digital Twin domains (goals, projects, hardware, software, skills,
knowledge, productivity, workflow beyond communication timing); any
autonomous *action*; general autonomy levels/execution trust
(`autonomy-engine`, Phase 4); NOVA's background cognition
(`cognitive-state-engine`, Phase 4).

---

## 3. Architecture and dependency map

```
                    ┌──────────────────────────┐
                    │ communication-engine      │
                    │ (session_lifecycle.py)    │
                    └─────────────┬─────────────┘
                                  │ publishes
                                  │ communication.session.completed
                                  │ (session_id, user_id, objective,
                                  │  turn_count, closed_at — ONLY,
                                  │  see §4/Fork B)
                                  ▼
                    ┌──────────────────────────┐
                    │ digital-twin-engine (NEW)  │
                    │ - Communication Profile     │
                    │ - Preference Evolution       │
                    │ - trust-development metric   │
                    │ - proactive-comm boundary    │
                    └─────┬───────────────┬───────┘
        publishes          │               │ serves (RPC)
        personality.       │               │ digital_twin.preferences.get
        memory.update      │               │ (already-defined contract)
        (already-defined   │               │
         contract)         ▼               ▼
                 ┌──────────────────┐  ┌─────────────────────────┐
                 │ personality-engine │  │ communication-engine      │
                 │ (NEW subscription: │  │ (NEW: DigitalTwinPort,     │
                 │ handler for        │  │  called from               │
                 │ personality.memory │  │  resolve_response_shaping, │
                 │ .update →          │  │  see Fork A)                │
                 │ update_memory_     │  └─────────────────────────┘
                 │ profile — the      │
                 │ method Priority 6  │
                 │ fixed this session)│
                 └──────────────────┘
```

**Every existing component this phase is expected to touch:**

| Component | Change required | Nature |
|---|---|---|
| `digital-twin-engine` | Build from scratch | New engine |
| `nova-contracts` | Extend `CommunicationSessionCompletedPayload` (Fork B); no change needed for the two already-defined digital-twin payloads | Additive |
| `communication-engine` | New `DigitalTwinPort` + client (mirrors `PersonalityPort`/`ReasoningPort`); wire into `resolve_response_shaping()` (Fork A); optionally extend `Notification` delivery for the warm case (Fork D) | Additive |
| `personality-engine` | New subscription + handler for `personality.memory.update`, calling the already-correct `update_memory_profile` | Additive |
| `docker-compose.local.yml` | New `digital-twin-engine` (+ its outbox worker, per Priority 1's established precedent — §9) service | Infra |
| `.github/workflows/real-infra-checks.yml` | New matrix entry for `digital-twin-engine` | CI |
| `pr-checks.yml` / turbo pipeline | Automatic — no engine-specific config, per every prior engine's own onboarding | None |
| `apps/web-client` | Out of this document's scope (no `apps/` exists yet in this repo at all) | N/A |
| `world-model-engine`, `memory-engine`, `knowledge-engine`, `reasoning-engine`, `executive-cognition-engine`, `ai-model-orchestration-engine`, `perception-engine` | **None required** | Not touched |

**Dependency graph for this phase's own internal sequencing:**

```
communication-engine's CommunicationSessionCompletedPayload
enrichment (Fork B decision)
              │
              ▼
digital-twin-engine's domain layer (Communication Profile,
Preference Evolution, trust metric, proactive-boundary policy)
              │
      ┌───────┴────────┐
      ▼                ▼
personality-engine    communication-engine
subscription (small,   DigitalTwinPort (Fork A
independent)           decision) + optional
                        Notification wiring (Fork D)
```

Nothing in this phase depends on Phase 3 or Phase 4 work. Everything it
depends on (2A–2C, Memory/Knowledge/World Model from Phase 1) is already
built.

---

## 4. Prerequisites — verified state, not assumed

### 4.1 Completed prerequisites

- Phases 2A, 2B, 2C, and all six Phase 2D-C Closure priorities are
  implemented, Gate-Reviewed, and — as of this session — real-infrastructure
  confirmed (34/34 `real_infra` tests passing on GitHub Actions, Priority 6
  Gate Review). `communication-engine` can hold an actual, working
  conversation through Reasoning today (Priority 3).
- `personality-engine`'s `update_memory_profile` — the exact method
  `personality.memory.update`'s handler would call — is fixed and
  real-Postgres-confirmed working (this session, Priority 6 §2.1). This was
  not done *for* Phase 2D-D, but it is a genuine, verified enabler for it:
  before this session, calling this method against real Postgres crashed
  with `MissingGreenlet` on every invocation.
- Both of digital-twin-engine's wire contracts (`digital_twin.preferences.get`,
  `personality.memory.update`) are already defined, versioned (`schema_version`),
  and internally consistent with `MemoryProfile`'s existing field shape.
- ADR-030 is filed and unambiguous about the ownership boundary — no
  additional ADR is required before this phase's TDD.
- `communication.session.completed` genuinely fires on every session close
  — not dormant, not a stub.

### 4.2 Incomplete prerequisites (must be resolved as part of this phase, not assumed away)

- **`CommunicationSessionCompletedPayload` does not carry conversation
  evidence** (§1.1, Fork B). This blocks digital-twin-engine from learning
  anything from the event as currently shaped.
- **`personality-engine` has no subscription mechanism for
  `personality.memory.update`** — this is new work, not wiring an existing
  handler.
- **`communication-engine` has no `DigitalTwinPort`** — new work, though a
  direct structural mirror of `PersonalityPort`/`ReasoningPort` (no design
  novelty).

### 4.3 Dormant/unreachable code this phase would newly activate

- `personality-engine`'s `update_memory_profile` (dormant since it was
  written in 2D-A; becomes reachable the moment a `personality.memory.update`
  handler exists).
- `communication-engine`'s response-shaping path already threads `channel`
  through to `personality.style.select` — no change needed there; this
  phase adds a *second*, parallel data source (`digital_twin.preferences.get`
  or the `personality.memory.update`-mediated path — Fork A), not a
  replacement.

### 4.4 Stale documentation found

- None beyond what's already disclosed. `response_shaping.py`'s own
  docstring (`domain/response_shaping.py:10-15`) already correctly states
  `digital_twin.preferences.get` "is deliberately never called this
  phase... until Phase 2D-D's `digital-twin-engine` exists" — this is
  accurate, current, and does not need correction.
- `CommunicationSessionCompletedPayload`'s docstring already says "Memory
  Engine is this event's intended (not yet wired, out of Phase 2D-A scope)
  subscriber" (`events/communication.py:180-182`) — also accurate and
  current; Memory Engine's `SUBSCRIBABLE_SUBJECTS`
  (`services/memory-engine/src/nova_memory_engine/events/subscribed.py`)
  confirms this subscription genuinely does not exist. **This is not new
  technical debt this document is introducing — it is pre-existing, already
  disclosed, and this phase now has a direct stake in resolving at least the
  digital-twin-engine side of it (Fork B).**

### 4.5 Infrastructure-dependent gaps (inherited, not new)

- No companion-client transport exists anywhere in this repository (the same
  gap the 2D-C closure document disclosed for Priority 1/4's "cold case").
  This directly caps Fork D (§10) — true proactive delivery to a
  disconnected user is out of reach this phase, for the identical,
  already-disclosed reason, not a new gap.
- The outbox-worker-as-a-deployed-process gap Priority 1 closed *only for
  perception-engine* remains open for every other engine, including the two
  this phase touches most (`communication-engine`, `personality-engine` —
  neither has its own migrations this phase touches, so this doesn't block
  Fork B, but `digital-twin-engine` itself will need its own worker service
  deployed from day one, following Priority 1's precedent exactly, not the
  older undeployed pattern — see §9).

### 4.6 Architectural inconsistencies vs. the original TDD/Blueprint

None found. The Master Blueprint's own text is internally consistent with
current code at every point checked (§1.1's table). The one place existing
code and the Blueprint's prose could be read two ways — how
`digital_twin.preferences.get` and `personality.memory.update` relate to
each other — is not an inconsistency, it is an underspecified design
question this document raises as Fork A.

---

## 5. Existing patterns and precedents to reuse (searched before proposing anything new)

- **Engine skeleton**: `perception-engine`'s file layout is the closest
  precedent — a minimal-form stateful engine shipped in exactly this same
  incremental spirit ("ships now with two sensing modalities instead of the
  full breadth," Master Blueprint §9.1). Its structure
  (`api/`, `clients/`, `config.py`, `domain/`, `events/{handlers,published,
  publishers,subscribed}.py`, `main.py`, `observability.py`,
  `repository/{models,outbox_dispatcher,postgres_*_repository}.py`,
  `workers/outbox_worker.py`) is the template `digital-twin-engine` should
  follow, not a novel structure.
- **Shared infrastructure**: `nova-service-kit` (`create_engine`,
  `create_session_factory`, `make_health_router`, `dispatch_ready_events`,
  `OutboxRepository`) — used identically by every prior engine, zero
  engine-specific knowledge (ADR-034). No new shared package is needed.
- **Outbox pattern**: every write-then-publish path in this codebase uses
  the same transactional-outbox shape (`enqueue_outbox` alongside the
  domain write, dispatched by `workers/outbox_dispatcher.py`). Reused
  as-is.
- **Port/client pattern for a new synchronous dependency**:
  `communication-engine`'s `PersonalityPort`/`ReasoningPort`/`WorldModelPort`
  (`domain/ports.py`) plus their `clients/*.py` implementations are the
  exact, already-proven template for the new `DigitalTwinPort` — a
  `Protocol` in `domain/ports.py`, an implementation in `clients/`, injected
  the same way, degraded-mode fallback the same way (Fork A's mechanics
  reuse this precedent regardless of which option is chosen).
- **Fake port for testing**: `nova-testkit`'s `FakePerceptionSignalSource`
  (built for 2D-C) is the direct precedent for a `FakeDigitalTwinPort`/
  similar this phase would add to `nova-testkit`, not a bespoke per-test
  fake.
- **"Warm case only" precedent for a partially-blocked feature**: Priority
  4's `StartListeningSignal` (mirrors `BargeInSignal` exactly, ships the
  warm case, explicitly defers the cold case for the identical
  already-disclosed reason) is the direct precedent Fork D's recommended
  option follows.
- **Real-Postgres verification pattern**: every existing engine's
  `tests/integration/test_repository_real_postgres.py` +
  `nova_testkit.postgres` fixtures — `digital-twin-engine` follows this
  exactly, no new pattern needed (§12).
- **ADR precedent for a one-way, enforced-by-omission dependency**: ADR-030
  already *is* this pattern (modeled directly on ADR-017's World Model
  boundary) — no new ADR needed for anything this document proposes, since
  nothing here changes an existing ownership boundary.

No existing pattern was found for: a trust/confidence-tracked preference
history table (genuinely new to this codebase, though Bible Part 15's
Knowledge Engine has an adjacent "maturity lifecycle" —
ADR-015 — worth consulting as a *conceptual* precedent for "confidence
that changes gradually with evidence," even though its schema is
domain-specific to knowledge nodes and not directly reusable).

---

## 6. Prerequisite gaps found in existing evidence sources (not adjacent debt — named 2D-D scope items with no data to learn from)

Per instruction, these are reported because they are hard prerequisites for
functionality this phase's own scope explicitly names, not unrelated
findings.

### 6.1 Communication Profile / Preference Evolution evidence

Needs `ConversationMemory`'s `preferences`/`corrections`/`feedback` lists
(Bible Part 13, Bible Part 16's own "Preference Evolution" discipline
requires "consistent evidence" across multiple sessions). **Currently
inaccessible to any subscriber of `communication.session.completed`** —
this is Fork B.

### 6.2 Habit Detection (interaction-timing slice)

Needs only `closed_at` (already present) plus, ideally, per-turn
timestamps to detect intra-session pacing — `ConversationTurn` already has
its own timestamp per the existing schema (not verified line-by-line in
this pass, reasonable to assume present given every other domain model's
timestamp discipline; **flagged as documented-not-fully-verified** for the
implementer to confirm before relying on it). The coarsest form
("session closed at time X") is already sufficient for the narrow
"prefers terse responses during working hours" example the Blueprint
itself gives, so this domain's minimum viable evidence need is **already
met**, unlike §6.1/§6.3.

### 6.3 Trust-development metric — all three named inputs have gaps

- **Correction frequency**: same gap as §6.1 (`ConversationMemory.corrections`
  not exposed in the completion event) — resolved by the same Fork B
  decision.
- **Clarification-question acceptance**: `communication-engine`'s
  Clarification Engine (`domain/clarification.py`) is scoped to
  **addressee-ambiguity clarification only** (its own docstring, lines
  1-7) — a fixed two-template system (`ADDRESSEE_CHECK_IN_CUE`,
  `resume_offer()`), not general content clarification. There is
  **no existing signal anywhere recording whether a user accepted,
  answered, or ignored a clarification** — this would need to be newly
  instrumented (e.g., as a new field on `ConversationDecisionTrace`, whose
  `decision_type` enum does not currently include a
  clarification-response outcome — `domain/models.py:180-182`).
- **Proactive-suggestion acceptance/dismissal**: has **no evidence source
  at all** — proactive suggestions have never been deliverable (§4.5), so
  there is nothing to have an acceptance/dismissal rate over yet. This is
  the most structurally incomplete of the three inputs.

**This means the trust-development metric, as literally specified by the
Master Blueprint's three named inputs, cannot be fully built this phase
without also instrumenting new signals communication-engine does not
currently produce.** This is not a reason to abandon the feature — it is a
scope-precision finding: the TDD that follows this document's approval must
either (a) instrument all three signals as part of 2D-D's own scope, or (b)
explicitly narrow the trust metric to whichever subset of the three inputs
has real evidence this phase, with the rest added when their own
prerequisite (Fork D's proactive-delivery mechanism, general clarification)
ships. **This is folded into Fork C (§10) rather than decided here.**

---

## 7. Contracts and data flow

### 7.1 Already-defined, reused as-is

```python
# nova_contracts.events.communication
@register_payload("digital_twin.preferences.get.request")
class DigitalTwinPreferencesGetRequestPayload(BaseModel):
    user_id: UUID
    schema_version: int = 1

@register_payload("digital_twin.preferences.get.reply")
class DigitalTwinPreferencesGetReplyPayload(BaseModel):
    user_id: UUID
    preferences: dict[str, Any] | None = None
    schema_version: int = 1

# nova_contracts.events.personality
@register_payload("personality.memory.update")
class PersonalityMemoryUpdatePayload(BaseModel):
    verbosity: str | None = None
    technical_depth: str | None = None
    terminology_preference: dict[str, Any] | None = None
    source: str = "digital_twin"
    schema_version: int = 1
```

Both are ADR-024-compliant (versioned, additive-safe) and require no
changes for this phase's minimum scope. `DigitalTwinPreferencesGetReplyPayload.preferences`
being an untyped `dict[str, Any]` is a **known looseness** worth tightening
in the TDD proper (a typed sub-model per Communication Profile field) but
not a blocker — the contract as defined is functional.

### 7.2 New, additive contract needed (Fork B)

`CommunicationSessionCompletedPayload` needs new optional fields to carry
learning evidence — proposed shape (illustrative, not final — the TDD
should finalize exact naming):

```python
class CommunicationSessionCompletedPayload(BaseModel):
    session_id: UUID
    user_id: UUID
    objective: str | None = None
    turn_count: int
    closed_at: datetime
    # New, optional (ADR-024), populated from ConversationMemory:
    corrections: list[str] | None = None
    preferences: list[str] | None = None
    feedback: list[str] | None = None
    decisions: list[str] | None = None
    schema_version: int = 1
```

This is additive and backward-compatible; no existing consumer breaks
(there are currently zero consumers of this event outside its own
publisher).

### 7.3 New port/client

`communication-engine`'s `domain/ports.py` gains a `DigitalTwinPort`
Protocol, structurally identical to `PersonalityPort`:

```python
class PreferenceSelection(BaseModel):
    verbosity: str | None
    technical_depth: str | None
    # further fields per Fork A's resolution

@runtime_checkable
class DigitalTwinPort(Protocol):
    async def get_preferences(
        self, *, user_id: UUID, correlation_id: UUID | None = None
    ) -> PreferenceSelection | None: ...
```

Implemented by a new `clients/digital_twin_client.py`, calling
`digital_twin.preferences.get.request` — the same shape as
`clients/personality_client.py`/`clients/reasoning_client.py`.

### 7.4 Data flow summary

```
Turn evidence accumulates in ConversationMemory during a session (existing,
unchanged) → session closes → communication.session.completed (enriched,
Fork B) → digital-twin-engine consumes, updates Communication Profile /
Preference Evolution / trust metric (its own persisted state) →
digital-twin-engine publishes personality.memory.update (already-defined)
→ personality-engine's new handler calls update_memory_profile (already
correct) → future personality.style.select calls reflect the learned
baseline.

In parallel, mid-turn: communication-engine's resolve_response_shaping()
optionally also calls digital_twin.preferences.get directly (Fork A) for
data personality-engine's narrower StyleSelection doesn't carry.
```

---

## 8. Persistence implications

`digital-twin-engine` is stateful (Master Blueprint §8) and needs its own
Postgres schema, following every prior engine's exact pattern: a
`digital_twin` schema (mirroring `personality`, `perception`,
`communication`), an Alembic migration chain starting at `0001_initial_schema.py`,
and — per Bible Part 16's own "Digital Twin Memory" section ("every
important change becomes part of historical evolution... track what
changed, when, why, confidence, source") — an append-only history table
for Preference Evolution, not just a single mutable current-value row
(mirroring `ConversationDecisionTrace`'s own append-only design, §5.5 of
this document, and `ADR-016`'s "contradiction recording, not overwriting"
principle from Knowledge Engine — the same evidence-preserving discipline
applied to a different domain).

Proposed minimal schema shape (illustrative — the TDD proper defines
exact columns):

- `communication_profile` (current resolved values — verbosity,
  technical_depth, terminology_preference, explanation_style,
  conversation_pacing — one row per user, mirroring `memory_profile`'s
  singleton-per-user shape).
- `preference_evolution_history` (append-only: what changed, when, why,
  confidence, source — per Bible Part 16 verbatim).
- `habit_signal` (interaction-timing observations, conversation-scoped
  only per §2's scope limit).
- `trust_metric` (current resolved trust signal + its own history,
  same evolution discipline).
- `proactive_boundary_policy` (user-configured frequency/topic limits).

No cross-engine shared table (ADR-004 compliance, matching every other
engine's Postgres schema being private to that engine).

---

## 9. Security and boundary analysis

- **ADR-004** (Event Bus is the only legal cross-engine channel): every
  proposed integration point (§7) is an event/RPC, not a direct import or
  HTTP call between engines. Compliant by construction.
- **ADR-005** (only `communication-engine` renders user-facing output):
  `digital-twin-engine` never speaks directly — even the
  proactive-communication boundary policy only ever *permits or denies*
  something communication-engine (or a future notification path) would
  say; it never itself delivers content. Compliant.
- **ADR-030**: this document proposes zero changes to the one-way
  dependency direction it establishes. `personality-engine` still gets no
  port to query digital-twin — the flow stays publish-only, exactly as
  decided.
- **Consent/privacy** (Bible Part 16's own "Privacy First," Doc 22
  Principle 8): Communication Profile and Preference Evolution data is
  more sensitive than most prior engines' data (it is literally a model of
  how the user communicates). The existing `perception-engine` consent
  pattern (`api/consent.py`, `domain/consent.py` — per-source, explicit,
  revocable) is the direct precedent to reuse for user control over
  digital-twin-engine's learning (Bible Part 16's own "User Control"
  section: view/modify/delete/export/pause/reset). **This is a genuine
  scope item for the TDD, not optional** — Bible Part 16 states
  "Transparency is mandatory," and this phase is the first time any engine
  stores a model *of the user's own communication patterns* rather than
  content the user explicitly sent.
- **Data ownership matrix** (Master Blueprint §7): this document's schema
  proposal (§8) respects "never touches: goals/projects/hardware/software/
  skills domains" — nothing proposed here reads or writes outside
  Communication Profile / conversation-scoped Preferences / trust /
  proactive-boundary.
- **No new authorization signal**: unlike ADR-032 (identity confidence as
  authorization for perception-engine), nothing in this phase's proposed
  design uses any digital-twin data as an authorization/access-control
  input — it only ever shapes *how* NOVA responds, never *whether* it's
  allowed to.

---

## 10. Design forks requiring the user's decision

### Fork A — How does `communication-engine` combine `personality.style.select` and `digital_twin.preferences.get`?

**Evidence**: Master Blueprint §4.3 states response-length/tone selection
consumes *both* "personality-engine's style rules and digital-twin-engine's
learned preferences... via served RPC." ADR-030 establishes digital-twin
already pushes its resolved values into personality-engine via
`personality.memory.update`, so `personality.style.select`'s reply should
already reflect digital-twin's latest learning by the time it's called.

**Options:**
1. **Personality-mediated only.** Do not call `digital_twin.preferences.get`
   from `resolve_response_shaping()` at all this phase. Rely entirely on
   the async `personality.memory.update` → `update_memory_profile` →
   `personality.style.select` chain. **Cost:** the served RPC contract
   (`digital_twin.preferences.get`) ships but has zero real callers this
   phase either — the same "defined, not yet called" state it's in today,
   just moved one phase later than the Blueprint's own text implies.
   **Benefit:** avoids the exact "guaranteed extra synchronous hop" latency
   cost `response_shaping.py`'s own docstring already argued against once
   (Master Blueprint §13.2), for data that (for verbosity/technical_depth)
   is already flowing through the existing call.
2. **Direct RPC only**, for fields `personality-engine`'s `StyleSelection`
   doesn't carry (conversation pacing, interaction habits) — leave
   `personality.memory.update` unused this phase. **Cost:** two independent
   preference pathways with no defined precedence if they ever disagree on
   an overlapping field (they shouldn't, if scoped correctly, but nothing
   enforces that). **Benefit:** matches the Blueprint's literal "both" text
   for the fields that are genuinely digital-twin-only.
3. **Both, scoped to non-overlapping fields** — `personality.memory.update`
   remains the path for verbosity/technical_depth/terminology (fields
   `personality-engine` already owns and applies); `digital_twin.preferences.get`
   is called only for fields personality-engine has no concept of
   (conversation pacing, habit-derived timing hints) that response-shaping
   or silence-policy logic would consume directly. **Cost:** the most
   design work (deciding the exact field split); **Benefit:** matches the
   Blueprint's "both" text precisely, keeps ADR-030's boundary
   (personality-engine still never learns), avoids redundant computation.

**Recommendation:** **Option 3.** It is the only option that is both
literally consistent with the Blueprint's own "both" language and internally
non-redundant. The field split should be drawn along the same line ADR-030
already draws — anything personality-engine's `MemoryProfile` already models
(verbosity, technical_depth, terminology) stays on the async path;
anything it doesn't (pacing, timing habits) goes on the direct RPC path,
called only when that data is actually needed (e.g., only when silence/pacing
policy is being evaluated, not on every single turn) to preserve the
low-latency tie-break rule.

### Fork B — How does `digital-twin-engine` obtain conversation evidence?

**Evidence:** §4.2, §6 — `CommunicationSessionCompletedPayload` carries
none of `ConversationMemory`'s substance today; Memory Engine's own
intended subscription to this event was never wired either (a pre-existing,
disclosed gap this phase now has a direct stake in).

**Options:**
1. **Enrich the event additively** (§7.2) so `digital-twin-engine` gets
   everything from the event it already subscribes to. **Cost:** touches
   `communication-engine`'s publish call site and `nova-contracts`
   (both additive, low risk). **Benefit:** simplest, most local change;
   `digital-twin-engine` needs no new outbound call to learn.
2. **`digital-twin-engine` calls back into `communication-engine`** via a
   new served RPC (e.g. `communication.session.memory.get`), keyed by
   `session_id`, upon receiving the (unenriched) completion event.
   **Cost:** a new RPC surface on `communication-engine`, plus an extra
   synchronous hop *after* the session has already closed (lower latency
   sensitivity than Fork A, since nothing is waiting on this in a live
   turn) — but two round trips (event, then RPC) to get one session's data.
3. **Route through Memory Engine instead** — also wire Memory Engine's own
   long-disclosed subscription to `communication.session.completed`
   (enriched per Option 1 or its own RPC per Option 2) so it archives the
   full session, and have `digital-twin-engine` read from Memory Engine's
   episodic store rather than directly from communication-engine. **Cost:**
   the largest — fixes a second engine's gap as a side effect of this
   phase, which is exactly the kind of scope expansion instruction #10
   asks to flag rather than silently absorb. **Benefit:** matches Master
   Blueprint §4.3's own stated intent ("written to Memory Engine... as this
   session's episodic record") most faithfully, and gives every future
   consumer of session history (not just digital-twin-engine) one place to
   read it from.

**Recommendation:** **Option 1** for this phase's own scope, with Option
3's Memory Engine wiring **explicitly flagged as a separate, adjacent
prerequisite gap** (not a hard blocker for 2D-D, since Option 1 lets
digital-twin-engine learn directly without waiting on Memory Engine) that
should be tracked and closed independently — consistent with instruction
#10's "flag unrelated findings separately unless they are a hard
prerequisite." It is not a hard prerequisite here because Option 1 fully
unblocks 2D-D on its own.

### Fork C — How much of the trust-development metric ships this phase, given §6.3's evidence gaps?

**Evidence:** §6.3 — all three named inputs (correction frequency,
clarification-acceptance, proactive-suggestion acceptance/dismissal) have
either a data-shape gap (correction frequency — resolved by Fork B) or no
existing signal at all (the other two).

**Options:**
1. **Ship correction-frequency only this phase** (the one input Fork B's
   resolution directly unblocks), with the metric explicitly documented as
   partial, and clarification-acceptance/proactive-suggestion inputs added
   later as their own prerequisites (general clarification instrumentation;
   Fork D's delivery mechanism) ship. **Cost:** the trust metric is
   narrower than the Blueprint's literal three-input description this
   phase. **Benefit:** honest, ships something real rather than a
   fabricated composite; matches this project's own standing discipline
   against inventing evidence that doesn't exist yet (Doc 22, Doc 23 §6).
2. **Instrument all three inputs as part of this phase's own scope** —
   add a clarification-response outcome to `ConversationDecisionTrace`
   (communication-engine change) and build Fork D's warm-case delivery
   path with acceptance/dismissal tracking, before digital-twin-engine's
   trust metric is considered "done." **Cost:** meaningfully larger scope,
   touching communication-engine's decision-trace model and requiring
   Fork D resolved first as a hard dependency rather than a parallel item.
   **Benefit:** ships the metric as literally specified.

**Recommendation:** **Option 1.** Building a metric on two-thirds fabricated
or absent evidence would violate this project's own repeated,
already-established discipline (Bible Part 16's own "never create
assumptions without evidence"; Doc 22/23's anti-fabrication rules already
cited throughout this codebase's own docstrings). A correctly-scoped
partial metric, honestly disclosed as partial, is preferable to a complete-
looking one that isn't.

### Fork D — Does this phase build any real proactive-communication delivery, or policy only?

**Evidence:** §4.5, §9 — no companion-client transport exists (inherited
gap); `Notification`/`POST /v1/communication/notifications` already exists
but only persists, never delivers; Priority 4's `StartListeningSignal`
precedent shows a "warm case now, cold case deferred" split is both
possible and already-approved practice in this exact codebase.

**Options:**
1. **Policy only.** `digital-twin-engine` builds and exposes the
   proactive-communication boundary policy (config, limits, an evaluation
   function returning allow/deny for a hypothetical proactive message) with
   no wiring to any actual delivery path. **Cost:** the feature is
   contract/fake-verifiable only — no real end-to-end proof it changes
   anything a user would experience. **Benefit:** zero new risk surface,
   fully honest about the existing companion-client gap, smallest change.
2. **Warm-case delivery**, mirroring Priority 4 exactly: when a session is
   already connected (`SessionRegistry.is_connected`), a proactive message
   that passes the boundary policy is actually deliverable through the
   existing WS connection via the intent gate (extending `Notification`
   or a similar new path); the cold case (no connected session) remains
   explicitly out of reach, for the same already-disclosed reason as
   Priority 1/4. **Cost:** touches `communication-engine`'s delivery path
   again, a second time this phase (on top of Fork A's `DigitalTwinPort`).
   **Benefit:** genuinely, fully end-to-end verifiable for the warm case,
   with no hardware/companion-client fabrication — the same asymmetry the
   2D-C closure document highlighted for Priority 3/4 as achievable without
   compromise.

**Recommendation:** **Option 2**, using the exact warm-case-only precedent
Priority 4 already established and the 2D-C closure document already
validated as sound engineering discipline (its own §14 asymmetry note).
This is the one place this document recommends *more* scope than the
minimum, specifically because doing so costs nothing new architecturally
(the precedent and the connection-registry mechanism already exist) and
produces a genuinely verifiable feature rather than a policy nobody can
observe working.

---

## 11. Does anything here reopen a Phase 2D-A/B/C decision?

**No.** Checked explicitly, per instruction #11:

- ADR-030's boundary is preserved exactly (§9).
- Priority 3's synchronous-RPC design (Fork #1 of the closure document) is
  not touched — this phase adds a *new* synchronous RPC following the same
  precedent, not a change to the existing reasoning loop.
- Priority 4's `StartListeningSignal`/warm-case pattern is *reused*, not
  altered.
- Priority 5's channel-based verbosity-only scope is unaffected —
  `digital_twin.preferences.get`/`personality.memory.update` operate on the
  same `verbosity`/`technical_depth` fields Priority 5 already established
  boundaries for, without changing those boundaries.
- Priority 6's real-infra verification discipline is extended (a new
  engine added to the same matrix, §12), not changed.
- The stale `ResponseShapingDirective`/task-tracker items the user
  previously told me not to reopen remain untouched.

No concrete blocker was found that would require reopening any of the
above.

---

## 12. Failure and degraded-mode behavior

Following the exact pattern every prior integration in this codebase uses
(Doc 22 Principle 3 — silence is a choice, never an outage symptom):

- **`digital-twin-engine` unreachable when `communication-engine` calls
  `digital_twin.preferences.get`** (Fork A, if chosen): same
  `TimeoutError` → degraded-default pattern `resolve_response_shaping()`
  already implements for `personality.style.select` — falls back to
  whatever `personality.style.select`'s own resolved value already is
  (which, per Fork A Option 3, already reflects the last-known digital-twin
  state via the async path), never blocks delivery.
- **`personality-engine` unreachable when `digital-twin-engine` publishes
  `personality.memory.update`**: this is fire-and-forget pub/sub, not a
  request needing a reply — the standard outbox-retry semantics every
  other publish in this codebase already has apply unchanged; no new
  failure mode.
- **`communication-engine` unreachable when `digital-twin-engine` tries to
  learn from a session**: `digital-twin-engine`'s subscription simply
  never fires for that session; no crash, no partial state (mirrors
  perception-engine's own "no event published, sensor marked failed, no
  partial signal" discipline, closure doc §3.6).
- **Malformed/missing evidence in an enriched `CommunicationSessionCompletedPayload`**
  (Fork B): all new fields are optional — a `None` list means "no evidence
  this session," which `digital-twin-engine`'s Preference Evolution logic
  must treat as "no update," never as "user has no preferences" (avoiding
  exactly the false-negative-as-fact failure Bible Part 16 warns against).

---

## 13. Observability

Reuses the existing, established pattern with zero new observability
primitives needed: every RPC call gets `correlation_id` propagation
(already mandatory per every existing port's signature); every domain
decision (a preference change, a trust-metric update, a proactive-boundary
allow/deny) gets an append-only trace row, mirroring
`ConversationDecisionTrace`'s exact shape and Doc 22's explainability
principle — the user should be able to see *why* NOVA now responds more
tersely to them, not just that it does. `nova-observability`'s existing
OTel wiring (used identically by all ten current engines) applies
unchanged.

---

## 14. Testing strategy

Two-tier convention unchanged (ADR-033): fast unit/contract tests against
fakes for every new function (default tier); `real_infra`-marked tests for
the new Postgres schema/migration and the real event round-trip, following
`personality-engine`'s/`perception-engine`'s own `test_repository_real_postgres.py`
pattern exactly.

**New fakes needed in `nova-testkit`**: `FakeDigitalTwinPort` (mirrors
`FakePerceptionSignalSource`'s precedent).

**Specific new test classes:**
- Preference Evolution discipline test (Bible Part 16's own requirement,
  named explicitly in the existing roadmap's Phase 2D testing strategy): a
  single contradicting data point must never flip a stored preference —
  this is a **named acceptance criterion already in `ENGINEERING_ROADMAP.md`**,
  not a new invention.
- Degraded-mode tests for every failure mode in §12.
- Contract round-trip tests for the enriched `CommunicationSessionCompletedPayload`
  and both existing digital-twin payloads (mirrors every prior
  `test_*_events.py` file in `nova-contracts/tests/`).
- Warm-case proactive-delivery integration test (Fork D, if Option 2), the
  same shape as Priority 4's own `StartListeningSignal` integration test.

---

## 15. Real-infrastructure verification requirements

`digital-twin-engine` needs its own `tests/integration/test_repository_real_postgres.py`
and a new matrix entry in `.github/workflows/real-infra-checks.yml`
(currently 4 packages: `nova-testkit`, `communication-engine`,
`personality-engine`, `perception-engine` — this phase adds a 5th). Given
this session's own Priority 6 experience, the concrete recommendation is:
**write these tests as part of the engine's own build, but do not consider
Phase 2D-D "done" until they have an actual green execution on
GitHub Actions** — the same standard just enforced for Priority 6, not a
lower bar for a new engine.

---

## 16. Technical debt discovered during this research (flagged separately, per instruction #10 — not expanded into this phase's scope)

- Memory Engine's long-disclosed, still-unwired subscription to
  `communication.session.completed` (§4.4, Fork B's Option 3). Not a hard
  2D-D blocker (Fork B Option 1 avoids needing it), but genuinely adjacent
  and worth its own tracked item.
- The outbox-worker-as-a-deployed-process gap remains open for every engine
  except perception-engine (Priority 1's fix was scoped to that engine
  only, by explicit prior instruction). `digital-twin-engine` should be
  built with its worker deployed from day one (§9) rather than adding to
  this gap, but the existing gap for the other 9 engines is unrelated to
  this phase and not proposed for fixing here.
- `DigitalTwinPreferencesGetReplyPayload.preferences: dict[str, Any]` is
  untyped (§7.1) — worth a typed sub-model when the real TDD is written,
  not a blocker for this research document.

---

## 17. Recommended implementation order

1. **Fork B's decision**, then the `CommunicationSessionCompletedPayload`
   enrichment (`nova-contracts` + `communication-engine`'s one publish call
   site) — small, additive, unblocks everything downstream.
2. **`digital-twin-engine`'s domain layer** (Communication Profile,
   Preference Evolution with its evidence discipline, Habit Detection
   slice, trust metric scoped per Fork C, proactive-boundary policy) —
   buildable and fully unit-testable against fakes before any other engine
   changes.
3. **`digital-twin-engine`'s repository/API/events/main.py scaffold**,
   following perception-engine's template (§5) — including its own outbox
   worker service in `docker-compose.local.yml` from the start.
4. **`personality-engine`'s new subscription** (small, independent, can
   happen in parallel with step 3).
5. **`communication-engine`'s `DigitalTwinPort`**, wired per Fork A's
   resolution, into `resolve_response_shaping()`.
6. **Fork D's warm-case delivery wiring** (if approved), last, since it is
   the one item that touches `communication-engine`'s delivery path a
   second time and benefits from steps 1-5 already being stable.
7. **Real-infrastructure verification** (§15) — write alongside each step,
   confirm on GitHub Actions before declaring the phase done, per Priority
   6's own precedent.

---

## 18. Summary — verified / contract-verified / unverified, applied to this proposal itself

This document proposes no code; the table below is a forward statement of
what each piece's verification status *would be* once built, so the
eventual TDD and Gate Review are checked against the same bar Priority 6
was:

| Integration | Expected classification once built |
|---|---|
| `digital-twin-engine`'s own Postgres repository | Fully verified once `real_infra`-tested (§15) |
| `personality.memory.update` publish → personality-engine consumption | Fully verified — both sides already exist or are simple, real, in-process code; no external client needed |
| `communication.session.completed` (enriched) → digital-twin-engine consumption | Fully verified, same reasoning |
| `digital_twin.preferences.get` RPC (Fork A) | Fully verified — both sides run in-process in this monorepo, no hardware dependency |
| Fork D warm-case delivery | Fully verified — no companion client needed, mirrors Priority 4's own already-verified precedent |
| Fork D cold case | Not applicable — explicitly out of reach, inherited limitation |
| Trust-development metric (Fork C, scoped) | Contract/fake verified for the shipped input; the other two inputs remain absent, not partially-fake-verified — they simply don't exist yet |

---

## 19. What this document is not

This is not an approved Technical Design Document. It does not specify
exact API request/response shapes, exact Alembic column types, or exact
handler function signatures — that level of detail belongs in the TDD this
document's approval would authorize, following the same
Design → Implementation → Testing → Architecture Review → Gate Review →
Metrics → Approval sequence every prior phase used. No implementation
begins until the user reviews this document and its four forks and gives
explicit approval.
