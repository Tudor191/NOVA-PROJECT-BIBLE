# Phase 2D-C Closure — Priority 4 Implementation Proposal: the "start listening" cross-context mechanism

**Status: PROPOSAL ONLY. Not approved. No production code, test, contract,
ADR, or existing documentation was modified to produce this document.**
Per direct instruction, this is a research/design deliverable — implementation
does not begin until every fork in §13 is explicitly resolved by the user.

**Scope of this review: Priority 4 only.** Priorities 1, 2, and 3 are
implemented and closed (see their own Gate Reviews) and are not reopened
here except to verify a prerequisite. Priorities 5 and 6 are not touched,
referenced as implementation targets, or expanded into. Phase 2D-D has not
started.

**Headline finding: the closure document's own §6 design for Priority 4 is
directionally correct on its central claim (the warm-case mechanism can be
built entirely in-process, inside communication-engine, with no new
cross-engine contract) but contains two inaccuracies about the current
implementation, and this review's own tracing surfaced one significant,
pre-existing, unrelated defect in the already-shipped `BargeInSignal`
mechanism the closure document proposes mirroring.** All three are detailed
in §1 and carried through into the fork list (§13).

---

## 1. Current-state findings — re-verified directly against code, per instruction

### 1.1 The exact intended path, traced end to end

```
perception.addressee_signal.candidate (Event Bus, already publishes
  user_id since Priority 2)
  -> communication-engine's make_addressee_signal_handler
     (already subscribed, already computing FusionOutcome via fuse())
  -> [MISSING] resolve payload.user_id -> a target session_id
  -> [MISSING] decide whether/how to trigger that session
  -> SessionRegistry (in-process, same communication-engine instance)
  -> api/websocket.py's receive loop for that session_id's live connection
  -> local `turn_active = True` (mirrors client-sent TRIGGER_START)
  -> user's actual speech arrives as AUDIO_CHUNK messages
  -> VAD detects end-of-utterance -> transcribe -> record_inbound_turn
  -> real FSM TRIGGER + CAPTURED, communication.session.state_changed fires
  -> Priority 3's existing conversation_orchestration takes over from there
```

Everything from `record_inbound_turn` onward already exists and is already
tested (Priorities 1-3). Priority 4's entire scope is the two `[MISSING]`
steps above and the mechanism that connects them to the receive loop.

### 1.2 `BargeInSignal` — exact semantics (investigated directly, not assumed)

`domain/speech.py::BargeInSignal` is a minimal two-method class:
`trigger()` sets an internal flag; `is_set()` reads it. **There is no
`clear()`/`reset()` method anywhere on this class, and no call site resets
one after construction.** `SessionRegistry.register()` constructs exactly
one `BargeInSignal()` per WebSocket connection (not per turn); every
subsequent `deliver_content_to_session` call for that connection's
lifetime fetches the *same* instance via `get_barge_in_signal(session_id)`.

Consumption happens in exactly one place: `domain/speech.py::speak_response`,
called from `intent_gate.deliver_intent` — itself called only from
`events/handlers.py::deliver_content_to_session`, which runs as part of
Priority 3's background turn-delivery task, **not** inside `api/websocket.py`'s
receive loop. **`api/websocket.py`'s receive loop never reads
`barge_in_signal` at all** — confirmed by exhaustive grep; the loop's only
per-tick timeout behavior today is feeding the VAD when a turn is already
active. It *sets* the signal (via `trigger_barge_in`, in the `AUDIO_CHUNK`
branch, when `state is SPEAKING`), but never polls it.

**This directly contradicts the closure document's own §6.1/§6.3 claim**
("`api/websocket.py`'s receive loop checks this signal on the same poll
cadence it already checks `barge_in_signal`") — no such existing poll
exists to reuse. Building the warm-case mechanism as designed requires
adding the **first** per-tick, in-loop check of a `SessionRegistry`-held
signal inside the receive loop itself — a small, well-justified addition
(§3), but a new pattern, not literally already wired.

### 1.3 A significant, pre-existing, unrelated defect this review surfaced

Tracing `BargeInSignal`'s full consumption path (per instruction: "race
conditions between start-listening, barge-in, thinking, speaking, and
session completion") surfaced a real bug in already-shipped, already-
Gate-Reviewed code, **not caused by and not part of Priority 4's own
scope**, disclosed here because it directly bears on how much this
review can trust `BargeInSignal` as a proven precedent to mirror:

1. A barge-in occurs: `api/websocket.py`'s `AUDIO_CHUNK` branch calls
   `trigger_barge_in(session_id)` (sets the shared, connection-lifetime
   `BargeInSignal` — permanently, since nothing ever clears it) and
   `session_lifecycle.mark_barge_in(...)`, which applies the FSM's
   `BARGE_IN` event, moving the session `SPEAKING -> LISTENING` and
   **persisting that state change immediately.** `turn_active = True` is
   set in the same branch.
2. The user's continuing speech (the utterance that caused the barge-in)
   keeps accumulating into `audio_buffer` via the loop's existing
   `if turn_active:` block. When VAD detects end-of-utterance,
   `_finalize_utterance()` calls `session_lifecycle.record_inbound_turn`.
3. `record_inbound_turn` **unconditionally applies `TRIGGER` first, then
   `CAPTURED`** (`domain/session_lifecycle.py:123-134`) — written assuming
   the session is always in `IDLE`/`WAITING` when a turn is captured (true
   for the normal client-`TRIGGER_START` flow, since that message never
   touches persisted state). But after step 1, the session is already in
   `LISTENING`, and **`(LISTENING, TRIGGER)` is not a defined transition**
   (`domain/state_machine.py:69-83`) — `transition()` raises
   `InvalidTransitionError`.
4. **Nothing catches this in the WebSocket path.** `api/sessions.py` catches
   `InvalidTransitionError` around its own HTTP calls to
   `record_inbound_turn`/`pause_session`/`resume_session`; `events/handlers.py`
   catches it around `mark_content_ready`/`mark_delivered` (the *delivery*
   side). **`api/websocket.py` imports/catches `InvalidTransitionError`
   nowhere.** The exception propagates out of `_finalize_utterance()`,
   out of the receive loop's `while True` body, past the `except
   WebSocketDisconnect` clause (which does not match a `ValueError`
   subclass), and out of `session_websocket` itself — the `finally:` block
   still runs (unregisters the session, pauses it), but the connection
   terminates via an unhandled-exception path rather than a clean one.

**Net effect: today, the very first user utterance following any barge-in
in a voice session cannot be successfully recorded** — it crashes that
WebSocket connection instead. No integration test exercises this exact
sequence (`test_intent_gate.py` unit-tests `deliver_intent` in isolation
with caller-supplied session state; `test_state_machine.py` unit-tests the
transition table directly; neither drives the real `api/websocket.py` loop
through an actual barge-in-then-continue sequence), which is why this has
not previously surfaced. This is orthogonal to Priority 4's own trigger
mechanism but lives in the exact file/pattern Priority 4 is asked to
extend — see Fork E (§13) for how this review proposes handling it.

### 1.4 `SessionRegistry` and session lifecycle

`session_registry.py` (top-level, not `domain/` — needs `ChannelAdapter`/
`BargeInSignal` instances, framework-adjacent) is a single per-process
`SessionRegistry`, keyed entirely by `session_id`:
`_adapters: dict[UUID, ChannelAdapter]`, `_barge_in_signals: dict[UUID,
BargeInSignal]`. **It has no `user_id`-keyed index or lookup method of any
kind.** `is_connected(session_id) -> bool` exists and is exactly what §6.3's
design needs — but only once a `session_id` is already known.

**This corrects the closure document's own dependency-graph prose (§2),
which describes Priority 4 as using "SessionRegistry lookup keyed by
user_id" — no such capability exists.** Resolving `payload.user_id` (now
present on every candidate signal since Priority 2) to a target
`session_id` is a genuinely unaddressed prerequisite, not an
already-solved detail the closure document assumed correctly. See §2 and
Fork B/C (§13).

`CommunicationRepository` (the persistence port) has `get_session(session_id)`
(by primary key) and `list_non_terminal_sessions()` (all non-terminal
sessions, every user — already used by restart recovery in `main.py`, and
already implemented by both `FakeCommunicationRepository` and
`PostgresCommunicationRepository`) — **no `user_id`-filtered query exists
either.**

`ConversationSession.user_id` is a required field, and **nothing enforces
at most one non-terminal session per user** — `api/sessions.py::create_session`
performs no uniqueness check. `session_registry.py`'s own docstring cites
design doc §14: "this phase's real deployment is one concurrent session
per instance" (ADR-025's single-trusted-user default) — **this is a stated
expectation about the real deployment, not a schema- or code-enforced
invariant.** Multiple concurrent, connected, non-terminal sessions for the
same `user_id` (e.g., a voice-channel smart-speaker session and a
text-channel phone session open simultaneously) is a real, reachable state
in the current data model, even though it is not the common case this
phase targets. This is the "what happens when multiple sessions exist"
question named explicitly in the task — see Fork C.

### 1.5 The FSM, and what "start listening" can and cannot mean today

`domain/state_machine.py`'s `_TRANSITIONS` table defines `TRIGGER` as legal
only from `IDLE` and `WAITING` (both -> `LISTENING`). The client-sent
`InboundMessageKind.TRIGGER_START` (`api/websocket.py:148-152`) **does not
call the FSM at all** — it only flips the receive loop's own local
`turn_active` closure variable and resets the VAD/audio buffer. The
persisted `ConversationSession.state` only actually advances
(`IDLE`/`WAITING -> LISTENING -> THINKING`) later, atomically, inside
`record_inbound_turn`, once content has actually been captured and
transcribed. **This part of the closure document's §6.1/§6.4 claim is
accurate** and is the correct mental model for what a server-triggered
equivalent must do: flip the same local flag, touch no persisted state
directly.

Consequence, confirmed by direct trace, not previously stated by the
closure document: **the client-sent `TRIGGER_START` path has no state
guard** — nothing stops a client sending it while the session is actually
`THINKING`/`SPEAKING`, which (per §1.3's mechanism) would eventually hit the
identical unguarded `InvalidTransitionError` crash on capture. A
server-triggered mechanism that reuses this same unguarded path would
inherit and could amplify that exposure (a wrongly-timed activation is now
also reachable without a possibly-malicious/buggy client). §3 proposes an
explicit state guard Priority 4's own mechanism should apply that the
existing client-facing path does not — see Fork D.

### 1.6 Addressee fusion — what already flows through it

`domain/addressee_fusion.py::fuse()` (unchanged since Priority 2D-C,
Voice-channel-only by its own docstring — "text has no addressee
ambiguity") produces `FusionOutcome(score, tier, action)` from
`FusionSignals` (`wake_word_matched/confidence`, `identity_id/confidence`,
`gaze_toward_device`, `session_active`) via the same weighted formula
unchanged since it was built: `wake_word=0.35, identity=0.30, gaze=0.20,
session_active=0.15`, `high_threshold=0.70`. `tier=="high"` implies
`action=="activated"` by construction (single threshold branch) — checking
either is equivalent.

`events/handlers.py::make_addressee_signal_handler` **already reads
`payload.identity_id`, `identity_confidence`, `session_active`** (Priority
2's fields) into `FusionSignals` and computes `outcome` — but **does not
read `payload.user_id` at all**, and unconditionally writes
`ConversationDecisionTrace(session_id=None, ...)` regardless of `outcome.tier`.
This matches the handler's own docstring ("Deliberately does not itself
activate a live session") and `ConversationDecisionTrace.session_id`'s own
field docstring ("`None` for a pre-session addressee check... until/unless
the fusion outcome is `HIGH`") — the data model already anticipated this
gap being closed, it just hasn't been yet. **This is the exact, and only,
site Priority 4 needs to extend** — everything upstream of it (fusion
computation, the trace write for every candidate) is unchanged.

`corroborate_identity_confidence` (World Model corroboration) remains
completely unwired, confirmed unaffected by anything Priority 4 proposes —
same disclosed, unwired state Priority 2's own Gate Review left it in.

### 1.7 Text channel is out of scope by construction, not by new decision

`channels/text_adapter.py::TextChannelAdapter.receive()` can only ever
produce `InboundMessageKind.TEXT` — never `TRIGGER_START`/`AUDIO_CHUNK`.
"Start listening" has no meaning for a text session (nothing to start
capturing). Combined with `domain/addressee_fusion.py`'s own "voice channel
only" scope statement, Priority 4's session-resolution step (§3) filters
to `ConversationSession.channel is ChannelType.VOICE` — a direct,
non-forked consequence of how the addressee-fusion signal is already
scoped, not a new policy choice.

### 1.8 ADR-025 / ADR-032 / Doc 22 — re-checked directly, not from memory

- **ADR-032** ("identity confidence is also an authorization signal")
  is explicitly scoped to engines "that gate a **privileged capability**:
  automation, smart-home control, financial operations, security-sensitive
  actions." Starting to listen executes nothing, controls no device,
  authorizes no operation — it is not a privileged capability in this
  ADR's sense, and this proposal introduces no gating logic in
  perception-engine (which ADR-032 §Decision-3 forbids regardless). No
  conflict.
- **ADR-025**'s "single trusted user" default supports treating
  `payload.user_id` as a legitimate basis for session resolution (exactly
  as Priority 2 already established for the payload's own `user_id`
  field), but — per §1.4 — does **not** by itself resolve what to do when
  more than one session exists; that remains a real decision.
- **Doc 22 Principle 5** ("Presence is more important than wake words...
  wake-word detection is one signal, never the only one a future design is
  allowed to depend on") is already satisfied structurally: the trigger
  condition proposed is `FusionOutcome.tier == "high"` (the full weighted
  combination), never a raw wake-word bit alone.
- **Doc 22 Principle 6** ("a false-positive response is strictly worse than
  a false-negative... context over keywords") directly informs the
  no-eligible-session and multiple-eligible-session defaults recommended in
  §13 — silence over a guess.
- **Doc 22 Principle 7** ("every identity judgment is probabilistic... every
  downstream consumer must handle 'uncertain'") is satisfied by writing a
  `ConversationDecisionTrace` for every trigger attempt, matching the
  closure document's own §6.3 item 5, whether or not a session was actually
  activated.
- **Doc 22 Principle 8** (consent, revocable with immediate effect) is
  unaffected — this mechanism only acts on a signal that already passed
  perception-engine's own consent gate (Priority 2) before ever being
  published; it adds no new sensing capability.

---

## 2. Exact missing pieces

1. A way to resolve `payload.user_id` to zero, one, or more target
   `session_id`s — **does not exist anywhere today** (§1.4).
2. A policy for what to do when that resolution finds zero, exactly one, or
   more than one eligible session — **not decided** (§1.4, Fork C).
3. A state guard for which `ConversationSession.state` values are eligible
   to be triggered from — **not decided, and the existing client-facing
   `TRIGGER_START` path itself has no such guard to copy** (§1.5, Fork D).
4. `SessionRegistry` needs a second per-session signal dict
   (`_start_listening_signals`), mirroring `_barge_in_signals`'s existing
   shape, **but with a `clear()` method `BargeInSignal` itself lacks**
   (§1.2/§1.3) — a deliberate, disclosed deviation from "exact mirror,"
   not an oversight.
5. `api/websocket.py`'s receive loop needs its **first** in-loop poll of a
   `SessionRegistry`-held signal on the existing `_SILENCE_POLL_INTERVAL_S`
   timeout tick — a new pattern, not a reuse of an existing one (§1.2).
6. A `ConversationDecisionTrace` write path for the activation attempt
   itself, distinct from (in addition to) the trace every candidate signal
   already gets — small, additive (§8).

Nothing on this list requires a new cross-engine contract, a new Event Bus
subject, a new database migration, or a change to any other engine.
Everything lives inside `services/communication-engine/`.

---

## 3. Proposed end-to-end flow (warm case only — see §11 for why the cold case remains out of reach)

```
perception.addressee_signal.candidate arrives (user_id always present,
Priority 2; identity_id/confidence and session_active real, Priority 2)
  |
  v
make_addressee_signal_handler (events/handlers.py, unchanged existing code)
  computes FusionOutcome via fuse() (unchanged)
  writes the existing per-candidate ConversationDecisionTrace (unchanged)
  |
  v  [NEW] only when outcome.tier == "high":
maybe_activate_listening(app, user_id=payload.user_id, correlation_id=...)
  1. candidates = [s for s in await repository.list_non_terminal_sessions()
                    if s.user_id == user_id
                    and s.channel is ChannelType.VOICE
                    and session_registry.is_connected(s.session_id)
                    and s.state in (ConversationState.IDLE, ConversationState.WAITING)]
  2. zero candidates  -> write ConversationDecisionTrace(session_id=None,
       decision_type="listening_activation", outcome="no_eligible_session"),
       return (Fork C)
  3. >1 candidate      -> write ConversationDecisionTrace(session_id=None,
       decision_type="listening_activation", outcome="ambiguous_sessions",
       inputs recording every candidate session_id), return, per Doc 22
       Principle 6 (Fork C)
  4. exactly 1 candidate -> session_registry.trigger_start_listening(session_id)
       write ConversationDecisionTrace(session_id=<resolved>,
       decision_type="listening_activation", outcome="activated")
  |
  v  (asynchronously, on that session's own WebSocket connection)
api/websocket.py's receive loop, next _SILENCE_POLL_INTERVAL_S timeout tick:
  signal = session_registry.get_start_listening_signal(session_id)
  if signal is not None and signal.is_set():
      signal.clear()                    # one-shot, NEW method
      if not turn_active:               # do not clobber an in-progress turn
          vad.reset(); audio_buffer = bytearray(); turn_active = True
  (falls through into the loop's existing VAD-feed logic, unchanged)
  |
  v
user's real speech arrives as AUDIO_CHUNK messages -> VAD ENDED ->
_finalize_utterance -> record_inbound_turn (existing, unchanged) ->
TRIGGER + CAPTURED fire for real, communication.session.state_changed
publishes (existing, unchanged) -> Priority 3's conversation_orchestration
takes over from here, entirely unchanged.
```

No new Event Bus subject. No new `nova-contracts` payload. No change to
`ConversationSession`'s schema. No change to the FSM's transition table —
the mechanism only ever calls the same `TRIGGER` edge the client path
already uses, at the same point in the sequence, gated to only fire from
the states that edge is already legal from.

---

## 4. Affected files/packages (all within `services/communication-engine/`)

| File | Change |
|---|---|
| `domain/speech.py` | Add `StartListeningSignal` (trigger/is_set/**clear** — three methods, not `BargeInSignal`'s two; see §1.3/Fork E for why) |
| `session_registry.py` | Add `_start_listening_signals` dict, `get_start_listening_signal`, `trigger_start_listening`; extend `register`/`unregister` |
| `conversation_orchestration.py` | New `maybe_activate_listening` function (or equivalent name), following this module's own existing "app.state-needing orchestration lives here, not in `domain/`" precedent (Priority 3) |
| `events/handlers.py` | `make_addressee_signal_handler` calls the new function when `outcome.tier == "high"`; reads `payload.user_id` for the first time |
| `api/websocket.py` | Receive loop's `except TimeoutError:` branch gains the new poll (§3 step 5) |
| `domain/models.py` | `ConversationDecisionTrace.decision_type` Literal gains one new value (proposed: `"listening_activation"`) — purely additive, same pattern `"interruption_recovery"`/`"silence"` already established alongside `"addressee_fusion"` |
| `tests/fakes/*` | `FakeCommunicationRepository` already has everything needed (`list_non_terminal_sessions`); no new fake methods anticipated |
| `tests/unit/`, `tests/integration/` | New tests per §9 |

**Not touched:** `nova-contracts` (no payload changes), `perception-engine`
(no changes — it already publishes everything this needs, since Priority
2), `reasoning-engine`, `personality-engine`, `world-model-engine`, any
Alembic migration, `infra/docker/docker-compose.local.yml` (no new
service).

---

## 5. New contracts

**None required for the warm case.** This is a direct, re-verified
confirmation of the closure document's own conclusion, not an assumption
carried forward: both `make_addressee_signal_handler` (the trigger source)
and `api/websocket.py`'s receive loop (the trigger consumer) already run
inside the same `communication-engine` process, sharing the same
`app.state.session_registry` instance. Introducing an Event-Bus round trip
for a service to signal itself has zero precedent anywhere in this
codebase and no benefit — the identical reasoning Priority 3's Fork #1
already resolved for reusing `deliver_content_to_session` in-process rather
than re-issuing a same-engine RPC. See Fork A (§13) — presented for
approval regardless, per the explicit instruction not to silently resolve
Event-Bus-vs-in-process questions, even where the answer is clear.

**Cold case** (no session exists / no client connected) still requires
`CommunicationSessionCreateRequestPayload.device_id` (required field,
re-confirmed unchanged) and a companion-client transport that does not
exist (re-confirmed: `apps/` remains empty). Out of reach for the identical,
already-disclosed reason Priority 1 named — not a new gap, not a fork,
restated with fresh verification per instruction #3.

---

## 6. State-machine changes

**None to `domain/state_machine.py`'s transition table.** The mechanism
never introduces a new `ConversationEvent` or a new edge — it only ever
causes the *existing* client-triggered path (local flag flip, no direct
FSM call) to fire from a server-originated cause instead of a client
message, gated to the same two states (`IDLE`, `WAITING`) that path's own
eventual `TRIGGER` application is legal from (Fork D formalizes a guard the
client path itself lacks today).

---

## 7. Failure and degraded-mode handling

| Case | Behavior |
|---|---|
| `payload.user_id` resolves to zero eligible sessions | No-op, decision trace recorded (`outcome="no_eligible_session"`), Doc 22 Principle 6 |
| `payload.user_id` resolves to >1 eligible sessions | No-op by default recommendation (Fork C), decision trace recorded with every candidate `session_id` for later analysis |
| Resolved session exists but is not `IDLE`/`WAITING` (mid-turn) | No-op, decision trace recorded (`outcome="session_busy"`) — Fork D; avoids the `InvalidTransitionError` class of defect found in §1.3 |
| Resolved session is `IDLE`/`WAITING` but disconnects between resolution and the WS loop's next tick | `SessionRegistry.unregister()` already pops the signal dict entry alongside the adapter; `trigger_start_listening` on an unregistered session is a silent no-op, mirroring `trigger_barge_in`'s own existing defensive `if signal is not None` — no new code needed, verified by direct reading, not assumed |
| Duplicate `perception.addressee_signal.candidate` delivery (at-least-once, no dedup anywhere in this codebase's outbox convention, confirmed project-wide) | Naturally idempotent: `trigger()` on an already-triggered signal is harmless; the WS loop's own consumption re-applies `vad.reset()`/fresh `audio_buffer`/`turn_active=True`, which is safe to repeat |
| `repository.list_non_terminal_sessions()` itself fails/times out | Propagates as an exception out of the addressee-signal handler; **this is already the existing behavior for the current handler's own repository calls** — no new failure mode, no new handling required beyond what the subscription's own existing error path does today |

---

## 8. Observability

Every trigger *attempt* (not just successful activations) writes a
`ConversationDecisionTrace` row — matching the closure document's own §6.3
item 5 and Doc 22 Principle 7's "every judgment is probabilistic, must be
inspectable" requirement. Proposed `decision_type`: `"listening_activation"`
(new Literal member, additive). `inputs` carries the full candidate list
considered (session_ids, states, channels) for exactly the kind of
after-the-fact debugging Priority 4's own multi-session/no-session
branches need to be inspectable, not just logged. `session_id` is set only
on the `"activated"` outcome — consistent with the field's own existing
docstring.

`metrics.addressee_fusion_total` already exists and is unaffected (it
counts every candidate, not just activations). A new counter, e.g.
`metrics.listening_activations_total`, is a natural small addition
following that same existing pattern — flagged as a small extension, not a
fork.

---

## 9. Testing strategy

Two-tier convention unchanged (ADR-033). Proposed new tests:

- **Unit** (`domain/speech.py`'s new `StartListeningSignal`): trigger/is_set/
  clear semantics in isolation, including "trigger after clear still works"
  and "clear before trigger is a safe no-op" — the exact case `BargeInSignal`
  itself was never tested for, per §1.3's finding.
- **Unit** (the new `maybe_activate_listening`-equivalent function, via a
  `FakeCommunicationRepository`/fake `SessionRegistry` double, mirroring
  `test_observation_orchestration.py`'s own `_FakeApp` pattern from
  Priorities 1/2): zero candidates, exactly one candidate, multiple
  candidates, a candidate in a non-`IDLE`/`WAITING` state, a candidate that
  is non-terminal but not `is_connected`, a candidate on the text channel
  (must be excluded).
- **Integration**, through the real `create_app()` + `TestClient.websocket_connect`
  (the exact pattern `test_websocket_text.py` already establishes): create a
  voice-channel session, connect a WebSocket, publish
  `perception.addressee_signal.candidate` via `nova_testkit`'s
  `FakePerceptionSignalSource` with signals scored to reach `tier=="high"`
  and `user_id` matching the session's own `user_id`, **without ever
  sending a client-side `TRIGGER_START`**, then send `AUDIO_CHUNK` frames
  and poll the HTTP context endpoint for `turn_count`/`state` — proving the
  server-side trigger alone was sufficient to have the audio recorded as a
  turn. A second integration test asserts the negative: the identical
  sequence with a *mismatched* `user_id` never accumulates a turn from
  those audio chunks.
- **Integration, negative case for §1.3's finding**: if Fork E is approved
  for a fix in this same pass, an integration test driving a real
  barge-in-then-continue sequence through the actual WebSocket loop,
  asserting the connection survives and the follow-up utterance is
  correctly recorded — proving the fix, not just asserting it by
  inspection.

No `real_infra`-marked test is anticipated — no new migration, no new
Postgres interaction (both repository methods this reuses,
`list_non_terminal_sessions`/`get_session`, already exist and are already
covered by whatever real-Postgres coverage they already have, unaffected).

---

## 10. Anticipated four-way verification classification

Not yet executed — implementation has not started. Stated here as the
target classification this proposal's eventual Gate Review would need to
confirm or correct, per the same discipline Priorities 1-3 applied:

| Component | Anticipated classification |
|---|---|
| `StartListeningSignal` (trigger/is_set/clear) | Fully verifiable — pure, deterministic, no external dependency |
| Session-resolution branching (zero/one/many candidates, state/channel/connectivity filters) | Fully verifiable against fakes, exercising every branch directly |
| The real WebSocket receive-loop poll, through `create_app()` + `TestClient.websocket_connect` | Fully verifiable — the actual production loop, actually exercised, the only fake in the chain being `FakePerceptionSignalSource` standing in for a real cross-process `perception-engine` publish (the same tier Priorities 1-3 already established for this exact boundary) |
| A real two-process proof (a real `perception-engine` process publishing onto a real bus, a real `communication-engine` process consuming and activating a real session) | Not reachable in this sandbox — the same disclosed, standing limitation every prior priority has carried |
| Real Postgres round-trip for `list_non_terminal_sessions` under this new call pattern | Not newly exercised — no new migration; existing real-Postgres coverage of that method (if any) is unaffected and unchanged by this priority |
| An actual companion client actually connecting and actually reacting to being told to listen | Hardware/client-dependent, not verified, not claimed — no such client exists anywhere in this codebase (§5's cold-case note) |

---

## 11. Risks

- **§1.3's defect, if left unfixed, undermines confidence in the precedent
  Priority 4 is asked to mirror.** Recommended: resolve via Fork E before
  or alongside implementation, not left as a second, separate surprise
  discovered later.
- **The multiple-eligible-sessions case (Fork C) is genuinely rare in the
  Personal Edition's real target deployment** (ADR-025), meaning it will
  be lightly exercised in practice regardless of which policy is chosen —
  the risk is not "this breaks often," it is "if it is ever hit, the wrong
  default silently does something surprising to a user with two connected
  devices." Recommending the conservative (no-op) default for exactly this
  reason.
- **A false-positive "high" fusion tier now has a real, visible side
  effect** (a connected device starts capturing audio) where before
  Priority 4 it only produced an inert decision-trace row. This raises,
  slightly, the cost of a fusion miscalibration — mitigated by the fact
  that `high_threshold=0.70` was already deliberately set "well above the
  sum of any two signals alone" (the module's own docstring) specifically
  so this day would come without requiring the threshold itself to change.
- **No real end-to-end (two-process) proof is possible in this sandbox**,
  identical to every prior priority's own disclosed limitation — not a new
  risk Priority 4 introduces, restated for completeness.

---

## 12. Dependency order

Priority 4 depends on Priority 2's `user_id` field, which is implemented
and closed. No dependency on Priority 5 (personality's `channel`
parameter) or Priority 6 (real-infrastructure verification status) —
confirmed independent by direct re-reading of the closure document's own
dependency graph (§2), which this review found accurate on this point.
Nothing in this proposal blocks or is blocked by either.

---

## 13. Explicit approval forks

Per instruction, none of these has been resolved. Each recommendation is
offered, not assumed.

### Fork A — Event Bus vs. in-process delivery for the trigger itself

**Recommendation: in-process**, via a `SessionRegistry`-held
`StartListeningSignal`, exactly as §3 describes. Both ends of this signal
already run inside the same process; no precedent anywhere in this
codebase introduces a same-service Event-Bus round trip, and Priority 3's
own Fork #1 resolved the structurally identical question the same way.

### Fork B — how to resolve `user_id` → target `session_id`

- **B1 (recommended):** filter the existing `list_non_terminal_sessions()`
  in Python (by `user_id`, `channel`, `is_connected`, `state`) — reuses an
  already-tested, already-used repository method (restart recovery's own
  precedent), adds no new repository surface. Personal Edition's real
  deployment (0-1 non-terminal sessions per instance, per ADR-025) makes
  the O(n) scan immaterial.
- **B2:** add a new repository method (e.g. `get_active_sessions_by_user`)
  pushing the filter into SQL. More repository surface (must be implemented
  by both `PostgresCommunicationRepository` and every test fake); only
  worth it if session counts were expected to be large, which ADR-025's own
  stated assumption says they are not.
- **B3:** maintain a second, `user_id`-keyed index inside `SessionRegistry`
  itself (mirroring perception-engine's own `SessionActivityTracker`
  shape), populated at `register()`/`unregister()`. Fastest, but introduces
  a second source of truth for "which sessions exist for this user" that
  must be kept in sync with the repository's own — a correctness risk this
  project's own precedent (single source of truth per concern) argues
  against.

### Fork C — behavior when zero, or more than one, eligible session is found

- **Zero eligible:** no real alternative to a no-op — included for
  completeness, not a genuine fork.
- **Multiple eligible (recommended: C2, trigger none):** silently picking
  one of several connected devices risks exactly the false-positive Doc 22
  Principle 6 names as strictly worse than a false negative. **Alternative
  (C1): trigger all eligible sessions** — defensible if the product intent
  is "every device you're signed into should react," but this is a real UX/
  product decision this document has no authority to make silently.
  **Alternative (C3): trigger only the most-recently-active session** —
  a tiebreak heuristic with its own failure mode (guessing wrong is still
  a false positive on the *other* device, silently).

### Fork D — which session states are eligible to be triggered

**Recommendation: `IDLE`/`WAITING` only** (exactly the two states the FSM's
own `TRIGGER` edge is already legal from) — a no-op, disclosed via decision
trace, for any other state (`THINKING`/`SPEAKING`/`PAUSED`). **Alternative:**
treat a `high`-tier fusion signal arriving while `SPEAKING` as a *second*,
addressee-driven barge-in trigger, distinct from the existing
audio-energy-driven one. This is a materially larger design question
(new interruption semantics, not just an activation mechanism) this
proposal deliberately does not open — flagged as a possible, explicitly
out-of-scope future extension rather than decided against silently.

### Fork E — the pre-existing barge-in-continuation defect (§1.3)

Discovered during this review, not caused by it, and not strictly
Priority-4 scope — but directly touches the same file (`api/websocket.py`)
and the same signal-consumption pattern Priority 4 is asked to extend.

- **E1 (recommended): fix it in this same implementation pass.** The fix
  is small and localized — `record_inbound_turn` (or its `api/websocket.py`
  call site) needs to tolerate a session already in `LISTENING` (skip the
  redundant `TRIGGER` application when already there) rather than
  unconditionally applying it; alternatively, wrap the WS loop's call to
  `record_inbound_turn` in the same `except InvalidTransitionError` pattern
  `api/sessions.py` already uses. Low risk, small diff, directly adjacent
  to code this priority already touches, and leaves Priority 4's own new
  mechanism easier to test with confidence in the surrounding machinery.
- **E2: file it as a separate, independently-tracked defect**, implemented
  and verified on its own, outside Priority 4's own commit/Gate Review —
  keeps Priority 4's diff minimal and strictly scoped, at the cost of
  leaving a known, reproducible connection-crashing defect live in the
  interim.

Both are legitimate; this is the user's call per the standing instruction
never to silently expand — or silently defer — scope.

---

## 14. Explicitly out of scope, not touched, not assumed resolved

- Priorities 1, 2, 3 — unmodified, not reopened.
- Priorities 5, 6 — not referenced as implementation targets, no code path
  touched.
- Phase 2D-D — not started.
- The cold case (no session/no client) — confirmed still out of reach,
  same disclosed reason as Priority 1, not re-litigated.
- World Model corroboration — confirmed still unwired, unaffected.
- Any change to `perception-engine`, `reasoning-engine`,
  `personality-engine`, or `world-model-engine` — none proposed, none
  required.
