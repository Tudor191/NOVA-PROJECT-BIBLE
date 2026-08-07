# Architecture Review Report — Phase 2D-B: Identity & Presence

Companion to [Phase 2D-B Gate Review](phase-2d-b-gate-review.md). Covers the new
`perception-engine` and its two cross-engine extensions (`ai-model-orchestration-engine`'s
biometric/wake modalities, World Model Engine's `present_identities`), per
[docs/design/phase-2d/03-perception-engine.md](../../design/phase-2d/03-perception-engine.md)
and [ADR-032](../../architecture/adr/ADR-032-identity-confidence-is-also-an-authorization-signal.md).

## 1. What was implemented

- **`perception-engine`** (new engine, Bible Part 11's minimal slice): the Sensor
  Abstraction Layer (`domain/sensor.py`'s full six-state lifecycle contract, `Sensor`
  Protocol), two concrete sensors (`VoiceSensor`, `CameraSensor`), the Identity
  Registry (`domain/enrollment.py`'s Fernet application-level template encryption,
  `domain/matching.py`'s cosine-similarity matching), consent management
  (`domain/consent.py`), the evidence-fusion algorithm (`domain/identity_fusion.py`:
  `fuse_window`/`smooth`, the `SINGLE_SIGNAL_CONFIDENCE_CEILING`), a
  `PostgresPerceptionRepository` over a 5-table `perception` schema plus the
  transactional outbox, an `AIModelOrchestrationClient` (the sole legal path to a
  wake/voiceprint/faceprint/gaze model, ADR-020), a `SessionActivityTracker` fed by
  `communication-engine`'s session lifecycle, seven published event subjects plus
  four outbound RPCs, and a nine-endpoint admin/config API under `/v1/perception`.
- **`ai-model-orchestration-engine` biometric/wake extension**: four new modalities
  (`wake_phrase_detection`, `voice_embedding`, `face_embedding`, `gaze_estimation`),
  four new specialized connectors (each real only in its own specialty, `NotSupportedError`
  everywhere else — the same shape every existing connector already follows), capability-
  weighted routing functions mirroring the `transcribe`/`synthesize` precedent, and four
  new `/v1/models/...` endpoints.
- **World Model Engine extension**: `ActiveContext.present_identities` (a
  `PresentIdentitySignal` list), fed by a new dispatch handler
  (`make_perception_dispatch_handler`) that routes `perception.presence.observed`/
  `perception.identity.observed` to `upsert_present_identity`/`clear_present_identities`
  while preserving the original object-graph path for every other `perception.*.observed`
  subject — one handler on one wildcard subscription, not two competing subscriptions.
- **Governance**: ADR-032 (identity confidence is also an authorization signal — a
  NOVA-wide permanent principle, not scoped to this engine), a new standing rule in
  [15-development-workflow.md §9.0](../../architecture/15-development-workflow.md)
  ("always verify the implementation before trusting the documentation"), and a
  correction to this phase's own TDD (§13.3: `communication.session.state_changed`
  is not subscribed — its payload carries no `user_id`).

Full test suite: **89 tests** in `perception-engine` (domain, sensors, events, API,
contract), **172** in `ai-model-orchestration-engine` (+11 this phase), **64** in
`world-model-engine` (+10 this phase). Ruff, mypy (whole-package, not just `src/`),
and import-linter all pass across all three engines — see the Gate Review's Quality
Metrics for exact figures.

## 2. Why each architectural decision was made

- **Sensors never touch raw capture hardware.** `VoiceSensor`/`CameraSensor` operate
  on already-captured audio windows / already-detected face crops, mirroring
  `WhisperConnector`/`PiperConnector` (never touch an audio device) and
  `VoiceChannelAdapter` (reads an already-connected WebSocket). Building a fabricated
  microphone/camera integration this environment cannot verify working would violate
  Doc 23 §6's "never claim a capability NOVA does not have."
- **Evidence fusion is a structural constraint, not a policy statement.** The
  `SINGLE_SIGNAL_CONFIDENCE_CEILING` (0.75, below the 0.85 "high" tier boundary) makes
  it mechanically impossible for one modality to produce a High-confidence identity
  verdict — the property is enforced by the function's own arithmetic, verified
  directly by `test_single_signal_never_reaches_high_confidence_even_at_max_raw_score`,
  not left to a reviewer reading a comment.
- **Identity confidence never gates anything itself (ADR-032).** `perception-engine`
  produces confidence-scored, tiered signals only; every event payload and domain
  model that can leave this engine carries the full float alongside the tier (never
  the tier alone), and `test_identity_observed_carries_full_confidence_float_alongside_tier`
  guards that property directly, since a future privileged-capability engine (Action
  Engine, Autonomy Engine) depends on the precision this engine chose not to discard.
- **`perception.wake.detected`/`perception.addressee_signal.candidate` deliberately
  don't match World Model's `perception.*.observed` wildcard.** Both are discrete
  triggers/candidate signals, never "current state of reality" facts (ADR-017);
  `test_trigger_and_candidate_subjects_do_not_match_world_models_wildcard` verifies
  this with the actual `fnmatchcase` mechanism the Event Bus uses, not by naming
  convention alone.
- **Continuous reassessment (§0.10) is exponential smoothing over a live,
  never-persisted `IdentityConfidenceState`**, distinct from the append-only
  `IdentityObservation` audit trail — mirrors `communication-engine`'s own
  `session_registry.py` precedent for exactly this kind of restart-safe-to-lose
  live state, keeping the audit trail (Postgres, permanent) and the live signal
  (in-process, disposable) genuinely separate.
- **`router.py`'s 4-way duplication is a deliberate, reasoned deviation, not an
  oversight.** `_plan_perception_routing`/`_route_and_record_perception` factor out
  the shared shape across all four new modalities while keeping each modality's own
  named public function, balancing DRY against the codebase's own "no premature
  abstraction" convention — documented in the code's own docstring rather than
  silently applied.

## 3. Tradeoffs considered

- **No live capture/ingestion path this phase, by design.** Building a synthetic
  "correlation window orchestrator" that calls `fuse_window`/`smooth`/publishes
  events on a timer, with nothing real yet feeding it audio/frames, would have been
  exercising a mechanism against fabricated input — Sec0.1 scopes this phase to the
  mechanism (sensors, fusion, admin API), leaving the live wiring to a future
  desktop/companion client. The cost: the full "sensor → fusion → publish" pipeline
  is unit-tested piece by piece, never as one end-to-end live flow this phase.
- **Presence-detection thresholds are a heuristic mean/frame-difference gate, not
  real audio-engineering RMS.** A properly weighted RMS over signed PCM samples
  would need a real audio format decision this phase doesn't make (raw bytes have no
  declared sample format yet); the simpler mean-based gate is honestly documented as
  a "starting, calibratable value," matching `identity_fusion.ALPHA`'s own precedent
  for admitting an untuned constant rather than presenting it as validated.
- **Automatic sensor restart-on-failure is state-machine-capable but not yet an
  autonomous poller.** Building a background health-check loop for two sensors that
  have no live process to fail asynchronously (no capture loop is running without a
  real client) would be infrastructure with nothing to exercise it; the state
  machine's `failed → initialize` transition and `report_error()` exist and are
  tested, the poller itself is deferred to whenever a live capture path exists.

## 4. Known limitations

- No live sensor data ingestion path exists this phase (§0.1's own scope boundary,
  not a bug).
- Automatic sensor restart-on-failure has no autonomous trigger yet (§12's table
  describes the intended behavior; the mechanical building blocks exist, the poller
  does not).
- Confidence-tier boundaries and `ALPHA` (the smoothing rate) are considered starting
  points, not calibrated against real biometric data (§8, §24).
- `nova_contracts.events.perception` does not yet exist — this engine's own event
  payloads (`events/publishers.py`) are shaped inline with `schema_version: 1` but
  not yet formally registered via `register_payload`, tracked as a near-term
  follow-up rather than blocking this phase (mirrors how `perception.*.observed`
  itself was built in World Model before this engine existed).
- Real-Postgres verification of `PostgresPerceptionRepository` has not been
  performed — no Docker daemon has been reachable in this session's environment.
  This is now a three-engine open item (personality-engine, communication-engine,
  perception-engine), tracked continuously since Phase 2D-A's own gate review.

## 5. Technical debt introduced, if any

- **Two real bugs were introduced and caught by this phase's own test suite before
  being reported as complete** — reported here in full per the standing
  "verify before trusting" instruction, not smoothed over:
  1. `VoiceSensor`/`CameraSensor`'s original presence-detection thresholds (500.0)
     were mathematically unreachable against raw byte data (range [0, 255]) —
     `detect_presence()` would never fire for `VoiceSensor` and only fired on the
     very first frame for `CameraSensor`. Fixed (threshold lowered to 30.0, within
     the reachable range) before this phase's own tests were written; caught by
     writing the Sensor Abstraction Layer compliance suite (§20 of the TDD), not by
     manual review.
  2. `main.py`'s shutdown path called `sensor.stop()` unconditionally; a sensor
     already stopped (e.g., consent revoked mid-session) made that an illegal state
     transition, raising `ValueError` during FastAPI shutdown. Fixed by guarding the
     shutdown loop the same way `api/consent.py`'s own revocation handler already
     does. Caught by `test_revoke_consent_on_an_already_stopped_sensor_does_not_raise`.
  3. `packages/nova-contracts/typescript/ContextChangedPayload.ts` had drifted from
     its Python schema source of truth (`present_identities` was added to the
     Python model earlier this session but the generated TypeScript client was never
     regenerated). Caught while gathering this phase's generated-code-freshness
     metric and fixed by regenerating and committing the client, per
     `METRICS_TEMPLATE.md`'s own "regenerate and diff before reporting" instruction.
- `router.py` in `ai-model-orchestration-engine` is now the single largest file in
  the entire codebase (1,384 SLOC) after two consecutive modality extensions
  (speech in 2D-A, biometric/wake in 2D-B). Not refactored this phase — the shared
  `_plan_perception_routing`/`_route_and_record_perception` helpers already reduce
  duplication within it — but flagged here as a real candidate for a future
  restructuring (e.g. splitting per-modality-family) before a third extension makes
  it materially harder to navigate.

## 6. Future improvements

- Register `nova_contracts.events.perception` formally once this engine's payloads
  are considered stable (tracked in the TDD's own §24).
- Build the live correlation-window orchestrator once a real audio/camera capture
  client exists (Phase 4's `nova-companion`), replacing the heuristic presence
  thresholds with a genuine audio-format-aware energy computation at the same time.
- Add an autonomous sensor-health poller once there is a live sensor process worth
  polling.
- Calibrate `SINGLE_SIGNAL_CONFIDENCE_CEILING`, the tier boundaries, and `ALPHA`
  against real biometric data once available (§8, §24's own tracked follow-up).
- Consider restructuring `ai-model-orchestration-engine`'s `router.py` before a
  third modality family is added.

## 7. Risks

- **Calibration risk**: every confidence constant in `identity_fusion.py` is an
  engineering judgment call, not a validated parameter. A future privileged-capability
  engine building authorization thresholds on top of these tiers (ADR-032) inherits
  that uncertainty until real calibration data exists.
- **Scope-creep risk at the sensor boundary**: the temptation to make `VoiceSensor`/
  `CameraSensor` "just work" with real hardware for a demo would violate the
  documented scope boundary and Doc 23 §6; this risk is named explicitly so it is
  resisted deliberately, not drifted into.
- **Real-Postgres risk carried forward**: three engines' repository layers
  (personality, communication, perception) remain unverified against a real
  database. The longer this stays open, the more schema/query assumptions could
  silently accumulate that only a real Postgres instance would catch.

## 8. Compatibility with the NOVA Project Bible

- Bible Part 11 ("Perception Engine"): Sensor Abstraction Layer, Identity Registry,
  consent management, evidence fusion, presence/attention/gaze, wake-phrase
  detection — all present per this phase's own scope narrowing (§0.1). "Register
  Sensor"/"Remove Sensor" API endpoints are deliberately not exposed (startup-time
  configuration only, per §14) — a documented, not silent, scope decision.
  "Sensor Health" and "Failure Recovery" are present as data/state-machine
  capability, with the autonomous-restart loop itself deferred (§4, §5 above).
- Master Blueprint §5.1/§8/§9.1/§13.2: addressee-candidate signal boundary honored
  (no verdict field anywhere in `perception.addressee_signal.candidate`'s payload,
  mechanically verified); no served RPC this phase, per §8; full Sensor Abstraction
  Layer lifecycle contract from day one, per §9.1.
- ADR-020 (sole legal LLM/model provider channel): every biometric/wake model call
  routes through `ai-model-orchestration-engine`; import-linter's ADR-020 contract
  now includes `nova_perception_engine` in its forbidden-SDK-import source list.
- ADR-032 (this phase's own addition): identity confidence is a signal, never an
  authorization decision, made structurally true by this engine performing no
  gating of any kind.

## Sign-off

Prepared for the Phase 2D-B Gate Review. Recommend proceeding to Gate Review per the
established lifecycle (Implementation → Continuous testing → Architecture Review →
Gate Review → Engineering Metrics → Approval).
