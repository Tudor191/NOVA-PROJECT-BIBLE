# Phase 2D-C Closure — Conversation Intelligence Production Readiness

**Status: Priority 3 approved (Fork #1: synchronous RPC) and implemented —
see the
[Priority 3 Gate Review](../../roadmap/architecture-reviews/phase-2d-c-closure-priority-3-gate-review.md).
Priority 1 approved (Fork #3 Option 1: a real ingestion endpoint; and a new,
user-confirmed capability limit — no identity matching or session-active
lookup this pass, deferred to Priority 2) and implemented — see the
[Priority 1 Gate Review](../../roadmap/architecture-reviews/phase-2d-c-closure-priority-1-gate-review.md).
Priority 2 approved (Fork #2: yes, add `Settings.primary_user_id`, Option A
via E exactly as §4.2 recommends; plus two new, user-confirmed decisions —
gate identity matching on active consent before matching, and leave World
Model corroboration unwired this pass) and implemented — see the
[Priority 2 Gate Review](../../roadmap/architecture-reviews/phase-2d-c-closure-priority-2-gate-review.md).
Priorities 4, 5, and 6 remain DESIGN ONLY, exactly as below — no
implementation has begun on any of them, and per direct instruction this
document's remaining sections are not reinterpreted or silently resolved by
Priority 1, 2, or 3's completion.**

This document is the required deliverable of the "Phase 2D-C Closure" task,
using the [Phase 2D-C Gate Review](../../roadmap/architecture-reviews/phase-2d-c-gate-review.md)
(§5.4's six-item breakdown) as its sole authoritative starting point. It does
not reinterpret that Gate Review's findings; it extends them with the direct
code-level investigation the user required before any design choice could be
made, and it does not silently resolve any fork the Gate Review or the
investigation surfaced.

Every finding below was re-verified directly against the current source tree
this session (file paths and line-anchored evidence given throughout), not
recalled from documentation. Where documentation and code disagree, code is
treated as ground truth (Rule 6).

---

## 1. Current Phase 2D-C state (recap, not reinterpreted)

Phase 2D-C is implemented and Gate-Reviewed Go, Option B (per the TDD's
[§0.4](04-conversation-intelligence.md) fork, user-approved). 1,008 tests
pass; ruff/mypy clean; import-linter 6/6. What Go actually certified:

- **Fully verified, real end-to-end**: nothing changes here — see §14 below
  for the four-way classification applied to every path touched by this
  closure.
- **Contract/fake verified**: addressee fusion (`domain/addressee_fusion.py`),
  silence/interruption policy, Clarification Engine, response shaping,
  Conversation Memory — all built and tested against
  `FakePerceptionSignalSource` / fake ports, never against a live upstream.
- **Built but never called by any production code path** (the specific
  finding this closure exists to fix): `perception-engine`'s sensor→fusion→
  publish chain; the communication-engine↔reasoning-engine conversation loop;
  `ResponseShapingDirectivePayload`'s only consumer.

## 2. Dependency graph (Priorities 1-4, Rule 3)

```
                    ┌─────────────────────────────┐
                    │ P1: perception production    │
                    │ signal chain (sensor→fusion→ │
                    │ publish)                     │
                    └───────────────┬──────────────┘
                                    │ produces perception.addressee_signal.candidate
                                    │ (world_model.context.request needs user_id)
                    ┌───────────────▼──────────────┐
                    │ P2: user_id/session           │
                    │ correlation on that payload   │
                    └───────────────┬──────────────┘
                                    │ resolved user_id feeds
                     ┌──────────────┴──────────────┐
                     ▼                              ▼
        ┌─────────────────────────┐   ┌─────────────────────────────┐
        │ P4: start-listening       │   │ P3: communication↔reasoning │
        │ signal (uses SessionRegistry│  │ conversation loop           │
        │ lookup keyed by user_id)   │   │ (independent of P1/P2 —     │
        └─────────────────────────┘   │ triggered by an inbound turn,│
                                        │ not by addressee fusion)     │
                                        └─────────────────────────────┘
                     ┌─────────────────────────┐
                     │ P5: personality channel   │ — independent, no
                     │ parameter                 │   dependency on P1-4
                     └─────────────────────────┘
                     ┌─────────────────────────┐
                     │ P6: real-infra verification│ — independent,
                     │                            │   cross-cutting
                     └─────────────────────────┘
```

**Key finding that reshapes the dependency order the Gate Review implied:**
P3 (the reasoning conversation loop) is **not** downstream of P1/P2. It is
triggered by `communication.turn.received` (a human typing/speaking directly
into an already-connected session), which has nothing to do with
addressee-fusion or perception-engine at all. P1→P2→P4 is one dependency
chain (the "NOVA notices it's being addressed" path); P3 is an entirely
separate, independently buildable chain (the "NOVA answers what was said"
path). They only interact in that both ultimately call the same
`communication.intent` gate. **Recommended build order: P3 first** (it is
self-contained, has the clearest existing precedent to follow, and closes
the single biggest disclosed gap — NOVA cannot currently hold a conversation
at all through the documented loop), **then P1 → P2 → P4** as a chain, **P5**
in parallel with either (fully independent), **P6** continuously tracked
throughout.

## 3. Priority 1 — perception-engine's production signal chain

**Implemented — see the
[Priority 1 Gate Review](../../roadmap/architecture-reviews/phase-2d-c-closure-priority-1-gate-review.md).**
The design below (§3.1-§3.10) is preserved as-written, as the rationale
record. Fork #3 was resolved as Option 1 (a real ingestion endpoint,
`POST /v1/perception/observations`) per direct user approval. A second,
newly-surfaced question not anticipated by this section as originally
written — `VoiceSensor.match_voiceprint`/`CameraSensor.match_faceprint`/
`SessionActivityTracker.is_active` all require a `user_id` this priority
does not have — was put to the user before implementation and resolved as
"build without them, capped capability" (see the Gate Review's §1 for the
full finding and §8 for exactly what this caps).

### 3.1 What "production signal" means in this architecture (stated explicitly, per instruction)

There is no OS-level microphone or camera integration anywhere in this
codebase, and this closure does not add one. `VoiceSensor`/`CameraSensor`
are explicit about their own boundary:

> "this sensor never performs raw OS-level audio capture itself... this
> sensor's detection methods accept an already-captured window from
> whatever upstream transport supplies it — a future desktop/companion
> client, out of this phase's own scope."
> — `sensors/voice_sensor.py:7-18`

"Production signal chain" therefore means: **the path from an
already-captured, already-bounded sensor window (however it arrives) through
detection, fusion, and onto the Event Bus** — not hardware capture. No
upstream transport that supplies such a window exists yet (`apps/` is empty;
no gateway or companion-client service exists in this repository). This
closure is honest about that boundary throughout; it does not fabricate a
capture client.

### 3.2 Current execution path — confirmed directly

`main.py:93-102` constructs `VoiceSensor`/`CameraSensor`, calls
`initialize()` then `start()` on both at startup. Both sensors reach
`running` state. **Nothing else ever happens to them.** Direct confirmation:
grepping the entire perception-engine source tree for callers of
`detect_wake_phrase`, `match_voiceprint`, the camera equivalents, or any of
`events/publishers.py`'s seven shaping functions (`addressee_signal_candidate`,
`wake_detected`, `identity_observed`, `attention_observed`, `presence_observed`,
`consent_changed`, `sensor_health_changed`) returns **zero call sites** outside
their own definitions and `api/sensors.py`'s unrelated health-check plumbing.
`config.py` already carries a `correlation_window_seconds` setting — evidence
this cadence was planned for — but nothing reads it to drive a loop.

There is also no ingestion endpoint. `api/sensors.py` exposes only
`GET /v1/perception/sensors` (list), `POST /v1/perception/sensors/{id}/calibrate`,
and `GET /v1/perception/diagnostics` — no endpoint accepts a captured
audio/video window from a caller. `api/identities.py` and `api/consent.py`
are enrollment/consent surfaces, not capture ingestion.

**Conclusion: this is not a wiring bug in an otherwise-complete pipeline.
Two things are simultaneously missing: (a) any orchestration that turns a
captured window into a fusion signal and publishes it, and (b) any entry
point through which a captured window could arrive in the first place.**

### 3.3 Missing orchestration — what needs to exist

A per-observation-window orchestration function, conceptually:

```
handle_capture_window(sensor_id, window_bytes, correlation_id):
    sensor = sensors_by_id[sensor_id]
    if not sensor.detect_presence(window_bytes):   # cost-avoidance gate, already exists (Sec7.2)
        return
    wake = await sensor.detect_wake_phrase(window_bytes, correlation_id=...)   # already exists
    identity_signal = await sensor.match_voiceprint(window_bytes, user_id=..., correlation_id=...)  # already exists
    # correlate voice + camera results arriving within correlation_window_seconds
    # (identity_fusion.fuse_window / smooth — already exists, unit-tested, Sec6)
    gaze = ...  # from camera sensor's own equivalent detection call
    session_active = session_tracker.is_active(user_id)   # already exists
    event = addressee_signal_candidate(...)   # already exists, events/publishers.py:108
    await repository.enqueue_outbox(event)    # already exists (outbox pattern, every engine)
```

Every ingredient this function needs already exists and is already
unit-tested in isolation (`identity_fusion.fuse_window`/`smooth`,
`VoiceSensor.detect_wake_phrase`/`match_voiceprint`, `events/publishers.py`,
the outbox). **Nothing new needs to be invented at the domain-logic level.**
What's missing is purely the orchestration that calls them in sequence and
the entry point that triggers it.

### 3.4 Lifecycle / startup / shutdown behavior

No change to the existing sensor lifecycle state machine
(`domain/sensor.py`) is needed — `initialize()`/`start()` at startup and
`stop()` at shutdown (guarded for already-stopped sensors, `main.py:128-134`)
already correctly manage `VoiceSensor`/`CameraSensor`. The new orchestration
is a consumer of already-`running` sensors, not a change to how they start
or stop.

### 3.5 Event/outbox behavior

Unchanged pattern: the orchestration calls the existing
`events/publishers.py` shaping functions and enqueues via the existing
repository outbox port (`enqueue_outbox`), dispatched by the existing
`workers/outbox_dispatcher.py` / Arq worker cron (`workers/__init__.py`) —
**which itself is defined but not deployed as a separate process in
`docker-compose.local.yml` for any engine in this repository, not just
perception-engine.** This is a pre-existing, codebase-wide gap, confirmed
by inspecting the compose file: only `uvicorn` processes run; no `*-worker`
service exists anywhere. This closure does not silently expand scope to fix
that for all eight affected engines (Rule 13), but flags it as a
**cross-cutting infrastructure gap this specific closure will make visible
in practice for the first time** — until a worker process is actually
deployed, perception-engine's newly-orchestrated outbox rows will queue but
never dispatch. **This must be deployed (docker-compose + CI) as part of
Priority 1's own "done" definition**, not deferred, because otherwise the
freshly-built orchestration produces outbox rows nobody ever sends — the
same "claim production readiness before the path exists" failure Rule 15
forbids.

### 3.6 Failure handling

Mirrors `domain/sensor.py`'s existing `report_error`/`fail` transition and
`api/sensors.py`'s health-check pattern: a detection call that raises is
caught at the orchestration boundary, logged, and calls
`sensor.report_error(...)` (already implemented, transitions the sensor to
`failed`), without publishing a malformed or partial `addressee_signal.candidate`.
No event is better than a wrong one here — matches the existing "no single
signal sufficient" doctrine (Doc 22 Principle 7): a fusion consumer
(communication-engine) that never receives a signal behaves identically to
one it correctly ignored.

### 3.7 Is the Sensor Abstraction Layer sufficient?

Yes. Every method the orchestration needs (`detect_presence`,
`detect_wake_phrase`, `match_voiceprint`, and the camera sensor's
equivalents) already exists on the concrete sensor classes and is already
exercised by unit tests. No Protocol change is required.

### 3.8 Is a new cross-engine contract required?

No new contract. `perception.addressee_signal.candidate`'s shape is
unchanged by this priority (Priority 2 changes it, separately, below).

### 3.9 Tests required

- Unit tests for the new orchestration function against fake sensors/fake
  repository (fast tier, no real infra) — verifying: presence-gate
  short-circuits correctly; a wake+identity+gaze window produces the
  correct `addressee_signal_candidate` fields; a sensor exception is
  caught and does not publish; the outbox row is enqueued exactly once per
  window.
- An integration test proving the orchestration is actually wired to
  something that calls it (whatever the ingestion mechanism turns out to
  be — see the fork below).
- Docker-compose validation that the outbox worker process is actually
  running and dispatches a real enqueued row (closes §3.5's gap).

### 3.10 The fork requiring the user's decision

**What triggers the orchestration, given no real capture transport
exists?** Two genuinely different, both-valid answers:

- **Fork Option 1 — Add a real ingestion endpoint now.** A new
  `POST /v1/perception/observations` (or WS) endpoint that accepts an
  already-captured window and synchronously runs the orchestration. This
  mirrors the existing precedent exactly: `communication-engine`'s own WS
  endpoint "reads from an already-connected WebSocket, never opens a
  microphone" — i.e., it is normal and already-established in this
  codebase for a REST/WS surface to exist and simply wait for a caller
  that doesn't exist yet. This makes the chain genuinely real end-to-end
  from the moment any future client exists, with zero further
  perception-engine changes needed then. **Cost:** reopens a Gate-Reviewed
  Go engine with a new externally-facing API surface (the same tradeoff
  the TDD's own §0.4 named for "Option A").
- **Fork Option 2 — Build the orchestration function only, leave the
  ingestion mechanism as an explicitly disclosed follow-up.** Build and
  test the orchestration in isolation (§3.3-3.9 above), triggered only by
  tests / a manual admin call for now, and open a separately tracked item
  for "how a real window actually arrives" — deferring that decision until
  an actual companion-client transport is scoped (naturally Phase 2D-D or
  later). **Cost:** the chain is real up to the ingestion boundary but
  still cannot be observed working against anything resembling production
  traffic; repeats the exact disclosure pattern the TDD's own §0.4 Option
  B already used once.

This document's recommendation, offered but not assumed (mirroring how the
TDD itself handled §0.4): **Fork Option 1**. It costs one small, narrowly-
scoped new endpoint, closes the gap completely rather than partially, and
is lower risk than it sounds because REST/WS endpoints waiting for a
not-yet-built caller are already normal in this codebase (`api/sensors.py`
and the whole WS transport layer are exactly this shape already). But this
is a genuine architectural decision — a new public API surface on a
Gate-Reviewed engine — and per instruction this document stops here rather
than deciding it.

## 4. Priority 2 — the `user_id`/session-correlation problem

**Implemented — see the
[Priority 2 Gate Review](../../roadmap/architecture-reviews/phase-2d-c-closure-priority-2-gate-review.md).**
The design below (§4.1-§4.3) is preserved as-written, as the rationale
record. Fork #2 was resolved exactly as §4.2 recommends — Option A via E:
a new `Settings.primary_user_id: UUID | None`, populated onto every
outbound `perception.addressee_signal.candidate` regardless of whether
biometric identity matched. Two further decisions, not anticipated by this
section as originally written, were put to the user before implementation
and both resolved as recommended: identity matching
(`match_voiceprint`/`match_faceprint`) is now gated on active per-source
consent before it runs (Doc 22 Principle 8), and World Model's
`corroborate_identity_confidence` RPC remains deliberately unwired this
pass — see the Gate Review's §1 for the full findings.

### 4.1 Investigation findings

- `world_model.context.request` (the RPC `corroborate_identity_confidence`'s
  live caller would need) is **keyed by `user_id: UUID`, required, no
  alternative key** (`events/world_model.py:120-130`). There is no way to
  call it with only an `identity_id`.
- `perception.addressee_signal.candidate` carries `identity_id: UUID | None`
  but no `user_id` (`events/perception.py:130-145`).
- `EnrolledIdentity` (perception-engine's own Identity Registry) already
  links `identity_id → user_id` directly (`domain/models.py:45-57`) — but
  this link is **only available when a specific enrolled person was
  matched**, which is `identity_id is not None`.
- **This is not sufficient on its own.** The fusion formula
  (`domain/addressee_fusion.py`, verified against its own tests) reaches the
  `high`/"activated" threshold from `wake_word + gaze + session_active`
  alone, with `identity_confidence=0` and `identity_id=None`
  (`test_wake_word_gaze_and_active_session_reaches_exactly_the_high_threshold`,
  scoring exactly 0.70). **The majority-relevant case for Priority 4 — a
  clean high-confidence activation with no biometric match — is exactly the
  case where identity-based `user_id` resolution silently fails.** Relying
  solely on `EnrolledIdentity.user_id` would leave `user_id` null in
  precisely the scenario that matters most.
- No engine anywhere in this codebase resolves "the current user" from
  ambient/config state today — `user_id` is always an explicit, caller-
  supplied field on every request that needs it (confirmed: no
  `DEFAULT_USER_ID`/`PRIMARY_USER`/similar convention exists anywhere;
  `POST /v1/communication/sessions` requires a client-supplied `user_id`;
  `ReasoningRequestPayload.user_id` is required with no default).
- perception-engine has **no `device_id` concept anywhere** in its source
  tree — confirmed by exhaustive grep. This, plus `SessionRegistry`'s own
  docstring — **"this phase's real deployment is one concurrent session
  per instance" (ADR-025's single-user default)**
  (`session_registry.py:1-9`) — is strong, direct textual support that this
  deployment genuinely has exactly one relevant user per running instance,
  not a multi-tenant or multi-profile-household model this phase.
- ADR-025 itself: "Every engine, by default, is designed and configured for
  a single trusted user — 'who is calling' never requires an
  organization/tenant model to answer unless enterprise mode is explicitly
  enabled" (Decision item 1). This is direct, on-point authority for
  treating "the one user this instance serves" as a legitimate
  configuration-level fact, not something that must be re-derived from a
  biometric signal on every event.

### 4.2 Options compared (as required)

- **A. Add `user_id` directly to the payload.** Necessary regardless of how
  it's populated (§4.1 already establishes the RPC needs it) — the open
  question is *how it's populated*, not *whether the field exists*.
- **B. Add a session/conversation correlation identifier instead.** Doesn't
  solve the World Model corroboration call (`world_model.context.request`
  needs `user_id`, not a session id) and doesn't solve the cold-start case
  either — Priority 4's whole point is that no session exists yet when this
  matters most. Rejected as a substitute for `user_id`, though a session
  identifier may still be useful as an *additional* field for a warm-session
  case (see Priority 4).
- **C. Correlate through an existing context (World Model's ActiveContext,
  already keyed by `user_id`).** Circular — this still requires a `user_id`
  to query with; it relocates the problem rather than solving it.
- **D. Introduce another explicit signal.** E.g., a separate
  `perception.identity.resolved` event published only when
  `identity_id` is non-null. Doesn't help the no-identity-match case, which
  is the case that matters most for Priority 4's activation path. Rejected
  as insufficient alone.
- **E. Rely on ADR-025's single-instance-per-user deployment assumption.**
  Configure perception-engine (a new `Settings.primary_user_id: UUID`,
  mirroring how every engine already gets its Postgres DSN etc. via
  `Settings`) with the one user_id this instance serves, set once at
  deployment/onboarding time. Every outbound `addressee_signal.candidate`
  populates `user_id` from this configured value — **uniformly, regardless
  of whether biometric identity matched** — closing exactly the gap A/D
  leave open. `identity_id`, when present, remains a separate, more
  specific, additional signal (unchanged — `corroborate_identity_confidence`
  already consumes it correctly on its own).

**These are not mutually exclusive.** The recommended answer is **A,
populated via E**: add a required `user_id: UUID` field to
`PerceptionAddresseeSignalCandidatePayload`, sourced from instance-level
configuration justified by ADR-025, not derived per-event from
`EnrolledIdentity`. Communication-engine (the authoritative owner of real
session state) then does its own `user_id → session_id` resolution via its
existing `SessionRegistry`/repository when it needs to correlate to a
specific session (Priority 4) — perception-engine does not need to expose
session data at all; its own `SessionActivityTracker` mirror stays exactly
as scoped today (a boolean input to fusion, nothing more).

### 4.3 Is this a genuine fork? — Yes, flagged per instruction

The mechanics have a well-argued single best answer (A via E, above). What
remains a genuine decision for the user is **whether to encode a
config-level "primary user" onto perception-engine at all**, given this is
the first place in the codebase that would do so explicitly. This is a
real product/deployment-model decision (how onboarding assigns this value,
whether it's allowed to differ from other engines' notion of "the" user,
what happens if it's ever wrong), not just an engineering detail — it
touches the Personal Edition's actual onboarding story, which this
document has no authority to decide silently. **Flagged as Fork #2 in §12.**

## 5. Priority 3 — the communication-engine ↔ reasoning-engine conversation loop

**Implemented — see the
[Priority 3 Gate Review](../../roadmap/architecture-reviews/phase-2d-c-closure-priority-3-gate-review.md).**
The design below (§5.1-§5.5) is preserved as-written, as the rationale
record — the approved design was Fork #1 (synchronous RPC), built
essentially as designed, with one disclosed scope reduction (response-shaping
hints were not threaded into the reasoning request — the Gate Review's §1
explains why) and one implementation-level judgment call flagged for
confirmation (the Gate Review's §7).

### 5.1 Confirmed: the documented chain does not exist, on **both** ends

Direct grep of every engine's `events/subscribed.py`/`published.py`:

- `communication-engine` **publishes** `communication.turn.received`
  (`events/published.py:23`) — but **no engine in this codebase subscribes
  to it.** Grepping the whole `services/` tree for
  `"communication.turn.received"` outside communication-engine itself
  returns zero hits.
- `communication-engine` **subscribes to** `communication.intent.deliver.request`
  (`events/subscribed.py:21`) — but **no engine publishes it.** Grepping the
  whole tree for `"communication.intent.deliver.request"` outside
  communication-engine returns zero hits.
- `reasoning-engine` subscribes to exactly one subject:
  `reasoning.reason.request` (`events/subscribed.py:9`) — a **served RPC**,
  not an event subscription in the pub/sub sense. Grepping the whole tree,
  **nothing calls it** except reasoning-engine's own `POST /v1/reasoning/reason`
  REST handler.
- `reasoning-engine` publishes only lifecycle events
  (`reasoning.process.completed/.failed`, `reasoning.human_override.applied`)
  plus its own outbound RPC calls to memory/knowledge/world-model/ai-model.
  **No content ever leaves reasoning-engine except via the synchronous
  RPC reply** (`ReasoningReplyPayload.chosen_description`,
  `events/reasoning.py:120-133`) — confirmed deliberate:
  `domain/pipeline.py::run()` is the sole entry point for both the HTTP
  and RPC callers, and returns `(Decision, ReasoningTrace, Alternative | None)`
  directly, never via a published event.
- `executive-cognition-engine`'s own event lists (checked directly) touch
  neither `reasoning.*` nor `communication.*` at all — it is not a hidden
  intermediary.

**Conclusion, stated plainly: this is not one broken hop in an otherwise-
wired loop. Nothing on either side has ever been connected. If a human
speaks to communication-engine today, a turn is recorded and
`communication.turn.received` is published into a void; nothing responds.**

### 5.2 What already exists and is directly reusable

- `resolve_response_shaping()` (`domain/response_shaping.py:70-95`) is
  **already fully built, already calls `personality.style.select` via the
  existing synchronous `PersonalityPort`, already handles the degraded/
  timeout fallback** (Doc 22 Principle 3 — never block delivery). It is
  simply never called from the real turn-handling path yet.
  `ResponseShapingDirectivePayload`'s own docstring already says exactly
  this: "communication-engine computes and publishes this; it does not
  itself apply it... Whether/how a content-source engine currently consumes
  it is explicitly *not* implied by this payload's existence" — an honest,
  pre-existing disclosure, not new information.
- `personality-engine` needs **no changes** for this loop — it is already
  correctly called via `PersonalityPort`.
- Every other cross-engine call communication-engine makes today
  (`personality.style.select.request`, `world_model.context.request`,
  `ai_model.transcribe.request`/`synthesize.request`) is **synchronous
  request/reply over the Event Bus** (`bus.request()`), not
  publish-then-separately-subscribe. This is the engine's own established,
  consistent pattern — 100% of its existing cross-engine integrations use
  it, none use async pub/sub for a result it needs back.
- `ReasoningRequestPayload` (`events/reasoning.py:99-117`) already has
  `user_id: UUID` and `requesting_engine: str` as required fields —
  precedent that reinforces Priority 2's recommendation, and confirms
  `reasoning.reason.request` is already designed to be called by exactly
  this kind of caller.
- `communication.session.create.request` is **already a served RPC**
  (`make_session_create_handler`, `events/handlers.py:157-173`), directly
  relevant to Priority 4 below.

### 5.3 The design

1. Communication-engine's turn-handling path (`session_lifecycle.record_inbound_turn`,
   called from `api/websocket.py`/`api/sessions.py`) already persists the
   turn and publishes `communication.turn.received`. Immediately after,
   call `resolve_response_shaping()` (already built, §5.2) to get style/
   verbosity/technical_depth.
2. **New**: call `reasoning.reason.request` synchronously (mirroring the
   three existing RPC calls this engine already makes), passing the turn's
   content as `objective_text`, the session's `user_id`, `requesting_engine="communication-engine"`,
   and — **new, additive field(s)** on `ReasoningRequestPayload` — the
   resolved response-shaping directive (style/verbosity/technical_depth/
   situation_hint), optional/defaulted per ADR-024.
3. **New, inside reasoning-engine**: `domain/pipeline.py::run()`'s
   generation step (wherever it currently calls `model_port.generate` /
   `ai_model.generate.request`) folds these hints into the prompt/
   instructions it sends — additive, does not change ADR-020's sole-legal-
   provider-channel path.
4. Reasoning-engine returns synchronously, as it already does today (no
   change to its reply contract) — `ReasoningReplyPayload.chosen_description`
   is the response text.
5. Communication-engine receives the reply in the same call stack and
   invokes its **own existing `communication.intent` gate directly, in-
   process** — not via a round trip through `communication.intent.deliver.request`.
   The gate already lives inside this engine's process; nothing about
   ADR-005 requires the call to leave the process to reach it.
6. `communication.intent.deliver.request` (still subscribed, unchanged)
   is reserved for **out-of-band deliveries that do not originate from a
   live conversational turn** — e.g., a future proactive notification or
   reminder initiated by executive-cognition-engine or another engine
   that is not itself already inside a turn-handling call stack. This is a
   legitimate scope clarification of an already-built, already-correct
   gate — not a contradiction of its existing contract.
7. `communication.response_shaping.directive` keeps being published
   (already built, cheap) for observability/audit purposes (Doc 22's
   explainability principle) even though the actual mechanism this loop
   uses to deliver shaping to reasoning-engine is the synchronous RPC
   field, not a subscription — no consumer needs to subscribe to it for
   this loop to work.
8. **Degraded/failure propagation**: `resolve_response_shaping()` already
   defines the personality-unreachable fallback. A new, symmetrical
   fallback is needed for reasoning-engine being unreachable/timing out or
   returning `outcome != decided` — deliver a short, honest "I'm having
   trouble with that right now" utterance via the intent gate (mirroring
   `domain/intent_gate.py`'s own existing Sec9 hardcoded minimal-safe
   fallback pattern) rather than hanging the turn or silently dropping it
   (Doc 22 Principle 3, again). The exact fallback copy is an
   implementation-time detail, not a fork.

### 5.4 Engines requiring changes (explicit list, per instruction)

- **`reasoning-engine`**: additive fields on `ReasoningRequestPayload` (and
  the corresponding domain `ReasoningRequest`); the generation-prompt-
  building step folds in the shaping hints.
- **`communication-engine`**: new orchestration in the turn-handling path
  (call `resolve_response_shaping`, then `reasoning.reason.request`, then
  the in-process intent gate); new degraded-mode fallback for a reasoning
  failure.
- **`personality-engine`**: no changes.
- **`nova-contracts`**: additive schema change to `ReasoningRequestPayload`
  (ADR-024 compliant — optional, versioned).

### 5.5 Is this a fork requiring the user's decision?

**Yes — flagged as Fork #1 in §12.** The alternative (an event-driven
loop: reasoning-engine subscribes to `communication.turn.received`,
eventually publishes `communication.intent.deliver.request` itself) matches
what the subject names' own docstrings originally implied ("publishing
`communication.turn.received` for Reasoning Engine" — `session_lifecycle.py:5`)
and would keep the two engines more loosely coupled. But it requires
inventing a new capability reasoning-engine deliberately does not have today
(publishing response content as a bus event, which its own pipeline
docstring frames as a deliberate choice, not an oversight — broadcasting
raw response text onto a shared bus any engine can subscribe to is a larger
disclosure surface than a scoped point-to-point RPC reply) and has zero
existing precedent anywhere in this codebase. This document's
recommendation, offered but not assumed: **the synchronous design (§5.3)**,
because it has 3-for-3 existing precedent, requires no new privacy-relevant
capability, and is the smaller change — but this is exactly the kind of
"correct architecture requires changes to multiple engines" decision Rule
13/14 require surfacing rather than deciding silently.

## 6. Priority 4 — the "start listening" cross-context mechanism

### 6.1 Corrected framing (established this session, refining the Gate Review's own framing)

`WS /v1/communication/sessions/{session_id}` requires `session_id` as a
path parameter — **a `ConversationSession` must already exist before any
WebSocket connects at all** (`api/websocket.py:56-59`). "Start listening"
therefore cannot mean "activate a session" in the create/materialize sense
for an already-connected client; for an already-connected client it means
injecting the equivalent of the client-sent `InboundMessageKind.TRIGGER_START`
signal server-side, into that connection's already-running receive loop —
exactly the same shape as `BargeInSignal`, just the "start" counterpart to
its existing "stop."

### 6.2 Two genuinely different cases, not one

- **Warm case — a session already exists and has a live, registered
  WebSocket connection** (`SessionRegistry.is_connected(session_id)` is
  `True`) — e.g., a connected companion device sitting idle/paused,
  waiting for a wake word its own local detection didn't catch but
  perception-engine's server-side fusion did. **This is closeable now**:
  add a new `StartListeningSignal` to `SessionRegistry`, exactly mirroring
  `BargeInSignal`'s existing shape (`session_registry.py:28-53`) — a
  per-session in-process signal object, checked by the WS loop's existing
  receive-timeout poll cycle (`api/websocket.py`'s `_SILENCE_POLL_INTERVAL_S`
  cadence, which already polls `barge_in_signal` on the same cadence) —
  flipping the loop's local `turn_active` state the same way client-sent
  `TRIGGER_START` already does, without waiting for the client to send it.
- **Cold case — no session exists yet, and/or no client is connected at
  all.** `communication.session.create.request` already exists as a served
  RPC and could in principle be called by an addressee-fusion handler
  reaching a high-confidence "activated" outcome with `session_active=False`
  — **but `CommunicationSessionCreateRequestPayload.device_id` is a
  required field** (`events/communication.py:117-123`), and
  perception-engine has no `device_id` concept anywhere (§4.1). Even if a
  session were created, **nothing would connect a WebSocket to it** — that
  requires the same not-yet-existing companion-client transport Priority 1
  already discloses does not exist. **This case is explicitly out of reach
  this phase, for the identical, already-disclosed reason as Priority 1 —
  not a new gap, the same one, surfacing in a second place.**

### 6.3 The design (warm case only, per §6.2)

1. `SessionRegistry` gains `_start_listening_signals: dict[UUID, StartListeningSignal]`,
   populated/torn down in `register`/`unregister` exactly like
   `_barge_in_signals` is today.
2. A new method `trigger_start_listening(session_id)`, exactly mirroring
   `trigger_barge_in`.
3. communication-engine's own addressee-fusion handler (already subscribed
   to `perception.addressee_signal.candidate`, already computing
   `FusionOutcome`) — on `tier == "high"` / `action == "activated"` **and**
   `SessionRegistry.is_connected(session_id)` is `True` for the session
   resolved via Priority 2's `user_id` — calls `trigger_start_listening`.
4. `api/websocket.py`'s receive loop checks this signal on the same poll
   cadence it already checks `barge_in_signal`, and if set, behaves exactly
   as if `InboundMessageKind.TRIGGER_START` had arrived from the client,
   then clears the signal (one-shot, mirroring how barge-in's own signal
   is consumed).
5. **A `ConversationDecisionTrace` row is written for every trigger**
   (mechanism already exists, §3.2 of the TDD) — this activation is
   exactly the kind of consequential, explainable decision Doc 22
   Principle 7's probabilistic framing requires a visible trace for.

### 6.4 Preserved constraints — explicit check against every one named

- **ADR-005** (communication.intent is the only output gate): untouched —
  this mechanism only starts *listening*, never *speaking*. No content is
  generated or delivered by this signal.
- **Consent boundaries**: unaffected — sensor-level consent
  (`api/consent.py`, `domain/consent.py`) already gates whether perception
  publishes anything at all; this mechanism only acts on a signal that
  already passed that gate.
- **Identity-confidence rules / ADR-032**: identity confidence is **not**
  used as an authorization mechanism here — the trigger condition is the
  fusion `tier`/`action` (a *combination* of wake word + gaze + session
  state, with identity as one optional contributing signal among several,
  per `domain/addressee_fusion.py`'s own weighted formula), never
  `identity_confidence` alone. A session that already exists and is
  already connected is, definitionally, a session the user (or their
  already-connected device) already established through the existing,
  unmodified session-creation/consent path — this mechanism does not grant
  any capability a connected session didn't already have.
- **Doc 22 Principle 6** (context over keywords, false-positive strictly
  worse than false-negative): the trigger condition is the *same* fusion
  outcome already designed and tested to satisfy this principle
  (`domain/addressee_fusion.py`) — no new, separate detection logic is
  introduced.
- **Doc 22 Principle 7** (probabilistic, never binary): preserved by
  §6.3 item 5's decision-trace requirement — every activation is recorded
  with its confidence tier and reasoning, not treated as a silent binary
  flip.
- **Emotional stability rules**: unaffected — this mechanism does not
  change what NOVA says or how, only whether an already-existing,
  already-connected session starts listening.
- **"No single signal sufficient"**: preserved exactly — the trigger is
  `fuse()`'s multi-signal `tier == "high"` outcome, never a single raw
  signal.
- **Does not bypass the existing communication state machine**: preserved
  — the mechanism only flips the same local `turn_active` closure variable
  the client's own `TRIGGER_START` message already flips; the actual FSM
  `TRIGGER` event still only fires later, atomically with `CAPTURED`,
  inside `record_inbound_turn`, exactly as it does today for a
  client-initiated trigger.

### 6.5 Is this a fork?

No genuine fork for the warm case — §6.3's design is a narrow, direct
structural mirror of an already-approved precedent (`BargeInSignal`), with
every named constraint checked and preserved. The cold case is not a fork
either; it is an already-disclosed, shared limitation with Priority 1, not
a new decision to make.

## 7. Priority 5 — personality-engine's inert `channel` parameter

### 7.1 Why it exists, confirmed directly

`select_style`'s own docstring is explicit and already honest about this:
"`channel` is accepted for forward compatibility (Master Blueprint §13.6)
but does not yet influence selection — no Phase 2D-A acceptance criterion
depends on channel-specific style, and inventing that rule now, untested
against real usage, would be exactly the 'quality over feature count'
violation Master Blueprint §13.7 forbids" (`domain/style_selector.py:26-34`).
This was a deliberate, disclosed deferral from Phase 2D-A, not an oversight
— Master Blueprint §13.6 ("Progressive capability") names exactly this
kind of forward-compatible-but-inert parameter as an intentional pattern
used elsewhere in this project (`device_id` in the session schema is the
blueprint's own cited example).

`response_shaping.py`'s own docstring already discloses the same thing from
the caller's side: "`personality-engine`'s own `channel` parameter... is
documented but currently inert... passed through here unchanged... but
style selection will not actually vary by channel until that engine's own
fix lands" (`domain/response_shaping.py:17-22`).

### 7.2 The plan (smaller item, no fork)

A narrow, deterministic, channel-based **verbosity** adjustment only —
never `style`/tone/personality itself, preserving Personality Consistency
(the standing directive) and Doc 23 §7's own consistency test ("if a
proposed change would make NOVA feel like a different entity... it belongs
in the Constant column"). Concretely: `ChannelType.VOICE` caps verbosity at
a bound below `ChannelType.TEXT`'s ceiling (spoken responses are
synchronous and harder to skim/re-read than text — a Doc 22 "respect for
time" consideration, not a personality difference). `technical_depth` and
`style` remain unaffected by channel — the same content depth and
personality, expressed more concisely when spoken. This is a controlled
adaptation of the expression layer only, exactly the boundary Doc 23 §2/§7
already sanctions (verbosity/pacing/channel are explicitly named as
adaptive; identity/values/voice are not).

Existing test coverage: the current test suite for `select_style` has at
least one test that currently asserts channel has *no* effect — that test
will need to be rewritten to assert the new, intentional verbosity
difference rather than the bug it currently documents as correct behavior.

**Sequencing**: per the dependency-analysis instruction (Rule 3), this
item has no dependency on P1-P4 and could be done at any point — it is
sequenced last only because it is the smallest, most isolated, and lowest-
risk item, not because anything blocks it.

## 8. Priority 6 — real infrastructure verification status

### 8.1 Confirmed status (unchanged from the Gate Review, re-verified this session)

- `.github/workflows/real-infra-checks.yml` exists and is registered on
  GitHub Actions, but has **never executed** (`total_count: 0` runs) —
  no PR has ever been opened against this repository and no `main` branch
  exists yet to trigger it.
- The local sandbox environment cannot run it either — `docker info` fails,
  no reachable Docker daemon.
- `tests/integration/test_repository_real_postgres.py`
  (communication-engine, re-read directly this session) is real, complete,
  and correctly marked `@pytest.mark.real_infra` (ADR-033) — it exercises
  real Alembic-migrated schema, a real foreign-key constraint the fake
  repository cannot represent, and real `onupdate` timestamp behavior,
  including the Phase 2D-C additive schema (`ConversationMemory`,
  `interrupted_content`, `dnd_override`, `pending_questions`,
  `ConversationDecisionTrace`'s nullable `session_id`). It has never been
  executed anywhere, by its own docstring's own honest admission.
- **Offline partial validation is possible and was confirmed working**:
  `alembic history` and `alembic upgrade head --sql` both run without
  Docker and validate migration syntax and the migration chain — but this
  validates schema/migration correctness only, not execution of the
  `real_infra`-marked pytest suite itself (no INSERT/SELECT/UPDATE round
  trip, no real FK enforcement, no real timestamp behavior is actually
  exercised by this fallback).

### 8.2 Explicit prohibitions honored

This closure does **not** claim task #93 complete, does not fabricate a
passing Docker run, does not weaken or remove the `real_infra` marker, does
not delete these tests, and does not substitute a fake for real
infrastructure and call it equivalent. **Task #93 remains explicitly open.**

### 8.3 Disclosed fallback for the new communication-engine migration work this closure adds

Priority 4's `SessionRegistry` change is in-process/no schema change.
Priority 1's outbox usage is schema-unchanged (existing `enqueue_outbox`
port). Priority 3's `ReasoningRequestPayload` change is contract-only, no
migration. **This closure introduces no new database migrations** — so
Priority 6's scope for this closure is unchanged from its existing state:
keep the same offline `alembic upgrade head --sql` validation available for
whichever engine's migrations are touched, continue disclosing the gap at
every Gate Review, and execute the real suite the moment a Docker-capable
environment (or a real PR/CI run) becomes available.

## 9. Architecture decisions this closure makes (not forks — recorded here for traceability)

- Priority 1 §3.4-3.9: orchestration design, sensor sufficiency, test plan
  — no fork, single recommended design.
- Priority 2 §4.2: Option A populated via Option E — no fork on the
  mechanics; the fork is narrower (§4.3, Fork #2).
- Priority 3 §5.3: synchronous in-process design — fork on approach itself
  (Fork #1), synchronous design is the recommendation if approved.
- Priority 4 §6.3: `StartListeningSignal` mirroring `BargeInSignal` — no
  fork, direct structural precedent.
- Priority 5 §7.2: channel-scoped verbosity only, never style/tone — no
  fork.

## 10. Open forks requiring the user's decision (consolidated)

**Fork #1 (Priority 3):** Synchronous in-process RPC design (recommended)
vs. event-driven pub/sub design matching the subjects' original naming
intent. See §5.5.

**Fork #2 (Priority 2):** Whether to encode a config-level "primary user"
onto perception-engine (and by extension, formalize this as the pattern
other future single-instance-scoped engines follow), given this is the
first explicit instance of that pattern in the codebase. See §4.3.

**Fork #3 (Priority 1):** New perception-engine ingestion endpoint now
(recommended) vs. orchestration-only with the ingestion mechanism deferred
as a separately tracked follow-up. See §3.10.

Priority 4 and Priority 5 have no open forks (§6.5, §7.2).

## 11. Testing strategy (applies across Priorities 1-5)

Two-tier convention unchanged (ADR-033): fast unit/contract tests against
fakes for every new function (default `pytest`/`turbo run test`), plus
`real_infra`-marked tests only where a new migration or real-Postgres
behavior is introduced (none is, this closure — §8.3). New integration
tests specifically prove the previously-missing *wiring*, not just the
already-tested domain logic in isolation — e.g., a test asserting that
publishing `communication.turn.received` through the real turn-handling
path actually results in a `reasoning.reason.request` call and an intent-
gate invocation, using `nova-testkit` fakes for reasoning/personality
rather than fake-driven unit tests of the orchestration function alone.

## 12. Migration strategy

No new database migrations this closure (§8.3). `ReasoningRequestPayload`'s
new fields are optional/defaulted (ADR-024) — zero-downtime, no consumer
breakage. `PerceptionAddresseeSignalCandidatePayload.user_id` (Priority 2)
is a **breaking, required-field addition** to an already-registered
contract — since `communication-engine` is this payload's only consumer
and both engines deploy from the same monorepo/compose file, this is a
coordinated same-release change, not a staged rollout, consistent with how
every other contract change in this project has been handled (no
independent-deployment requirement exists yet for this codebase).

## 13. Rollback / failure behavior

Every new integration point degrades to "NOVA says nothing" or "NOVA
answers with an honest fallback," never to a crash or a fabricated
response, consistent with Doc 22 Principle 3 and the existing
`intent_gate.py` Sec9 pattern: reasoning-engine unreachable → fallback
utterance (§5.3 item 8); personality-engine unreachable → already-built
degraded defaults (§5.2); perception-engine orchestration failure → no
event published, sensor marked failed, no partial/malformed signal
(§3.6); start-listening signal with no connected session → no-op (the
signal is simply never set, §6.2 cold case).

## 14. Production-readiness criteria — four-way verification classification

Applied per instruction, never collapsed, for every new integration this
closure would add:

| Integration | Classification once built |
|---|---|
| Priority 1 orchestration (fake sensors/repo) | Contract/fake verified |
| Priority 1 orchestration ↔ real ingestion endpoint (Fork #3, if chosen) | Fully verified (real HTTP path), not end-to-end (no real capture client) |
| Priority 2 `user_id` field round-trip | Contract/fake verified until Priority 1's real path exists |
| Priority 3 communication→reasoning RPC | Fully verified (real synchronous call between real running engines) once built — this is the one item that becomes genuinely end-to-end without needing a hardware client, because both sides already run and the loop is entirely internal |
| Priority 3 reasoning→intent-gate delivery | Fully verified, same reasoning |
| Priority 4 `StartListeningSignal` (warm case) | Fully verified — same reasoning, no external client needed to prove a session that's already connected starts listening |
| Priority 4 cold case | Not applicable — explicitly out of reach this phase (§6.2) |
| Priority 5 channel-based verbosity | Fully verified (deterministic, no external dependency) |
| Priority 6 (all real-Postgres suites) | Real-infrastructure verified in code, **not yet real-infrastructure executed** — remains explicitly open |

**Note the asymmetry worth highlighting to the user directly**: Priority 3
and the warm case of Priority 4 can become **genuinely, fully
end-to-end production-verified** by this closure — no hardware, no
companion client, no fabrication required, because the entire loop runs
between already-existing, already-running engines. Priority 1 (and the
cold case of Priority 4) **cannot** reach that bar this phase, no matter
how the fork is resolved, because the thing they depend on — a real
capture/connection client — does not exist anywhere in this project yet.
This closure does not blur that line.

---

## 15. End-of-research summary (delivered to the user separately in this session's reply, per instruction — this section restates it for the document's own completeness)

See the chat response for the required 6-item summary (what's already
sufficient, what's genuinely missing, dependency order, every fork,
recommended architecture per fork, and what is proposed to implement
first). This document does not begin implementation; it is the design
artifact that summary references.
