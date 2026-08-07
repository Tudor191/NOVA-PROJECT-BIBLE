# Phase 2D-A Technical Design — 01: Communication Engine (Voice & Communication Foundation)

Implements [Bible Part 13](../../bible/part-13-communication-engine.md)'s transport
and lifecycle layer, per the
[Phase 2D Master Architectural Blueprint](00-master-blueprint.md) §4.1 (Phase
2D-A), governed throughout by
[Doc 22 — NOVA Human Interaction Principles](../../architecture/22-nova-human-interaction-principles.md)
and [Doc 23 — NOVA Personality Specification](../../architecture/23-nova-personality-specification.md)
(§16 maps every major decision below against both). Cross-references
[ADR-004](../../architecture/00-overview-and-decisions.md#adr-004--event-bus-is-the-only-legal-cross-engine-channel)
(Event Bus only),
[ADR-005](../../architecture/00-overview-and-decisions.md#adr-005--nova-never-speaks-except-through-the-communication-engine)
(sole legal speech channel), and
[ADR-020](../../architecture/adr/ADR-020-sole-legal-llm-provider-channel.md)
(sole legal AI-provider channel — §0.3 below is this document's most consequential
finding against it).

Status: **Approved. Implemented and Gate-Reviewed (Go), approved by the user.**
`communication-engine` is now built at production-grade per this design package,
with the
[Architecture Review Report](../../roadmap/architecture-reviews/phase-2d-a-voice-communication-foundation.md)
and the formal
[Phase 2D-A Gate Review](../../roadmap/architecture-reviews/phase-2d-a-gate-review.md)
filed.

## 0. The boundary this document defends

### 0.1 Scope: transport and lifecycle now, conversation intelligence later

Per the Master Blueprint §4.1, Phase 2D-A builds the *pipe*; Phase 2D-C makes the
pipe *smart*. Concretely, every step of Bible Part 13's ten-step Communication
Lifecycle (§6 below) is implemented end-to-end in this document, but the
*judgment* inside "Determine Intent" and "Select Communication Strategy" is
deliberately minimal — a direct pass-through, not a policy engine. This is not a
placeholder apologized for; it is the same "minimal-now, extended-later" discipline
already used twice in this project (`executive-cognition-engine` 2C→6,
`perception-engine`/`digital-twin-engine` 2D-B/2D-D→4). **Phase 2D-C extends this
same `communication-engine` service — it does not replace it, and this document's
data model and interfaces are written so that extension is additive.** §18 states
the extension points explicitly.

### 0.2 ADR-005 compliance: the sole legal speech channel

`communication-engine` is the only service in NOVA that ever renders user-facing
output. Every other engine — Reasoning (content), Perception (once 2D-B exists),
Digital Twin (once 2D-D exists), any future agent or capability — expresses a
desire to say something by publishing an event; this engine, and only this engine,
decides whether, how, and when that becomes delivered output. §7 specifies the
mechanism. No component described anywhere in this document ever writes directly
to a channel adapter except through that one gate.

### 0.3 ADR-020 compliance and the speech-modality gap this phase must close

This is the most consequential architectural finding in this document, surfaced
here rather than left for implementation to discover.

ADR-020 states, without exception: *"no subsystem may ever depend directly on an
LLM/AI provider... every interaction with any AI model — text generation,
embeddings, vision, **speech**, anything — passes exclusively through
`ai-model-orchestration-engine`."* Speech is named explicitly. But
`ai-model-orchestration-engine`'s current `ModelConnector` protocol
(`services/ai-model-orchestration-engine/src/nova_ai_model_orchestration_engine/domain/ports.py`)
exposes exactly `generate`, `stream`, `embed`, `health` — and its `Modality`
type (`domain/models.py`) is `Literal["text_generation", "streaming", "embedding",
"tool_calling"]`. **There is no speech modality.** A `communication-engine` that
called Whisper or Piper directly to satisfy 2D-A's own "speech recognition, speech
synthesis" scope would be a first-day ADR-020 violation.

**Decision:** this phase includes a small, additive extension to
`ai-model-orchestration-engine`, delivered before `communication-engine`'s audio
pipeline is implemented against it:

- `Modality` gains two new literals: `"speech_to_text"`, `"text_to_speech"`.
- `ModelConnector` gains three new methods, following the existing protocol's
  own `generate`/`stream` split (raise `NotSupportedError` — never a
  provider-SDK exception — for connectors that don't implement a modality;
  verified by the ADR-023 uniform connector compliance suite, extended to
  cover these three new methods exactly as it covers `generate`/`embed`
  today):
  ```python
  async def transcribe(self, request: TranscribeRequest) -> TranscribeResult: ...
  async def synthesize(self, request: SynthesizeRequest) -> SynthesizeResult: ...
  def synthesize_stream(self, request: SynthesizeRequest) -> Any:  # AsyncIterator[AudioChunk]
      ...
  ```
  **Correction found during implementation, applied here rather than left
  inconsistent with the built code:** the non-streaming `synthesize` is what
  `communication-engine` actually calls (§8.1 below) — `synthesize_stream`
  mirrors `stream()`'s existing HTTP/SSE-only boundary (`api/generate.py`'s own
  module docstring: *"streaming is the one path that never becomes an Event
  Bus contract... HTTP/SSE only"*) and is for a direct external caller, not an
  engine-to-engine one. This document's earlier draft described `synthesize`
  itself as streaming over the Event-Bus RPC; that was inaccurate against
  ADR-004 and the already-built `generate`/`stream` precedent —
  `EventBus.request()` returns a single `EventEnvelope`, never a stream, so no
  Event-Bus RPC can carry one. §4 and §13 below reflect the corrected design:
  `communication-engine` achieves perceived streaming by calling the
  non-streaming `synthesize` RPC once per response chunk (sentence/phrase) as
  content becomes available, not by streaming a single call's transport.
- One new connector, `WhisperConnector` (local, zero-budget default, mirroring
  `OllamaConnector`'s role for text), and one new connector,
  `PiperConnector` (local, zero-budget default, TTS), both registered exactly like
  every existing connector — through `ConnectorFactory`, scored by the same Model
  Router (capability × historical success / (latency, cost)), no special-cased
  bypass.
- `CapabilityScores` gains `speech_recognition_accuracy` and
  `speech_synthesis_quality` dimensions, scored identically to every existing
  dimension (Part 7's Model Capability Matrix, extended, not replaced).

This is registered as a required Phase 2D-A deliverable against
`ai-model-orchestration-engine`, additive only — the existing `generate`/`stream`/
`embed`/`health` surface, every existing connector, and every existing caller
(`reasoning-engine`) are unaffected. `communication-engine` calls
`transcribe`/`synthesize` through the same served Event-Bus RPC pattern
`reasoning-engine` already uses for `generate` (ADR-020's established precedent,
not a new communication pattern).

### 0.4 What addressee detection is not, yet

Phase 2D-B (Identity & Presence) and Phase 2D-C (the addressee-detection fusion
described in the Master Blueprint §5) do not exist yet. This document does not
implement wake-word spotting, speaker recognition, or any addressee judgment.
Instead, 2D-A's own acceptance criteria (Master Blueprint, roadmap §Phase 2D) are
satisfied with an honest interim mechanism: an explicit **trigger** per channel —
a send action in the text channel, a push-to-talk-style explicit start/stop signal
in the voice channel (client-side, not acoustic wake-word detection) — that starts
a turn. There is no silent "always listening, deciding whether to respond" behavior
in this phase; that begins in 2D-B/2D-C. This is stated plainly in §6 and §16
rather than left for a reader to assume is more capable than it is (Doc 23 §6:
"claiming a capability NOVA does not have" is a permanently forbidden behavior —
this section exists specifically so this document never implies one).

### 0.5 Relationship to `personality-engine`: real, load-bearing, built alongside

Unlike the deferred dependencies in §0.6, `personality-engine` is built in this
same sub-phase (Master Blueprint §4.1) and is a genuine synchronous dependency of
this document's response pipeline (§7, §8.3) from day one — Phase 2D's own
inherited acceptance criterion ("personality stays recognizably consistent across
at least two different underlying models") is a 2D-A criterion, not deferred.
`communication-engine` never renders text without first passing it through
`personality-engine`'s `personality.validate_response` RPC.

### 0.6 Relationship to `digital-twin-engine` and `perception-engine`: deferred, not designed around

Neither engine exists this phase (Phase 2D-D and Phase 2D-B respectively).
`communication-engine` defines the **ports** its Master-Blueprint-specified
integrations will use — `digital_twin.preferences.get` (consumed in 2D-C, not
2D-A: nothing in this document's own response pipeline calls it) and
`perception.*` signal subscriptions (consumed in 2D-C's addressee fusion, not
2D-A) — as forward-declared interfaces in `nova-contracts`, versioned from day one
per ADR-024, but this document's own runtime never calls them. This mirrors
Reasoning Engine's own precedent in Phase 2B, whose design doc explicitly deferred
Planning Engine integration because Planning didn't exist yet, rather than
building a speculative integration against an engine with no implementation to
validate against.

## 1. Overall architecture

```
                    ┌─────────────────────────────────────────────┐
                    │              communication-engine             │
                    │                                                │
  Text channel ────▶│  Channel Adapters (text, voice)                │
  Voice channel ───▶│         │                                      │
                    │         ▼                                      │
                    │  Transport VAD (voice only, §4)                │
                    │         │                                      │
                    │         ▼                                      │
                    │  Session Manager ──── ConversationSession       │
                    │  (10-state machine)      (Postgres, §10)        │
                    │         │                                      │
                    │         ▼                                      │
                    │  Communication Lifecycle Pipeline (§6)          │
                    │   Receive→Understand→RetrieveContext→           │
                    │   DetermineIntent→SelectStrategy  (pass-through │
                    │   this phase, §0.1)                             │
                    │         │                                      │
                    │         ▼                                      │
                    │  communication.intent gate (§7, ADR-005) ◀──────┼──── events from
                    │         │                                      │     Reasoning/AI
                    │         ▼                                      │     Orchestration/
                    │  Personality validate/style RPC (§8.3) ─────────┼───▶ personality-engine
                    │         │                                      │
                    │         ▼                                      │
                    │  Generate/Deliver (STT/TTS via §0.3 RPC) ───────┼───▶ ai-model-orchestration
                    │         │                                      │        -engine (extended)
                    │         ▼                                      │
  Text channel ◀────│  Channel Adapters (delivery)                   │
  Voice channel ◀───│                                                │
                    └─────────────────────────────────────────────┘
                         │                    │
                         ▼                    ▼
                  Memory Engine (session   World Model Engine
                  archival, §8.6)          (context retrieval, §8.7)
```

Five internal components, each independently testable:

1. **Channel Adapters** — one per channel (`TextChannelAdapter`,
   `VoiceChannelAdapter`), implementing a common `ChannelAdapter` protocol
   (`receive`, `deliver`, `capabilities`) so a future channel (Bible Part 13 names
   email, SMS, AR, robotics) is additive, never a redesign (Risk-mitigation
   pattern already established for `perception-engine`'s Sensor Abstraction
   Layer, Master Blueprint §9.1 — applied here to channels instead of sensors).
2. **Transport VAD** — voice-channel-only, acoustic energy/silence detection
   driving audio buffering and barge-in. Explicitly **not** the same thing as
   Phase 2D-B's future presence/attention-based signals (§3.4 draws this boundary
   precisely) — this is a dumb, local, low-latency mechanism with exactly one job:
   know when the user started and stopped producing audio.
3. **Session Manager** — owns the `ConversationSession` state machine (§3) and its
   persistence.
4. **Communication Lifecycle Pipeline** — the ten-step sequence (§6), mostly
   pass-through this phase.
5. **`communication.intent` Gate** — the ADR-005 enforcement point (§7).

## 2. Responsibilities of every component

| Component | Owns | Never does |
|---|---|---|
| Channel Adapters | Wire-format translation (WebSocket frames, audio codec framing) to/from a channel-neutral internal message shape | Session state, content generation, personality validation |
| Transport VAD | Voice activity boundaries for streaming/barge-in | Speaker identity, presence, attention (Phase 2D-B) |
| Session Manager | `ConversationSession` state machine, persistence, restart recovery | Content generation, channel wire formats |
| Lifecycle Pipeline | Sequencing the ten stages; this phase, stages 4–5 (Determine Intent, Select Strategy) are direct pass-through | Policy intelligence (2D-C) |
| Intent Gate | ADR-005 enforcement: every outbound utterance is validated, personality-filtered, and logged before delivery | Deciding *what* to say (that's the event publisher's content) |

## 3. The Conversation Session — data model & state machine

### 3.1 The ten states

Bible Part 13's ten conversation states, implemented as an explicit state machine
(not implicit flags), because the "Live Communication Dashboard" (Part 13) and any
future UI must be able to render the *real* current state, not an approximation
(Bible Part 6's "never generate fake animations" principle, applied to
conversation state rather than cognitive visualization):

```
Idle ──trigger (§0.4)──▶ Listening ──audio/text captured──▶ Thinking
  ▲                                                              │
  │                                                     content ready
  │                                                              ▼
Completed ◀──close──── Waiting ◀──clarification (2D-C, N/A yet)  Speaking
  ▲                        ▲                                     │
  │                        └─────────── delivered ────────────────┘
  │
Paused ◀──user pause/session pause API──── (any active state)
  │
  └──resume──▶ (state prior to pause)

Executing, Monitoring, Learning: reserved states this phase (§3.3) —
transitions into them are not exercised by 2D-A's own pipeline (no task
execution or background learning exists to occupy them yet), but the state
machine defines them now so Phase 3 (task execution) and Phase 2D-D/4
(learning) do not require a schema migration to use them later.
```

### 3.2 `ConversationSession` — required fields

| Field | Type | Notes |
|---|---|---|
| `session_id` | UUID | Primary key |
| `user_id` | UUID | Single-user default (ADR-025) |
| `channel` | `"text" \| "voice"` | Extensible enum — see §3.5's forward-compat requirement |
| `device_id` | UUID | **Present from day one even though only one device is ever populated this phase** — Master Blueprint Risk §11.6 names this explicitly: retrofitting a device dimension later is a migration, including it now costs nothing |
| `state` | one of the ten states (§3.1) | |
| `created_at`, `updated_at` | timestamp | |
| `turns` | ordered list of `ConversationTurn` | See §3.3 |
| `objective` | text, nullable | Bible Part 13's Conversation Memory field |
| `pending_questions` | list, nullable | Populated by 2D-C's Clarification Engine — schema present, unused this phase |
| `closed_at` | timestamp, nullable | Set when session transitions to `Completed` |

### 3.3 `ConversationTurn`

One row per user input or NOVA output within a session: `turn_id`, `session_id`,
`direction` (`"inbound" | "outbound"`), `content` (text, always present — voice
turns store the transcript, never only audio), `channel`, `personality_validated`
(bool, outbound only, §8.3), `created_at`. Raw audio itself is **not** persisted
in this schema — §15 states why (data minimization; the transcript is NOVA's
working representation, matching Bible Part 11's "local processing default"
discipline already established for Perception).

### 3.4 Transport VAD vs. Phase 2D-B's presence/attention signals

Named explicitly because the two are easy to conflate. Transport VAD (§1
component 2) answers *"is there audio energy right now"* — a signal-processing
fact, with no notion of who is speaking or whether they're addressing NOVA. Phase
2D-B's future presence/attention/gaze signals answer *"who is here and are they
engaged with NOVA"* — a Perception Engine responsibility per Bible Part 11's own
independence boundary (Master Blueprint §4.2). Transport VAD is a private
implementation detail of the audio pipeline (§4); it is never published as an
event, never consumed by another engine, and is explicitly **not** upgraded into
an addressee signal by this document. When Phase 2D-B ships, its presence/
attention signals arrive as separate, richer events that 2D-C's addressee fusion
consumes — Transport VAD is not replaced, because its job (buffering/barge-in
timing) is unrelated to addressee detection and continues unchanged.

### 3.5 Persistence and restart recovery

`ConversationSession` and its `turns` are written to Postgres synchronously on
every state transition (not batched) — Bible Part 13's "Conversation state should
survive restarts" is a correctness requirement, not a performance-optimization
target. On `communication-engine` restart, any session not in a terminal state
(`Completed`) is resumed: reloaded, transitioned to `Paused` if no channel
connection is currently live, and made resumable through the `Resume Conversation`
API (§12). No session silently disappears on a crash — this is the same recovery
discipline Phase 1's engines were held to (killing and restarting mid-write
resumes without data loss).

## 4. The audio pipeline

```
Microphone (client) → Voice Channel Adapter → Transport VAD → audio buffer
  → ai_model.transcribe RPC (§0.3) → transcript → Session Manager (as inbound turn)
  → ... (lifecycle pipeline, personality validation) → response text, chunked
  → ai_model.synthesize RPC (§0.3, non-streaming, one call per chunk) → audio
  → Voice Channel Adapter → speaker (client)
```

**Streaming input; chunked-call output, not a single streaming call.**
`transcribe` may be called incrementally on partial audio (final transcript on
VAD-detected end-of-utterance) — a genuine transport-level stream in the input
direction. In the output direction, per §0.3's correction, `synthesize` is a
non-streaming RPC (`EventBus.request()` cannot carry a stream — ADR-004);
`communication-engine` achieves the same perceived immediacy Bible Part 13's
"Streaming Communication" calls for (*"the user should receive useful
information immediately"*) by calling `synthesize` once per response chunk
(sentence/phrase) as the response text becomes available, delivering each
chunk's audio to the Channel Adapter as soon as its own RPC returns, rather
than waiting for the complete response to synthesize as one call. This
directly serves Master Blueprint Risk §11.1's latency-budget mitigation
exactly as a transport-level stream would, without requiring one.

**Barge-in (unconditional, per Master Blueprint §13.4 — Interruptibility).** While
NOVA is in the `Speaking` state, incoming audio above the Transport VAD threshold
**immediately and unconditionally**: (1) stops issuing further per-chunk
`synthesize` calls and discards any audio already returned but not yet played
— not after the current chunk finishes playing, within one Transport VAD
detection interval — (2) transitions the session out of
`Speaking`, (3) begins buffering the new input as the start of a new turn. This is
a transport-level mechanic only — 2D-A does not decide whether the interruption
was *appropriate* (that policy judgment is 2D-C's, per Doc 22 Principles 2–4) —
but the mechanical stop itself is never negotiable, never rate-limited, and never
deferred to finish a thought: the user must always be able to make NOVA stop
talking, without exception, in every future phase that touches this pipeline.

**Transient audio loss (per Master Blueprint §13.5 — Conversation continuity).**
A short gap in the incoming audio stream during an in-progress utterance — a
brief network hiccup, a moment of dropped frames — is not treated as an
end-of-utterance or a failed turn. The audio buffer tolerates a configured short
gap (bridging silence rather than immediately finalizing the transcript on any
detected pause) before Transport VAD concludes the utterance actually ended. This
is distinct from §9's channel-disconnect handling (a full connection loss, which
does transition the session to `Paused`) — a transient gap inside an otherwise-
live connection should never surface to the user as a dropped turn or a reset
conversation when the underlying connection never actually went down.

**Provider failure.** If the selected STT/TTS connector fails (per §0.3's
`ai_model.transcribe`/`synthesize` RPC), the Model Router's existing fallback
chain applies unchanged — this is not a new failure-handling pattern, it is
`ai-model-orchestration-engine`'s already-built fallback behavior, now exercised
for a second modality pair.

## 5. Channel abstraction — Communication Adapters

```python
class ChannelAdapter(Protocol):
    channel_type: Literal["text", "voice"]
    async def receive(self) -> InboundMessage: ...
    async def deliver(self, message: OutboundMessage) -> None: ...
    def capabilities(self) -> ChannelCapabilities: ...  # streaming: bool, audio: bool, ...
```

Two concrete adapters ship this phase: `TextChannelAdapter` (WebSocket, per
`ws-gateway`) and `VoiceChannelAdapter` (WebSocket audio frames, wrapping the
pipeline in §4). Bible Part 13's full channel list (notifications, email, SMS,
smartwatch, AR, VR, robotics) is **explicitly not built this phase** (Master
Blueprint §3.2) — the `ChannelAdapter` protocol exists specifically so adding one
is implementing the protocol, never redesigning the Session Manager or Lifecycle
Pipeline around a new channel's quirks.

## 6. The Communication Lifecycle — what's real vs. deferred this phase

Bible Part 13's ten-step lifecycle, honestly scoped (Doc 23 §6's "claiming a
capability NOVA does not have" forbids overstating any of these):

| Step | 2D-A implementation |
|---|---|
| Receive | Real — Channel Adapter → Transport VAD/text parse |
| Understand | Real, but shallow: transcript/text captured, no NLU beyond what STT/the eventual content-generating engine (Reasoning, via events) provides |
| Retrieve Context | Real — session history + one World Model context call (§8.7); no Digital Twin preferences (§0.6) |
| Determine Intent | **Pass-through this phase** — every inbound message becomes a `communication.turn.received` event; deciding what it *means* is Reasoning Engine's job via the existing event chain, not this engine's |
| Select Communication Strategy | **Pass-through this phase** — channel and style default to the requesting channel and `personality-engine`'s default style; no adaptive strategy selection (2D-C) |
| Generate Response | Delegated — this engine never generates content itself (§0.2); it receives already-generated content via `communication.intent` events |
| Choose Communication Channel | Real, but trivial this phase — same channel the turn arrived on (multi-channel routing is Phase 2D-C+/5 scope) |
| Deliver Response | Real — §7's gate, then the Channel Adapter |
| Monitor Feedback | Stub — turns are recorded (§3.3); no feedback-driven learning loop reads them yet (that's Phase 2D-D's `digital-twin-engine`) |
| Learn | **Not implemented this phase** — no engine exists yet to learn from these sessions (2D-D); sessions are archived to Memory Engine (§8.6) so nothing is lost in the meantime |

## 7. The `communication.intent` gate — ADR-005 enforcement

Every candidate outbound utterance, from any source (Reasoning Engine's content,
a future agent's status update, this engine's own clarification stub), arrives as
a `communication.intent.deliver` request (§11). The gate, in order:

1. **Schema/session validation** — the `session_id` exists and is not `Completed`.
2. **Personality validation** — synchronous call to `personality.validate_response`
   (§8.3). On success, the (possibly style-adjusted) content and a
   `personality_validated=true` flag proceed. On RPC failure/timeout, §9's
   documented fallback applies — the gate never blocks indefinitely.
3. **Delivery** — routed to the requesting session's current Channel Adapter,
   recorded as an outbound `ConversationTurn` (§3.3).

No other path to a Channel Adapter's `deliver` method exists in this codebase —
this is enforced structurally (only the gate holds a reference to Channel Adapter
instances) and by the import-boundary linter (ADR-004), not merely by convention.

## 8. Interaction with other engines

### 8.1 AI Model Orchestration Engine (extended this phase, §0.3)

`communication-engine` calls `ai_model.transcribe` (voice input) and
`ai_model.synthesize` (voice output) as served Event-Bus RPCs — never a
Whisper/Piper SDK directly. This is the same integration pattern
`reasoning-engine` already uses for `ai_model.generate`, applied to the two new
modalities this phase adds.

### 8.2 Content-source engines (Reasoning Engine, and later Planning/agents)

`communication-engine` never asks another engine what to say. It subscribes to
`communication.intent.deliver` requests (§7) — the content-producing engine
initiates. This keeps the dependency direction correct: `communication-engine`
does not need to know Reasoning Engine exists; Reasoning Engine (or any future
producer) depends on the gate's published contract, not the reverse.

### 8.3 `personality-engine` (real dependency, §0.5)

Two served RPCs consumed synchronously in the intent gate (§7):
`personality.validate_response` (consistency/tone check, may adjust phrasing) and
`personality.style.select` (style-palette selection, Bible Part 13's
"Communication Styles," applied per §6's "Select Communication Strategy" — trivial
default selection this phase, per §6's table). Both are specified in full in
[02-personality-engine.md](02-personality-engine.md) §7.

### 8.4 `digital-twin-engine` (deferred, §0.6)

Port defined (`digital_twin.preferences.get`) in `nova-contracts`, versioned,
unused. No 2D-A code path calls it.

### 8.5 `perception-engine` (deferred, §0.6)

No integration this phase. 2D-A's explicit-trigger interim (§0.4) replaces what
Perception's wake/presence signals will eventually provide.

### 8.6 Memory Engine (Phase 1)

On session close (`Completed`), a summary write: objective, turn count, key
decisions/preferences noted during the session (Bible Part 13's Conversation
Memory list, to the extent 2D-A actually populates it — mostly `objective` and
raw turns this phase, since Decisions/Corrections/Feedback extraction is a
Reasoning/2D-C-level judgment this document doesn't make). This is the *only*
long-term retention of conversation content — `communication-engine` itself
retains sessions only as long as operationally useful (§15).

### 8.7 World Model Engine (Phase 1)

One context call per session creation (`world_model.context.request`, already
built, sub-20ms p95 per ADR-012) — current time, active project if known. Not a
new integration pattern, just a new caller of an existing, proven RPC.

## 9. Failure handling

| Failure | Behavior |
|---|---|
| `personality.validate_response` RPC timeout/unavailable | Deliver the unvalidated content with `personality_validated=false` recorded, using a hardcoded minimal-safe default style (plain, unstyled text) — never silence (Doc 22 Principle 3; Master Blueprint Risk §11.7). Logged as a degraded-mode event for observability. |
| `ai_model.transcribe`/`synthesize` failure after fallback chain exhausted | Voice channel: deliver a short, honest text-channel-style notice ("voice temporarily unavailable") through the same session if a text-capable adapter is available, else mark the turn failed and surface it in the session state; never a silent drop. |
| Session write (Postgres) failure | Reject the triggering action with an explicit error — never proceed with an unpersisted state transition (violates §3.5's restart-recovery guarantee). |
| Channel Adapter disconnects mid-`Speaking` | Session transitions to `Paused` (§3.1), further per-chunk `synthesize` calls stopped, resumable via `Resume Conversation`. |
| Process crash mid-session | §3.5 — synchronous writes mean recovery reconstructs the session up to its last completed transition; the in-flight turn at crash time is the only possible loss, and it is the *inbound* side only if the crash occurred before that turn was persisted (write-before-process ordering, per §3.5). |

## 10. Data model — `communication` Postgres schema

```sql
CREATE TABLE communication.conversation_session (
    session_id      UUID PRIMARY KEY,
    user_id         UUID NOT NULL,
    channel         TEXT NOT NULL,       -- 'text' | 'voice', extensible per §5
    device_id       UUID NOT NULL,       -- populated, single value this phase (§3.2)
    state           TEXT NOT NULL,       -- one of the ten states, §3.1
    objective       TEXT,
    pending_questions JSONB,             -- schema present, unused this phase (2D-C)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at       TIMESTAMPTZ
);

CREATE TABLE communication.conversation_turn (
    turn_id                 UUID PRIMARY KEY,
    session_id              UUID NOT NULL REFERENCES communication.conversation_session,
    direction                TEXT NOT NULL,   -- 'inbound' | 'outbound'
    content                  TEXT NOT NULL,   -- transcript for voice turns, never raw audio (§3.3, §15)
    channel                  TEXT NOT NULL,
    personality_validated    BOOLEAN,          -- outbound only
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE communication.notification (
    notification_id  UUID PRIMARY KEY,
    user_id           UUID NOT NULL,
    content           TEXT NOT NULL,
    priority          TEXT NOT NULL,    -- minimal enum this phase; Bible's full
                                          -- prioritization intelligence is future scope
    delivered_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

No graph store, no vector store — `communication-engine` owns no long-term
semantic retrieval surface (that's Memory Engine's, §8.6). This mirrors Executive
Cognition's own minimal-schema precedent: a real, if narrow, system of record —
not "never owns data" taken to mean no schema at all.

## 11. Event contracts

RPC pairs (request/reply, served by this engine, consumed by any content-source
engine per §8.2):

- `communication.intent.deliver.request` / `.reply` — the ADR-005 gate (§7).
- `communication.session.create.request` / `.reply`
- `communication.session.close.request` / `.reply`

Published events (subscribed to by Memory Engine §8.6, and by
`digital-twin-engine`/`perception-engine` once they exist, §0.6):

- `communication.session.created`
- `communication.session.state_changed` — payload includes `from_state`,
  `to_state`, enabling the Live Communication Dashboard (Bible Part 13) to reflect
  real state, never fabricated (§3.1).
- `communication.session.completed`
- `communication.turn.received` — inbound turn recorded (§6's "Determine Intent"
  pass-through publishes this for Reasoning Engine to subscribe to).

Every payload carries `schema_version: int = 1` from first commit (ADR-024),
registered via `nova_contracts.registry.register_payload`, subject-named
`communication.<domain>.<action>` — identical convention to every prior engine's
contracts module (`executive.*`, `reasoning.*`, `ai_model.*`).

New `ai-model-orchestration-engine` contracts (§0.3, additive to the existing
`ai_model.*` set): `ai_model.transcribe.request` / `.reply`,
`ai_model.synthesize.request` / `.reply` — both non-streaming, called once per
response chunk to achieve perceived streaming (§0.3, §4).

## 12. APIs exposed

Bible Part 13's "Communication APIs" list, realized as `communication-engine`'s
FastAPI surface (external callers: `apps/web-client`, `api-gateway`/`ws-gateway`):

All routes are served under the `/v1/communication` prefix, per the project-wide
`/v1/<domain>/...` REST convention (Phase 2D-A Gate Review correction — bare
paths were an inconsistency against every other engine's own API surface):

| Endpoint | Method | Notes |
|---|---|---|
| `/v1/communication/sessions` | POST | Create Session |
| `/v1/communication/sessions/{id}/messages` | POST | Send Message (text) |
| `/v1/communication/sessions/{id}` (WebSocket) | — | Voice channel + streaming text, via `ws-gateway` |
| `/v1/communication/sessions/{id}/pause` | POST | Pause Conversation |
| `/v1/communication/sessions/{id}/resume` | POST | Resume Conversation |
| `/v1/communication/sessions/{id}` | DELETE | Close Session |
| `/v1/communication/sessions/{id}/context` | GET | Retrieve Context |
| `/v1/communication/notifications` | POST | Generate Notification (minimal, §10) |

`/internal/health`, `/internal/readiness`, `/internal/metrics` remain
unprefixed by `/v1` — the ops/probe surface, not a versioned domain API.

`Broadcast Update` and `Synchronize Devices` (Bible Part 13) are **not exposed
this phase** — both require multi-device continuity, explicitly out of Phase 2D's
scope (Master Blueprint §3.2); the `device_id` field (§3.2) exists so adding them
later doesn't require a schema change.

## 13. Performance considerations

Per Master Blueprint Risk §11.1: the full path from inbound audio to first
audible response byte stacks Transport VAD → `ai_model.transcribe` →
lifecycle pipeline → `communication.intent` gate (including the
`personality.validate_response` RPC) → `ai_model.synthesize` (first chunk's
call). Two required mitigations, both acceptance criteria for this phase, not
future optimizations:

1. **Chunked calls, not one call for the whole response** (§4) — the first
   response chunk (sentence/phrase) is sent to `ai_model.synthesize` and its
   audio delivered to the Channel Adapter as soon as it's available, before
   later chunks of the response even exist yet, achieving the same perceived
   immediacy a transport-level stream would.
2. **Fast-path acknowledgments** — short, low-stakes acknowledgment content (e.g.
   backchannel responses) may skip the full `personality.validate_response` round
   trip using a pre-validated, cached minimal style profile (`personality-engine`
   §8's `Identity Snapshot`), refreshed periodically rather than fetched
   synchronously per utterance. Substantive content always takes the full path.

Per Master Blueprint §13.2 (Low latency is part of NOVA's personality): wherever
an implementation choice in this pipeline has more than one option that satisfies
correctness, the lower-perceived-latency option is the required choice, not an
optional tuning pass revisited later — this governs, for example, choosing
streaming-capable local connectors (§0.3) over otherwise-equivalent
higher-latency alternatives during implementation.

## 14. Scalability considerations

Session state is keyed by `session_id`, horizontally partitionable by user
(ADR-025's single-user default means this phase's real deployment is one
concurrent session per instance; the schema does not assume that, so Phase 8's
multi-tenant scale-out is not blocked). Channel Adapters hold no session state
themselves (`Session Manager` is the single source of truth), so adapter
instances can be added/removed without session loss, mirroring `ws-gateway`'s own
existing connection-handling pattern.

## 15. Security considerations

- **Session validation** (Bible Part 13 "Security") — every API/WebSocket call
  authenticated against `nova-auth`'s existing local-device identity (Phase 0/2),
  no new auth mechanism introduced.
- **Raw audio is not persisted** (§3.3) — transcripts only, minimizing biometric/
  sensitive-audio retention surface, consistent with Doc 22 Principle 8
  (privacy-by-design) even though the *identity* half of that principle belongs
  to Phase 2D-B, not this document.
- **Encrypted transport** — WebSocket connections over TLS, matching every other
  `ws-gateway` consumer.
- **Notification content** — no sensitive-information-masking policy engine this
  phase (Bible Part 13's full "Communication Policies" — e.g. "never read
  sensitive information aloud" — is a 2D-C policy-intelligence concern); §0.4
  applies the same honesty: this document does not claim that capability yet.

## 16. Doc 22 / Doc 23 compliance

Required by both documents' "How this document is used" sections.

| Decision | Principle |
|---|---|
| §0.2 intent gate is the only path to output | Doc 22 Principle 3 (speaking is a decision) |
| §0.4 explicit trigger, no silent always-on addressee guessing | Doc 22 Principle 6 (context over keywords) — honestly deferred, not faked |
| §4 barge-in is mechanical, not a policy judgment | Doc 22 Principles 2–4 (silence/interruption judgment stays 2D-C's) |
| §9 personality-RPC-unavailable fallback never produces silence | Doc 22 Principle 3; Doc 23 §6 ("unnecessary interruptions" is about speaking without cause, not the inverse — but an *outage-caused* silence is equally a violation of "silence is intentional," not accidental) |
| §7 every response passes personality validation before delivery | Doc 23 §2 (constant traits enforced structurally, not by convention) |
| §3.3 raw audio not retained; §0.4 no overclaimed capability | Doc 23 §6 (forbidden: claiming a capability NOVA lacks) |
| §3.2 `device_id` present from day one | Doc 22 Principle 13 (the room should eventually become part of the interface — this document does not foreclose it) |
| §1's single intent-gate output path regardless of internal composition | Master Blueprint §13.1 (conversation must always feel continuous) |
| §13's streaming/fast-path requirements and the lowest-latency tie-break rule | Master Blueprint §13.2, §13.3 (latency is part of personality; streaming first) |
| §4's unconditional barge-in stop | Master Blueprint §13.4 (interruptibility) |
| §4's transient audio-gap tolerance | Master Blueprint §13.5 (conversation continuity through transient loss) |
| §0.6's deferred ports, §3.2's forward-populated `device_id`, §5's channel-adapter protocol | Master Blueprint §13.6 (progressive capability) |
| §3.2 exactly two channels, §0.4's honest interim over a half-built addressee detector | Master Blueprint §13.7 (quality over feature count) |

## 17. Testing strategy

- State-machine tests: every valid/invalid transition in §3.1's diagram, including
  restart recovery (§3.5) — kill the process mid-session, restart, assert correct
  resumption.
- Barge-in tests: inject audio during `Speaking`, assert stream cancellation and
  no audio loss on the new input, and assert cancellation latency stays within
  one Transport VAD detection interval (Master Blueprint §13.4's "unconditional,
  not eventually" requirement, measured, not just asserted qualitatively).
- Transient audio-gap tests (Master Blueprint §13.5): inject a short mid-utterance
  audio gap below the configured tolerance, assert the turn completes normally
  with no premature finalization; inject a gap above tolerance, assert normal
  end-of-utterance handling — the boundary itself, not just the two extremes.
- Degraded-mode tests (§9): `personality-engine` RPC forced to time out, assert
  delivery still occurs with the documented fallback, never silence — the
  specific test the Master Blueprint's Risk §11.7 names as required.
- Contract tests: every `communication.*` and new `ai_model.transcribe`/
  `synthesize` payload, plus a `FakeSpeechConnector`-driven integration suite
  (mirroring 2A's `FakeModelConnector` pattern) for deterministic CI, with a
  separate manually-triggered live-Whisper/Piper smoke test.
- E2E: text round-trip (send → personality-validated reply) and voice round-trip
  (speak → transcribe → reply → synthesize → hear), both exercising the full
  pipeline in §1's diagram.

## 18. Future extension points

- **Phase 2D-C** extends this same service: `communication.intent` gate gains
  real addressee-fusion input (consuming Phase 2D-B's signals), §6's
  pass-through steps (Determine Intent, Select Strategy) gain real policy logic,
  the Clarification Engine activates `pending_questions` (§3.2, already
  schema-present), and `digital_twin.preferences.get` (§0.6's deferred port)
  starts being called for adaptive response-length/tone selection.
- **Phase 3 (NAOS)**: agents' progress/results become new
  `communication.intent.deliver` producers (§8.2) — no gate change required,
  since the gate is producer-agnostic by design.
- **Phase 4**: `perception-engine`'s real signals replace §0.4's explicit-trigger
  interim; `digital-twin-engine`'s full preference model deepens what 2D-C
  already wired up.
- **Phase 5**: `Broadcast Update`/`Synchronize Devices` (§12) implemented once
  multi-device continuity is in scope, using the `device_id` dimension already
  present in every session record.
