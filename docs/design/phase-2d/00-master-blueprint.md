# Phase 2D Master Architectural Blueprint — Voice, Identity, Conversation & Companion

**Status: Approved.** Technical Design Document work for Phase 2D-A is authorized
and underway. This document is deliberately one level of abstraction above a
Technical Design Document, per direct user instruction: it is the equivalent of
designing an
operating system before building its individual services. It defines philosophy,
subsystem boundaries, responsibilities, communication patterns, data ownership, and
long-term direction for every subsystem this phase and its immediate successors
touch — no code, no per-engine API/data-model detail. Those come after this document
is approved, one TDD per engine, exactly as every prior phase has done.

**Companion documents:** [22 — NOVA Human Interaction
Principles](../../architecture/22-nova-human-interaction-principles.md) is the
philosophical constitution this blueprint's every technical decision is checked
against, and [23 — NOVA Personality
Specification](../../architecture/23-nova-personality-specification.md) is the
permanent character/identity specification `personality-engine` (built starting
in 2D-A, §4.1) exists to implement. Read both first; this document exists to make
them buildable.

## 0. A note on naming — reconciling "Phase 3" with the existing roadmap

This blueprint was requested under the working name **"Phase 3"** — divided into
sub-phases 3A (Voice & Communication Foundation), 3B (Identity & Presence), 3C
(Conversation Intelligence), and 3D (Personal Companion). Before drafting, this name
was checked against [`ENGINEERING_ROADMAP.md`](../../roadmap/ENGINEERING_ROADMAP.md)
and found to collide with an already-existing, unrelated **Phase 3** ("Planning &
the NOVA Agent Operating System" — `planning-engine`, NAOS, `action-engine`,
`capability-engine`), which has zero thematic overlap with voice, identity, or
conversation.

What this blueprint actually describes is a **much fuller realization of the
roadmap's existing Phase 2D** ("Give NOVA a Voice"), which was already scoped —
in outline only — to build `communication-engine` and `personality-engine`. Per
explicit user decision, **the roadmap's numbering is preserved**: this work is
**Phase 2D**, split into four sub-phases using the same lettering convention Phase 2
itself already uses (2A/2B/2C/2D):

| This blueprint calls it | Formerly proposed as | Builds |
|---|---|---|
| **Phase 2D-A** — Voice & Communication Foundation | "Phase 3A" | `communication-engine` (transport layer), `personality-engine` |
| **Phase 2D-B** — Identity & Presence | "Phase 3B" | `perception-engine` (minimal: voice + face/presence modalities only) |
| **Phase 2D-C** — Conversation Intelligence | "Phase 3C" | `communication-engine` (behavioral/policy layer, extends 2D-A) |
| **Phase 2D-D** — Personal Companion | "Phase 3D" | `digital-twin-engine` (minimal: Communication Profile + conversation-scoped preference domains only) |

Every reference to "Phase 3" in this project from this point forward means the
existing NAOS/Planning/Agents phase, unchanged. `ENGINEERING_ROADMAP.md` is updated
alongside this blueprint (§13) to carry this structure formally, so there is exactly
one canonical numbering, not two.

---

## 1. Why Phase 2D exists

Phases 2A–2C built NOVA a mind with no way to talk. AI Model Orchestration (2A) can
generate; Reasoning (2B) can decide; Executive Cognition (2C) can arbitrate — but
none of them may render anything to a person
([ADR-005](../../architecture/00-overview-and-decisions.md#adr-005--nova-never-speaks-except-through-the-communication-engine)),
and nothing yet knows *who* it would be talking to. Phase 2D is where that changes:
NOVA becomes reachable, recognizable, and — over the following sub-phases —
genuinely personal to talk to.

Per [ADR-025](../../architecture/adr/ADR-025-personal-edition-is-the-flagship.md),
NOVA is being built as one trusted user's lifelong AI companion, not a generic
assistant product. ADR-025 also ranks **Natural Interaction fourth** of four
standing priorities (behind Personal Intelligence, Long-Term Memory, and Personal
Automation) — but explicitly states that ranking governs *in-phase scope latitude*,
not the roadmap's phase *sequence*, which is unchanged. Phase 2D is next in sequence
regardless of that ranking. What the ranking *does* affect is how Phase 2D is built:
wherever this phase has latitude, it should resolve toward the engines that will
matter most to years of personalization (Communication Profile evolution, trust
tracking) over generic breadth (many channels, many languages, broad configurability)
— see §12.

**The single sentence this whole blueprint defends:** Phase 2D does not build "a
chatbot with a microphone." It builds the four things a lifelong companion needs
before it can have a first real conversation — a voice, a sense of who it's talking
to, the judgment to know when to use that voice, and the beginning of a memory for
how this one person, specifically, likes to be talked to.

## 2. What separates Phase 2D from Phases 2A–2C

Phases 2A–2C are **cognitively pure** — orchestration, reasoning, and arbitration,
with zero user-facing surface. Their acceptance criteria are all provable at the API
level with no UI (2A/2B/2C Gate Reviews, filed). Phase 2D is the first phase where
**a human is in the loop as a first-class architectural concern**, not just a caller
of an API:

- 2A–2C ask "is the answer correct." Phase 2D additionally asks "was saying it, in
  this way, at this moment, to this person, the right thing to do" — a qualitatively
  different question, governed by [Doc 22](../../architecture/22-nova-human-interaction-principles.md)
  rather than by correctness alone.
- 2A–2C are stateless-or-nearly-stateless gateways/pipelines over per-request work.
  Phase 2D introduces the project's first genuinely long-lived, cross-restart,
  cross-session *relationship* state (conversation sessions, identity, evolving
  preference), which changes what "correct" even means — it is no longer a fixed
  target, it is a moving target that must track one specific person over years.
  This is the same reason Phase 2C's own README distinguished coordination from
  ownership; here the distinction is between per-request correctness and
  accumulated, evidenced trust.
- 2A–2C never render output. Phase 2D is bound by ADR-005 for the first time with
  something to actually prove it against: every utterance NOVA produces from this
  phase forward must be traceable to a `communication.intent` event that
  `communication-engine` — and only `communication-engine` — turned into delivered
  output.

## 3. Scope

### 3.1 Explicitly inside Phase 2D

- Speech recognition (STT) and speech synthesis (TTS), streaming audio, and the
  audio pipeline connecting them to `communication-engine`'s session model.
- Conversation transport: session creation/pause/resume/close, multi-turn state,
  survives process restarts (Bible Part 13 "Conversation state should survive
  restarts").
- Interruption handling at both the transport level (2D-A: don't lose audio/text
  mid-utterance) and the policy level (2D-C: *should* NOVA yield, and how).
  latency budgets for voice responses.
- Multilingual **input** comprehension; **English-first** response generation
  (Doc 22 Principles 10–11) — with real, non-English understanding as a defined
  Phase 2D acceptance target, not a stretch goal.
- Speaker recognition, face recognition, presence/attention/gaze detection, wake
  logic, identity confidence scoring, contextual activation — scoped to the
  minimum needed to support conversational addressee detection (§5), not a general
  desktop-sensing platform.
- Conversation timing, silence policy, interruption policy, response-length
  adaptation, clarification strategy, emotional tone selection, multilingual
  understanding, English response policy, and the human-communication principles
  (Doc 22) applied concretely to a live conversation.
- Conversational memory *during an active session* (Bible Part 13's "Conversation
  Memory": objective, questions, decisions, preferences, corrections, feedback for
  *this* conversation) — explicitly not the same thing as Phase 4's Cognitive State
  Engine background thinking (§9.4).
- The beginning of long-term interaction adaptation, scoped to communication:
  preferred explanation depth, response-length/technical-depth preferences,
  interaction habits relevant to *when and how* NOVA is engaged, trust-development
  tracking, and user-configured proactive-communication boundaries.
- `personality-engine`: identity/values as a behavioral constraint layer (already
  in the original Phase 2D deliverable list), consistency validation.
- `api-gateway` + `ws-gateway` minimal implementation (already in the original
  Phase 2D deliverable list).
- `apps/web-client` conversation panel (already in the original Phase 2D
  deliverable list), extended with voice I/O controls and a presence/identity
  indicator.

### 3.2 Explicitly NOT inside Phase 2D

Every item below is named because it is easy to accidentally pull into this phase's
scope by proximity. Each has an owner phase.

- **Desktop/OS-level sensing** (filesystem, clipboard, window focus, process/system
  health) — `nova-companion`, Phase 4. Phase 2D's Perception slice (2D-B) senses
  only audio and camera-based presence/identity, nothing about the user's machine.
- **Autonomous action of any kind** — `action-engine`, Phase 3 (NAOS). Phase 2D
  engines only ever *speak*; none of them execute, click, run commands, or modify
  files. "Proactive assistance boundaries" (2D-D) governs whether NOVA *volunteers
  information*, never whether NOVA *takes action* unprompted — that boundary is
  Autonomy Engine's, Phase 4.
- **General autonomy levels / trust-gated execution** — `autonomy-engine`, Phase 4.
  2D-D's trust-development tracking is a *conversational* trust signal (does the
  user rely on NOVA's judgment, correct it less often, etc.) — a distinct axis from
  Autonomy's *execution* trust (how much unattended action is permitted), and
  Phase 4's Trust Engine design must consume 2D-D's signal as one input rather than
  re-derive an unrelated one (§9.3, §11).
- **Full multi-domain user modeling** (goals, projects, software/hardware
  environment, skills, knowledge profile) — `digital-twin-engine`'s remaining
  domains, Phase 4. 2D-D builds this same engine, but only two of its eventual
  eleven domains (§9.3).
- **NOVA's own internal background cognition** (Active Thoughts, Focus System,
  Attention Layers, "what am I thinking about right now, independent of any
  conversation") — `cognitive-state-engine`, Phase 4. See §9.4 for the explicit
  boundary against 2D-C's session-scoped conversation memory.
- **Full orchestration / cross-engine conflict resolution involving
  Communication** — `executive-cognition-engine`'s generalized conflict resolution,
  Phase 6. 2C's existing minimal Executive Cognition Engine is not extended to
  arbitrate Communication in this phase.
- **Non-voice channels beyond text and voice** (email, SMS, smartwatch, AR/VR,
  robotics) — Bible Part 13 names these as the channel model's eventual breadth;
  Phase 2D proves the *channel abstraction* (Communication Adapters) with exactly
  two concrete channels, not all of them. Adding a channel later must be additive
  (§7), never a redesign.
- **Multi-device session synchronization** (same conversation continuing live
  across desktop/mobile/tablet) — the data model must not foreclose this (Doc 22
  Principle 13, Risk §11.6), but the actual sync mechanism is out of scope; Phase 2D
  runs single-device.
- **Real-time translation as a user-facing feature** — multilingual *input
  understanding* is in scope; presenting NOVA as a translation tool is not.

## 4. The four sub-phases

### 4.1 Phase 2D-A — Voice & Communication Foundation

**Owns:** `communication-engine` (new), extends `personality-engine` (new).

**Responsible for:** speech recognition, speech synthesis, streaming audio,
interruption handling (transport level), latency, conversation transport,
multilingual input, English-first responses, audio pipeline.

This is the transport and plumbing layer — Bible Part 13's lifecycle (Receive →
Understand → Retrieve Context → Determine Intent → Select Strategy → Generate →
Choose Channel → Deliver → Monitor → Learn) implemented end-to-end for exactly two
channels (text, voice), with every step present but the *policy intelligence*
inside "Select Strategy" and "Determine Intent" deliberately minimal — that
intelligence is 2D-C's job. 2D-A proves the pipe works; 2D-C makes the pipe smart.

`personality-engine` is built starting here, not deferred to 2D-C, because even the
most minimal 2D-A response (a text acknowledgment) must already be
personality-consistent — Phase 2D's own inherited acceptance criterion ("Personality
stays recognizably consistent across at least two different underlying models") was
already part of the original Phase 2D scope and does not wait for conversation
intelligence to exist. Its TDD is written directly from [Doc 23 — NOVA Personality
Specification](../../architecture/23-nova-personality-specification.md), the
permanent, non-technical specification of NOVA's constant traits, values, and
ethical constraints (Doc 23 §2, §6) versus what is allowed to adapt (Doc 23 §7) —
this blueprint defines `personality-engine`'s boundaries and interfaces; Doc 23
defines what the engine must be faithful to.

**Concretely ships:** Model Registry-style STT/TTS provider abstraction (mirroring
2A's `ModelConnector` pattern — Whisper-class local model default, one cloud
provider as proof of swappability); a `ConversationSession` state machine
implementing Bible Part 13's ten conversation states (Listening, Thinking, Waiting,
Executing, Monitoring, Idle, Learning, Speaking, Paused, Completed); the audio
streaming pipeline (capture → VAD → STT → session → TTS → playback) with barge-in
support (the user can start speaking while NOVA is still talking, at the transport
level — 2D-C decides what to *do* with that signal); session persistence surviving
process restart.

### 4.2 Phase 2D-B — Identity & Presence

**Owns:** `perception-engine` (new — minimal form; see §9.1 for its Phase 4
extension path).

**Responsible for:** speaker recognition, face recognition, presence detection,
attention detection, gaze awareness, wake logic, identity confidence, contextual
activation.

This sub-phase exists to answer exactly one question on NOVA's behalf, continuously
and probabilistically: **who is present, and are they addressing NOVA right now?**
It never answers *what to do about it* — per Bible Part 11's own architectural
requirement, "the Perception Engine must remain independent from AI models,
Reasoning, Planning, Memory, Knowledge, World Model. Its responsibility is
observation. Understanding belongs to the higher cognitive systems." That sentence
is binding on 2D-B exactly as it will be binding on Perception Engine's full Phase 4
form — 2D-B may not contain a shred of "should I respond" logic, only "here is what
I observed, with what confidence." See §5 for how this hands off to 2D-C.

**Concretely ships:** an Identity Registry (locally-stored, encrypted voiceprint/
faceprint templates, explicit per-Doc-22-Principle-8 consent and revocation flow);
a wake-word/wake-phrase spotter as one input signal among several (Doc 22 Principle
5 — never the sole signal); speaker diarization for multi-person audio; presence/
gaze/attention state published as events, not queried synchronously by default
(World Model Engine, already built in Phase 1, caches the current "who's present"
snapshot per its existing Active Context pattern —
[ADR-012](../../architecture/adr/ADR-012-redis-as-primary-store-not-cache.md) — so
2D-B does not need to serve its own low-latency query path for this).

### 4.3 Phase 2D-C — Conversation Intelligence

**Owns:** extends `communication-engine` (behavioral/policy layer, on top of
2D-A's transport).

**Responsible for:** conversation timing, silence policies, interruption policy,
response length adaptation, clarification strategy, emotional tone selection,
conversational memory during active sessions, multilingual understanding, English
response policy, human communication principles.

This is where Doc 22 stops being philosophy and becomes running code. 2D-A built a
pipe; 2D-B built a sense of who's there; 2D-C is the judgment layer that decides,
for a specific person in a specific moment, whether to speak, what to say, how much
of it, in what tone, and in what language — Bible Part 13's "Adaptive
Communication," "Response Planning," "Clarification Engine," "Communication
Styles," and "Multi Language Support" sections, together. This sub-phase is
explicitly defined by the user's own framing: **it defines HOW NOVA communicates,
not WHAT it knows** — the *content* of a response still comes from Reasoning (2B)
and AI Model Orchestration (2A); 2D-C decides its shape and its timing.

**Concretely ships:** the silence/interruption policy engine (consuming 2D-B's
presence/attention signals, Bible Part 13's "Interruption Management"); the
Clarification Engine (Bible Part 13); response-length/tone selection consuming
`personality-engine`'s style rules and `digital-twin-engine`'s learned preferences
(2D-D) via served RPC; the addressee-detection decision itself (§5); session-scoped
Conversation Memory (Bible Part 13's list: objective, questions, decisions,
preferences, corrections, feedback — written to Memory Engine, Phase 1, as this
session's episodic record, not retained as 2D-C's own long-term store).

### 4.4 Phase 2D-D — Personal Companion

**Owns:** `digital-twin-engine` (new — minimal form; see §9.3 for its Phase 4
extension path).

**Responsible for:** long-term interaction adaptation — communication preferences,
preferred explanation depth, interaction habits, daily routines, personalization,
trust development, proactive assistance boundaries.

This sub-phase is where Phase 2D stops being "a good conversational interface" and
starts being what the user actually asked NOVA to become: a companion that gets
better, specifically for one person, across years. Its entire design is bound by
Bible Part 16's "Preference Evolution" discipline — *"Preferences change. The
Digital Twin should detect changes gradually. Never overwrite existing preferences
immediately. Require consistent evidence. Maintain preference history."* — and by
Doc 22 Principle 9 (trust through consistency, not confidence). A companion that
changes its behavior after one data point is not personalizing, it is thrashing.

**Concretely ships:** the Communication Profile domain (response length, technical
depth, preferred terminology, explanation style, conversation pacing — Bible Part
16), populated only from real 2D-A/2D-C session data, never synthetic; a
conversation-scoped slice of Preference Evolution and Habit Detection (interaction
timing patterns, e.g. "prefers terse responses during working hours, detailed
explanations in the evening" — not workflow/project habits, which stay Phase 4); a
trust-development metric tracked from correction frequency, clarification-question
acceptance, and proactive-suggestion acceptance/dismissal rates; a
proactive-**communication** boundary policy (Bible Part 13's "The user always
controls how proactive NOVA becomes" — configurable frequency/topic limits on
NOVA-initiated speech, never on NOVA-initiated action, which remains out of scope
per §3.2).

**How this avoids becoming Personality Engine's job twice** (§9.2 has the full
reasoning): `digital-twin-engine` **learns** preferences from evidence and **owns**
their history/confidence; `personality-engine` **stores and applies** the current
resolved value as a behavioral constraint on generation. Bible Part 16 says Digital
Twin "learns... continuously"; Bible Part 17 says Personality "stores long term
behavioral adjustments" and explicitly "never replace[s] core identity" — the
verbs are the tell. One engine is the epistemic learner, the other is the stable
identity that consumes what's been learned without itself doing the learning.

## 5. Talking TO NOVA vs. talking ABOUT NOVA — the addressee-detection boundary

This is named explicitly because the user named it explicitly, and because it is
the single clearest example of the Perception/Conversation split this whole
blueprint is built around.

**The failure this boundary exists to prevent:** a user says "yeah NOVA already
handles that for me" to a colleague on a call, and NOVA responds. Mentioning NOVA's
name is conversational content *about* NOVA, not an address *to* NOVA — and per
Doc 22 Principle 6, a keyword match is never sufficient grounds to respond.

**The architectural split:**

1. **Phase 2D-B (Perception) observes and publishes signals, never decides.**
   Candidate signals include: wake-word/wake-phrase match, speaker identity +
   confidence, gaze direction (looking at the device vs. looking away/at another
   person), directness-of-address acoustic features (if available), and whether a
   conversation session is already active with this speaker. Every signal is
   published as its own event with its own confidence — 2D-B never fuses them into
   a single "should respond" verdict, because that fusion is *understanding*, which
   Bible Part 11 explicitly forbids Perception from doing.
2. **Phase 2D-C (Conversation Intelligence) fuses the signals and decides.** It
   consumes 2D-B's signals *plus* conversational context it alone has access to —
   whether a session is mid-turn, whether the last utterance was a question NOVA
   asked, recent interaction history — and produces the actual addressee judgment,
   itself confidence-scored (Doc 22 Principle 7: identity/addressee judgments are
   probabilistic, never binary).
3. **The asymmetric cost is encoded, not left implicit.** Per Doc 22 Principle 6,
   a false-positive response (responding to a mention) is treated as strictly worse
   than a false-negative (missing a genuine address, which costs the user a repeat
   — mildly annoying, not a trust violation). 2D-C's fusion threshold is tuned
   asymmetrically for this reason, and the threshold itself must be exposed as a
   user-configurable sensitivity setting from day one (this is also Risk §11.2).
4. **Ambiguous cases resolve toward clarification, not silence or response.** Bible
   Part 13's Clarification Engine is the designed escape valve for genuinely
   ambiguous addressee signals — a brief, low-cost clarifying cue rather than a
   full unsolicited response, when confidence sits in the uncertain middle band
   (Bible Part 17's Confidence Expression model, applied here).

This same 2D-B-observes / 2D-C-decides split is the general pattern this blueprint
uses everywhere Perception and Conversation Intelligence meet — not a special case
invented only for addressee detection.

## 6. Cross-engine communication model

Every rule below is inherited, not invented — Phase 2D introduces zero new
communication patterns, it is the first phase to exercise the full set at once.

- **[ADR-004](../../architecture/00-overview-and-decisions.md#adr-004--event-bus-is-the-only-legal-cross-engine-channel):
  the Event Bus is the only legal cross-engine channel.** No Phase 2D engine ever
  imports another's internals or calls another's HTTP API for internal
  orchestration. `communication-engine`, `personality-engine`, `perception-engine`,
  and `digital-twin-engine` talk to each other and to every prior-phase engine
  exclusively via publish/subscribe events or NATS request/reply RPC routed through
  the bus.
- **[ADR-005](../../architecture/00-overview-and-decisions.md#adr-005--nova-never-speaks-except-through-the-communication-engine):
  only `communication-engine` renders user-facing output.** `perception-engine`,
  `digital-twin-engine`, and every engine from every prior phase that wants to say
  something to the user emits a `communication.intent` event; `communication-engine`
  alone decides how (and whether — Doc 22 Principle 2) it becomes delivered output,
  filtered through `personality-engine` for tone/style.
- **Synchronous request/reply RPC is used only where a response genuinely cannot
  proceed without an immediate answer**, mirroring the pattern 2A already
  established for its served Event-Bus RPCs consumed by Reasoning (2B) under
  ADR-020: `personality-engine` serves `personality.validate_response` and
  `personality.style.select`; `digital-twin-engine` serves
  `digital_twin.preferences.get`. Both are called synchronously by
  `communication-engine` mid-pipeline, and both must have a fast, safe default
  fallback (Risk §11.7) so their unavailability degrades response quality, never
  produces total silence.
- **Everything else is asynchronous publish/subscribe.** `perception-engine`
  publishes identity/presence/attention/wake signals; `communication-engine`
  publishes conversation-state and session-lifecycle events (consumed by, among
  others, `digital-twin-engine`'s learning loop and — eventually, Phase 6 — the
  full Executive Cognition Engine); `digital-twin-engine` subscribes to
  `communication.session.completed` to learn from completed sessions.

## 7. Data ownership matrix

| Engine | Owns (system of record) | Consumes (never owns) | Never touches |
|---|---|---|---|
| `communication-engine` | Conversation sessions & state machine; notification queue; channel registry; communication policy config | Personality style rules (RPC); Digital Twin preferences (RPC); Perception identity/presence signals (events); Reasoning/AI-Orchestration output (content) | Long-term memory storage (writes session summaries to Memory Engine, Phase 1, which owns them); biometric templates |
| `personality-engine` | Core identity/values config; resolved Personality Memory (applied behavioral adjustments); consistency-validation audit trail | Preference *evidence* from Digital Twin (consumes the resolved value, not the evidence trail) | Conversation content generation; identity/presence data |
| `perception-engine` (2D-B) | Identity Registry (voiceprint/faceprint templates, local, encrypted, revocable); per-source consent/permission state | Nothing (pure sensor layer) | "Who is currently present" as a world fact (publishes to World Model, which owns that projection — ADR-017); any content or decision logic |
| `digital-twin-engine` (2D-D) | Communication Profile domain; conversation-scoped Preference Evolution history; interaction-habit signals (communication-timing only); trust-development metric; proactive-communication boundary policy | Session data from `communication-engine` (events, to learn from) | Goals/projects/hardware/software/skills domains (Phase 4); conversation content; identity data |
| `api-gateway` / `ws-gateway` | Nothing (pure transport) | Everything, transiently | All persistent state |

**Only-consumes engines this phase:** `api-gateway`/`ws-gateway` are the only
Phase 2D components that own no data at all — pure transport, matching their
already-established minimal-implementation scope from the original Phase 2D plan.

## 8. API / RPC / statelessness matrix

| Engine | Public HTTP API | Served Event-Bus RPC | Stateless or stateful | Persists across restart |
|---|---|---|---|---|
| `communication-engine` | Yes — Create/Send/Receive/Pause/Resume/Close Session, Generate Notification, Broadcast Update, Synchronize Devices, Retrieve Context (Bible Part 13 "Communication APIs") | Serves `communication.intent.deliver` (the ADR-005 gate every other engine calls to speak) | **Stateful** | Yes — session state is the point |
| `personality-engine` | Yes — Retrieve Personality, Validate Response, Behavior Analysis, Communication Style, Identity Snapshot (Bible Part 17 "Personality APIs") | Serves `personality.validate_response`, `personality.style.select` | **Stateful**, but narrowly (small, mostly-static identity config + memory); validation/style logic itself is stateless computation over that state | Yes — identity/values/personality memory |
| `perception-engine` (2D-B) | Narrow admin/config surface only — Permission Status, Calibration, Enrollment (Bible Part 11's Sensor Abstraction Layer lifecycle); **no content API**, it produces no user-facing content | Serves none this phase (no synchronous query need identified — World Model's Active Context covers the one case that would need it, per ADR-012) | **Mixed** — Identity Registry is stateful; moment-to-moment signal processing (VAD, wake-spotting, diarization) is stateless/streaming | Yes, for the Identity Registry only |
| `digital-twin-engine` (2D-D) | Yes — Retrieve Profile (Communication Profile scope only), Update Profile, Retrieve Preferences (Bible Part 16 "Digital Twin APIs", scoped) | Serves `digital_twin.preferences.get` | **Stateful** | Yes — this is definitionally a persistent model |

Contrast with Phase 2A: [ADR-022](../../architecture/adr/ADR-022-stateless-cognitive-gateway.md)
established AI Model Orchestration as a *stateless* cognitive gateway — the correct
contrast for Phase 2D, where three of four engines are stateful by design, because
this phase's entire purpose is building NOVA's first cross-session, cross-restart
*relationship* state. Statelessness was right for a request-scoped gateway; it would
be wrong here.

## 9. Reconciling Phase 2D with already-canonical Bible engines

Bible Parts 11 (Perception), 16 (Digital Twin), and 6 (Cognitive State) already
describe full engines with responsibilities that overlap Phase 2D's scope. This
section makes the reconciliation explicit rather than leaving it for a future
engineer to discover mid-implementation — exactly the ambiguity the user's original
directive said must not exist.

### 9.1 `perception-engine`: minimal now, general later — precedented, not improvised

This is the same pattern already used once in this project:
`executive-cognition-engine` was stood up in Phase 2C in deliberately minimal form
("arbitrate attention/priority between exactly two contending engines... this is
not the full executive-cognition-engine of Phase 6 — Phase 6 extends the service
this phase starts"), and Phase 6's own roadmap entry confirms it: "additive to 2C's
existing service, not a rewrite." Phase 2D-B applies the identical discipline to
`perception-engine`: it ships now with exactly two sensing modalities (audio,
camera-based presence/identity) instead of Bible Part 11's full sensor breadth, but
it must implement the **full** Sensor Abstraction Layer lifecycle contract
(Initialize/Start/Pause/Resume/Stop/Health Check/Configuration/Calibration/
Permission Status/Error Reporting/Capability Discovery) from the start, so that
Phase 4 adding `nova-companion`'s desktop sensors (filesystem, clipboard, window
focus, process/system health) is a matter of registering new sensors behind an
already-correct interface, never a redesign. This mirrors Phase 1's World Model
shipping its "World Simulation" as a stub interface only — same discipline, applied
one phase-family over.

### 9.2 `personality-engine` vs. `digital-twin-engine`: who owns "preferred explanation depth"

Bible Part 16 and Part 17 both mention the same concrete example — "preferred
explanation depth" — under two different section names ("Communication Profile" and
"Personality Memory," respectively). This is not a contradiction in the Bible; it is
two engines looking at the same fact from two different angles, and Phase 2D-D
makes the boundary between those angles explicit for the first time (§4.4):
`digital-twin-engine` is the epistemic learner (detects the preference from
evidence, tracks its confidence and history, per Part 16's "Preference Evolution");
`personality-engine` is the stable identity that stores and applies the current
resolved value without itself doing any learning (Part 17's "Personality Memory:
...adjustments should refine personality, never replace core identity"). Upon this
blueprint's approval, this boundary should be filed as its own ADR before either
engine's TDD is written — mirroring how ADR-017 formalized the World Model boundary
separation at the equivalent point in Phase 1 (Risk §11.5).

### 9.3 `digital-twin-engine`: two of eleven domains now, the rest in Phase 4

Bible Part 16 defines eleven Digital Twin domains (Personal Workflow, Projects,
Software Environment, Hardware Environment, Knowledge Profile, Skill Profile,
Communication Style, Productivity Patterns, Goals, Preferences, Learning Progress).
Phase 2D-D builds exactly two — Communication Style/Profile and a
conversation-scoped slice of Preferences — because those are the two Phase 2D
actually has evidence to populate. The other nine wait for Phase 4, when real
Perception (desktop sensors) and Memory data exist to populate them honestly,
consistent with this project's standing rule against fabricated or premature state
(Bible Part 6's "never generate fake animations," applied here to data, not
visuals). Phase 4's `digital-twin-engine` entry in the roadmap (§13) is updated to
read "extend," not "build," for exactly this reason.

### 9.4 `communication-engine`'s session memory vs. `cognitive-state-engine`'s background cognition

Bible Part 6 draws this boundary itself, unprompted, in its own text: *"Unlike
conversation history, the Cognitive State Engine exists independently from user
interactions."* Phase 2D-C's Conversation Memory (Bible Part 13: objective,
questions, decisions, preferences, corrections, feedback) is scoped strictly to an
*active session* and stops existing as "current" the moment the session ends (it is
archived to Memory Engine, Phase 1, as an episodic record). `cognitive-state-engine`
(Phase 4) is NOVA's continuous internal thinking — Active Thoughts, Focus, Attention
Layers — that runs whether or not any conversation is happening at all, including
while the user is offline. Phase 2D builds none of that; a conversational silence
in 2D is simply "no active session," not "NOVA has stopped thinking," because in
this phase, outside of an active session, NOVA genuinely has no persistent internal
cognitive loop yet — that honest limitation is Phase 4's to close, not Phase 2D's to
fake.

## 10. Dependency graph

**Phase 2D depends on:** Phases 2A–2C complete (already true) — AI Model
Orchestration to generate content, Reasoning to decide what's worth saying,
Executive Cognition's existing two-engine arbitration (unchanged, unextended this
phase); Phase 1's Memory/Knowledge/World Model Engines (session archival, identity
projection, context retrieval, all already built).

**What depends on Phase 2D:**

- **Phase 3 (NAOS/Planning/Agents)** — already documented in the existing roadmap:
  "`communication-engine` from 2D to report progress/results." Agent supervisors'
  peer-review escalations and Planning's status updates become user-visible only
  through Phase 2D's `communication.intent` gate. No change to this dependency.
- **Phase 4 (Perception, Autonomy & Digital Twin)** — no longer *creates*
  `perception-engine` or `digital-twin-engine`; it *extends* both (§9.1, §9.3).
  Autonomy Engine's Trust Engine must consume 2D-D's conversational trust signal as
  one input to its own execution-trust model, not re-derive an unrelated one
  (§3.2). `cognitive-state-engine` is new in Phase 4 and must respect the boundary
  in §9.4 from its first line of design.
- **Phase 5 (Desktop App & Living Interface)** — no longer *builds* the voice
  channel (Whisper/Piper integration, streaming); that already exists from 2D-A.
  Phase 5's remaining scope is the *visual* voice UI (waveform/listening
  indicators, wake-word UX polish in the desktop shell) and native packaging —
  materially narrower than originally scoped. Updated in §13.
- **Phase 6 (Executive Cognition & Full Orchestration)** — generalizes conflict
  resolution to include `communication-engine` as one of the arbitrated engines
  for the first time (2C's minimal arbitrator today only knows about AI
  Orchestration and Reasoning); adds the Personality dashboard panel (already
  planned).

## 11. Architectural risks

1. **Latency budget conflict.** Bible Part 13 demands voice responses "minimize
   latency," but the full pipeline (Perception signal → addressee fusion →
   Reasoning/AI-Orchestration content generation → Personality validation RPC →
   Digital Twin preference RPC → Communication delivery) stacks multiple
   synchronous hops before a word is spoken. *Mitigation:* streaming partial
   responses (Bible's "Streaming Communication") and a fast-path for short
   acknowledgments that skips non-essential RPCs, both required acceptance
   criteria for 2D-A/2D-C's TDDs, not optimizations to consider later.
2. **Addressee-detection tuning is a real, bidirectional UX risk.** Too permissive:
   NOVA responds to mentions (Doc 22 Principle 6's named failure). Too
   conservative: NOVA feels unresponsive to genuine address. *Mitigation:*
   user-configurable sensitivity from day one, plus continuous confidence-
   calibration data collection so the threshold can be evidenced, not guessed,
   over time.
3. **Premature interface lock-in in `perception-engine`.** If 2D-B's Sensor
   Abstraction Layer is implemented narrowly to fit only two sensor types instead
   of the full Bible Part 11 lifecycle contract, Phase 4's desktop-sensor
   extension risks a redesign. *Mitigation:* §9.1's discipline is a hard TDD
   requirement, verified in 2D-B's own Gate Review, not left to good intentions.
4. **Premature schema lock-in in `digital-twin-engine`.** Same risk, applied to
   data model instead of interface: if Communication Profile is modeled ad hoc
   rather than against Bible Part 16's full eleven-domain shape, Phase 4 risks a
   migration. *Mitigation:* §9.3's discipline, same enforcement path.
5. **The Personality/Digital-Twin boundary (§9.2) is new, not previously drawn
   anywhere in the Bible, and is exactly the kind of distinction future
   convenience quietly erodes** — a future engineer (or a future instance of this
   same coding agent, under time pressure) collapsing "preferred explanation
   depth" back into one undifferentiated preferences blob nobody cleanly owns.
   *Mitigation:* file this boundary as a dedicated ADR immediately upon this
   blueprint's approval, before either engine's TDD is written — the same
   sequencing ADR-017 followed for the World Model boundary at the equivalent
   point in Phase 1 — so the boundary has independent, citable authority beyond
   this blueprint's prose.
6. **Multi-device continuity is a stated future requirement (Doc 22 Principle 13)
   that Phase 2D does not build**, running single-device only. If the
   `ConversationSession` schema is designed without a device/channel dimension
   from the start, retrofitting multi-device continuation later becomes a
   migration rather than an extension. *Mitigation:* the session data model must
   include device/channel as a first-class dimension in 2D-A's TDD even though
   only one is ever populated this phase.
7. **New synchronous failure points.** `communication-engine`'s response pipeline
   now depends on `personality-engine` and `digital-twin-engine` being reachable
   mid-response, on top of AI Orchestration and Reasoning already in that path.
   An outage in either new dependency must not silence NOVA entirely — it directly
   threatens Doc 22 Principle 3 (silence should be a choice, never an outage
   symptom). *Mitigation:* both RPCs require a safe, explicit default-value
   fallback with degraded-mode logging, specified in 2D-A's TDD as a required
   failure-scenario test, matching every prior phase's failure-scenario testing
   discipline.
8. **English-first response scope could quietly widen or narrow without a
   decision.** Doc 22 Principles 10–11 draw a deliberate line between broad input
   comprehension (in scope) and broad output generation (explicitly deferred).
   *Mitigation:* multilingual input comprehension and English-only output are both
   named, testable acceptance criteria for 2D-C, not aspirational prose — a future
   phase that wants to widen output language must do so as an explicit, named
   scope decision, not an incidental side effect of a model upgrade.

## 12. Alignment with the long-term vision

NOVA is not being built as a generic AI assistant. It is being built as a lifelong
personal AI companion for one trusted user
([ADR-025](../../architecture/adr/ADR-025-personal-edition-is-the-flagship.md)).
Every sub-phase in this blueprint was checked against that framing, not just
against the Bible's feature lists:

- **2D-A** could have been scoped as "support as many channels and providers as
  possible" (breadth). It is instead scoped as "get exactly two channels — text and
  voice — working with genuinely low latency and true multi-turn continuity"
  (depth), because a companion the user actually talks to every day needs one
  channel that works excellently before it needs five that work adequately.
- **2D-B** could have been scoped as a general biometric-identity platform. It is
  instead scoped tightly to what conversational addressee detection needs, because
  ADR-025's priority order ranks Natural Interaction behind Personal Intelligence
  and Long-Term Memory — this sub-phase earns its place in the sequence by serving
  those higher priorities (accurate addressee detection is what makes every later
  personalization trustworthy), not by maximizing sensing capability for its own
  sake.
- **2D-C** could have optimized for "sounds impressive in a demo." It is instead
  bound end-to-end by [Doc 22](../../architecture/22-nova-human-interaction-principles.md),
  whose entire premise is that a companion earns trust through restraint and
  consistency (Principles 2–4, 9) — the opposite of what makes a good demo.
- **2D-D** is, of every sub-phase, the one that most directly operationalizes
  ADR-025's **highest** priority — Personal Intelligence — inside a phase whose
  own sequence position is nominally about the *lowest*-ranked priority (Natural
  Interaction). This is not a contradiction: 2D-D is where "Natural Interaction"
  and "Personal Intelligence" first meet, the same way ADR-029 already
  operationalized Personal Intelligence for Executive Cognition's arbitration
  logic in Phase 2C. It is deliberately built as a real, if narrow, slice of
  `digital-twin-engine` rather than throwaway logic inside `communication-engine`,
  precisely because personalization is not this phase's side effect — for the
  user, it is close to the point of the entire phase.

## 13. Phase 2D Engineering Principles

Seven permanent engineering principles, given by the user at the same approval
point that authorized Phase 2D-A implementation to begin. Per their own framing —
"every subsystem introduced in Phase 2D should be designed so later phases can
extend it naturally" (Principle 6 below) — these are scoped to Phase 2D and
everything built on top of it, the same scope this entire blueprint document
governs, rather than a NOVA-wide addition to Doc 22. Where a principle is really
an *interaction-philosophy* concern Doc 22 already covers, that overlap is named
explicitly rather than duplicated; where a principle is genuinely new engineering
guidance, it is stated here as the authority every current and future Phase 2D TDD
is checked against, alongside Doc 22/23.

### 13.1 Human conversation must always feel continuous

Regardless of how many engines compose a response — Reasoning generating content,
Personality validating it, eventually Digital Twin shaping it and Perception
gating it — the user experiences one continuous conversation with one companion.
Subsystem boundaries must never become visible in the interaction itself (they
may, and should, remain visible in observability/debugging surfaces — invisibility
is a user-experience property, not a transparency violation). This is the
architectural sibling of Doc 22 Principle 12 (technology should become invisible),
applied specifically to multi-engine composition. **Already structurally enforced**
by `01-communication-engine.md`'s design: the `communication.intent` gate (§7 of
that document) is the *only* path any engine has to the user, so no matter how
many engines contributed to a response, the user only ever sees one coherent
delivery — there is no code path where two engines could independently address
the user and reveal the seams between them.

### 13.2 Low latency is part of NOVA's personality

Responsiveness is not merely a non-functional requirement scored in a performance
report — it directly shapes whether NOVA feels intelligent and natural, the same
way a person who responds thoughtfully but instantly reads as more capable than
one who is correct but slow. **Standing tie-break rule:** whenever multiple
implementations satisfy a requirement's correctness bar, the one with the lowest
perceived latency is preferred, never treated as an optional optimization to
revisit later. `01-communication-engine.md` §13's streaming/fast-path
requirements and `02-personality-engine.md` §12's sub-millisecond, no-model-call
design (§0.3 of that document) are both already built to this standard; this
principle makes explicit, permanent, and binding on every *future* Phase 2D
decision what was previously implicit in those two documents' own reasoning.

### 13.3 Streaming first

Wherever technically possible, communication is designed around streaming rather
than request/response: speech recognition, speech synthesis, model generation,
long-running operations, and — not yet in scope, but a standing design constraint
on anything built toward it — future visual interaction. **Already the default**
in `01-communication-engine.md` §4: input is a genuine transport-level stream
(`transcribe` called incrementally on partial audio); output achieves the same
perceived immediacy through chunked calls to the non-streaming `synthesize` RPC
rather than a transport-level stream, since `EventBus.request()` (ADR-004) can
carry only a single reply, never a stream — `synthesize_stream`'s real
transport-level streaming exists (§0.3) but is HTTP/SSE-only, for a direct
external caller, mirroring 2A's `generate`/`stream` split exactly, not an
Event-Bus contract any engine-to-engine caller can use. This principle
generalizes the *chunk-for-perceived-immediacy* discipline beyond audio: any
future Phase 2D-C/D capability that could be designed as either a single
blocking call or an incremental sequence of calls must default to the
incremental design, with a single-call fallback only where a real technical
constraint (not convenience) forces it.

### 13.4 Interruptibility

At any moment, the user can interrupt NOVA while it is speaking. NOVA stops
immediately — not "eventually," not "after finishing the current sentence" — and
continues naturally from the new conversational context. `01-communication-engine
.md` §4's barge-in mechanic already implements the transport-level half of this
(immediate stream cancellation on detected input during `Speaking`); this
principle makes the requirement **unconditional at the transport level**, closing
a hedge that document's original text left open (see the amendment in §4 of that
document, applied alongside this principle). Whether the interruption was
conversationally *appropriate* remains Phase 2D-C's policy judgment (Doc 22
Principles 2–4) — but the *mechanical* stop is never negotiable, in any phase,
under any policy.

### 13.5 Conversation continuity through transient loss

A brief network blip, a moment of audio dropout, a short pause — none of these
should reset the conversation when recovery is possible. Interactions should
resemble natural human conversation, where a person doesn't restart from scratch
because you paused to think or the room got briefly noisy. `01-communication-
engine.md` §3.5 (restart recovery) and §9 (channel disconnect → `Paused`, resumable)
already cover *structural* interruptions (process crash, channel disconnect); this
principle extends the same discipline to *transient* ones that never rise to a
full disconnect — a short audio gap mid-utterance should be bridged by the audio
pipeline's own buffering, not treated as turn failure. See the amendment to
`01-communication-engine.md` §4 and §9, applied alongside this principle.

### 13.6 Progressive capability

Every subsystem introduced in Phase 2D must be designed so later phases can
extend it naturally, without architectural redesign. This is not new guidance —
it is the explicit naming of the discipline this entire blueprint has already
applied throughout: `perception-engine`'s full Sensor Abstraction Layer contract
shipped in 2D-B despite only two sensor modalities existing (§9.1); every deferred
port to `digital-twin-engine` and `perception-engine` defined in both current
TDDs before either dependency exists (`01-communication-engine.md` §0.6,
`02-personality-engine.md` §0.2, §10); `device_id` present in the session schema
from day one though only one device is ever populated (`01-communication-engine
.md` §3.2, Risk §11.6). Stating it here as a named principle makes it an explicit
review criterion for 2D-B/C/D's own TDDs, not merely an inherited habit.

### 13.7 Communication quality over feature count

Fewer capabilities built exceptionally well outweigh many built incompletely.
Natural interaction — the thing a lifelong companion is actually judged on — is
the priority over channel breadth, language breadth, or feature-list length. This
is the principle behind every explicit scope cut already made in this blueprint
and its TDDs: two channels, not eleven (§3.2); English-first responses, not
simultaneous multilingual generation (§0.1 of Doc 22's Principles 10–11); an
honest explicit-trigger interim instead of a half-built addressee detector
(`01-communication-engine.md` §0.4). Stated here as a permanent standard: a future
temptation to add a third channel, a second language, or a new notification type
before the existing two channels' voice/text experience is genuinely excellent
should be resisted by default, not treated as free additive progress.

## 14. Roadmap update

`ENGINEERING_ROADMAP.md` is updated alongside this blueprint to restructure the
Phase 2D section into 2D-A/B/C/D per this document, and to update Phase 4 and Phase
5's entries to say "extend" rather than "build" for `perception-engine` and
`digital-twin-engine` (Phase 4) and to narrow Phase 5's voice-channel scope to UI
polish (Phase 5) — see the roadmap file itself for the applied diff. No other
phase's content changes.

## 15. What happens next

**Approved.** This blueprint, [Doc 22](../../architecture/22-nova-human-interaction-principles.md),
[Doc 23](../../architecture/23-nova-personality-specification.md), and the first
two Phase 2D-A Technical Design Documents
([01](01-communication-engine.md), [02](02-personality-engine.md)) are all
approved. Implementation of Phase 2D-A is authorized and underway, following the
same discipline as every prior phase: Design → Implementation → Testing →
Architecture Review → Gate Review → Engineering Metrics → Approval, one layer at a
time, with honest reporting of every tradeoff and limitation along the way.
[ADR-030](../../architecture/adr/ADR-030-personality-stores-digital-twin-learns.md)
(the Personality/Digital-Twin boundary named in Risk §11.5) has been filed. The
remaining sub-phases — `perception-engine` (2D-B), `communication-engine`'s
conversation-intelligence extension (2D-C), `digital-twin-engine` (2D-D) — follow
in the same order, each with its own TDD, reviewed and approved before that
sub-phase's implementation begins.
