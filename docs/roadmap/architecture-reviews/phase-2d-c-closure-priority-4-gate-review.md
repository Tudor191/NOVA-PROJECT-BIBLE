# Phase 2D-C Closure — Priority 4 Gate Review: the "start listening" cross-context mechanism

**Scope of this review: Priority 4 only**, per direct instruction. Priorities
1, 2, and 3 of the
[closure design document](../../design/phase-2d/05-conversation-intelligence-closure.md)
are implemented and closed (their own Gate Reviews) and are not reopened here.
Priorities 5 and 6 are **untouched**. Phase 2D-D has not been started.

**Decision: Go**, for Priority 4 as scoped and as approved. The warm-case
server-triggered "start listening" mechanism now exists, entirely in-process
inside `communication-engine`, exactly as the
[implementation proposal](phase-2d-c-closure-priority-4-proposal.md) designed
it. Two adjacent, pre-existing defects surfaced during implementation were
fixed in the same pass, per explicit instruction (Fork E) and disclosed
judgment (§3.3) — see §3 for both.

## 1. What was implemented

The approved design (proposal §3):

```
perception.addressee_signal.candidate (tier == "high")
  -> make_addressee_signal_handler (unchanged fusion + existing trace)
  -> maybe_activate_listening(app, user_id, correlation_id)   [NEW]
       resolve user_id -> zero/one/many eligible sessions
       (list_non_terminal_sessions(), filtered in Python: channel is VOICE,
       is_connected, state in IDLE/WAITING)
       zero -> no-op, decision trace
       many -> no-op, decision trace + explicit log (Doc 22 Principle 6)
       one  -> session_registry.trigger_start_listening(session_id)
  -> api/websocket.py's receive loop, next silence-poll tick   [NEW poll]
       consumes StartListeningSignal (one-shot), sets turn_active = True
  -> user's real speech -> VAD ended -> record_inbound_turn (unchanged)
  -> Priority 3's conversation_orchestration takes over from here
```

Concretely:

1. **`domain/speech.py`** — new `StartListeningSignal` (trigger/is_set/clear),
   mirroring `BargeInSignal`'s shape with the one-shot `clear()` method
   `BargeInSignal` itself lacked (see §3.1).
2. **`session_registry.py`** — `_start_listening_signals: dict[UUID,
   StartListeningSignal]`, `get_start_listening_signal`,
   `trigger_start_listening`; `register`/`unregister` extended alongside the
   existing `_barge_in_signals` dict.
3. **`conversation_orchestration.py`** — new `maybe_activate_listening(app,
   *, user_id, correlation_id)`, following this module's own
   `handle_conversation_turn` precedent (a plain, directly-awaitable async
   function; app-state-needing orchestration lives here, not in `domain/`).
   Writes a `ConversationDecisionTrace` for every attempt, not only a
   successful activation.
4. **`domain/models.py`** — `ConversationDecisionTrace.decision_type` gains
   `"listening_activation"` (purely additive `Literal` member; the backing
   column is `Text`, no migration needed — confirmed by reading
   `repository/models.py` before touching it).
5. **`events/handlers.py`** — `make_addressee_signal_handler` now reads
   `payload.user_id` (present since Priority 2) and calls
   `maybe_activate_listening` when `outcome.tier == "high"`. The import is
   function-local (inside `handle()`), not module-level: `conversation_
   orchestration.py` already imports `deliver_content_to_session` from this
   same module, so a top-level import here would be circular. Also fixed the
   handler's own docstring, which had gone stale after Priority 2 — it still
   claimed the payload "carries no `user_id`" (§3.2).
6. **`api/websocket.py`** — the receive loop's `except TimeoutError:` branch
   gains the first in-loop poll of a `SessionRegistry`-held signal: reads
   `get_start_listening_signal`, clears it if set, and — only if no turn is
   already active — resets the VAD/audio buffer and sets `turn_active = True`,
   exactly mirroring what the client's own `TRIGGER_START` message already
   does, from a server-originated cause instead of a client message.
7. **`observability.py`** — `listening_activations_total` counter, labeled by
   outcome (`activated` / `no_eligible_session` / `ambiguous_sessions`),
   following the existing `addressee_fusion_total` pattern.

**Not touched, confirmed by direct verification, not assumption:**
`nova-contracts` (zero diff after regenerating TypeScript — §5),
`perception-engine`, `reasoning-engine`, `personality-engine`,
`world-model-engine`, any Alembic migration, `docker-compose.local.yml`.

## 2. The five approved decisions, as implemented

1. **In-process `SessionRegistry` signal, no Event Bus round trip.**
   `maybe_activate_listening` and `api/websocket.py`'s receive loop share
   `app.state.session_registry` directly — no new subject, no new RPC.
2. **`user_id -> session_id` via `list_non_terminal_sessions()` filtered in
   Python.** No new repository method, no second `user_id`-keyed index.
   `channel is ChannelType.VOICE`, `session_registry.is_connected(...)`, and
   `state in (IDLE, WAITING)` are all applied as a single list comprehension
   in `maybe_activate_listening`.
3. **Ambiguous sessions (>1 eligible) trigger none.** Neither candidate's
   signal is touched; a `ConversationDecisionTrace(outcome="ambiguous_
   sessions")` records every candidate `session_id`, and `logger.warning(
   "listening_activation_ambiguous_sessions", ...)` logs it explicitly, per
   instruction — verified directly by
   `test_maybe_activate_listening_declines_to_guess_with_multiple_eligible_sessions`.
4. **Fork E fixed in this same pass** — see §3.1.
5. **Eligibility limited to `IDLE`/`WAITING`.** Any other state (`THINKING`/
   `SPEAKING`/`PAUSED`) is silently excluded from the candidate list and
   produces `outcome="no_eligible_session"`, disclosed via decision trace.
   No `SPEAKING`-state addressee-driven barge-in behavior was introduced.

## 3. Defects found and fixed, disclosed separately from the five decisions

### 3.1 Fork E — the pre-existing `BargeInSignal` lifecycle bug (user-approved fix)

Two distinct, compounding defects in already-shipped code, both fixed:

- **`BargeInSignal` never reset.** `SessionRegistry.register()` builds one
  instance per connection, reused for every response on that connection's
  lifetime. Once triggered, `speak_response`'s very first `is_set()` check
  would abort delivery on **every subsequent response**, forever — a
  connection that has ever experienced one barge-in would go permanently
  silent. Fixed by giving `BargeInSignal` a `clear()` method and calling it
  inside `speak_response` itself, once, right after computing `barged_in`
  from the final `is_set()` read — after the current response's own
  interruption decision is already finalized, so this does **not** weaken
  the existing "already-triggered signal aborts delivery" contract
  `test_voice_delivery_stops_and_discards_on_barge_in` (unit, unmodified)
  depends on. Proven directly by
  `test_speak_response_clears_the_signal_once_a_barge_in_is_consumed`
  (new unit test): a signal pre-triggered before one `speak_response` call
  aborts that call as before, but is clear and delivers normally on the
  *next* call.
- **`record_inbound_turn` unconditionally applied `TRIGGER`.** After a
  barge-in, the session is already `Listening` (the FSM's own `BARGE_IN`
  edge already moved it there); `(Listening, TRIGGER)` is not a defined
  transition, so the very first user utterance following any barge-in
  raised `InvalidTransitionError` — uncaught anywhere in
  `api/websocket.py`, crashing the WebSocket connection via an unhandled
  exception. Fixed in `domain/session_lifecycle.py::record_inbound_turn`:
  `TRIGGER` is now applied only when `session.state in (IDLE, WAITING)`;
  when already `Listening`, it is skipped and `CAPTURED` is applied
  directly (a legal edge from `Listening`). Any other state (`THINKING`/
  `SPEAKING`/`PAUSED`) still raises via the `CAPTURED` application, unchanged
  — this fix is deliberately narrow, not a general state-guard rewrite.

Regression coverage, per instruction ("through the actual WebSocket state
machine," not just by inspection):
- Unit: `test_record_inbound_turn_from_listening_skips_the_redundant_trigger`
  and `test_record_inbound_turn_from_thinking_still_raises` (the negative
  control — a genuinely invalid state still raises).
- Integration, through the real receive loop:
  `test_a_barge_in_followed_by_continuing_speech_does_not_crash_the_connection`
  (`test_websocket_voice.py`) — forces a connected session directly to
  `Speaking` (the minimal precondition; the full reasoning/delivery pipeline
  is irrelevant to this specific defect), sends one real `AUDIO_CHUNK`
  WebSocket frame, and asserts the connection survives and the turn is
  recorded. **Empirically verified, not just traced**: temporarily reverting
  only the `if session.state in (IDLE, WAITING)` guard (restoring the
  unconditional `TRIGGER` application) and re-running both this test and
  the new unit test reproduces the exact predicted failure —
  `InvalidTransitionError: Cannot apply 'trigger' from state 'listening'`
  for the unit test, and the integration test's `turn_count == 1` assertion
  failing (the crash prevents the turn from ever being recorded) — before
  the guard was restored and the full suite re-confirmed green (135/135).

### 3.2 Stale docstring correction

`make_addressee_signal_handler`'s docstring claimed
`perception.addressee_signal.candidate` "carries none" for `user_id` — false
since Priority 2 (`PerceptionAddresseeSignalCandidatePayload.user_id` is a
required field). Corrected while touching this exact function.

### 3.3 A sixth, newly-discovered defect: `VoiceChannelAdapter` crashed on disconnect

Writing the first-ever real-WebSocket integration test against the voice
channel (`test_websocket_voice.py`) surfaced a defect with zero relationship
to Priority 4's own trigger mechanism: `VoiceChannelAdapter.receive()` uses
the raw ASGI-level `WebSocket.receive()` (needed because a single voice
connection carries both binary audio and JSON control frames, unlike
`TextChannelAdapter`'s single-mode `receive_json()`). Unlike `receive_text()`/
`receive_bytes()`/`receive_json()`, raw `receive()` does **not** itself raise
`WebSocketDisconnect` on a `{"type": "websocket.disconnect"}` message — it
returns that message like any other, and `VoiceChannelAdapter.receive()` had
no case for it, falling through to `raise ValueError(f"Unrecognized voice
channel WebSocket message: ...")`. **Every clean disconnect of a voice-channel
WebSocket connection crashed with an unhandled `ValueError`** instead of the
existing, already-correct `except WebSocketDisconnect: pass` handling in
`api/websocket.py`. Not previously caught because no test exercised a real
voice-channel WebSocket connect/disconnect cycle before this pass — the only
existing WebSocket integration coverage (`test_websocket_text.py`) is
text-channel only, and `TextChannelAdapter.receive_json()` doesn't have this
gap.

This was not named in the approved five decisions or Fork E, and is not
architectural — a three-line, mechanical fix (raise `WebSocketDisconnect`
explicitly, mirroring Starlette's own `_raise_on_disconnect` precedent used
internally by the three higher-level `receive_*` methods), directly blocking
this pass's own required WebSocket-level verification. Applying the same
"fix small, directly-adjacent, disclosed defects in this pass" principle the
user already approved for Fork E, rather than either silently working around
it in test teardown or dropping the real-WebSocket tests the verification
standard calls for. Flagged here explicitly since it was not pre-approved by
name — the fix is `channels/voice_adapter.py`, four lines, no behavior change
to any successful (non-disconnect) message path, confirmed by the full
existing suite passing unmodified elsewhere.

## 4. Tests added

- **`tests/unit/test_speech.py`** (new, 10 tests): `BargeInSignal`/
  `StartListeningSignal` trigger/is_set/clear in isolation, including
  "trigger after clear still works" and "clear before trigger is a safe
  no-op" (the exact cases §1.3 of the proposal named `BargeInSignal` as
  never having been tested for); `speak_response`'s own clear-on-consume
  behavior (§3.1).
- **`tests/unit/test_session_lifecycle.py`** (+2 tests): the Fork E fix and
  its negative control (§3.1).
- **`tests/integration/test_conversation_orchestration.py`** (+6 tests):
  `maybe_activate_listening` through the real app + lifespan — exactly one
  eligible session (activates), zero eligible (no-op), multiple eligible
  (no-op + ambiguity trace), wrong state, disconnected, and text-channel
  (all three correctly excluded). Placed in this existing integration-tier
  file rather than a new unit-tier file with a hand-rolled `_FakeApp`,
  deliberately deviating from the proposal's own suggested tier — this file
  already establishes the exact `_make_app`/`FakeCommunicationRepository`/
  `session_registry.register` pattern needed, at equivalent verification
  depth, for this same module.
- **`tests/integration/test_addressee_signal_handler.py`** (updated): the
  pre-existing "high"-tier test now also produces a second, `listening_
  activation` decision trace (`no_eligible_session`, since it seeds no
  session) — asserted explicitly rather than left to silently break.
- **`tests/integration/test_websocket_voice.py`** (new, 3 tests) — the first
  real-WebSocket, voice-channel integration coverage in this codebase:
  1. Server-triggered listening activates audio capture with **no client
     `TRIGGER_START` ever sent** — a real `perception.addressee_signal.
     candidate` published over the app's own in-memory Event Bus (via
     `TestClient`'s own `anyio` portal, so it runs on the same event
     loop/thread as the WebSocket connection rather than an unsynchronized
     second one) drives one real `AUDIO_CHUNK` frame into a recorded turn.
  2. The negative: a mismatched `user_id` never accumulates a turn.
  3. The Fork E regression (§3.1), through the real receive loop.

## 5. Verification results

| Check | Result |
|---|---|
| `ruff check` (whole monorepo, `pnpm lint` / `turbo run lint`) | 18/18 packages pass |
| `mypy src` (whole monorepo, the actual CI-equivalent gate — confirmed via `package.json`'s own `lint` script, which runs `mypy src`, never `tests/`) | 18/18 packages pass, 0 errors |
| Full pytest suite (whole monorepo, `pnpm test` / `turbo run test`, excludes `real_infra`) | 18/18 packages pass |
| communication-engine domain/ coverage | 99.6% (gate: 85%) |
| Coverage gate negative control | `--cov-fail-under=100` (unreachable) → **exit 1**, `FAIL Required test coverage of 100% not reached. Total coverage: 99.60%` — the gate genuinely enforces |
| import-linter | 6/6 contracts kept, 0 broken — identical set to every prior checkpoint |
| `docker compose -f infra/docker/docker-compose.local.yml config` | exit 0 — no service/image/env change this pass |
| TypeScript contract generation (`generate_typescript.py`) | re-run, **zero diff** — confirms no `nova-contracts` payload was touched |
| Targeted end-to-end WebSocket regression tests | 3/3 pass, stable across 3 repeated runs (no flakiness observed) |

A note on the `mypy` scope: an initial `mypy src tests` run surfaced ~50
"Unused type: ignore comment" / "Function is missing a type annotation"
errors. A/B comparison against a clean stash of this branch (including
untracked files) showed **30 of these already exist on the unmodified
baseline**, in files this pass never touched (`test_silence_policy.py`,
`test_intent_gate.py`, `test_events_communication_request.py`,
`test_api_notifications.py`) as well as in files this pass did touch
(pre-existing tests in `test_conversation_orchestration.py`/
`test_addressee_signal_handler.py`). This pass's new tests reproduce the
exact same established `# type: ignore[no-untyped-def]` convention already
used throughout this test suite, which happens to trip the same pre-existing
mypy/pytest-asyncio version mismatch. The actual gate this repository runs
(`package.json`'s `lint` script, `mypy src`) never includes `tests/` and
passes with zero errors. This pre-existing, project-wide `tests/`-only noise
is disclosed, not fixed — fixing it would mean touching dozens of unrelated
test files across multiple engines, well outside Priority 4's scope.

Real-Postgres (`real_infra`) tests: not newly exercised (no new migration,
no new database interaction) — confirmed unaffected by collecting them
cleanly (11/11 collect, 0 errors). Not run for real: no Docker daemon in
this sandbox, the same disclosed, standing limitation every prior priority
has carried.

## 6. Classification (per the closure document's own four-way standard — never collapsed)

- **Fully verified, real end-to-end**: `StartListeningSignal` (pure,
  deterministic); the session-resolution branching in
  `maybe_activate_listening` (every branch exercised against the real app +
  lifespan, real `FakeCommunicationRepository`, real `SessionRegistry`); the
  actual production `api/websocket.py` receive loop, actually polling and
  consuming a real signal, actually recording a real turn from real
  WebSocket frames — proven by `test_websocket_voice.py`'s first test, the
  only fake in that chain being `FakePerceptionSignalSource` standing in for
  perception-engine's own still-unwired-in-this-sandbox publisher (the same
  tier Priorities 1-3 already established for this exact boundary). The Fork
  E fix is proven the same way, through the same real loop.
- **Contract/fake verified**: none beyond the above — Priority 4's own scope
  has no failure-mode branches that depend on a fake upstream port the way
  Priority 3's reasoning-timeout/malformed-reply branches did.
- **Real-infrastructure verified**: not applicable — no new migration, no
  new database interaction this pass.
- **Not verified / not claimed**: a real two-process proof (a real
  perception-engine process publishing onto a real bus, a real
  communication-engine process consuming and activating a real session) —
  not reachable in this sandbox, the same disclosed, standing limitation
  every prior priority has carried. An actual companion client actually
  connecting and actually reacting to being told to listen — hardware/
  client-dependent, no such client exists anywhere in this codebase (the
  cold case, confirmed still out of reach for the same reason Priority 1
  named).

## 7. Remaining limitations — explicitly not closed by this pass

- **Priorities 5 and 6 of the closure document remain exactly as
  disclosed there.** `personality-engine`'s `channel` parameter is still
  inert (Priority 5); real-Postgres verification (task #93) is still
  unexecuted anywhere (Priority 6).
- **The cold case (no session / no client connected) is still out of
  reach** — `CommunicationSessionCreateRequestPayload.device_id` still
  requires a companion-client transport that does not exist anywhere in
  `apps/`. Not a new gap; restated per instruction #3.
- **World Model corroboration remains unwired.**
  `corroborate_identity_confidence` is still never called from
  `make_addressee_signal_handler`, unaffected by and unrelated to this
  pass.
- **The narrow race window this review's own fix leaves intentionally
  open** (disclosed, not silently accepted): `speak_response`'s
  `barge_in_signal.clear()` runs once, after that response's own
  interruption decision is finalized. If a client's audio chunk sets
  `trigger_barge_in` in the brief window between `mark_content_ready`
  (`Thinking -> Speaking`) and `speak_response`'s own first `is_set()`
  check — an inherent race already present before this pass, not
  introduced by it — that trigger is correctly consumed by the *current*
  response. A separate, much narrower race (a stray `trigger_barge_in` call
  landing *after* `speak_response` has already returned `barged_in=False`,
  because the receive loop's own read of session state momentarily lagged
  the delivery task's own state transition) could leave one future response
  incorrectly treated as interrupted. This existed in an even worse form
  before this pass (permanently, not narrowly) and is not fully closed here
  — closing it fully would require a per-turn signal identity/generation
  counter, which is state-machine refactoring beyond what Fork E approved.
- **The general "client `TRIGGER_START` sent while not `Idle`/`Waiting`"
  exposure named in the proposal's §1.5 is unchanged.** Priority 4's own
  new mechanism applies the `Idle`/`Waiting` guard the existing client path
  lacks (decision 5), but the client-facing path itself still has no such
  guard. Out of scope by explicit instruction ("do not broaden this into
  unrelated session-state refactoring").

Phase 2D-D has not been started. Priorities 5 and 6 have not been touched.
Per instruction, this review stops here and awaits the user's review before
any further work begins.
