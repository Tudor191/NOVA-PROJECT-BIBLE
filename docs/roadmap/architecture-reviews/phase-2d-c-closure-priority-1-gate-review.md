# Phase 2D-C Closure — Priority 1 Gate Review: perception-engine's production signal chain

**Scope of this review: Priority 1 only**, per direct instruction. Priorities
2, 4, 5, and 6 of the
[closure design document](../../design/phase-2d/05-conversation-intelligence-closure.md)
are **untouched** — no code was modified for any of them. Phase 2D-D has not
been started. No changes were made to communication-engine or
reasoning-engine — the review found nothing this priority strictly required
there.

**Decision: Go**, for Priority 1 as scoped, with two disclosed, user-approved
capability limits (not gaps — deliberate, confirmed boundaries): no identity
matching, no session-active signal, both deferred to Priority 2. See §6 for
exactly what "production signal chain" now means end-to-end and what it
still does not.

## 1. Pre-implementation review — what was verified before writing code

Per instruction, a full architecture/implementation review preceded any
code change, re-verifying the closure document directly against current
source rather than trusting it as already-settled:

- Sensor lifecycle (`main.py:93-102`, `domain/sensor.py`), the missing
  ingestion path, and the zero-callers finding for all seven
  `events/publishers.py` functions — **all confirmed exactly as the closure
  document described**, no drift since it was written (`git log` shows no
  commits touching perception-engine since).
- **New finding beyond the closure document, surfaced this review**:
  `VoiceSensor.match_voiceprint`, `CameraSensor.match_faceprint`, and
  `SessionActivityTracker.is_active` all require a concrete, non-optional
  `user_id: UUID` — a hard internal dependency the closure document's own
  pseudocode elided, not merely a wire-payload detail belonging to
  Priority 2. Reported to the user before any code was written (see the
  chat record) rather than resolved unilaterally.
- **New finding, same review pass**: each ingestion call is necessarily
  single-sensor (one window per call — no synchronized multi-sensor
  capture exists or is being fabricated). Without correlating a call's own
  contribution with a still-fresh contribution from the *other* sensor,
  every published signal would carry only wake *or* gaze, never both —
  capping fusion below the ceiling already described to the user when the
  `user_id` question was raised. Addressed by `WindowCorrelationBuffer`
  (§3), not by asking a second time, since it does not touch `user_id` or
  Priority 2 and has a single well-justified design.
- `IdentityConfidenceState`/`identity_fusion.smooth()`/`perception.identity.observed`
  were investigated and **deliberately not touched** — that trio was
  already uncalled before this review (a pre-existing, undisclosed-as-a-gap
  condition the original Phase 2D-B TDD itself never fully specified who
  allocates a `presence_session_id`) and is not part of what the Gate
  Review named as needing closure (only `perception.addressee_signal.candidate`
  was named). Not a regression, not silently expanded scope.
- Both forks — the already-disclosed ingestion-mechanism fork (closure doc
  §3.10) and the newly-surfaced `user_id` capability question — were put to
  the user via `AskUserQuestion` before implementation began. Both
  recommended options were approved: a real ingestion endpoint now, and
  capped capability (no identity matching, no session-active) rather than
  reaching into Priority 2.

## 2. What was implemented

1. **`domain/correlation_buffer.py`** (new) — `WindowCorrelationBuffer`,
   an in-process, ephemeral store of the most recent wake and gaze
   contributions, each independently timestamped and expired against
   `correlation_window_seconds`. Mirrors `SessionActivityTracker`'s own
   established "safe to lose on restart, single instance, no cross-tenant
   keying" pattern (ADR-025) — not a new architectural concept, the direct
   implementation of what that config setting was already named for.
2. **`observation_orchestration.py`** (new, deliberately outside `domain/`
   for the same reason `communication-engine`'s `conversation_orchestration.py`
   is — it needs `app.state`) — `handle_observation_window`: looks up the
   sensor for the given source, checks it is `running`, runs the existing
   `detect_presence` cost-avoidance gate, calls the existing
   `detect_wake_phrase`/`estimate_attention` detection methods, records the
   result into the correlation buffer, reads back the combined view, and
   publishes via the existing `addressee_signal_candidate` shaping function
   and the existing outbox. Every domain-logic ingredient was already
   built and already tested before this pass — only the sequencing that
   calls them is new.
3. **`api/observations.py`** (new) — `POST /v1/perception/observations`
   (user-approved Fork #3, Option 1). The window travels as the raw request
   body (`application/octet-stream`), not a JSON `bytes` field — see §7 for
   why that design changed mid-implementation. `source`/`correlation_id`
   are query parameters.
4. **`main.py`** — wires `WindowCorrelationBuffer` onto `app.state`,
   registers the new router.
5. **`infra/docker/docker-compose.local.yml`** — a new
   `perception-engine-worker` service (same image, `arq
   nova_perception_engine.workers.WorkerSettings` command instead of
   `uvicorn`), closing the outbox-dispatch gap the closure document
   committed to as part of Priority 1's own "done" definition. Its
   HTTP healthcheck is disabled (meaningless for a non-HTTP process) rather
   than left to falsely report unhealthy. This same gap exists for every
   other engine in this compose file — closing it elsewhere is explicitly
   out of this priority's scope.

**Deliberately not implemented (§1, user-confirmed):** identity matching
and the session-active lookup. Every published `perception.addressee_signal.candidate`
this pass always carries `identity_id=None`, `identity_confidence=0.0`,
`session_active=False` — honest values, never fabricated.

## 3. The exact chain, traced end to end

```
POST /v1/perception/observations?source=microphone&correlation_id=...
  (raw audio bytes as the request body)
  -> api/observations.py: submit_observation
  -> observation_orchestration.handle_observation_window
       -> sensors_by_source["microphone"] (VoiceSensor, already built)
       -> sensor.state() == "running"? (already built)
       -> sensor.detect_presence(window)  -- cost-avoidance gate (already built)
       -> sensor.detect_wake_phrase(window, correlation_id=...)  -- real
          ai-model-orchestration-engine RPC via AIModelOrchestrationPort
          (already built)
       -> WindowCorrelationBuffer.record_wake(...)  (new)
       -> WindowCorrelationBuffer.current(...)  -- combines with any still-
          fresh gaze contribution from a separate camera call (new)
       -> events.publishers.addressee_signal_candidate(...)  (already built)
       -> repository.enqueue_outbox(event)  (already built)
  -> perception-engine-worker (new compose service) dispatches the outbox
     row onto the real Event Bus within its 10-second poll cadence
  -> perception.addressee_signal.candidate lands on the bus, in the exact
     shape communication-engine's Phase 2D-C addressee fusion
     (domain/addressee_fusion.py) already consumes -- contract unchanged,
     confirmed byte-for-byte identical to before this priority
```

## 4. Every case the user asked to be verified, addressed explicitly

- **Sensor start/operation**: unchanged — `main.py`'s existing
  `initialize()`/`start()` sequence, confirmed still correct, no lifecycle
  code touched.
- **How windows enter the system**: the new `POST /v1/perception/observations`
  endpoint (Fork #3, Option 1) — a real, reachable REST surface with no
  caller yet anywhere in this repository, exactly like
  `communication-engine`'s own WebSocket endpoint before any client used
  it.
- **Ingestion → detection**: direct, synchronous calls to the sensor's own
  already-tested `detect_presence`/`detect_wake_phrase`/`estimate_attention`
  methods — no new detection logic, no bypass of the Sensor Abstraction
  Layer.
- **Detection → identity fusion/smoothing**: deliberately **not** wired
  this pass (§1, §2) — `identity_fusion.fuse_window`/`smooth` are not
  called; `WindowCorrelationBuffer` (new) is a distinct, purpose-built
  mechanism for cross-sensor wake/gaze correlation only, not identity
  fusion.
- **`perception.addressee_signal.candidate` production**: traced in full
  in §3 — every field's origin is named, none fabricated.
- **The perception ↔ communication contract**: unchanged. No field added,
  removed, or retyped. `PerceptionAddresseeSignalCandidatePayload` is
  byte-for-byte what it was before this priority; verified directly by the
  zero TypeScript diff (§5) and by communication-engine's own existing
  addressee-fusion tests, none of which needed any change.
- **Outbox handling**: the existing transactional-outbox pattern, unchanged
  — plus the new `perception-engine-worker` compose service so rows
  actually dispatch (§2 item 5).
- **Failure case**: a raising detection call is caught at the orchestration
  boundary, logged, calls the sensor's existing `report_error` (transitions
  it to `failed`), and publishes nothing — tested directly
  (`test_a_raising_detection_call_reports_the_sensor_error_and_publishes_nothing`).
- **Invalid window**: the only "invalid window" this sandbox can construct
  without real hardware — empty bytes — is handled gracefully via the
  existing presence gate or the same exception-boundary safety net; tested
  directly. Deeper malformed-input validation is `ai-model-orchestration-engine`'s
  own boundary, not reinvented here.
- **Duplicate window**: no idempotency/dedup key exists anywhere in this
  codebase's outbox convention (confirmed by direct inspection); a
  duplicate ingestion call produces a duplicate event, the same
  at-least-once, idempotent-consumer-expected semantics every other
  engine's outbox already has. Documented as accepted behavior, tested
  directly, not a new gap.
- **Insufficient data**: exactly the existing cost-avoidance presence gate
  — a window with no detected change never reaches a model call or a
  publish; tested directly for both silent audio and the not-`running`
  sensor state.
- **Sensor not `running`** (paused, e.g. consent revoked mid-session, or
  `failed`): a new, explicit check added this pass (not named in the
  closure document's own pseudocode, found necessary during this review) —
  treated as a legitimate no-op, not an error; tested directly.

## 5. Verification results

| Check | Result |
|---|---|
| `ruff check` (whole monorepo, `turbo run lint`) | 18/18 packages pass |
| `mypy` (whole monorepo, `turbo run lint`) | 18/18 packages pass, 0 errors |
| Full pytest suite (whole monorepo, `turbo run test`, excludes `real_infra`) | 18/18 packages pass |
| perception-engine domain/ coverage | 99% (gate: 85%) |
| import-linter | 6/6 contracts kept |
| `docker compose config` (`infra/docker/docker-compose.local.yml`, including the new worker service) | valid |
| TypeScript contract generation | re-run, **zero diff** — no `nova-contracts` payload was added or changed |

21 new tests: 8 for `WindowCorrelationBuffer` (freshness/expiry, both
channels independently), 10 for `handle_observation_window` (every branch
in §4, using a configurable `FakeSensor` double for deterministic control
over failure/edge cases), and 7 through the real, lifespan-driven app with
the real `VoiceSensor`/`CameraSensor` (`test_api_observations.py`).

## 6. Classification — never collapsed, per instruction

| Component | Classification |
|---|---|
| `WindowCorrelationBuffer` (freshness/expiry logic) | **Fully verified** — pure, deterministic, no external dependency |
| `handle_observation_window`'s branching (gate, failure, not-running, correlation) | **Fully verified** against a configurable double, exercising every code path directly |
| The real `VoiceSensor`/`CameraSensor` lifecycle + `detect_presence`/`detect_wake_phrase`/`estimate_attention` calls, driven through the real FastAPI app | **Fully verified** — these are the actual production classes, actually invoked, actually transitioning actual sensor state; the only fake in this chain is `FakeAIModelOrchestrationPort`, standing in for the real `ai-model-orchestration-engine` process (ADR-020's own RPC boundary) |
| `perception.addressee_signal.candidate`'s wire shape reaching a real fusion consumer | **Contract/fake verified** — the payload shape is proven correct and unchanged, but this review did not run a real `communication-engine` process consuming a real bus message from a real `perception-engine` process; that is a two-process, real-infrastructure proof this sandbox cannot perform |
| The new `perception-engine-worker` outbox dispatch | **Infrastructure-dependent, not executed** — `docker compose config` proves the YAML is valid and buildable; no Docker daemon is reachable in this sandbox (confirmed, same limitation as every prior real-infra item in this project), so the worker has never actually run and dispatched a real row here |
| Real Postgres round-trip for anything this priority touches | **Not applicable** — no new migration, no new database interaction (task #93 remains exactly as open as before, untouched) |
| Actual microphone/camera capture, actual wake-word/face-embedding/gaze model output, actual human speech or gaze | **Hardware-dependent, not verified, not claimed** — no such capability exists anywhere in this codebase, and this priority does not add one (§3.1 of the closure document's own boundary, unchanged) |

**What this means plainly, since fake-backed tests passing is explicitly
not sufficient on its own (per instruction):** the code path from a
captured window arriving at the new endpoint through to a correctly-shaped
outbox row is now real, not simulated — the sensors, their lifecycle, their
detection methods, and the fusion/publish sequencing all genuinely execute.
What remains unexecuted in this sandbox is everything *outside*
perception-engine's own process: the real AI-model RPC backend, the real
outbox-dispatch worker process, and a real second engine actually consuming
the published event. None of that is claimed as done.

## 7. A design correction made during implementation, not a fork

The first draft of `api/observations.py` carried the window as a `bytes`
field inside a JSON body. Testing (not review) surfaced that Pydantic's
`bytes` validation from a JSON string does **not** base64-decode it — it
UTF-8-encodes the string verbatim, which would have silently corrupted any
window byte outside the ASCII range (i.e., almost all genuine audio/image
data). Verified directly with a minimal reproduction before concluding this
was a real bug, not a test-setup error. Fixed by moving the window to the
raw request body (`application/octet-stream`) with `source`/`correlation_id`
as query parameters — no base64, no JSON-encoding ambiguity, and every test
in `test_api_observations.py` now exercises the corrected shape. Disclosed
here as a real defect this pass introduced and then caught itself, not
hidden.

## 8. Remaining limitations — explicitly not closed by this pass

- **Priorities 2, 4, 5, and 6 remain exactly as disclosed in the closure
  document.** In particular: no `user_id` reaches the outbound signal or
  perception-engine's own internal identity-matching/session-active calls
  (Priority 2); no cross-context "start listening" mechanism exists
  (Priority 4, and per §6 of the closure doc, was already known to depend
  on Priority 2's resolution); `personality-engine`'s `channel` parameter
  is still inert (Priority 5); real-Postgres verification (task #93) is
  still unexecuted anywhere (Priority 6).
- **`perception.addressee_signal.candidate` can now genuinely reach the
  "uncertain" tier (wake+gaze combined via the correlation buffer) but
  still cannot reach "high"/"activated"** — that requires
  `session_active=True`, which requires `user_id`, which is Priority 2's
  question. This is the same ceiling disclosed to the user before
  implementation began, now precisely confirmed by the shipped code and
  its tests rather than only estimated.
- **No real second process was exercised.** Every test in this pass runs
  within a single perception-engine test process. Genuine two-engine,
  multi-container verification (perception-engine actually publishing,
  communication-engine actually consuming, over a real NATS bus) has not
  been performed and is not claimed.
- **The outbox worker has never actually dispatched a real row.** The
  compose service is defined and validated as syntactically correct; it
  has not run, because no Docker daemon is reachable in this sandbox — the
  same disclosed, unresolved limitation this project has carried across
  every prior real-infrastructure item.
- **`WindowCorrelationBuffer` is a new, small piece of unreviewed-by-the-
  original-TDD design** — it was not named in Phase 2D-B's TDD or the
  closure document; it exists because per-sensor ingestion (the
  user-approved Fork #3 answer) would otherwise never reach fusion's
  higher confidence bands at all. A reasonable, disclosed design choice
  with a single-instance, restart-safe-to-lose scope matching every
  existing precedent in this engine — but genuinely new surface, named
  here rather than described as "already implied by the closure document."

Phase 2D-D has not been started. Priorities 2, 4, 5, and 6 have not been
touched. Per instruction, this review stops here and awaits the user's
review before any further Priority 1-6 work begins.
