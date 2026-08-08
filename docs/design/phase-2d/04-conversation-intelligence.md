# Phase 2D-C Technical Design — 04: Conversation Intelligence

Implements [Bible Part 13](../../bible/part-13-communication-engine.md)'s
behavioral/policy layer — Adaptive Communication, Response Planning, the
Clarification Engine, Communication Styles, Multi Language Support,
Interruption Management, and the "talking TO vs. talking ABOUT NOVA"
addressee-detection boundary — on top of Phase 2D-A's transport
(`01-communication-engine.md`) and consuming Phase 2D-B's signals
(`03-perception-engine.md`), per the
[Phase 2D Master Architectural Blueprint](00-master-blueprint.md) §4.3,
governed throughout by
[Doc 22 — NOVA Human Interaction Principles](../../architecture/22-nova-human-interaction-principles.md)
and [Doc 23 — NOVA Personality Specification](../../architecture/23-nova-personality-specification.md)
(§21 maps every major decision below against both, plus every applicable ADR).

**Status: Approved and implemented (Option B, per §0.4).** See the
[Phase 2D-C Gate Review](../../roadmap/architecture-reviews/phase-2d-c-gate-review.md)
for the full implementation record, including the explicit breakdown of
what is fully verified, what is verified only through contract-level
fakes, and what remains genuinely unverified end-to-end pending
`perception-engine`'s still-unwired production signal chain. This document
was produced only after a
full verification pass of `communication-engine`, `personality-engine`,
`perception-engine`, `world-model-engine`, and all applicable ADRs/Bible
sections against their **actual current code**, per the standing rule
established this session: *verify the implementation before trusting the
documentation*. §0.5 and §0.6 disclose two required, additive cross-engine
extensions found this way; §0.4 discloses one genuine architectural fork with
no single correct answer, presented for decision rather than resolved
silently. **No production code has been modified to produce this document.**

## 0. The boundary this document defends

### 0.1 Scope: the judgment layer, not a new engine

Per the Master Blueprint §4.3, Phase 2D-C **extends** `communication-engine`
— it is not a new service, has no new `services/` directory, and inherits
every architectural commitment `01-communication-engine.md` already made
(the `communication.intent` gate as the sole path to the user, ADR-005; the
ten-state `ConversationSession` machine; "this engine never generates
content itself," §0.2/§6 of that document). Phase 2D-C's own job, stated in
the user's own framing that the Master Blueprint quotes verbatim: **it
defines HOW NOVA communicates, not WHAT it knows.** Concretely, it makes real
the two lifecycle steps 2D-A deliberately left as pass-through (§6 of
`01-communication-engine.md`: "Determine Intent," "Select Communication
Strategy") and adds one new capability those steps never had a signal for —
addressee detection — because that signal (Perception's) did not exist until
2D-B shipped.

### 0.2 The addressee-detection split — verified against actual code, not just prose

Master Blueprint §5 draws the split precisely: **2D-B observes and publishes
signals, never decides; 2D-C fuses the signals and decides.** Both halves
were independently verified this session:

- **2D-B's half is real, but incompletely wired (see §0.4 — this is the
  fork).** `perception-engine`'s `events/publishers.py::addressee_signal_candidate()`
  exists and is correctly shaped — a genuine "never fuses" implementation,
  carrying `wake_word_matched: bool`, `wake_word_confidence: float`,
  `identity_id: str | None`, `identity_confidence: float`,
  `gaze_direction: str`, `session_active: bool`, `schema_version: int` — but
  it is called only by its own unit test. No orchestration module anywhere
  in `perception-engine`'s production code (sensors → `identity_fusion.
  fuse_window`/`smooth` → these publishers → the outbox) exists yet. This is
  a materially different finding than "the signal shape might need
  revision" (which Phase 2D-B's own Gate Review Recommendation 3
  anticipated) — the shape is sound; nothing produces it in production.
- **2D-A's half genuinely has zero addressee logic to conflict with.**
  Confirmed by exhaustive grep: every hit for "addressee"/"wake" in
  `communication-engine`'s codebase is a docstring *disclaiming* the
  capability, never implementing it. The only existing per-utterance gating
  mechanism is `domain/models.py::InboundMessageKind` — client-side
  `TRIGGER_START`/`TRIGGER_STOP` control frames (voice) and unconditional
  `TEXT` handling (text) — exactly the "honest explicit-trigger interim"
  `01-communication-engine.md` §0.4 describes, with no hidden partial
  implementation anywhere.

Doc 22 Principle 6 is the binding requirement this split exists to satisfy:
"Saying NOVA's name in a sentence... is never, by itself, sufficient
justification for NOVA to respond. Addressee detection is a contextual
judgment... not a keyword match." §4 below is this document's fusion design.

### 0.3 What 2D-C is not: a rewrite of anything already built

Nothing in this document proposes changing `communication-engine`'s state
machine transition table, `ConversationSession`'s existing fields, the
intent gate's three-step structure, the Transport VAD, or barge-in mechanics
— all confirmed working exactly as `01-communication-engine.md` describes
and as `phase-2d-a-gate-review.md` verified (70 tests, 65% total coverage —
the domain layer itself is documented separately as ~99% in the Project
Health Review, the low total figure being real-infra-only code, not domain
logic). Every addition below is either a new domain module alongside the
existing seven (`state_machine.py`, `vad.py`, `chunking.py`, `intent_gate.
py`, `speech.py`, `session_lifecycle.py`, `ports.py`), or a small, additive
field on an existing schema/payload that was already reserved for exactly
this purpose (`pending_questions` on `ConversationSession`, the `CLARIFICATION`
event's placeholder comment in `state_machine.py`, `channel`'s currently-inert
parameter on `personality.style.select`).

### 0.4 OPEN ARCHITECTURAL FORK — perception-engine's missing production wiring

**This is presented as a decision for the user, not resolved in this
document.** Two independently valid paths exist, with real tradeoffs on
both sides; per direct instruction, this document does not choose silently.

**The finding.** `perception-engine` was Gate-Reviewed **Go** for Phase 2D-B.
Its identity-fusion math (`domain/identity_fusion.py`) is real and
unit-tested; its sensors (`sensors/voice_sensor.py`, `sensors/camera_sensor.
py`) implement real detection logic against an already-captured audio/video
window. But no code path in the running system ever calls the chain sensors
→ `identity_fusion.fuse_window`/`smooth` → `events/publishers.py`'s
functions → the outbox. `perception.addressee_signal.candidate` — the exact
event this document's fusion algorithm (§4) is designed to consume — has
**never been exercised end-to-end**, confirmed independently by both this
session's code audit and Phase 2D-B's own Gate Review §4 ("No live
audio/camera capture client exists anywhere in this project yet").

**Why this matters specifically for Phase 2D-C, not just as a perception-engine
footnote:** this document's addressee-fusion design (§4) can be fully
specified, implemented, and unit/contract-tested against the *published
contract* today (using a fake signal source, per this project's established
two-tier testing convention, ADR-033) — but it cannot be verified
**end-to-end against real perception-engine behavior** until that
production wiring exists. Depending on which option below is chosen, that
gap is either closed before 2D-C's own implementation begins, or carried
forward as an explicitly tracked open item exactly like the real-Postgres
verification recommendation this project has already carried open across
three consecutive Gate Reviews without blocking any of them.

**Option A — Close the gap first, as a disclosed 2D-C prerequisite.**
Before this TDD's own implementation begins, land a small, separately
reviewable patch to `perception-engine` (already-approved, Phase 2D-B) that
wires its existing, already-tested sensor and fusion functions into a real
orchestration path (a worker or event-driven pipeline calling `fuse_window`/
`smooth` on a cadence or per-observation-window, then calling the publisher
functions and enqueuing to the outbox) — mirroring this project's own
STEP 3 precedent, where a prerequisite fix to already-shipped code
(`memory-engine`'s repository-port cutover) was scoped, reviewed, and
merged as its own explicit step *before* the extraction wave that depended
on it. **Tradeoff:** reopens an engine whose Gate Review already said "Go";
delays 2D-C's own start; but produces a genuinely complete, testable
addressee-detection stack before 2D-C ships.

**Option B — Proceed against the contract; track the wiring gap separately.**
Design, implement, and verify 2D-C's own fusion logic (§4) entirely against
`perception.addressee_signal.candidate`'s documented shape, using a
`FakePerceptionSignalSource` (nova-testkit, mirroring the existing
`FakeModelGateway` pattern from STEP 2) for all contract/unit tests. Open a
tracked, non-blocking item for perception-engine's missing production
wiring — consistent with how this project already carries the real-Postgres
verification recommendation open, unresolved, across three Gate Reviews
without treating it as a blocker. **Tradeoff:** 2D-C ships and gate-reviews
cleanly on schedule, fully verified against the contract; but nobody can
observe real end-to-end addressee detection working until the separate item
closes, and there is a real (if likely small) risk the live wiring surfaces
a genuine shape problem Gate Review Recommendation 3 already flagged as
possible.

**This document's recommendation, offered but not assumed:** Option B. It
keeps engine ownership clean (perception-engine's internals stay
perception-engine's to fix, the same strict-boundary discipline enforced
everywhere else in this project), uses a testing pattern already proven
twice in this codebase, and treats the gap with exactly the same honesty
this project already affords the real-Postgres item — carried open,
disclosed at every relevant Gate Review, never hidden. **This document does
not proceed as if that choice has been made** — §22 (testing strategy) and
§20 (prerequisites) both describe the consequence of each option explicitly,
and implementation does not begin until the user picks one.

### 0.5 Required cross-engine extension #1 — World Model's `present_identities` cannot reach a synchronous caller today

Verified, not assumed: `world-model-engine`'s `ActiveContext` domain model
already has a `present_identities: list[PresentIdentitySignal]` field (built
per task #96, this project's own history), and two event-driven write paths
correctly populate it from `perception.presence.observed`/`perception.
identity.observed`. But **neither read path a synchronous caller can use
today actually returns it**:

- `ContextReplyPayload` (the `world_model.context.request`/`.reply` RPC —
  the exact mechanism `communication-engine`'s own `WorldModelClient`
  already uses, once per session creation, per `01-communication-engine.md`
  §8.7) has no `present_identities` field. The RPC handler in
  `world-model-engine/main.py` builds the reply manually and cannot include
  data its own payload class has no slot for.
- `GET /v1/world/context?scope=...` (the REST path) **does** include
  `present_identities` when `scope` is omitted — but every named agent
  scope in `_AGENT_SCOPE_FIELDS` (`domain/context.py`), **including the
  design doc's own worked example, `"communication-engine"`**, omits it.
  Only an unscoped call carries it, and an unscoped call is not what any
  existing per-agent integration uses.

**Why this blocks §4's fusion design as written:** low-latency addressee
fusion needs World Model's already-cached "who's present" snapshot exactly
the way ADR-012 intends it to be consumed (a fast, synchronous read of
already-fused state, not a fresh computation) — not a REST round-trip
outside the Event-Bus RPC pattern every other cross-engine read in this
codebase uses.

**Required fix, small and additive, mirroring `01-communication-engine.md`
§0.3's own precedent** (a disclosed, necessary extension to an
already-built engine, landed before the dependent engine's pipeline uses
it): add `present_identities: list[PresentIdentityPayload]` to
`ContextReplyPayload` (mirroring the field `ContextChangedPayload` already
has) and add `present_identities` to `_AGENT_SCOPE_FIELDS["communication-engine"]`
so the scoped REST path also carries it. Both changes are additive
(`present_identities` defaults to `[]`), touch no other consumer of
`ContextReplyPayload`, and require no schema/migration change — `ActiveContext`
already has the field; only the two read paths need to expose it. This
extension belongs to `world-model-engine`, not `communication-engine` —
scoped, reviewed, and merged as its own small prerequisite change, the same
way 2D-A's AI-Orchestration speech-modality extension was.

### 0.6 Required cross-engine extension #2 — `perception.*` payloads are unregistered raw dicts

Verified: every one of `perception-engine`'s 7 published subjects
(`perception.presence.observed`, `.identity.observed`, `.attention.
observed`, `.wake.detected`, `.addressee_signal.candidate`, `.consent.
changed`, `.sensor.health_changed`) is built by a plain-dict-returning
function in `events/publishers.py`, not a registered `nova_contracts`
Pydantic class — confirmed by that module's own docstring ("registering them
formally in `nova_contracts.events.perception`... tracked as a near-term
follow-up") and independently by Phase 2D-B's own Gate Review §18/§19
Recommendation 4. This is a real gap against ADR-024 ("every public
interface is versioned from the beginning") — every other cross-engine event
in this codebase, without exception, is a registered `nova_contracts`
class.

**Required fix:** land `packages/nova-contracts/src/nova_contracts/events/
perception.py`, formally registering all 7 payload shapes exactly as
currently implemented (no field changes — this is a registration, not a
redesign), before `communication-engine`'s new consumer code (§4, §10)
subscribes to any of them. This is small, mechanical, and precedented by
every other engine's own contracts module — it is explicitly named as a
prerequisite, not bundled silently into this document's own event-contract
section, because it is `perception-engine`'s (and `nova-contracts`') file to
change, not `communication-engine`'s.

### 0.7 Required cross-engine extension #3 — response-shaping hints must reach content generation, one level upstream of this engine

`communication-engine` never generates content (§0.2 above) — Reasoning
Engine does, via `ai-model-orchestration-engine`'s `generate` RPC, triggered
by subscribing to `communication.turn.received` (already published today).
Two of this document's own responsibilities — English-first response policy
(§8) and response-length/technical-depth adaptation (§7) — are decisions
about content that has not been generated yet, which this engine, by its
own hard architectural rule, may never generate itself. The only compliant
mechanism is to attach the resolved policy as **additive data on an event
`communication-engine` already owns and publishes**, for Reasoning Engine to
read and honor when it constructs its own generation request.

**Scope boundary, stated honestly:** this document specifies the
`communication-engine`-side half in full (§7, §8, §10) — computing and
publishing a `ResponseShapingDirective` (style, verbosity, technical_depth,
`response_language: "en"`) alongside `communication.turn.received`. It does
**not** specify Reasoning Engine's own consumption of it, because this
session's research did not include a verified read of Reasoning Engine's
content-generation/prompt-construction code — asserting exact mechanics
there without that verification would violate this document's own standing
rule. **This is named as a required cross-engine extension whose Reasoning-Engine-side
mechanism must be verified against that engine's actual code before
implementation**, not specified here from documentation alone (§20).

### 0.8 Conversation Memory extends the existing Postgres schema — not a new Redis store

A real question, resolved here with a citable answer rather than left
implicit: Bible Part 13's Conversation Memory (objective, questions,
decisions, preferences, corrections, feedback) is explicitly "session-scoped."
ADR-012 ("Redis as primary store, not cache") could be read as mandating
Redis for anything session-scoped. It does not apply here, and the
distinction is worth stating precisely: ADR-012 governs *derived,
cheap-to-rebuild current-state snapshots* (World Model's Active Context,
rebuildable from underlying facts/events). `communication-engine`'s own
`ConversationSession` already made, and justified, the opposite choice for
its own session record — synchronous Postgres writes on every transition,
specifically *because* "Conversation state should survive restarts" is "a
correctness requirement, not a performance-optimization target"
(`01-communication-engine.md` §3.5). Conversation Memory is an *extension of
that same durable record*, not a new kind of state — losing a user's
corrections or stated preferences mid-session to a Redis eviction or
restart would be a real data-loss bug, not an acceptable cache miss.
**Decision:** Conversation Memory's structured fields are added to the
existing `communication.conversation_session`/`communication.conversation_turn`
tables (§9, §14), written with the same synchronous-on-transition discipline
already established, not a new Redis-backed store.

### 0.9 Emotional-cue detection: a rule-based heuristic this phase, not ML sentiment classification

Doc 23 §4.6 (Empathy) requires NOVA to recognize emotional cues (frustration,
confusion, urgency, fatigue) and adapt pacing/directness accordingly, while
never claiming to *feel* anything (the `fabricated_shared_feeling` hard-stop
`personality-engine`'s validator already enforces). Building a genuine
ML-based sentiment/emotion classifier would require a new `ai-model-orchestration-engine`
modality (mirroring the STT/TTS precedent, `01-communication-engine.md`
§0.3) — a materially larger, undisclosed capability this phase's "quality
over feature count" principle (Master Blueprint §13.7) argues against
adding implicitly. **Decision, scoped honestly rather than overclaimed
(Doc 23 §6):** this phase derives an emotional-cue *hint* from signals
already available in this engine's own domain — rapid successive
corrections or repeated clarifying questions from the user → `"frustration"`;
short, high-tempo turns with explicit urgency markers → `"urgency"`; a long
gap or an explicit pause request → `"fatigue"` — passed as `situation_hint`
to the already-existing `personality.style.select` RPC (§7). Full ML-based
emotion classification is named here as an explicit, deferred future
capability (consistent with `personality-engine`'s own design doc §5/§17,
which already anticipates "adaptive style selection... tone-matching the
user's own emotional state" as 2D-C+ scope), not silently implied as already
built.

### 0.10 Relationship to `digital-twin-engine`: deferred exactly as 2D-A deferred it — not called this phase either

`digital-twin-engine` does not exist (`services/` confirmed, no
directory). `nova_contracts.DigitalTwinPreferencesGetRequestPayload`/`ReplyPayload`
already exist, forward-declared, unused — exactly the state
`01-communication-engine.md` §0.6 left them in. Calling an RPC nothing
serves would either hang until timeout on every single turn (a direct
violation of Master Blueprint §13.2's "low latency is part of NOVA's
personality" tie-break rule) or require a synthetic always-fail fast-path
that provides no real value yet. **Decision, matching 2D-A's own precedent
exactly:** this document defines the `DigitalTwinPreferencesGetRequestPayload`-consuming
port in code (§7's `ResponseShapingDirective` resolver has an explicit,
named extension point for it) but **does not call it this phase** —
`personality-engine`'s existing static-default Personality Memory
(`verbosity`, `technical_depth`) is the sole preference source until Phase
2D-D ships and this port is switched from skipped to called, a one-line
change at that point, not a redesign.

## 1. Overall architecture

```
                    ┌───────────────────────────────────────────────────────┐
                    │           communication-engine (extended)              │
                    │                                                        │
  perception.* ────▶│  Addressee Fusion (§4) ◀── perception.addressee_signal  │
  events (2D-B)      │       │                    .candidate, World Model     │
                    │       │                    present_identities (§0.5)    │
                    │       ▼                                                │
                    │  [existing 2D-A pipeline: Transport VAD → Session       │
                    │   Manager → Lifecycle Pipeline]                        │
                    │       │                                                │
                    │       ▼                                                │
                    │  Determine Intent (real, §4, §6) ── Select Strategy     │
                    │  (real, §7, §8) ── Silence/Interruption Policy (§5)     │
                    │       │                                                │
                    │       ▼                                                │
                    │  communication.turn.received  ─────────────────────────┼──▶ Reasoning Engine
                    │  + ResponseShapingDirective (§0.7, §10)                │    (content generation,
                    │                                                        │     unchanged path)
                    │  [existing 2D-A: communication.intent gate,            │
                    │   Personality validate/style RPC, Generate/Deliver]     │
                    │       │                                                │
                    │       ▼                                                │
                    │  Conversation Memory (§9, extends existing schema) ────┼──▶ Memory Engine
                    │  Clarification Engine (§6) ── pending_questions         │    (session archival,
                    │                                                        │     unchanged path)
                    └───────────────────────────────────────────────────────┘
```

Everything inside the dashed extension is new; everything labeled
"[existing 2D-A ...]" is unmodified, cited by reference to
`01-communication-engine.md`.

## 2. Responsibilities and boundaries

| Layer | Owns (this document) | Consumes, never owns | Never does |
|---|---|---|---|
| Addressee Fusion (§4) | The fusion algorithm, confidence scoring, threshold config | `perception.addressee_signal.candidate` (2D-B, raw signal), World Model `present_identities` (2D-B→1, cached snapshot) | Sensing (2D-B's job); privileged-action authorization (ADR-032 — see §16) |
| Silence/Interruption Policy (§5) | Interruption-recovery state, do-not-disturb config, notification-priority gating | Session state (existing), World Model activity (existing `WorldModelSnapshot`) | Desktop/activity sensing (Phase 4, out of scope) |
| Clarification Engine (§6) | `pending_questions` lifecycle, templated clarifying utterances | Addressee-fusion's uncertain-band output | Generating novel clarifying text (communication-engine never generates content) |
| Response Shaping (§7, §8) | `ResponseShapingDirective` computation and publication | `personality.style.select` (existing RPC), `digital_twin.preferences.get` (deferred, §0.10) | Applying the directive to generated text (Reasoning Engine's job, once extended per §0.7) |
| Conversation Memory (§9) | Structured decision/preference/correction/feedback fields on the existing session schema | Turn content (existing) | Long-term retrieval, semantic search (Memory Engine's job, unchanged §8.6 of `01-communication-engine.md`) |

Contrast against the other three sub-phases, restated from the Master
Blueprint's own data-ownership matrix (§7) and unchanged by this document:
`perception-engine` owns sensing and the Identity Registry, never decision
logic; `personality-engine` owns identity/values/style rules, never
conversation content or identity/presence data; `digital-twin-engine`
(2D-D, not yet built) will own long-term preference *evidence* and
learning, never the resolved value `personality-engine` applies (ADR-030).
2D-C introduces no new data-ownership row — it is entirely inside
`communication-engine`'s existing row.

## 3. Data model — additive fields only

### 3.1 `ConversationSession` — additive fields

| Field | Type | Notes |
|---|---|---|
| `pending_questions` | `list[str] \| None` | **Already exists** (`01-communication-engine.md` §3.2), unused until now — the Clarification Engine (§6) is its first real writer. |
| `conversation_memory` | `JSONB`, structured | New. `{objective, questions: list[str], decisions: list[str], preferences: list[str], corrections: list[str], feedback: list[str]}` — Bible Part 13's exact Conversation Memory list (§0.8's decision). `objective` already exists as its own top-level column (`01-communication-engine.md` §3.2); the new JSONB column carries the other five categories additively rather than duplicating `objective`. |
| `interrupted_content` | `TEXT \| None` | New. Set when a barge-in (2D-A, mechanical) discards in-flight content; cleared once resumed or explicitly dropped (§5.1). |
| `dnd_override` | `BOOLEAN DEFAULT false` | New. User-set do-not-disturb toggle (§5.2) — the one activity signal available this phase without desktop sensing. |

### 3.2 New domain model: `ConversationDecisionTrace`

One row per addressee-fusion or silence/interruption decision — the
observability/explainability mechanism (§15), modeled directly on Phase
2C's `ExecutiveDecisionTrace` precedent (same discipline: structured
metadata *about* a decision, never the content decided about):

```python
class ConversationDecisionTrace(BaseModel):
    id: UUID
    session_id: UUID | None            # None for pre-session addressee checks
    decision_type: Literal["addressee_fusion", "interruption_recovery", "silence"]
    inputs: dict[str, Any]             # every signal consumed, verbatim
    confidence: float | None
    confidence_tier: Literal["high", "medium", "low", "unknown"] | None
    outcome: str                       # e.g. "activated", "silent", "clarify", "resumed"
    reason: str
    created_at: datetime
    schema_version: int = 1
```

### 3.3 Persistence

Per §0.8: written synchronously to Postgres alongside the existing
`conversation_session`/`conversation_turn` writes, same "correctness
requirement, not a performance target" discipline as `01-communication-engine.md`
§3.5. `ConversationDecisionTrace` gets its own table
(`communication.conversation_decision_trace`) — high write volume (one row
per candidate signal window, not per turn) argues against bloating the
session row itself, and its own restart-recovery story is simpler: traces
are an append-only log, never mutated, so no recovery logic beyond normal
crash-safe inserts is needed (unlike `ConversationSession`, which has real
in-flight-transition recovery semantics already built).

## 4. Addressee-detection fusion

**Scope:** voice channel only. Text has no addressee ambiguity — a message
arriving inside an already-authenticated session's WebSocket is
unambiguously address to NOVA by construction of the channel itself; this
matches `01-communication-engine.md` §6's own existing (unchanged) handling
of `InboundMessageKind.TEXT`.

**Inputs** (per §0.4/§0.6, consumed once perception-engine's event is
registered and, depending on §0.4's resolution, either fake- or
real-sourced):

- `perception.addressee_signal.candidate`: `wake_word_matched`,
  `wake_word_confidence`, `identity_id`, `identity_confidence`,
  `gaze_direction` (`toward_device`/`away`/`unknown`), `session_active`.
- World Model `present_identities` (§0.5, once exposed): corroborating
  identity signal, independent of the direct perception event (a second,
  independently-sourced confirmation, not a duplicate read of the same
  fact — World Model's copy is the *fused, smoothed* cross-session view;
  Perception's own event is the *instantaneous* candidate).
- This engine's own conversation state: whether a session is already
  `LISTENING`/`THINKING`/`SPEAKING` with this identity (redundant with, but
  independently computed from, `session_active` — a deliberate
  cross-check, not a duplicate signal, since `session_active` comes from
  Perception's own `SessionActivityTracker`, sourced from
  `communication.session.*` events, while this check reads
  `communication-engine`'s own live state directly).

**Scoring — a deterministic weighted rule, not ML, matching this project's
established pattern for exactly this kind of decision** (`personality-engine`'s
style selector is a "deterministic rule table," explicitly deferring ML to
a later phase; the same discipline applies here for the same reason —
inspectable, testable, no training data or model-serving dependency this
phase):

```
score = (0.35 × wake_word_confidence if wake_word_matched else 0)
      + (0.30 × identity_confidence if identity_id is not None else 0)
      + (0.20 if gaze_direction == "toward_device" else 0)
      + (0.15 if session_active else 0)
```

Weights are a named, user-configurable structural setting (Master Blueprint
Risk §11.2's required "user-configurable sensitivity from day one"), not a
hardcoded constant — exposed as engine configuration, defaulted to the
values above. **Asymmetric threshold, per Doc 22 Principle 6 ("a
false-positive response... is treated as strictly worse than a
false-negative"):** `HIGH` (auto-activate) requires `score ≥ 0.70`; `LOW`
(stay silent) is `score < 0.35`; the band between is `UNCERTAIN`.

**Outcomes, per Master Blueprint §5 item 4 ("ambiguous cases resolve toward
clarification, not silence or response"):**

| Score band | Action | `ConversationDecisionTrace.outcome` |
|---|---|---|
| `HIGH` (≥0.70) | Feed `TRIGGER` into the existing state machine (`IDLE`→`LISTENING`), identical to today's explicit-trigger path | `"activated"` |
| `UNCERTAIN` (0.35–0.70) | Emit one of a small fixed set of low-cost audio check-in cues (§6.2) — never a generated question | `"clarify"` |
| `LOW` (<0.35) | No action. Recorded per Doc 22 Principle 2 ("silence... a first-class outcome") | `"silent"` |

The client-side explicit trigger (`TRIGGER_START`/`TRIGGER_STOP`) **remains
available unconditionally, alongside fusion, never replaced by it** — per
Doc 22 Principle 5 ("wake-word detection is one signal... never the only
signal a future design is allowed to depend on") and as an explicit
accessibility/privacy fallback path.

## 5. Silence & interruption policy

### 5.1 Interruption recovery (Bible Part 13's "Interruption Management")

2D-A's barge-in (`01-communication-engine.md` §4) is unconditional and
mechanical — it stops audio immediately, with no policy judgment, by design
(Master Blueprint §13.4). What it does not do, and what "no information
should be lost" (Bible Part 13) requires: preserving the *interrupted*
content so the conversation can return to it. On barge-in, this engine
writes the discarded response content to `ConversationSession.interrupted_content`
(§3.1) rather than dropping it. Once the new turn (the interruption itself)
completes and the session returns to `WAITING`, if `interrupted_content` is
still set, `communication-engine` may offer to resume it ("you were asking
about X before — want me to continue?") — itself a templated utterance
(§6.2's mechanism, reused), never fabricated content.

### 5.2 Do-not-disturb / notification gating

Bible Part 13's "Communication Policies" ("never interrupt while gaming,"
"silence notifications during meetings") require activity signals this
phase genuinely does not have — desktop/activity sensing is explicitly
Phase 4 (`nova-companion`, Master Blueprint §3.2). Honestly scoped for this
phase (Doc 23 §6): the **mechanism** ships now — a policy engine keyed on
`ConversationSession.dnd_override` (§3.1, user-set) and existing session
state (an active session already suppresses competing proactive
notifications, since `01-communication-engine.md`'s notification model
already queues rather than interrupts) — with named, explicit extension
points for activity-specific triggers (`gaming`, `meeting`) to be wired
once Phase 4's sensing exists, not faked now.

### 5.3 Proactive-interruption cost (Doc 22 Principle 4)

The full cost-benefit calculus this principle describes — weighing task
importance, focus depth, and recency of NOVA's last unprompted utterance —
is primarily **2D-D's `digital-twin-engine` "proactive-communication
boundary policy"** (Master Blueprint §4.4), since it needs the
trust/interaction-habit history 2D-D is scoped to build. 2D-C ships the
**mechanism** this policy will configure: every candidate proactive
utterance (a `communication.intent.deliver.request` with no corresponding
recent inbound turn) is queued through the same `dnd_override`/session-active
gate as §5.2, with `NotificationPriority` (already an existing field) as
the one signal this phase has to rank queued items — not a full cost model,
an honest partial mechanism 2D-D extends.

## 6. Clarification Engine

**Scope, stated explicitly rather than left to infer:** this phase's
Clarification Engine addresses **addressee ambiguity only** (§4's
`UNCERTAIN` band) — not general content-level ambiguity in what the user is
asking for, which would require Reasoning Engine to signal "I need more
information," a capability this session's research did not verify exists
and which is not named in this phase's scope by the Master Blueprint. This
is a deliberate, disclosed scope cut (Master Blueprint §13.7, quality over
feature count), not an oversight.

### 6.1 Mechanism

`communication-engine` never generates content (§0.2) — the Clarification
Engine therefore never composes novel question text. It selects from a
small, fixed, versioned template set, parameterized only by what's already
structured data (never by inserting arbitrary user-derived text into a
generated sentence):

- Addressee-uncertain check-in (§4's `UNCERTAIN` outcome): a short audio
  cue or minimal verbal prompt (e.g., a rising tone, or "Yes?") — the
  lowest-cost possible acknowledgment, matching Bible Part 13's own
  requirement ("questions should minimize interruption... reduce
  ambiguity").
- Interruption-resume offer (§5.1): one fixed template,
  `"{objective} — want me to continue?"`, `{objective}` sourced from the
  existing `ConversationSession.objective` field, never freely generated.

### 6.2 State machine integration

`pending_questions` (already reserved, §3.1) is populated with the pending
clarification; the session transitions `THINKING → WAITING` via the
already-reserved-but-unwired `CLARIFICATION` event
(`state_machine.py`'s own docstring names this exact gap — see §0.3). No
new state is added; this activates a transition the state machine already
declares but has never exercised.

## 7. Response-length, technical-depth, and tone selection

Computed once per inbound turn, published as `ResponseShapingDirective`
(§0.7, §10) alongside `communication.turn.received`:

1. Call `personality.style.select` (existing RPC) with `situation_hint`
   derived from §0.9's rule-based emotional-cue heuristic plus session
   context (e.g. `"debugging"` if the session's recent turns match a
   troubleshooting pattern — reusing `personality-engine`'s own existing
   nine-value vocabulary, no new styles invented), and `channel` (the
   session's actual channel).
2. **Required fix inside `personality-engine` itself, disclosed here since
   this document's own design depends on it working:** `select_style`'s
   `channel` parameter is currently accepted but inert (confirmed this
   session — its own docstring says so). For 2D-C's channel-appropriate
   length/pacing to mean anything, `personality-engine`'s rule table needs
   at minimum a channel-based verbosity adjustment (voice responses
   shorter/less punctuation-dense than text, by default). This is
   `personality-engine`'s file to change, disclosed as a small, additive,
   named prerequisite exactly like §0.5/§0.6, not bundled into this
   document's own `communication-engine` changes.
3. Resolve `digital_twin.preferences.get` — **skipped this phase, per
   §0.10** — falling back entirely to step 1's result.
4. Publish the resolved `{style, verbosity, technical_depth, situation_hint}`
   bundle as part of `ResponseShapingDirective`.

## 8. Multilingual understanding & English-response policy

Per Doc 22 Principles 10–11: input comprehension is already effectively
multilingual today, inherited for free from STT (`ai-model-orchestration-engine`'s
Whisper-class connector, 2D-A) and the underlying generation model Reasoning
Engine already calls — no new component is required for *understanding* an
input in another language, since nothing in this pipeline currently
restricts input language. What this phase adds is the **output** half:
an explicit, enforced `response_language: "en"` field, always `"en"` this
phase (Doc 22 Principle 11: the user's configured response language is a
Digital Twin/2D-D preference, not built yet — see §0.10), carried on
`ResponseShapingDirective` (§7, §10) for Reasoning Engine to honor once
extended (§0.7). This engine does not itself perform language detection or
translation of any kind — both are explicitly out of scope (Master
Blueprint §3.2, "real-time translation as a user-facing feature").

## 9. Session-scoped Conversation Memory

Per §0.8's decision: the five new categories (questions, decisions,
preferences, corrections, feedback — `objective` already exists) are
appended to `ConversationSession.conversation_memory` (§3.1) incrementally
as the session progresses, sourced from structured signals this engine
already has access to, not free-text extraction this engine has no
authority to perform (content understanding is Reasoning Engine's job,
§0.1):

- `questions`: every `pending_questions` entry, once resolved (§6).
- `decisions`/`preferences`/`corrections`/`feedback`: **populated from a
  new, additive field on `communication.intent.deliver.request`** —
  `memory_annotations: list[{category, text}] | None` — that
  Reasoning Engine may optionally set when it already knows a piece of
  content it's delivering represents one of these categories (e.g., it
  just recorded a user correction). This engine only *stores* what it's
  told, categorized by the producing engine, never infers the category
  itself — consistent with "this engine never generates content" extended
  to "never classifies content" either. If Reasoning Engine does not set
  this field, that category simply accumulates nothing this phase — an
  honest, additive, non-blocking design, not a silent gap.

At session close (`Completed`), the full `conversation_memory` blob is
included in the existing Memory Engine archival write
(`01-communication-engine.md` §8.6) — additive to that write's existing
payload, no change to Memory Engine itself required.

## 10. Event-Bus contracts

**New payload, registered in `nova_contracts.events.communication`**
(extending the existing module, not a new one — this event is
`communication-engine`'s own, per §0.7's ownership boundary):

```python
class ResponseShapingDirectivePayload(BaseModel):
    session_id: UUID
    style: CommunicationStyle
    verbosity: str
    technical_depth: str
    situation_hint: str | None
    response_language: str = "en"
    schema_version: int = 1
```

Published alongside (same correlation_id as) `communication.turn.received`
— not merged into that payload, since `ResponseShapingDirective` is a
policy decision *about* the turn, not a property *of* it, matching this
codebase's existing convention of keeping decision-trace-shaped data in its
own payload (e.g. `ArbitrationResult` vs. `ExecutiveRequestPayload` in
Phase 2C).

**Extended, additively, existing payloads:**

- `CommunicationIntentDeliverRequestPayload` gains `memory_annotations:
  list[dict[str, str]] | None = None` (§9) — additive, default `None`,
  every existing producer unaffected.

**New subscriptions** (once §0.6's registration lands):

- `perception.addressee_signal.candidate` — consumed by §4.
- `world_model.context.changed` (already registered, unused by this
  engine today) — an additional consumption path for `present_identities`
  independent of the RPC fix in §0.5, since the `.changed` event already
  carries the field; both are specified because the RPC (synchronous, for
  the single point-in-time fusion check) and the event (asynchronous, for
  keeping a locally cached "who's likely present" view warm between checks)
  serve genuinely different latency needs, not redundant designs.

No change to any subject this engine already serves
(`communication.intent.deliver.request`, `.session.create.request`,
`.session.close.request`) — all three keep their existing shape.

## 11. APIs exposed

No new public HTTP endpoints. Two additive extensions to existing routes:

- `GET /v1/communication/sessions/{id}/context` — reply gains
  `conversation_memory` (§9) and `pending_questions` (already reserved,
  now populated).
- Session `state` values returned by any session-status endpoint now
  reachably include `WAITING` entered via the `CLARIFICATION` transition
  (§6.2) — no new enum member, just a newly-reachable transition on an
  existing one.

`dnd_override` (§5.2) is exposed as a field on the existing session-update
surface — no new endpoint, an additive field on
`POST /v1/communication/sessions/{id}/pause`'s sibling update path (exact
placement is an implementation-time decision, not an architectural one).

## 12. Interaction with other engines — updated from `01-communication-engine.md` §8

| Engine | 2D-A relationship | 2D-C change |
|---|---|---|
| `perception-engine` | None (§8.5 of 01, "deferred") | **New**: subscribes to `perception.addressee_signal.candidate` (§4) — real integration, contingent on §0.4's resolution and §0.6's prerequisite |
| `world-model-engine` | One RPC call per session creation (§8.7 of 01) | **Extended**: same RPC, reply gains `present_identities` (§0.5, prerequisite); new subscription to `.context.changed` |
| `personality-engine` | Real, load-bearing (§8.3 of 01) | **Extended**: `situation_hint` now genuinely derived (§0.9) rather than defaulted; `channel` parameter becomes load-bearing (§7, prerequisite in `personality-engine` itself) |
| `digital-twin-engine` | Deferred, port-only (§8.4 of 01) | **Unchanged** — still deferred, still not called (§0.10) |
| Reasoning Engine | Subscribes to `communication.turn.received`, no other contract (§8.2 of 01) | **Extended, pending verification (§0.7, §20)**: must additionally read `ResponseShapingDirectivePayload` and honor `response_language`/`verbosity`/`technical_depth`; may optionally set `memory_annotations` on its `communication.intent.deliver.request` calls |
| Memory Engine | Session summary at close (§8.6 of 01) | **Extended, additive only**: summary payload gains `conversation_memory` (§9), no schema change on Memory Engine's side required (it already accepts a free-form summary write) |

## 13. Failure handling — additive to `01-communication-engine.md` §9

| Failure | Behavior |
|---|---|
| `perception.addressee_signal.candidate` never arrives (no signal in window) | No fusion score computed; explicit client trigger remains the sole activation path — never a hang, since fusion is additive to, not a replacement for, the existing trigger (§4) |
| World Model `present_identities` RPC fails/degrades | `WorldModelSnapshot.degraded=True` already propagates (existing 2D-A mechanism); fusion treats a degraded/missing corroborating signal as simply absent (its weight contributes 0), never as a hard failure |
| `personality.style.select` RPC fails | Existing 2D-A fallback applies unchanged (`01-communication-engine.md` §9: unvalidated content, minimal-safe default style) — `ResponseShapingDirective` in this case defaults to `{style: PROFESSIONAL, verbosity: "moderate", technical_depth: "moderate", response_language: "en"}`, matching that same hardcoded minimal-safe default |
| Reasoning Engine does not honor `ResponseShapingDirective` (not yet extended, or a bug) | Non-fatal by design — content still delivers through the existing intent gate unchanged; the directive is advisory input to content generation, never a gate on delivery itself, so its absence degrades quality, never causes silence (Doc 22 Principle 3) |

## 14. Persistence requirements

- `communication.conversation_session.conversation_memory` (JSONB),
  `.interrupted_content` (TEXT), `.dnd_override` (BOOLEAN) — additive
  columns, no new table, synchronous writes matching §3.3.
- `communication.conversation_decision_trace` — new table (§3.2),
  append-only, standard indexed-by-`session_id`/`created_at` access
  pattern.
- No new Redis usage (§0.8) and no new graph/vector store — matching
  `01-communication-engine.md` §10's existing "no graph store, no vector
  store" scope statement, unchanged.

## 15. Observability & explainability

`ConversationDecisionTrace` (§3.2) is the primary mechanism, directly
serving two named, binding requirements: Doc 22 Principle 7 ("every
identity/addressee judgment... carries an explicit confidence value") and
Master Blueprint Risk §11.2 ("continuous confidence-calibration data
collection so the threshold can be evidenced, not guessed, over time").
Every fusion score, every silence decision, every interruption-recovery
outcome is a row, queryable per-session for debugging and, longer-term, for
the calibration data Risk §11.2 explicitly calls for. This is structurally
identical to Phase 2C's `ExecutiveDecisionTrace` — same discipline, same
project, applied to a different decision domain. Standard OpenTelemetry
spans wrap the fusion computation and RPC calls, matching every other
engine's existing observability setup (`nova-observability`, unchanged).

## 16. Security, authorization, and privacy implications

**The one boundary stated explicitly, per ADR-032:** addressee-fusion
confidence (§4) gates **only** whether NOVA activates a conversational
turn — a low-stakes, fully reversible decision (worst case: a missed
address, costing a repeat, or an unwanted brief audio cue). It is never
used, in this document's design, to gate access to any privileged data,
action, or capability. ADR-032's actual subject — identity confidence as an
*authorization* signal — remains entirely `perception-engine`'s Identity
Registry's concern (2D-B), untouched by this document. If a future phase
ever wants to use addressee/identity confidence for authorization, that is
an explicit, separate design decision requiring its own review — not an
incidental extension of §4's fusion score.

**Data minimization:** `ConversationDecisionTrace.inputs` stores signal
*values* (confidences, booleans, identity IDs), never raw biometric data —
voiceprints/faceprints remain exclusively `perception-engine`'s Identity
Registry, never duplicated here (matching Doc 22 Principle 8, already
enforced by 2D-B's own design). Conversation Memory (§9) may contain
sensitive user statements (corrections, stated preferences) — it is
protected by the same session-scoped auth already governing every other
`communication.*` table (`01-communication-engine.md` §15, unchanged), and
is archived to Memory Engine's existing access-control model at session
close, not given a new one.

**Communication Policies (§5.2)** are the mechanism Bible Part 13's "never
read sensitive information aloud" points toward — this phase ships the
policy *engine* honestly scoped to what it can enforce today (§5.2), not a
content-classification system that would need to inspect message content
for sensitivity, which is out of scope.

## 17. Performance considerations

Per Master Blueprint §13.2's lowest-latency tie-break rule: §4's fusion
computation is a pure, synchronous, in-process weighted sum over already-
delivered event data — no model call, no new RPC hop on the critical path
beyond the World Model corroboration check already made once per session
(§0.5, unchanged cadence from `01-communication-engine.md` §8.7). §7's
`personality.style.select` call is already on the existing critical path
(2D-A, §8.3 of `01-communication-engine.md`) — this document adds no new
RPC there, only a better-computed `situation_hint` argument to a call that
already happens. The one genuinely new synchronous cost is negligible: a
single additional Postgres write for `ConversationDecisionTrace`, on the
same connection/transaction pattern as every other session-scoped write
already made per turn.

## 18. Scalability considerations

Unchanged from `01-communication-engine.md` §14 — `ConversationDecisionTrace`
is keyed by `session_id` exactly like every other table this engine owns,
horizontally partitionable the same way. No new stateful in-process
component is introduced (the fusion computation is stateless per
invocation, reading already-published events, not accumulating its own
session-keyed in-memory state the way `session_registry.py`'s existing
`ChannelAdapter` map does).

## 19. Doc 22 / Doc 23 / ADR compliance mapping

| Decision | Principle / ADR |
|---|---|
| §4's fusion never treats a single signal as sufficient; explicit trigger remains available unconditionally | Doc 22 Principle 5 (presence over wake words) |
| §4's contextual, multi-signal fusion, never a keyword match | Doc 22 Principle 6 (context over keywords) — the entire reason this document's split with 2D-B exists |
| §4's asymmetric threshold (false-positive costs more than false-negative) | Doc 22 Principle 6, explicit cost asymmetry |
| §4's every fusion outcome confidence-scored, `UNCERTAIN` band never rounds to a binary yes/no | Doc 22 Principle 7 (identity/addressee is probabilistic) |
| §5's `LOW`-band silence explicitly recorded as a decision, not an absence | Doc 22 Principle 2 (silence is intentional) |
| §5.3's proactive-notification gate, deferred cost model to 2D-D | Doc 22 Principle 4 (measurable interruption cost) — mechanism now, full model 2D-D |
| §6's templated-only clarification, never generated text | Doc 23 §6 (never overclaim/fabricate); §0.2 (communication-engine never generates content) |
| §8's English-first response, multilingual input untouched | Doc 22 Principles 10–11 |
| §0.9's rule-based (not ML) emotional-cue heuristic, honestly scoped | Doc 23 §6 (no overclaimed capability), Doc 23 §4.6 (Empathy — recognize cues, never claim to feel) |
| §0.9's `fabricated_shared_feeling` boundary respected, unchanged | Doc 23 §4.6, already enforced in `personality-engine`'s validator, not modified here |
| §16's addressee confidence never used for authorization | ADR-032 |
| §0.8's Conversation Memory extends durable Postgres, not treated as ADR-012's ephemeral-cache category | ADR-012 (correctly distinguished, not misapplied) |
| §0.5/§0.6/§0.7's disclosed, additive, precedented cross-engine extensions | ADR-004 (Event Bus only), ADR-024 (versioned from day one) |
| §16's addressee decision never gates output directly — still routed through the unchanged `communication.intent` gate | ADR-005 |
| Every new/extended payload carries `schema_version: int = 1` | ADR-024 |
| No direct AI-provider/model call anywhere in this document's own logic (fusion is deterministic; content generation stays Reasoning Engine's) | ADR-020 |
| §0.10's honest non-call of `digital_twin.preferences.get` this phase, mirroring 2D-A's own precedent | ADR-030 (Digital Twin learns, Personality stores — this phase has no learner yet, so nothing to consume) |
| §15's `ConversationDecisionTrace`, calibration-data collection named as a first-class requirement | ADR-031 (subjective experience quality is first-class) |
| §12's disclosed extensions kept minimal, single-user-first framing preserved throughout | ADR-025 |

## 20. Documentation-vs-implementation conflicts found this session

1. **`personality-engine`'s `select_style` documents `channel` as a
   selection key; code accepts but ignores it.** §7 depends on this being
   fixed — named as a required, disclosed prerequisite there, not silently
   worked around.
2. **`personality.style.select`'s reply is documented as including "the
   current Personality Memory profile" in full; the actual reply carries
   only `verbosity`/`technical_depth`, not `terminology_preference`/`source`.**
   §7's design does not depend on the missing fields, so this is noted but
   requires no fix for this document's own scope.
3. **`perception-engine`'s design doc claims every published payload is
   `nova_contracts`-registered; none of them are.** §0.6 is the required
   fix this finding drives.
4. **`perception-engine`'s addressee-fusion event has never been produced
   in production**, despite a "Go" Gate Review. §0.4 is the fork this
   finding drives.
5. **World Model's `ContextReplyPayload` and agent-scoped REST views both
   omit `present_identities`**, despite `ActiveContext` itself already
   having the field. §0.5 is the required fix this finding drives.
6. **The Phase 2D-A Gate Review's own text (bare API paths, no
   real-Postgres tests for communication-engine) is already stale against
   current code** — both have since been fixed (verified: routes now
   correctly prefixed `/v1/communication/...`; `tests/integration/
   test_repository_real_postgres.py` exists with 6 real-Postgres test
   functions). Not a defect in this document's design, but worth recording
   so a future reader does not cite the Gate Review's literal text as
   still-current — this is itself a small instance of the standing rule
   this document was written under.

## 21. Required cross-engine extensions — consolidated

| # | Extension | Engine | Size | Blocking? |
|---|---|---|---|---|
| 1 | Wire sensor→fusion→publish orchestration into production | `perception-engine` | Small-medium | **Fork — §0.4, user decision required** |
| 2 | Register `nova_contracts.events.perception` (no shape change) | `nova-contracts` + `perception-engine` | Small, mechanical | Yes — before §4/§10 can subscribe to real payload types |
| 3 | Add `present_identities` to `ContextReplyPayload` + agent-scoped views | `world-model-engine` | Small, additive | Yes — before §4's corroborating signal is reachable |
| 4 | Make `channel` load-bearing in `select_style` | `personality-engine` | Small | Yes — before §7's channel-appropriate shaping has any effect |
| 5 | Consume `ResponseShapingDirectivePayload`; honor `response_language`/verbosity/technical_depth; optionally set `memory_annotations` | `reasoning-engine` | Unverified — requires reading that engine's generation code first | Yes — before §7/§8/§9 have any observable effect on delivered content |

Items 2–4 are small, additive, precedented (mirroring 2D-A's own
AI-Orchestration extension), and this document recommends landing them as
ordinary prerequisite work, the same way 2D-A did. Item 1 is §0.4's fork.
Item 5 requires a verification pass this session did not perform before any
implementation-level commitment is made about it.

## 22. Testing & verification strategy

### 22.1 Testable today, without any prerequisite or real infrastructure

- §4's fusion scoring function: pure function, unit-testable today against
  synthetic `perception.addressee_signal.candidate`-shaped dicts (or, once
  item 2 lands, the registered contract type) — every score-band boundary,
  weight configuration, and the asymmetric-threshold behavior.
- §5.1's interruption-recovery state transitions and §6.2's `CLARIFICATION`
  state-machine wiring: extends the existing, already-tested
  `state_machine.py` test pattern directly.
- §6's templated clarification/resume utterances: deterministic string
  output, trivially unit-tested.
- §9's `conversation_memory` accumulation logic: pure data-shape tests
  against synthetic `memory_annotations` input, independent of whether
  Reasoning Engine ever actually sends any yet.
- §13's failure/fallback behavior: every row in that table is testable
  today with fakes, exactly like `01-communication-engine.md`'s own
  degraded-mode tests (§17 of that document) were.

### 22.2 Testable only once a prerequisite lands (§21)

- End-to-end fusion against a real `perception.addressee_signal.candidate`
  contract type: blocked on item 2 (registration) — until then, tests use
  hand-built dicts, not an imported contract class.
- Fusion's World Model corroboration path: blocked on item 3.
- Channel-appropriate response shaping's actual observable effect: blocked
  on item 4.
- Any assertion that a delivered response actually reflects
  `ResponseShapingDirective`: blocked on item 5.

### 22.3 Requires real infrastructure (per ADR-033's two-tier convention, non-blocking, opt-in)

- Postgres persistence of the new `conversation_memory`/`interrupted_content`/
  `dnd_override` columns and the new `conversation_decision_trace` table —
  `@pytest.mark.real_infra`, following the same `testcontainers` pattern
  STEP 2 already established for this engine.
- No new backing-store technology is introduced (no new Redis, no new
  graph/vector store, §14) — no new fixture type is required beyond what
  `nova-testkit` already provides.

### 22.4 Genuinely blocked pending §0.4's resolution

- Real end-to-end verification that a live wake-word/gaze/identity signal
  from `perception-engine`'s actual sensors produces a correct fusion
  outcome — this is the one test category no amount of fakes can
  substitute for, and it is exactly the gap §0.4 asks the user to resolve
  the scope of. Under Option A, this closes before 2D-C's own
  implementation is considered complete. Under Option B, this is tracked
  open, the same way real-Postgres verification has been for three Gate
  Reviews running, and 2D-C's own Gate Review would say so explicitly
  rather than implying full end-to-end coverage exists.

## 23. Technical debt and prerequisites — summary

In dependency order, before implementation of this document's own scope
begins:

1. **User decision on §0.4** (perception-engine production-wiring fork) —
   nothing else is blocked on this except item 6 below (real end-to-end
   testing), but the decision changes this document's own Gate Review
   framing.
2. Register `nova_contracts.events.perception` (§0.6/§21 item 2).
3. Extend `ContextReplyPayload` + `_AGENT_SCOPE_FIELDS` in
   `world-model-engine` (§0.5/§21 item 3).
4. Make `channel` load-bearing in `personality-engine`'s `select_style`
   (§7/§21 item 4).
5. **Verify `reasoning-engine`'s actual content-generation/prompt-construction
   code** (not done this session) before finalizing exactly how it consumes
   `ResponseShapingDirectivePayload` (§0.7/§21 item 5) — this document
   specifies the `communication-engine`-side contract fully but explicitly
   defers the Reasoning-Engine-side mechanism pending that verification.
6. If Option A (§0.4) is chosen: wire perception-engine's production
   orchestration before this document's own Gate Review can claim
   end-to-end verification; if Option B, open the tracked item and proceed.

None of items 2–4 require this document's own scope to change if deferred
— §22.1/§22.2 already specify exactly what remains testable in their
absence. Item 5 is the one genuine open technical question requiring
research (not a decision) before implementation can be fully scoped.

## 24. What happened next

**Approved.** The user resolved §0.4 as Option B, authorized the §21 items
2–3 prerequisites (World Model, perception registration), and confirmed
item 4 (`personality-engine`'s `channel` fix) was explicitly *not*
authorized this wave — outside the §0.5–§0.7 prerequisite scope the
approval was bounded to. Item 5 (Reasoning Engine's consumption mechanism)
was investigated as instructed and found to have no existing integration
to hook into at all — a larger, disclosed finding, not implemented this
wave. Implementation, full verification, and the
[Gate Review](../../roadmap/architecture-reviews/phase-2d-c-gate-review.md)
are complete; see that document for the exact record of what is and isn't
verified end-to-end. Phase 2D-D does not begin without further explicit
approval.

Followed this project's established discipline: Design → Implementation →
Testing → Architecture Review → Gate Review → Engineering Metrics →
Approval, one layer at a time, with every tradeoff disclosed as it's found,
not smoothed over in the telling.
