# Architecture Review Report — Phase 2D-A: Voice & Communication Foundation

**Phase:** 2D-A — Voice & Communication Foundation (Bible Parts 13, 17)
**Completed:** 2026-08-07
**Design document(s):** [docs/design/phase-2d/](../../design/phase-2d/README.md) —
`00-master-blueprint.md` (the Phase 2D Master Architectural Blueprint, approved before
any Phase 2D-A design work began), `01-communication-engine.md` and
`02-personality-engine.md` (both full Technical Design Documents, approved before
implementation began), plus two non-technical foundational documents required before
any of the above:
[Doc 22 — NOVA Human Interaction Principles](../../architecture/22-nova-human-interaction-principles.md)
and
[Doc 23 — NOVA Personality Specification](../../architecture/23-nova-personality-specification.md).
**Author:** Claude (Anthropic), AI-assisted implementation under direct human
architectural direction and review throughout. This phase followed the permanent
subsystem lifecycle the user established at Phase 2C's close in full for the first
time: Roadmap → Blueprint → Human/Philosophical documents → TDD → explicit approval →
Implementation → continuous testing → this Architecture Review → Gate Review →
Engineering Metrics → final approval. One architecturally-significant correction was
found during implementation and escalated before being applied (§2 below, the
streaming-synthesis design fix); every other implementation-time decision recorded
below was either a narrow, in-scope correctness fix or a choice consistent with the
already-approved design, documented rather than silently made.

## 1. What was implemented

Two independently deployable engines plus a required, additive extension to a
Phase 2A engine, plus the `nova-contracts` additions all three required.

**AI Model Orchestration Engine speech extension** (`services/ai-model-orchestration-engine/`)
— required before `communication-engine`'s audio pipeline could be built at all
(design doc 01 §0.3's own finding: ADR-020 names speech explicitly as an AI-provider
interaction that must route through this engine, but its `ModelConnector` protocol had
no speech modality). `Modality` gained `speech_to_text`/`text_to_speech`;
`ModelConnector` gained `transcribe`/`synthesize`/`synthesize_stream`; two new
connectors (`WhisperConnector`, `PiperConnector`, both local-server, zero-budget
defaults mirroring `OllamaConnector`'s role for text); `CapabilityScores` gained
`speech_recognition_accuracy`/`speech_synthesis_quality`; the ADR-023 connector
compliance suite extended to cover all three new methods. Additive only — the
existing `generate`/`stream`/`embed`/`health` surface and every existing caller are
unaffected.

**Personality Engine** (`services/personality-engine/`) — Bible Part 17. NOVA's Core
Identity, Consistency Validator, and Style Selector: rule-based, deterministic, zero
model calls (design doc 02 §0.3, mirroring Executive Cognition's own "calls no model"
precedent — ADR-020-compliant by construction, not by restraint). Stores and applies
resolved preferences, never learns them (ADR-030): `MemoryProfile` is a static default
until Phase 2D-D's `digital-twin-engine` exists to publish real values.

- **Domain layer** (`domain/`, framework-free, 4 modules): `models.py` (`CoreIdentity`,
  `MemoryProfile`, `ValidationResult`, `IdentitySnapshot`), `validator.py` (four check
  families — confidence-language and professionalism-floor as soft corrections;
  forbidden-pattern and emotional-stability as hard stops, per design doc §8),
  `style_selector.py` (a deterministic context-hint → style rule table), `ports.py`
  (`PersonalityRepository`, the engine's one port).
- **Repository layer**: `PostgresPersonalityRepository` (3 tables: `core_identity`,
  `memory_profile`, `validation_audit`), no transactional outbox (this engine
  publishes nothing this phase, design doc §10), a hand-written initial Alembic
  migration seeding `core_identity` directly from Doc 23 §2/§6.
- **API**: `GET /identity`, `GET /identity/snapshot`, `POST /validate`, `GET /style`,
  `GET /memory`. 7 route handlers total (5 public + 2 internal health) plus 1 mounted
  metrics endpoint.
- **Events**: serves `personality.validate_response.request` and `personality.style
  .select.request` as Event Bus RPCs, both calling the identical domain functions the
  HTTP routes call. Publishes nothing (`events/published.py` is an empty frozenset by
  design).
- **The one no-graceful-degradation failure mode in either engine this phase**: a
  Core Identity load failure at startup fails readiness without crashing the
  process — there is no safe default for *who NOVA is* (design doc §8).

**Communication Engine** (`services/communication-engine/`) — Bible Part 13. NOVA's
transport and lifecycle layer: channel adapters, the ten-state `ConversationSession`
machine, and the `communication.intent` gate — the sole legal path to user-facing
output (ADR-005). Deliberately pass-through on Determine Intent / Select Communication
Strategy this phase (design doc §0.1) — Phase 2D-C extends this same service, it does
not replace it.

- **Domain layer** (`domain/`, framework-free, 7 modules): `state_machine.py` (the
  ten-state machine, an explicit transition table with two documented implementation
  clarifications — see §2), `vad.py` (Transport VAD, single-threshold transient-gap
  tolerance), `chunking.py` (sentence/phrase splitting for perceived-streaming
  synthesis), `intent_gate.py` (the ADR-005 gate — the only function that delivers
  generated content), `speech.py` (barge-in-aware chunked voice delivery),
  `session_lifecycle.py` (create/close/pause/resume/turn-recording/restart recovery),
  `ports.py` (`ChannelAdapter`, `CommunicationRepository`, `PersonalityPort`,
  `ModelOrchestrationPort`, `WorldModelPort`).
- **Channels** (`channels/`): `TextChannelAdapter`, `VoiceChannelAdapter` — thin
  WebSocket wire-format translators implementing `ChannelAdapter`, no session state,
  no content generation, no personality validation (design doc §2's own boundary
  table).
- **Clients** (`clients/`, one adapter per upstream port): `personality_client.py` (a
  real, load-bearing dependency from day one, design doc §0.5 — unlike every other
  upstream port), `model_orchestration_client.py` (`transcribe`/`synthesize`, never a
  Whisper/Piper SDK directly), `world_model_client.py` (one context call per session
  creation, never per turn, design doc §8.7).
- **Repository layer**: `PostgresCommunicationRepository` (4 tables:
  `conversation_session`, `conversation_turn`, `notification`, `outbox_event`), the
  standard transactional outbox (this engine publishes 4 event types), a hand-written
  initial Alembic migration.
- **API**: `POST /sessions`, `POST /sessions/{id}/messages`, `WS /sessions/{id}`,
  `POST /sessions/{id}/pause`, `POST /sessions/{id}/resume`, `DELETE /sessions/{id}`,
  `GET /sessions/{id}/context`, `POST /notifications`. 10 route handlers total (8
  public + 2 internal health, the WebSocket endpoint counted once) plus 1 mounted
  metrics endpoint.
- **Events**: publishes `communication.session.created`/`.state_changed`/
  `.completed`, `communication.turn.received`; serves `communication.intent.deliver
  .request`, `communication.session.create.request`, `communication.session.close
  .request` as Event Bus RPCs.
- **Workers**: `outbox_worker.py` only, the same one-worker shape every engine after
  Reasoning Engine has established.
- **`session_registry.py`** (process root, not `domain/`): the one piece of
  genuinely live, in-memory state — a `session_id -> ChannelAdapter` map only a
  running WebSocket connection can populate (design doc §14's own single-instance-
  per-session admission for this phase).

**`nova-contracts` additions**: `communication.py` (10 subjects — 3 served RPC pairs,
4 published events, plus `digital_twin.preferences.get.request`/`.reply`, forward-
declared per §0.6 but unused this phase), `personality.py` (5 subjects — 2 served RPC
pairs, `personality.memory.update` unused this phase), plus the speech extension's
`TranscribeRequest`/`Reply`, `SynthesizeRequest`/`Reply` payloads (already merged
before this report). Every payload carries `schema_version: int = 1` (ADR-024). The
generated TypeScript client was regenerated and reconfirmed non-stale (74 payload
files + index, up from 53 before this phase's work began).

**A gap in `nova-contracts`' own test coverage was found and closed this phase, not
only the new subjects tested**: no dedicated test file existed for the personality
payloads added earlier in this project's history (unlike every other domain module,
which each has one). Added `test_personality_events.py` (6 tests) alongside the new
`test_communication_events.py` (8 tests), rather than silently leaving the pre-existing
gap unaddressed while adding only the new phase's own coverage.

**124 tests** across the two new engines (54 personality-engine, 70
communication-engine — 44 unit, 26 integration; the personality/communication event
tests add 14 more in `nova-contracts`), all passing; `ruff check` and `mypy` clean
across both engines' `src/`; the root `import-linter`'s existing four contracts all
still passing with both engines included.

## 2. Why each architectural decision was made

Two new ADRs were filed this phase, both requested by the user directly and both
covering a boundary decision the design docs themselves needed to reference, not
retrofitted after the fact — with one honest process exception noted below:

- **ADR-030 (Personality stores, Digital Twin learns)**: the dependency direction
  between `personality-engine` and the not-yet-built `digital-twin-engine` is
  one-way — Digital Twin publishes resolved preferences, Personality applies them,
  Personality never queries Digital Twin. Filed with a "Process note" admitting it
  was filed *after* both Phase 2D-A TDDs were approved rather than before, as the
  Master Blueprint had originally committed to (mirroring ADR-017's own Phase 1
  sequencing) — no architectural boundary was actually violated, only the filing
  order slipped, and this was recorded honestly rather than silently corrected.
- **ADR-031 (Subjective experience quality is a first-class requirement)**: the
  user's own standing instruction — "whenever multiple implementations satisfy the
  requirements, prefer the one that produces the most natural, responsive, and
  consistent user experience" — generalized from Master Blueprint §13.2's
  Phase-2D-scoped latency principle into a NOVA-wide standing tiebreaker, filed as
  its own ADR rather than left as blueprint-local guidance.

One implementation-time correction rose to the level of an architecturally-significant
fork and was escalated to the user before being applied, exactly as the standing
instruction requires:

- **The streaming-synthesis design in `01-communication-engine.md`'s original draft
  was architecturally impossible.** The approved TDD (and the Master Blueprint's own
  §13.3) described `ai_model.synthesize` as literally streaming audio over the
  Event-Bus RPC. While implementing the speech extension, this was found to violate
  ADR-004 directly: `EventBus.request()` (per `nova_eventbus_sdk`'s own
  `EventPublisher.request` signature) returns a single `EventEnvelope`, never a
  stream — and the already-built `api/generate.py`'s own module docstring had already
  established the precedent this project follows: *"streaming is the one path that
  never becomes an Event Bus contract... HTTP/SSE only."* This was not a discretionary
  choice needing a design decision — only one ADR-004-compliant design exists.
  Corrected to: a non-streaming `synthesize` RPC, called once per response chunk
  (sentence/phrase) as content becomes available, achieving the same perceived
  immediacy without an actual transport-level stream; `synthesize_stream` (HTTP/SSE
  only, mirroring `generate`/`stream`'s precedent) exists for direct external callers,
  never engine-to-engine. Both the implementation and every affected section of both
  the Master Blueprint and the communication-engine TDD were corrected together, not
  left inconsistent. **User approved this correction explicitly**: *"The architectural
  correction regarding streaming synthesis is the correct solution and remains fully
  aligned with ADR-004 and ADR-020."*

Two further implementation-time decisions were made and documented, neither requiring
escalation since each resolves an ambiguity the approved design left implicit rather
than overriding an explicit design choice:

- **`ConversationSession`'s state-machine diagram left two transitions implicit.**
  Design doc 01 §3.1's diagram draws `Idle --trigger--> Listening` for session start
  but does not explicitly draw the identical mechanism recurring for every later turn
  in a multi-turn conversation, nor does it specify what "resume to the state prior to
  pause" means given §3.2's required-fields table has no `state_before_pause` column.
  Resolved as: `Waiting` accepts the same `TRIGGER` event `Idle` does (the natural
  multi-turn loop), and `Paused` always resumes to `Listening` (the same natural
  resumption point restart recovery already uses) — both documented directly in
  `domain/state_machine.py`'s own module docstring as implementation clarifications,
  not silently assumed.
- **A rejected or failed content delivery has no recovery edge in the approved state
  diagram.** Once a session enters `Speaking` (via `mark_content_ready`), the only
  documented outgoing edges are `DELIVERED -> Waiting` and `BARGE_IN -> Listening` —
  neither covers "the personality gate rejected this content" or "synthesis failed."
  Resolved as: `events/handlers.py`'s `communication.intent.deliver.request` handler
  applies the `DELIVERED` transition regardless of whether delivery actually
  succeeded, since the alternative — a session permanently stuck in `Speaking` after
  any content-source engine failure — would be a materially worse defect than
  reusing an existing edge for a case its literal wording doesn't cover. Documented
  in the handler's own code comment and this engine's README "Known limitations."

## 3. Tradeoffs considered

- **Restart recovery and WebSocket disconnects bypass the validated state-transition
  table entirely** (`session_lifecycle.recover_session_to_paused`), rather than
  reusing the `PAUSE` event. Found necessary during testing: a session disconnecting
  while still `Idle` (no message ever sent) has no valid `PAUSE` edge, so the
  FSM-validated path left it permanently un-paused. Both restart recovery (§3.5) and
  a live disconnect are the same underlying fact — "no channel connection is live" —
  regardless of which state the session was in, so both use the same direct-write
  function rather than forcing every possible disconnect state to define its own
  `PAUSE` edge.
- **The intent gate's `deliver` call is not literally the only call site of
  `ChannelAdapter.deliver` in the codebase.** One narrow, documented exception exists:
  `api/websocket.py` delivers a short, honest transport-status notice directly
  ("voice temporarily unavailable") when `ai_model.transcribe` fails after the Model
  Router's fallback chain is exhausted (design doc 01 §9). This is not generated
  *content* requiring personality review — the same reasoning a `Paused` state
  transition itself is never personality-gated — so `domain/intent_gate.py`'s own
  docstring was corrected to scope its "only function" claim precisely rather than
  leave an inaccurate absolute statement once this exception existed.
- **`personality-engine` caches Core Identity and Personality Memory in `app.state`
  at startup rather than fetching per request.** The design doc's own §12 performance
  target ("sub-millisecond, no external calls") would not survive a real Postgres
  round trip per validation call — this is the concrete implementation-level
  application of ADR-031/Master Blueprint §13.2's standing tiebreak, not a
  discretionary optimization revisited later.
- **`communication-engine`'s Transport VAD silence detection in `api/websocket.py`
  uses a 100ms receive-timeout poll**, not a continuous audio-sample-rate cadence —
  this sandbox has no real audio hardware to drive a genuine per-sample tick. The VAD
  logic itself (`domain/vad.py`) is fully unit-tested independent of this cadence
  choice, so the cadence is an integration-layer approximation, not an untested
  domain-logic gap.

## 4. Known limitations

Both engines' own READMEs carry the full list under "Known limitations (Phase 2D-A)."
Restated here for a reader who doesn't cross-reference:

- **Neither engine has committed pytest coverage against a real Postgres
  instance** — the same accepted gap every prior engine's own committed suite has;
  this sandbox has no Docker daemon.
- **`personality-engine`'s `MemoryProfile` is a static default for the whole
  phase** (ADR-030) — real personalization arrives only once `digital-twin-engine`
  ships in Phase 2D-D.
- **`communication-engine`'s Determine Intent and Select Communication Strategy are
  pass-through, by design** (§0.1) — Phase 2D-C's scope, extending this same service.
- **`Close Session` only succeeds from `Waiting`** (§3.1's one documented close
  edge) — forcing close from an arbitrary state is a reasonable future extension, not
  implemented without a documented transition to implement it against.
- **`Notification` delivery is recording-only this phase** — no push-notification
  channel integration exists yet.
- **The WhisperConnector/PiperConnector local-server default has no corresponding
  container in `docker-compose.local.yml` yet** — noted at this phase's infra-wiring
  step (task tracking, not a design doc requirement) as a real, open gap for a
  future phase to close before real speech I/O can be exercised locally.
- **Several metrics are declared but not yet incremented** in both engines
  (`communication_engine_session_state_transitions_total`,
  `_transcribe_failures_total`, `_synthesize_failures_total`) — the live subset is
  named in each engine's own README.

## 5. Technical debt introduced, if any

None accepted as debt in the traditional sense, consistent with every prior phase's
own finding. The candidates evaluated are all deliberate, documented scope decisions
(§3, §4) or genuine gaps found and fixed during this phase's own work rather than
left open:

- The streaming-synthesis design correction (§2) and the two state-machine
  clarifications (§2) are closed, not deferred — the approved documents were
  corrected in place, not left inconsistent with the shipped code.
- The pre-existing `nova-contracts` test-coverage gap for personality payloads (§1)
  was closed this phase rather than only covering the new communication payloads.

## 6. Future improvements

- **Wire a real Whisper/Piper container into `docker-compose.local.yml`** (§4) so
  the speech extension's local-server default can actually be exercised end to end
  in this project's own local dev stack.
- **Build a committed test suite against a real Postgres instance**, for these two
  engines and every prior one (§4) — carried forward from every prior phase's Gate
  Review, unaddressed since Phase 1.
- **Extend `select_style`'s `channel` parameter to actually influence selection**
  once Phase 2D-C's real policy layer exists — currently accepted but unused,
  forward-compatible by design (Master Blueprint §13.6).
- **Increment the declared-but-inert metrics** (§4) once a real caller exercises
  the corresponding code paths.
- **Run the now-nine-service compose stack in a Docker-capable environment**
  (carried forward from every prior phase's Gate Review) to capture a first real
  latency measurement for the full inbound-audio-to-first-audible-response-byte
  path Master Blueprint Risk §11.1 names.

## 7. Risks

- **Operational:** neither engine has been booted against real Postgres/NATS/Redis
  in this sandbox (no Docker daemon) — both are verified exclusively via fakes at
  the integration-test layer, a materially thinner verification than Phase 2C's own
  real-Postgres round trip achieved for Executive Cognition Engine. This is an
  honest regression in verification depth versus the immediately prior phase, named
  explicitly rather than left implicit.
- **Architectural:** the `Speaking -> Waiting` transition applying regardless of
  delivery success (§2) means a content-source engine's own failure is not
  distinguishable from a successful delivery purely from the session's `state` field
  — a caller must inspect `CommunicationIntentDeliverReplyPayload.rejection_reason`
  to tell the two apart. Correct by design, but a future reader inspecting only
  session state could be misled.
- **Cross-engine:** `communication-engine` is the first engine in this project with
  a WebSocket surface and genuinely live, in-process state (`session_registry.py`).
  This is a new architectural shape relative to every prior stateless-between-
  requests engine, and its single-instance-per-session scope (design doc §14) is an
  accepted Phase 2D-A limit, not yet load-tested even at the fake level.
- **Scale:** performance targets (Master Blueprint Risk §11.1's latency budget)
  remain entirely unmeasured against real infrastructure, the same unmeasured-until-
  Docker status every prior phase's performance target still carries.

## 8. Compatibility with the NOVA Project Bible

- **Personality Engine (Bible Part 17):** implemented at the breadth the Phase 2D-A
  design doc scoped — Core Identity, the Consistency Validator's four check
  families, the Style Selector's context-hint rule table. `Update Preferences`,
  `Behavior Analysis`, `Emotion Profile`, `Teaching Mode` are explicitly not exposed
  this phase (design doc §11) — each requires an engine that doesn't exist yet.
- **Communication Engine (Bible Part 13):** implemented at the breadth the Phase
  2D-A design doc scoped — the Communication Lifecycle's Receive/Retrieve Context/
  Choose Channel/Deliver Response steps are real; Determine Intent/Select Strategy
  are honest pass-throughs (§0.1, §6); `Broadcast Update`/`Synchronize Devices` are
  explicitly not exposed this phase (§12) — multi-device continuity is out of Phase
  2D's scope.
- **Doc 22 (NOVA Human Interaction Principles) and Doc 23 (NOVA Personality
  Specification)** governed every major decision in both TDDs — both design docs'
  own §16 compliance tables map every section against the specific principle it
  satisfies; verified again this review by direct re-reading rather than assumed
  carried-forward.
- **ADR-025's Personal Edition principle** required no retrofit: both engines are
  single-user by default (`device_id` present from day one per Master Blueprint
  Risk §11.6, populated with a single value this phase).
- **ADR-030/031**, filed specifically to govern this phase, held without amendment
  through implementation — verified by direct inspection of `personality-engine`'s
  `MemoryProfile` (never learns) and both engines' own architectural decisions
  (§2, §3) tracing to ADR-031's tiebreak rule.
- All Known Limitations (§4) are, per the user's standing instruction carried
  forward from every prior phase, deliberately preferred over any speculative
  implementation of behavior the design docs did not specify.

## Sign-off

- [x] All items in both engines' design-doc review checklists
      ([docs/design/phase-2d/README.md](../../design/phase-2d/README.md)) are
      satisfied — both designs were approved before implementation began, and the
      one deviation from approved text (the streaming-synthesis correction, §2) was
      escalated and approved before being applied.
- [x] The phase's Definition of Done
      ([SAD 15 §4](../../architecture/15-development-workflow.md#4-definition-of-done-per-pr))
      was met: implementation, tests, observability, and documentation delivered
      together, not as follow-up work.
- [x] The ten-item build-time deliverable checklist
      ([SAD 15 §9.1](../../architecture/15-development-workflow.md#91-the-ten-item-build-time-deliverable-checklist))
      was met for both engines built this phase.
