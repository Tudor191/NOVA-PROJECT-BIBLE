# Phase 2D-D — Personal Companion: Technical Design Document

**Status: TDD — scope and all forks approved by the user. No production code
has been written or modified to produce this document.** This document
supersedes and completes `06-personal-companion.md`'s earlier
research/proposal revision, incorporating the four originally-approved
forks (A-D) and a fifth fork (E) discovered and approved during this pass.
Every claim was verified directly against the current source tree this
session, file:line cited throughout.

---

## 0. Approved decisions incorporated

| Fork | Decision | Where addressed |
|---|---|---|
| A | `personality.style.select` and `digital_twin.preferences.get` split by field — verbosity/technical_depth/terminology stay on the `personality.memory.update`-mediated path; digital-twin-owned fields (pacing, habit-timing) go on the direct RPC | §7.3 |
| B | `CommunicationSessionCompletedPayload` enriched additively with `ConversationMemory`'s evidence fields; Memory Engine's unwired subscription stays separate, non-blocking debt | §6 |
| C | Correction-frequency ships as the (explicitly partial) trust-development metric this phase; clarification-acceptance and proactive-suggestion acceptance/dismissal are not fabricated | §9 |
| D | Warm-case proactive delivery ships; cold case stays out of scope, documented | §10 |
| E | `reasoning-engine` added to scope to provide the correction signal; narrow, evidence-based, reuses the engine's one existing content-understanding model call rather than a new classifier | §5 |

---

## 1. Current-state findings (re-verified this pass, supersedes anything in the prior revision that conflicts)

### 1.1 Corrected understanding from this pass's deeper verification

Two findings this pass revise the prior research document's picture —
recorded here explicitly rather than silently:

- **`deliver_intent()` (`domain/intent_gate.py:59-70`) has no
  `memory_annotations` parameter — but it is not the function Priority 3's
  real turn path calls.** `conversation_orchestration.py` (the real,
  wired turn-handling path) calls `events/handlers.py`'s
  `deliver_content_to_session()` — a shared wrapper that **already**
  applies `memory_annotations` to `ConversationMemory` *before* calling
  `deliver_intent()` (`events/handlers.py:67-97`). The exact same wrapper
  is what `make_intent_deliver_handler` (the `communication.intent.deliver.request`
  event handler) calls too (`events/handlers.py:161-172`). **Both the real
  turn path and the event-driven out-of-band path already funnel through
  one shared, `memory_annotations`-capable function.** This means the
  correction signal (§5) needs no new storage mechanism in
  communication-engine — only a value to pass into a parameter that
  already exists and is already wired into the real path.
- **Fork D's warm-case delivery needs no new communication-engine delivery
  mechanism either.** The 2D-C closure document already reserved
  `communication.intent.deliver.request` by name for exactly this: "a
  future proactive notification or reminder initiated by...another engine
  that is not itself already inside a turn-handling call stack" (closure
  doc §5.3 item 6). `deliver_content_to_session()` already resolves
  `session_registry.get_adapter(session_id)` (`events/handlers.py:111`),
  which is already `None` for a disconnected session, and `deliver_intent()`
  already returns a clean `rejection_reason="no_live_channel_connection"`
  rather than crashing (`intent_gate.py:113-121`). The warm/cold
  distinction is not new work — it's the existing, already-approved
  behavior of code that has simply never had a real caller yet.

### 1.2 `ReasoningRequestPayload`/`ReasoningReplyPayload` — exact current shape

```python
# nova_contracts.events.reasoning
class ReasoningRequestPayload(BaseModel):
    objective_text: str
    user_id: UUID
    requesting_engine: str
    correlation_id: UUID = Field(default_factory=uuid4)
    reasoning_mode_hint: ReasoningMode | None = None
    reasoning_level_hint: int | None = None
    thinking_mode_hint: str | None = None
    goals: list[GoalPayload] = Field(default_factory=list)
    constraints: list[ConstraintPayload] = Field(default_factory=list)
    parent_process_id: UUID | None = None
    schema_version: int = 1

class ReasoningReplyPayload(BaseModel):
    reasoning_process_id: UUID
    decision_id: UUID | None = None
    chosen_description: str | None = None
    explanation: str | None = None
    confidence_score: float | None = None
    outcome: ReasoningOutcome
    trace_id: UUID | None = None
    error: str | None = None
    schema_version: int = 1
```

**Neither payload has any field carrying the current session's recent
conversation history.** `context_assembly.assemble_context()`
(`domain/context_assembly.py:29-92`) fans out to Memory/Knowledge/World
Model/PersonalContext/Goals ports — none of which have access to an
*in-progress* session's own turns (Memory Engine only ever receives
archived, post-completion sessions, and — per §6.4 — does not even receive
those today). **Reasoning-engine, as currently wired, cannot know what
NOVA itself said earlier in the live conversation it is being asked about.**
This is a hard prerequisite for Fork E's correction judgment, addressed in
§5.2.

### 1.3 The one place reasoning-engine already does real content understanding

`domain/hypothesis_generation.py`'s `generate_hypotheses()` is the **sole,
explicitly-documented exception** where reasoning-engine calls a model for
actual content understanding — its own docstring states this plainly:
"Why this step legitimately calls a model, unlike almost every other
domain-layer decision in NOVA... this module is the deliberate, documented
exception" (`hypothesis_generation.py:1-13`). Every other stage
(`decision_matrix`, `confidence`, `constraint_evaluator`, `goal_evaluator`)
is deliberately structural and model-free. `pipeline.py::run()` calls it
once, at line 258-269, with the full assembled `ContextBundle`.

---

## 2. Approved scope (unchanged from the prior revision, restated for completeness)

**Builds** `digital-twin-engine` (new, minimal form — Bible Part 16's
Communication Profile domain + a conversation-scoped Preference
Evolution/Habit Detection slice + a trust-development metric + a
proactive-communication boundary policy).

**Extends** `communication-engine` (new `DigitalTwinPort`; enriched
`CommunicationSessionCompletedPayload` producer; correction-signal
transport; warm-case proactive delivery, reusing existing infrastructure),
`personality-engine` (new `personality.memory.update` subscription), and —
**newly, per Fork E** — `reasoning-engine` (one additive request field, one
additive reply field, one extended existing model call).

**Does not touch**: `world-model-engine`, `memory-engine` (beyond the
already-disclosed, non-blocking debt item in §6.4), `knowledge-engine`,
`executive-cognition-engine`, `ai-model-orchestration-engine`,
`perception-engine`.

---

## 3. Architecture and data flow

```
                          ┌───────────────────────────┐
                          │ communication-engine         │
                          │ conversation_orchestration.py │
                          └──────────────┬────────────────┘
                                          │ reasoning.reason.request
                                          │ (+ NEW: prior_nova_utterance)
                                          ▼
                          ┌───────────────────────────┐
                          │ reasoning-engine              │
                          │ hypothesis_generation.py      │
                          │ (existing model call, EXTENDED)│
                          └──────────────┬────────────────┘
                                          │ reasoning.reason.reply
                                          │ (+ NEW: is_correction)
                                          ▼
                          ┌───────────────────────────┐
                          │ communication-engine          │
                          │ conversation_orchestration.py │
                          │ builds memory_annotations      │
                          │ from is_correction, passes to  │
                          │ deliver_content_to_session()   │
                          │ (ALREADY memory_annotations-   │
                          │  capable, no new mechanism)    │
                          └──────────────┬────────────────┘
                                          │ ConversationMemory.corrections
                                          │ accumulates during session
                                          ▼
                              session closes → session_lifecycle.py
                                          │ communication.session.completed
                                          │ (NEW: enriched with corrections/
                                          │  preferences/feedback/decisions)
                                          ▼
                          ┌───────────────────────────┐
                          │ digital-twin-engine (NEW)      │
                          │ - Communication Profile          │
                          │ - Preference Evolution            │
                          │ - correction-frequency trust      │
                          │   metric (partial, per Fork C)     │
                          │ - proactive-boundary policy         │
                          └──────┬───────────────┬─────────────┘
              publishes           │               │ serves (RPC)
              personality.        │               │ digital_twin.preferences.get
              memory.update       │               │ (Fork A: pacing/habit fields
              (verbosity/         │               │  only, not verbosity/depth)
              technical_depth/    ▼               ▼
              terminology)  ┌──────────────┐ ┌──────────────────────┐
                            │personality-   │ │ communication-engine    │
                            │engine (NEW    │ │ (NEW DigitalTwinPort,    │
                            │subscription → │ │  called from              │
                            │update_memory_ │ │  resolve_response_shaping)│
                            │profile, fixed │ └──────────────────────┘
                            │Priority 6)    │
                            └──────────────┘

              Separately, warm-case proactive delivery (Fork D):
              digital-twin-engine → communication.intent.deliver.request
              (EXISTING event/handler, reserved for exactly this by the
               2D-C closure document — no new communication-engine
               mechanism required, §10)
```

---

## 4. Engine ownership and boundaries

Unchanged from the Master Blueprint's data ownership matrix (§7 of that
document) and ADR-030, with one addition: **`reasoning-engine` now owns the
correction judgment** — a narrow, additive responsibility, not a new
category of ownership. Reasoning-engine already owns "deciding what's
worth saying" (ADR-026); judging whether what's worth saying corrects a
prior statement is the same kind of content-understanding judgment, not a
new kind of authority.

**Why communication-engine cannot make this judgment itself:** every
existing docstring in this engine's own domain layer states this
explicitly and repeatedly — `response_shaping.py:50-53` ("never from
parsing turn content, which stays Reasoning Engine's job... this engine
never generates or classifies content"), `intent_gate.py`'s own framing
(never generates content, only gates it), `clarification.py:8-9` ("this
engine has no channel to request that from Reasoning Engine... inventing
one here would be exactly the kind of undisclosed scope expansion this
project's standing discipline forbids"). Communication-engine has never,
anywhere in its design or implementation, been given semantic
understanding of what users say — only structural signals it can count
(turn counts, timestamps, decision traces). Judging "does this correct
what NOVA said" requires understanding *meaning*, which this engine is
architecturally forbidden from doing.

**Why reasoning-engine is the correct owner:** it is the only engine in
this chain with (a) real content understanding via a model call
(`hypothesis_generation.py`), (b) already-assembled context about the
objective, and (c) an existing, precedented "the caller passes hints,
reasoning-engine folds them into its one real model call" pattern
(Priority 3 already established this for response-shaping hints — see
`05-conversation-intelligence-closure.md` §5.3 item 3).

---

## 5. The correction signal — exact design

### 5.1 Semantics — precisely defined, per instruction

**`is_correction: bool`** on `ReasoningReplyPayload` means: *reasoning-engine's
own judgment, made with the current turn's text and the immediately
preceding NOVA utterance in this session both in view, that the current
turn asserts something factually or substantively inconsistent with what
NOVA previously said* — not merely different, not merely a follow-up.

**Explicitly excluded, per instruction, and encoded directly in the model
prompt's own instructions** (§5.3):

- **Uncertainty** ("I'm not sure that's right") — a hedge, not a
  correction, unless it also asserts what *is* right.
  correct.
- **Disagreement** ("I don't think so") with no substantive counter-claim
  — disagreement alone is not evidence of what NOVA got wrong.
- **Clarification requests** ("what did you mean by X?") — the user
  seeking understanding, not asserting NOVA was wrong.
- **User self-correction** ("sorry, I meant Y not X") — corrects the
  *user's own* prior statement, not NOVA's.

Only an inbound turn that substantively contradicts or corrects content
NOVA itself previously delivered counts. This is deliberately the
narrowest reading available, per instruction #3.

### 5.2 Where the prior-NOVA-utterance context comes from

**New, additive field on `ReasoningRequestPayload`:**

```python
prior_nova_utterance: str | None = None
```

Sourced from data `communication-engine` already owns — the session's most
recent outbound `ConversationTurn`. **New, small repository method**
(mirroring `CommunicationRepository.list_non_terminal_sessions()`'s own
precedent of a purpose-built read query):

```python
async def get_last_outbound_turn(self, session_id: UUID) -> ConversationTurn | None: ...
```

Called by `conversation_orchestration.py` immediately before its existing
`state.reasoning_port.reason(...)` call (`conversation_orchestration.py:84`),
populating the new request field. **This introduces no new cross-engine
dependency** — the data already lives in `communication-engine`'s own
repository; this is a same-engine query added to an already-existing
outbound call, not a new port or a new call direction. This directly
answers instruction #5: existing context (`assemble_context`'s
memory/knowledge/world-model/personal-context/goals fan-out) is **not**
sufficient — none of those ports have access to an in-progress session's
own turns — but the fix does not require introducing a new dependency,
only widening a payload `communication-engine` already sends with data it
already has.

### 5.3 Reasoning pipeline integration point — exact

**`domain/hypothesis_generation.py`**, not a new module, not a new pipeline
stage. `build_prompt_context()` (`hypothesis_generation.py:47-`) gains one
more optional context component, using the exact same `_component()`
helper every other context source already uses:

```python
if prior_nova_utterance:
    components.append(_component("prior_response", prior_nova_utterance, priority=9))
```

The model call this function already makes is extended with an additional,
explicit instruction — appended to the existing prompt construction, not a
second call — asking the model to also emit a structured correction
verdict when `prior_response` context is present, using §5.1's precise
definition verbatim in the instruction text (uncertainty/disagreement/
clarification/self-correction explicitly named as non-qualifying, mirroring
how this codebase already encodes precise behavioral distinctions directly
in prompts elsewhere — e.g., `personality.validate_response`'s own
constraint-checking approach). `generate_hypotheses()`'s return type gains
one additive field alongside its existing `hypotheses`/`model_used`
tuple members; `pipeline.py::run()` threads it through the `Decision`
object to `ReasoningReplyPayload.is_correction`.

**No new classifier, no new model call, no parallel reasoning path.** One
existing model invocation now also answers one more well-defined question
in the same completion.

### 5.4 Storage — reuses existing, already-wired mechanism (§1.1)

`conversation_orchestration.py`, upon receiving `is_correction=True` in
`ReasoningOutcomeResult` (an additive field on this port-level result type
too, mirroring `outcome`/`confidence_score`'s existing shape,
`domain/ports.py:112-119`), constructs a `memory_annotations` entry:

```python
[{"category": "correction", "text": <the current turn's content>}]
```

and passes it into the **already-existing** `memory_annotations` parameter
of `deliver_content_to_session()` — the same call this orchestration
already makes for delivery. **Zero new storage code path.**
Communication-engine's role here is exactly instruction #6's constraint:
it transports and stores a value reasoning-engine already computed; it
never itself decides whether something is a correction.

### 5.5 Complete path (instruction #4)

```
inbound turn (WS/HTTP) → record_inbound_turn (existing)
→ conversation_orchestration.handle_conversation_turn (existing)
→ get_last_outbound_turn (NEW, same-engine query) → prior_nova_utterance
→ reasoning_port.reason(..., prior_nova_utterance=...) (existing call, additive arg)
→ reasoning-engine: pipeline.run() → context_assembly (unchanged)
→ hypothesis_generation.generate_hypotheses (EXTENDED: one more prompt
  component, one more parsed field) → is_correction
→ ReasoningReplyPayload.is_correction (NEW field) → communication-engine
→ conversation_orchestration builds memory_annotations (NEW, ~5 lines)
→ deliver_content_to_session(memory_annotations=...) (EXISTING, unchanged)
→ apply_memory_annotations → ConversationMemory.corrections (EXISTING,
  unchanged, simply reached for the first time)
→ [session closes] → CommunicationSessionCompletedPayload (ENRICHED,
  Fork B) → digital-twin-engine consumes corrections list
→ correction-frequency = len(corrections) per session, accumulated per
  user over time, per Fork C's approved partial-metric scope
```

---

## 6. `CommunicationSessionCompletedPayload` enrichment (Fork B)

```python
class CommunicationSessionCompletedPayload(BaseModel):
    session_id: UUID
    user_id: UUID
    objective: str | None = None
    turn_count: int
    closed_at: datetime
    # New, additive (ADR-024), sourced from ConversationMemory:
    corrections: list[str] | None = None
    preferences: list[str] | None = None
    feedback: list[str] | None = None
    decisions: list[str] | None = None
    schema_version: int = 1
```

Populated in `session_lifecycle.py`'s existing close transition
(`session_lifecycle.py:235-236`) directly from the session's own, already-
loaded `ConversationMemory` — no new read required, the data is already in
hand at the point this event is constructed.

### 6.4 Memory Engine's subscription — confirmed, separate, non-blocking

Re-confirmed this pass: `services/memory-engine/src/nova_memory_engine/events/subscribed.py`'s
`SUBSCRIBABLE_SUBJECTS` does not include `communication.session.completed`.
Per Fork B's approval, this stays **explicitly out of Phase 2D-D's scope**
— digital-twin-engine subscribes directly to the enriched event and does
not depend on Memory Engine's wiring. Tracked separately, not absorbed.

---

## 7. API/RPC/event contracts — complete list

### 7.1 New engine: `digital-twin-engine`

- `GET /v1/digital-twin/profile` — Retrieve Profile (Communication Profile
  scope, Bible Part 16 "Digital Twin APIs", scoped per Master Blueprint §8).
- `PATCH /v1/digital-twin/profile` — Update Profile (user-initiated
  correction/override — Bible Part 16's "User Control": view/modify).
- `GET /v1/digital-twin/preferences` — Retrieve Preferences (mirrors the
  served RPC below, HTTP-accessible for a future dashboard).
- `POST /v1/digital-twin/reset` — Reset Domain (Bible Part 16's own-named
  user-control capability, scoped to this phase's two domains only).
- Serves `digital_twin.preferences.get.request`/`.reply` (already defined,
  §7.3).
- Publishes `personality.memory.update` (already defined, §7.3).
- Publishes a new `communication.intent.deliver.request` call (as a
  *client*, for Fork D's warm-case proactive delivery, §10) — reuses the
  existing subject, digital-twin-engine simply becomes a second caller of
  it (mirroring the closure document's own "another engine" framing).
- Subscribes to `communication.session.completed` (enriched, §6).

### 7.2 `communication-engine` additions

- New `DigitalTwinPort` Protocol (`domain/ports.py`), structurally
  identical to `PersonalityPort`:
  ```python
  class PreferenceSelection(BaseModel):
      conversation_pacing: str | None
      habit_timing_hint: str | None
      # Fork A: only fields personality-engine's StyleSelection does not
      # already cover.

  @runtime_checkable
  class DigitalTwinPort(Protocol):
      async def get_preferences(
          self, *, user_id: UUID, correlation_id: UUID | None = None
      ) -> PreferenceSelection | None: ...
  ```
  Implemented by new `clients/digital_twin_client.py`, mirroring
  `clients/personality_client.py` exactly.
- New `CommunicationRepository.get_last_outbound_turn()` (§5.2).
- `resolve_response_shaping()` extended to optionally call
  `digital_twin_port.get_preferences()` (Fork A, Option 3's field split —
  called only when pacing/timing data is actually consulted, e.g. by
  silence-policy logic, not on every single turn, preserving Master
  Blueprint §13.2's low-latency rule).
- `conversation_orchestration.py` extended per §5.5's complete path.
- A small `user_id → connected session_id` resolution capability for
  Fork D's warm-case delivery (§10.2) — the one genuinely new piece of
  communication-engine logic this phase adds to the delivery path itself.

### 7.3 `nova-contracts` changes — complete list

| Payload | Change | ADR-024 compliance |
|---|---|---|
| `ReasoningRequestPayload` | `+ prior_nova_utterance: str \| None = None` | Additive, optional, versioned |
| `ReasoningReplyPayload` | `+ is_correction: bool \| None = None` | Additive, optional, versioned |
| `CommunicationSessionCompletedPayload` | `+ corrections/preferences/feedback/decisions: list[str] \| None = None` | Additive, optional, versioned |
| `DigitalTwinPreferencesGetReplyPayload` | Unchanged this phase (its `preferences: dict[str, Any]` looseness is noted but not fixed here — not a blocker) | N/A |
| `PersonalityMemoryUpdatePayload` | Unchanged — already fits exactly | N/A |

No breaking changes. No existing consumer of any modified payload exists
today (all are either brand-new consumers this phase creates, or, for
`ReasoningReplyPayload`, the sole existing consumer is
`conversation_orchestration.py` itself, which this phase also modifies in
the same pass).

---

## 8. Personality preference integration (Fork A — exact field split)

| Field | Path | Owner of the value |
|---|---|---|
| `verbosity` | `personality.memory.update` (async, digital-twin publishes) → `personality-engine.MemoryProfile` → `personality.style.select` (existing, unchanged call) | `personality-engine` applies; digital-twin learns |
| `technical_depth` | Same path | Same |
| `terminology_preference` | Same path | Same |
| `conversation_pacing` | `digital_twin.preferences.get` (sync, direct RPC, new `DigitalTwinPort`) | `digital-twin-engine` only — `personality-engine` has no concept of pacing |
| habit-timing hints | Same direct RPC | Same |

This is the precise resolution of Fork A: no field is ever sourced from
both paths, eliminating the "undefined precedence on conflict" risk named
in the original research document's Fork A discussion.

---

## 9. Correction-frequency calculation (Fork C, incorporating Fork E)

```
correction_frequency(user_id, window) =
    sum(len(session.corrections) for session in
        completed_sessions(user_id, within=window))
    / count(completed_sessions(user_id, within=window))
```

A simple, explicitly-partial trust signal: average corrections per
completed session over a rolling window (exact window size — e.g. last 20
sessions, or last 30 days — is an implementation-time parameter, not an
architectural fork). Stored with the same evolution discipline as
Communication Profile (§8 of the prior revision's persistence section,
unchanged): append-only history, current resolved value, never overwritten
on one data point.

**Explicitly not computed this phase** (Fork C, unchanged from original
approval): clarification-question acceptance, proactive-suggestion
acceptance/dismissal. `digital-twin-engine`'s trust-metric API/schema
should reserve space for these (nullable columns, per Bible Part 16's own
"every stored element should indicate origin, purpose, confidence" —
applies to *absence* of a signal too) without computing them, so adding
them later is additive, not a migration.

---

## 10. Proactive suggestion policy — warm case (Fork D)

### 10.1 The policy itself (digital-twin-engine's own domain logic)

A pure function, no side effects: given a proposed proactive message
(content, topic tag) and the user's configured boundary policy
(frequency limit per topic, per time window; enabled/disabled), returns
allow/deny. This is the only genuinely new logic this feature needs —
everything downstream of "allowed" reuses existing infrastructure (§1.1).

### 10.2 Delivery — reusing existing infrastructure, not new plumbing

1. Digital-twin-engine's policy allows a proactive message for `user_id`.
2. Digital-twin-engine needs a `session_id` to target. **New, small
   capability**: communication-engine needs a way to answer "does this
   user have a currently-connected session, and if so, which one" — today,
   `SessionRegistry` is keyed by `session_id`, not `user_id` (matching its
   documented single-concurrent-session-per-instance scope, `session_registry.py:5-9`).
   The smallest addition consistent with that existing scope assumption:
   `SessionRegistry` gains a `user_id → session_id` lookup for currently-
   connected sessions only (not a general multi-session index — ADR-025's
   single-user-per-instance assumption, already relied on by Priority 2,
   makes "the one connected session, if any" a well-defined question).
   Exposed via a small new RPC or reused from an existing session-lookup
   surface — **implementation-time detail, not an architectural fork**,
   since there is exactly one sensible shape given the existing
   single-instance assumption already governing this codebase.
3. If a connected session is found: digital-twin-engine publishes
   `communication.intent.deliver.request` with that `session_id`
   (`requesting_engine="digital-twin-engine"`) — the **existing**,
   already-implemented, already-tested event/handler path
   (`make_intent_deliver_handler`), which already runs the message through
   personality validation (ADR-005 compliance, unchanged) and delivers
   through the live channel adapter.
4. If no connected session is found: **no delivery is attempted** — the
   suggestion is not queued, not retried, simply not deliverable this
   phase (§10.3).

### 10.3 Cold case — explicit limitation

No companion-client transport exists anywhere in this repository (the
same, already-disclosed gap from the 2D-C closure document's Priority 1/4
"cold case" — re-confirmed unchanged this session). A user with no
currently-connected session cannot receive a proactive message this phase,
under any design — this is a companion-client/transport gap, not a
digital-twin-engine or communication-engine limitation, and is not
proposed to be closed here. Documented, not fabricated around.

---

## 11. Persistence and repository changes

### 11.1 `digital-twin-engine` (new, own Postgres schema)

- `communication_profile` — current resolved values, one row per user.
- `preference_evolution_history` — append-only (Bible Part 16's "Digital
  Twin Memory": what changed, when, why, confidence, source).
- `habit_signal` — conversation-scoped interaction-timing observations.
- `trust_metric` — current correction-frequency value + its own history
  (nullable columns reserved for the two not-yet-computed inputs, §9).
- `proactive_boundary_policy` — user-configured limits.
- Own Alembic migration chain, `0001_initial_schema.py`, following every
  prior engine's exact convention.

### 11.2 `communication-engine` (no new schema — additive query only)

- `get_last_outbound_turn()` (§5.2) — reads the existing `conversation_turn`
  table with a new query shape (most-recent-outbound-by-session), no new
  columns, no migration.
- No new persisted field is required for `is_correction` beyond what
  `ConversationMemory.corrections` (existing column, `repository/models.py:48`)
  already stores.

### 11.3 `reasoning-engine` (no new schema)

`is_correction` is a reply-only, transient value — not itself persisted by
reasoning-engine (mirrors `confidence_score`'s own treatment: part of the
reply and the trace, not a new dedicated table).

### 11.4 `personality-engine` (no new schema)

`update_memory_profile` (already exists, already correct — Priority 6)
writes to the existing `memory_profile` table. No migration needed.

---

## 12. Failure and degraded-mode behavior

Extends §12 of the prior revision with Fork E's new integration points:

- **Reasoning-engine unreachable/times out when correction-judgment
  context is included**: identical to the existing, already-implemented
  fallback (`conversation_orchestration.py`'s existing `TimeoutError`
  handling) — `is_correction` simply absent from the reply; no
  `memory_annotations` entry is built; the turn still delivers normally.
  Never blocks delivery.
- **Model call inside `generate_hypotheses` fails**: existing
  `HypothesisGenerationError` handling (`pipeline.py`'s existing Failure
  Recovery step) applies unchanged — a failed hypothesis generation
  already degrades the whole reasoning process; `is_correction` is simply
  never computed for that turn, same as any other hypothesis-generation
  failure.
- **`get_last_outbound_turn()` returns `None`** (first turn of a session,
  no prior NOVA utterance exists yet): `prior_nova_utterance` stays
  `None`; reasoning-engine's prompt omits the `prior_response` component
  entirely; no correction judgment is even attempted — correctly, since
  there is nothing to correct yet.
- **Digital-twin-engine unreachable when `communication-engine` calls
  `digital_twin.preferences.get`**: identical `TimeoutError` → degraded-
  default pattern already established for `personality.style.select`
  (§12 of the prior revision, unchanged).
- **No connected session for a proactive message** (§10.2 step 4): no-op,
  not a retry loop, not an error — the same "no signal is better than a
  wrong one" discipline this codebase already applies elsewhere
  (perception-engine's own orchestration failure handling, closure doc §3.6).

---

## 13. Security and consent boundaries

Unchanged from the prior revision's §9, with one addition: the correction
signal is derived from content the user already sent and NOVA already
said — no new data collection, no new consent surface. It is a
*re-classification* of existing conversation content already stored in
`ConversationMemory` under the exact category scheme
(`decisions`/`preferences`/`corrections`/`feedback`) this project approved
in Phase 2D-C. Reasoning-engine already has access to `objective_text`
(the full turn content) for every request regardless of this feature —
adding `prior_nova_utterance` does not expose it to anything it couldn't
already see.

Bible Part 16's "User Control" (view/modify/delete/export/pause/reset)
remains a genuine scope item for `digital-twin-engine`'s own API (§7.1) —
unchanged from the prior revision's assessment that this is required, not
optional, given this is the first engine storing a model of the user's own
communication patterns.

---

## 14. Observability and decision traces

- Every new RPC (`digital_twin.preferences.get`,
  `reasoning.reason.request`'s widened payload) carries `correlation_id`
  end-to-end, per existing convention.
- **New `ConversationDecisionTrace.decision_type` value**: the existing
  `Literal["addressee_fusion", "interruption_recovery", "silence",
  "listening_activation"]` (`domain/models.py:180-182`) gains
  `"correction_detected"` — one row per `is_correction=True` verdict,
  recording the trace_id linking back to reasoning-engine's own
  `ReasoningTrace` (Doc 22's explainability principle: the user should be
  able to see why NOVA now treats them as having corrected it, not just
  that it does).
- Digital-twin-engine's own preference/trust-metric changes get their own
  append-only trace rows (§11.1's `preference_evolution_history`), per
  Bible Part 16's own explicit requirement.

---

## 15. Testing strategy

Two-tier convention unchanged (ADR-033).

**New unit/contract tests:**
- `hypothesis_generation.generate_hypotheses`'s extended prompt/parsing:
  verify the `prior_response` component is included only when
  `prior_nova_utterance` is supplied; verify `is_correction` parsing
  against fixed example model outputs covering **every excluded case from
  §5.1 explicitly** (uncertainty, disagreement, clarification request,
  self-correction) asserting each yields `is_correction=False`, plus at
  least one genuine-correction fixture asserting `True`.
- `conversation_orchestration.py`: `is_correction=True` produces the
  correct `memory_annotations` entry passed to `deliver_content_to_session`;
  `is_correction=False`/`None` produces none.
- `get_last_outbound_turn()`: returns `None` for a session with no prior
  outbound turn; returns the correct turn otherwise.
- `CommunicationSessionCompletedPayload` round-trip with the new fields
  (mirrors every existing `test_*_events.py` pattern).
- Digital-twin-engine's own domain logic: Preference Evolution's
  single-data-point-never-flips-a-preference discipline (already a named
  acceptance criterion in `ENGINEERING_ROADMAP.md`); correction-frequency
  calculation against fixture session data; proactive-boundary policy
  allow/deny logic.
- `FakeDigitalTwinPort`/`FakeReasoningPort` extensions in `nova-testkit`
  (the latter already exists per Priority 3 — gains `is_correction` to its
  fake's configurable response).

**New integration tests:**
- Full path: fake reasoning port configured to return `is_correction=True`
  → real turn-handling orchestration → real `ConversationMemory.corrections`
  populated → session close → enriched event payload carries it.
- Warm-case proactive delivery: a connected fake session + an allowed
  proactive suggestion → delivered through the real intent gate, personality-
  validated, same shape as every other intent-gate delivery test already in
  this codebase.
- Cold-case: no connected session → no delivery attempted, no error raised.

---

## 16. Real-infrastructure verification

`digital-twin-engine` needs its own `tests/integration/test_repository_real_postgres.py`
(new Alembic-migrated schema, real singleton/append-only constraints —
mirroring every prior engine's own real-Postgres test shape) and a new
entry in `.github/workflows/real-infra-checks.yml`'s matrix (currently 4
packages, becomes 5). Per this session's own Priority 6 experience, the
concrete standard is: **write these tests as part of the build, but do not
consider any part of this phase "done" until it has an actual green
execution on GitHub Actions** — not a lower bar than Priority 6 was just
held to.

No new real-infra tests are needed for `reasoning-engine`,
`communication-engine`, or `personality-engine`'s own changes beyond what
already exists — none of the additive fields change persistence behavior
those engines' existing real-Postgres suites already cover (schema is
unchanged for all three).

---

## 17. Migration / backward-compatibility considerations

- Every contract change (§7.3) is additive and optional — zero-downtime,
  no consumer breakage, per ADR-024, consistent with every prior contract
  change in this project.
- `digital-twin-engine`'s own schema is brand new — no migration-compatibility
  concern (nothing to migrate from).
- `communication-engine`'s new repository method is additive (a new query,
  not a schema change) — no migration.
- No coordinated same-release requirement exists this phase, unlike
  Priority 2's breaking `PerceptionAddresseeSignalCandidatePayload` change
  — every payload here stays backward-compatible on its own.

---

## 18. Explicit non-goals

Restated and extended from the prior revision's §2/§9.3, §3.2 boundary:

- The other nine Bible Part 16 domains (goals, projects, hardware,
  software, skills, knowledge, productivity, general workflow) — Phase 4.
- Clarification-question acceptance and proactive-suggestion
  acceptance/dismissal as trust-metric inputs — deferred, not fabricated
  (Fork C).
- Cold-case proactive delivery — blocked on a companion-client transport
  that doesn't exist anywhere in this repository (Fork D).
- Any heuristic inside communication-engine for inferring corrections from
  timing, rephrasing, or textual similarity — explicitly forbidden by
  instruction, not merely deprioritized.
- Wiring Memory Engine's own unwired `communication.session.completed`
  subscription — separate, tracked debt (Fork B).
- Any change to `PersonalContextClient`/`PersonalContextPort`
  (executive-cognition-engine's and reasoning-engine's existing "honest
  placeholder for the future Digital Twin Engine") — confirmed, on
  inspection, to model an entirely different data shape (goals, project_id,
  device, task — Phase 4's domains), not Communication Profile. Out of
  scope, not adjacent debt worth flagging further.
- Any autonomy-level or execution-trust capability — Phase 4,
  `autonomy-engine`.

---

## 19. Verification classification (per instruction)

| Behavior | Classification |
|---|---|
| `hypothesis_generation.py`'s existing model call mechanics | Fully verified (read directly, current session) |
| `deliver_content_to_session()`'s existing `memory_annotations` handling | Fully verified (read directly, current session) |
| `communication.intent.deliver.request`'s existing warm/cold handling | Fully verified (read directly, current session) |
| `StartListeningSignal`'s exact shape (referenced as precedent, not reused directly — see §10) | Fully verified (read directly, current session) |
| `ReasoningRequestPayload`/`ReasoningReplyPayload` current shape | Fully verified (read directly, current session) |
| Memory Engine's non-subscription to `communication.session.completed` | Fully verified (read directly, current session) |
| `is_correction` semantic distinction (§5.1) actually holding up against real model output | **Unverified until built and real-infra tested** — the definition is precise, but whether a real LLM reliably respects it is an empirical question §15's fixture tests exist to answer, not something this document can verify in advance |
| Fork A's field-split avoiding conflicting values in practice | Contract verified once built (no runtime data exists yet to contradict it) |
| Correction-frequency metric's usefulness as an actual trust signal | **Intentionally out of scope to verify** — this phase ships the mechanism per Bible Part 16's own "requires consistent evidence" discipline; whether the resulting metric is *good* is an empirical question for after real usage accumulates, not a Phase 2D-D acceptance criterion |
| Everything else in §15/§16's planned test suites | Will be fake/test-verified pre-implementation, fully verified once real-infra-tested (§16), exactly per every prior phase's own discipline |

---

## 20. Risks and mitigations

1. **The LLM-based correction judgment could be unreliable in practice**
   (over- or under-triggering). *Mitigation:* §15's fixture-based test
   suite covering every named exclusion explicitly; the metric is already
   scoped as partial and disclosed (Fork C), so a noisy signal degrades
   gracefully into "a somewhat noisy partial metric," not a false claim
   of precision.
2. **Widening `ReasoningRequestPayload`'s prompt with `prior_nova_utterance`
   could affect hypothesis-generation quality/latency for unrelated
   reasoning calls.** *Mitigation:* the field is optional and additive;
   non-communication-engine callers (a future Planning Engine, per that
   payload's own docstring) simply never populate it, and the prompt
   component is only appended when present.
3. **`digital-twin-engine` becomes a new synchronous failure point in the
   response pipeline** (Fork A's direct RPC). *Mitigation:* §12's
   degraded-mode fallback, identical in shape to every other synchronous
   dependency this codebase already has; called selectively (not on every
   turn), per Master Blueprint §13.2.
4. **Fork D's warm-case delivery, despite reusing existing infrastructure,
   is still a new *caller* of a path that has never had a real caller
   before** — latent bugs in `make_intent_deliver_handler` could surface
   for the first time. *Mitigation:* §15's integration tests exercise this
   path with real assertions, not just contract shape; this is exactly the
   kind of "genuinely new caller of old code" risk Priority 6 already
   demonstrated real value in catching (the two genuine bugs that pass
   found), so the same rigor is applied here before any claim of
   correctness.
5. **Scope crept to include `reasoning-engine`** (Fork E). *Mitigation:*
   already explicitly approved, narrowly scoped (one field in, one field
   out, one existing call extended), and documented here precisely so its
   boundary doesn't quietly widen further during implementation.

---

## 21. Implementation order (revised for Fork E)

1. **`nova-contracts` changes** (§7.3) — all four additive payload changes,
   in one pass, with their own contract round-trip tests.
2. **`reasoning-engine`**: extend `hypothesis_generation.py`'s prompt
   construction and output parsing (§5.3); thread `is_correction` through
   `pipeline.py` to the reply. Fully testable in isolation against fixture
   model outputs before any other component changes.
3. **`communication-engine`, correction-signal transport**:
   `get_last_outbound_turn()` (§5.2); `conversation_orchestration.py`
   passes `prior_nova_utterance` in, builds `memory_annotations` from
   `is_correction` on the way out (§5.4-5.5). Testable against a
   `FakeReasoningPort` before digital-twin-engine exists.
4. **`CommunicationSessionCompletedPayload` enrichment** (§6) —
   `session_lifecycle.py`'s one publish call site.
5. **`digital-twin-engine`'s domain layer** (Communication Profile,
   Preference Evolution, correction-frequency metric, proactive-boundary
   policy) — buildable and fully unit-testable against fakes, independent
   of steps 2-4 having real counterparts (uses `nova-testkit` fakes).
6. **`digital-twin-engine`'s scaffold** (repository/API/events/main.py,
   own outbox worker in `docker-compose.local.yml` from day one, per
   Priority 1's precedent) — mirrors `perception-engine`'s template.
7. **`personality-engine`'s new subscription** — small, independent, can
   happen any time after step 1.
8. **`communication-engine`'s `DigitalTwinPort`** (Fork A) — wired into
   `resolve_response_shaping()`.
9. **Fork D's warm-case delivery**: the `user_id → connected session_id`
   lookup (§10.2) + digital-twin-engine's own call to
   `communication.intent.deliver.request`.
10. **Real-infrastructure verification** (§16) — written alongside each
    step, confirmed on GitHub Actions before declaring the phase done.

**Rationale for reordering ahead of the prior revision's plan:** Fork E's
correction signal is now a genuine cross-engine dependency chain
(reasoning → communication → eventual digital-twin consumption), so it
moves earlier, before digital-twin-engine itself, so that by the time
digital-twin-engine's own domain layer is built, the evidence it will
consume is already flowing and independently tested — not built against a
hypothetical shape.

---

## 22. Expected files/components affected (complete list)

**New:**
- `services/digital-twin-engine/` (full engine, mirroring `perception-engine`'s
  file layout — `api/`, `clients/`, `config.py`, `domain/`, `events/`,
  `main.py`, `observability.py`, `repository/`, `workers/`, `tests/`,
  `alembic/`, `Dockerfile`, `pyproject.toml`, `README.md`).
- `packages/nova-testkit/src/nova_testkit/`: `FakeDigitalTwinPort` (and
  `FakeReasoningPort` extension for `is_correction`).

**Modified:**
- `packages/nova-contracts/src/nova_contracts/events/reasoning.py` (2 new
  fields).
- `packages/nova-contracts/src/nova_contracts/events/communication.py`
  (4 new fields).
- `services/reasoning-engine/src/nova_reasoning_engine/domain/hypothesis_generation.py`,
  `domain/pipeline.py`, `domain/models.py` (new field on internal request/
  result types).
- `services/communication-engine/src/nova_communication_engine/domain/ports.py`
  (`DigitalTwinPort`, `ReasoningOutcomeResult.is_correction`,
  `CommunicationRepository.get_last_outbound_turn`), `domain/models.py`
  (`ConversationDecisionTrace.decision_type` new literal value),
  `domain/response_shaping.py` (Fork A wiring), `conversation_orchestration.py`
  (§5.5), `session_lifecycle.py` (§6), `clients/digital_twin_client.py` (new),
  `session_registry.py` (§10.2's lookup), `repository/postgres_communication_repository.py`
  (new query implementation).
- `services/personality-engine/src/nova_personality_engine/events/subscribed.py`,
  `events/handlers.py` (new subscription).
- `infra/docker/docker-compose.local.yml` (new `digital-twin-engine` +
  `digital-twin-engine-worker` services).
- `.github/workflows/real-infra-checks.yml` (new matrix entry).
- `docs/roadmap/ENGINEERING_ROADMAP.md` (Phase 2D-D status line, once
  implemented — not part of this design pass).

**Not modified:** every other engine and package in the monorepo.

---

## 23. What this document is not

This TDD specifies exact contract fields, exact integration points, and
exact call chains, but does not specify Alembic column-level types, exact
FastAPI request/response model field names, or exact prompt wording for
reasoning-engine's extended instruction — that remains implementation-time
detail within the boundaries this document sets. No implementation begins
until the user reviews this document and gives explicit approval.
