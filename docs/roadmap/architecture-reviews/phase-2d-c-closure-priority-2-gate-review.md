# Phase 2D-C Closure — Priority 2 Gate Review: the `user_id`/session-correlation problem

**Scope of this review: Priority 2 only**, per direct instruction. Priorities
4, 5, and 6 of the
[closure design document](../../design/phase-2d/05-conversation-intelligence-closure.md)
are **untouched** — no code was modified for any of them. Phase 2D-D has not
been started. Priority 1 was not reopened — this pass builds directly on top
of its `WindowCorrelationBuffer`/`handle_observation_window` without
modifying either's Priority-1-scoped behavior. No changes were made to
reasoning-engine. communication-engine's only change is two test call sites
(§2) updated to supply the new required contract field — its production code
(`domain/addressee_fusion.py`, `events/handlers.py::make_addressee_signal_handler`)
was already unconditionally consuming `identity_id`/`identity_confidence`/
`session_active`, so it needed no change to benefit from this priority.

**Decision: Go**, for Priority 2 as scoped, with one disclosed, user-scoped
limitation carried forward (not introduced by this pass) and one disclosed,
user-confirmed deferral. See §6 for the full four-way classification.

## 1. Pre-implementation review — what was verified before writing code

Per instruction, a full architecture/implementation-gap review preceded any
code change, addressing each of the eleven points raised, all re-verified
directly against current source rather than trusted from the closure
document:

1. **`user_id` resolution**: no engine anywhere in this codebase resolves
   "the current user" from ambient state — confirmed exhaustively (no
   `DEFAULT_USER_ID`/`PRIMARY_USER` convention exists). The closure
   document's own §4.1 finding (`EnrolledIdentity.user_id` is only available
   when `identity_id is not None` — exactly the case that fails for the
   majority-relevant clean-activation path) was re-confirmed directly
   against `domain/addressee_fusion.py`'s own passing tests.
2. **`primary_user_id`'s fit with the configuration/deployment model**:
   confirmed against `config.py`'s existing pattern —
   `template_encryption_key: str = ""` is the closest precedent (empty by
   default, engine still boots, explicit failure only when actually
   exercised). `docs/architecture/13-auth-and-security.md` describes a
   **future, not-yet-built** `current_principal`/device-keypair mechanism —
   confirmed no competing mechanism exists in current code, so
   `primary_user_id` is a legitimate, scoped stopgap, not a design
   collision.
3. **Identity matching, voice and face**: `VoiceSensor.match_voiceprint`/
   `CameraSensor.match_faceprint` were already fully built (Phase 2D-B) but
   had zero production callers before this pass — confirmed by the same
   grep-for-callers method used in Priority 1's review. Both extract an
   embedding via the real `AIModelOrchestrationPort` RPC, then call
   `domain/matching.py::best_match` against `repository.get_identity_templates`.
4. **Identity confidence calculation/smoothing**: `domain/identity_fusion.py::fuse_window`
   (per-window fusion, single-signal ceiling 0.75, agreement bonus 0.15,
   disagreement capped at 0.5) and `smooth` (exponential moving average,
   requires `presence_session_id`/a previous `IdentityConfidenceState`) were
   both re-read directly. `smooth` requires `presence_session_id: UUID`
   allocation, which nothing in this codebase currently assigns — a
   pre-existing, undisclosed-as-a-gap condition the original Phase 2D-B TDD
   never fully specified. **Confirmed out of scope**: the closure document
   names only `perception.addressee_signal.candidate` for closure, not
   `perception.identity.observed`/the smoothed-state stream. `fuse_window`
   (not `smooth`) is what this pass actually uses, via a new
   `WindowCorrelationBuffer` extension (§2), for exactly the same
   "correlate this call's contribution with a still-fresh one from the
   other sensor" reason Priority 1's wake/gaze channel exists.
5. **`SessionActivityTracker.is_active`**: confirmed unchanged and already
   correct — `session_activity.py:32-33`, a simple `dict[UUID, set[UUID]]`
   membership check, fed by `communication.session.created`/`.completed`
   events already subscribed in `main.py`. Needed only a concrete `user_id`
   to call with, which this priority now supplies.
6. **Reaching `perception.addressee_signal.candidate`**: traced the exact
   wiring point — `observation_orchestration.py::handle_observation_window`,
   the same orchestration Priority 1 built, extended rather than replaced
   (§2).
7. **Effect on communication-engine's addressee fusion tiers**: confirmed
   `make_addressee_signal_handler` (`events/handlers.py`) already
   unconditionally reads `payload.identity_id`/`identity_confidence`/
   `session_active` into `FusionSignals` — **zero communication-engine
   production code changes required** for this priority to take effect,
   confirmed by direct inspection before implementation, not assumed.
8. **ADR-032 authorization implications**: re-read directly. ADR-032 states
   identity confidence is a future authorization signal, but **only binding
   on future privileged-capability engines** (Action Engine/Autonomy
   Engine, Phase 3/4) — perception-engine "never performs the gating
   itself," remains a pure evidence producer. This priority changes nothing
   about that boundary: it populates evidence fields more completely, it
   does not add any gating logic to perception-engine. No ADR-032 conflict.
9. **Consent's effect on identity matching**: **new finding, this
   review** — `domain/consent.py`'s own docstring claims sensor `start()`
   is gated by `require_active_consent` ("the one gate every sensor
   `start()` call... passes through"), but this is **false in the actual
   code**. `main.py:101-104` calls `voice_sensor.start()`/
   `camera_sensor.start()` unconditionally at startup; `api/consent.py`'s
   `grant_consent` (lines 52-62) never calls `require_active_consent` or
   starts anything — it only persists a grant row. Only `revoke_consent`
   actually gates anything (stops an already-running sensor). This is a
   **pre-existing bug**, newly consequential now that identity matching is
   about to go live, not a defect this pass introduces. Reported to the
   user before any code was written; the user approved gating the
   **identity-matching call site specifically** (Doc 22 Principle 8), not
   the broader `start()`-gating bug — see §7 for exactly what remains open.
10. **Failure/degraded-mode behavior**: designed and implemented explicitly
    for every case named — unset `primary_user_id` (publish nothing, not a
    guess), consent withheld (matching skipped, wake/gaze still real,
    `identity_id=None`), no match found (honest `None`, not a fabricated
    low-confidence guess), disagreement between modalities (existing
    `fuse_window` suppression, capped at 0.5, unchanged). See §4 for the
    exact test coverage of each.
11. **Testable now vs. hardware/infrastructure-dependent**: addressed in
    full in §6, using the same never-collapsed four-way classification as
    Priorities 1 and 3.

Fork #2 (whether to add a config-level "primary user" to perception-engine
at all) and the two new findings from items 9 and (a separate) World Model
corroboration-scope question were put to the user via `AskUserQuestion`
before implementation began. All three recommended options were approved:
add `primary_user_id` (Option A via E, exactly as §4.2 of the closure
document argues), gate identity matching on active consent before matching,
and leave World Model's `corroborate_identity_confidence` unwired — stay
out of communication-engine and reasoning-engine entirely this pass.

## 2. What was implemented

1. **`packages/nova-contracts/src/nova_contracts/events/perception.py`** —
   added `user_id: UUID` (required) to
   `PerceptionAddresseeSignalCandidatePayload`, a breaking, coordinated
   same-release addition (Sec12's own migration-strategy reasoning: this
   payload's only consumer, communication-engine, deploys from the same
   monorepo). The payload's own docstring now explicitly distinguishes
   `user_id` (the configured instance owner, present on every candidate)
   from `identity_id` (a per-window, evidence-scored verification result,
   `None` whenever no match occurred) — a future consumer must not treat
   `user_id` as an identity-confidence claim.
2. **`config.py`** — `Settings.primary_user_id: UUID | None = None`,
   mirroring `template_encryption_key`'s own "empty by default, explicit
   degrade when actually needed, never a silent fallback" pattern.
3. **`domain/correlation_buffer.py`** — `WindowCorrelationBuffer` extended
   with a second, parallel channel: `record_identity_signal`/
   `current_identity`, keyed by modality (`"voice"`/`"face"`), reusing
   `identity_fusion.fuse_window` rather than duplicating its
   agreement/disagreement logic. Solves the same single-sensor-per-call
   problem Priority 1's wake/gaze channel already solves, for identity
   signals specifically.
4. **`observation_orchestration.py::handle_observation_window`** — extended,
   not replaced:
   - Short-circuits immediately after the sensor-running check, before any
     detection call, when `primary_user_id` is unset: publishes nothing,
     logs a warning. Never guesses an identity for an unconfigured
     deployment.
   - For microphone: after the existing `detect_wake_phrase` call (still
     unconditional — see §7), checks
     `repository.has_active_consent(user_id, source="microphone")` before
     ever calling `sensor.match_voiceprint`; a match feeds
     `correlation_buffer.record_identity_signal`.
   - Symmetric for camera/`match_faceprint`.
   - `session_active` now resolves via `state.session_tracker.is_active(user_id)`
     — real, not the Priority-1 hardcoded `False`.
   - `identity_id`/`identity_confidence` now come from
     `correlation_buffer.current_identity(...)`'s fused result — real, not
     the Priority-1 hardcoded `None`/`0.0`.
   - `user_id` is threaded through to `addressee_signal_candidate(...)` on
     every publish.
5. **`events/publishers.py::addressee_signal_candidate`** — accepts and
   passes through the now-required `user_id: UUID` parameter.
6. **`tests/fakes/sensor.py::FakeSensor`** — extended with
   `match_voiceprint`/`match_faceprint`, each returning a configurable
   `ModalitySignal | None`, plus a `match_calls` list for asserting whether
   (and with which `user_id`) matching was actually attempted.
7. **`packages/nova-testkit/src/nova_testkit/perception_signal_source.py`**
   — `FakePerceptionSignalSource.publish_addressee_signal_candidate` now
   takes a required `user_id: UUID` (no default — mirrors the real
   contract exactly, so a test caller must decide it rather than inherit a
   hidden one).
8. **Call-site propagation** — every construction site of the payload/fake
   updated: `services/perception-engine/tests/unit/test_publishers.py`,
   `packages/nova-testkit/tests/test_perception_signal_source.py` (2 call
   sites), `services/communication-engine/tests/integration/test_addressee_signal_handler.py`
   (2 call sites), and Priority 1's own
   `tests/integration/test_api_observations.py`/`tests/unit/test_observation_orchestration.py`
   fixtures, which now configure `primary_user_id` so their existing
   Priority-1-era assertions keep passing for the right reason (no consent
   granted in those fixtures → matching is genuinely skipped, not silently
   broken by the new short-circuit).

**Deliberately not implemented (§1 item 9, user-confirmed):** sensor
`start()` itself remains ungated by consent — the pre-existing bug in
`domain/consent.py`'s own docstring claim. **Deliberately not implemented
(user-confirmed, separate question):** World Model's
`corroborate_identity_confidence` RPC remains completely unwired — this
priority stays entirely inside perception-engine.

## 3. The exact chain, traced end to end

```
POST /v1/perception/observations?source=microphone&correlation_id=...
  -> observation_orchestration.handle_observation_window
       -> primary_user_id is None?  -> publish nothing, log warning (new)
       -> sensor.detect_presence(window)          -- unchanged, Priority 1
       -> sensor.detect_wake_phrase(window, ...)   -- unchanged, Priority 1
       -> correlation_buffer.record_wake(...)      -- unchanged, Priority 1
       -> repository.has_active_consent(user_id, "microphone")?  (new)
            yes -> sensor.match_voiceprint(window, user_id=..., ...)
                     -> ai_model_port.embed_voice(...)            (real RPC)
                     -> repository.get_identity_templates(user_id, "voice")
                     -> domain/matching.best_match(...)           (cosine similarity)
                   -> correlation_buffer.record_identity_signal(...)  (new)
            no  -> matching never attempted (new)
       -> correlation_buffer.current(...)          -- wake/gaze, unchanged
       -> correlation_buffer.current_identity(...) -- fused identity (new)
       -> session_tracker.is_active(user_id)       -- real, not hardcoded False (new)
       -> events.publishers.addressee_signal_candidate(
            wake_word_matched, wake_word_confidence,
            identity_id, identity_confidence,   -- now real
            gaze_direction,
            session_active,                     -- now real
            user_id,                            -- now present on every candidate
          )
       -> repository.enqueue_outbox(event)
  -> perception-engine-worker dispatches onto the real Event Bus
  -> perception.addressee_signal.candidate lands on the bus; communication-
     engine's make_addressee_signal_handler already unconditionally
     consumes every one of these fields -- no change needed there
```

## 4. Every case the user asked to be verified, addressed explicitly

Each of the eleven review points (§1) has direct, passing test coverage:

- **Unconfigured `primary_user_id`** — `test_unconfigured_primary_user_id_publishes_nothing`
  (unit, via `_FakeApp`) and its integration-level twin through the real
  app/sensor lifecycle (`test_unconfigured_primary_user_id_publishes_nothing`,
  `test_api_observations.py`): nothing is published, the presence gate is
  never even reached.
- **Consent withheld** — `test_identity_matching_is_skipped_without_active_consent`:
  wake-word detection proceeds (a separate, disclosed, unfixed gap — §7),
  matching is never attempted, `identity_id`/`identity_confidence` publish
  as honest zeros.
- **Consent granted, match found** — `test_identity_matching_runs_and_publishes_with_active_consent`
  (unit, `FakeSensor`) and `test_enrolled_and_consented_voice_match_reaches_the_payload`
  (integration, through the real `VoiceSensor`, a real encrypted-then-
  decrypted template round trip, and real cosine-similarity scoring):
  `identity_id` and `identity_confidence` (capped at the single-signal
  ceiling, 0.75) reach the published payload.
- **Consent granted, no match** — `test_a_no_match_result_publishes_no_identity_even_with_consent`:
  an honest `None`/`0.0`, never a fabricated guess.
- **Cross-modality agreement** — `test_identity_signals_from_both_modalities_are_fused_across_calls`:
  a voice match and a face match for the same identity, from two separate
  ingestion calls, both still fresh, combine via `fuse_window`'s existing
  agreement bonus to exceed the single-signal ceiling — the identity-signal
  counterpart to Priority 1's own wake/gaze cross-sensor correlation test.
- **Identity-signal expiry** — `test_an_expired_identity_signal_does_not_contribute`
  (correlation-buffer unit test): an identity signal older than
  `correlation_window_seconds` reports the honest absent default, not a
  stale value.
- **`session_active` resolution** — `test_session_active_reflects_the_session_tracker`:
  a real `SessionActivityTracker` with an active session for
  `primary_user_id` publishes `session_active=True`; every other test
  (no session created) confirms the honest `False` default.

## 5. Verification results

| Check | Result |
|---|---|
| `ruff check` (all touched packages) | pass |
| `mypy` (perception-engine, nova-contracts, nova-testkit) | pass, 0 new errors — the pre-existing `_FakeApp`/`FastAPI` structural-typing mismatch in `test_observation_orchestration.py` (13 occurrences before this pass, confirmed via `git stash`) now has more occurrences (20) purely because this pass added more test functions using the same pre-existing, already-accepted double; no new *kind* of error was introduced |
| `mypy` (communication-engine) | pass, 0 new errors — confirmed identical 30 pre-existing errors via `git stash`, same pre-existing multi-line `# type: ignore` placement pattern, unrelated to this pass's changes |
| Full pytest suite, perception-engine (`pytest -m "not real_infra"`) | 127 passed, 7 deselected (`real_infra`) |
| perception-engine `domain/` coverage | 99% (gate: 85%) |
| Full pytest suite, communication-engine (`pytest -m "not real_infra"`) | 114 passed, 11 deselected (`real_infra`) |
| communication-engine `domain/` coverage | 99% (gate: 85%) |
| nova-contracts test suite | 76 passed |
| nova-testkit test suite (excl. `real_infra`) | 14 passed |
| import-linter | 6/6 contracts kept |
| `docker compose config` (`infra/docker/docker-compose.local.yml`) | valid — no service topology change this priority |
| TypeScript contract generation | re-run, **zero diff** — see §8 for the pre-existing gap this surfaced |

**13 new tests** this pass (confirmed by diff, not estimated): 5 new
`WindowCorrelationBuffer` identity-channel tests, 6 new
`handle_observation_window` unit tests (unconfigured `primary_user_id`,
consent withheld/granted, match/no-match, `session_active`, cross-modality
fusion), 2 new integration tests through the real app
(`test_api_observations.py`) — plus the mechanical `user_id` propagation
across every existing call site of the contract/fake in 7 test files
(`test_publishers.py`, `test_perception_signal_source.py`,
`test_addressee_signal_handler.py`, `test_api_observations.py`'s existing
`Settings(...)` constructions, `tests/fakes/sensor.py`), all confirmed
still passing.

## 6. Classification — never collapsed, per instruction

| Component | Classification |
|---|---|
| `WindowCorrelationBuffer`'s identity-signal channel (freshness/expiry, per-modality keying) | **Fully verified** — pure, deterministic, no external dependency |
| `handle_observation_window`'s new branching (unset `primary_user_id`, consent gate, match/no-match, `session_active`) | **Fully verified** against a configurable `FakeSensor`/`FakePerceptionRepository`, exercising every code path directly |
| The real `VoiceSensor.match_voiceprint` → `AIModelOrchestrationPort.embed_voice` → `repository.get_identity_templates` → `domain/matching.best_match` chain, including real Fernet encryption/decryption of an actually-enrolled template | **Fully verified** through the real FastAPI app and real production classes — the only fake in this chain is `FakeAIModelOrchestrationPort`, standing in for the real `ai-model-orchestration-engine` process (ADR-020's own RPC boundary), exactly the same tier Priority 1 already established for wake/gaze |
| `SessionActivityTracker.is_active` resolving `session_active` from a real, in-process tracker | **Fully verified** — the same real class Priority 1 left uncalled, now genuinely exercised |
| `perception.addressee_signal.candidate`'s new `user_id` field reaching a real fusion consumer | **Contract/fake verified** — the payload shape (including `user_id`) is proven correct via `PerceptionAddresseeSignalCandidatePayload.model_validate` round trips and communication-engine's own existing addressee-fusion tests (unchanged, still passing); this review did not run a real `communication-engine` process consuming a real bus message from a real `perception-engine` process — that two-process proof remains unperformed, the same limitation Priority 1 disclosed |
| Real Postgres round-trip for `get_identity_templates`/`has_active_consent` under this priority's new call pattern | **Infrastructure-dependent, not executed** — no new migration; the existing `test_repository_real_postgres.py` `real_infra` suite covers the repository methods themselves but requires a Docker daemon not reachable in this sandbox (confirmed, same disclosed limitation carried since Phase 2D-B; task #93 remains exactly as open as before) |
| Actual microphone/camera capture, actual voice/face embeddings from a real human, actual biometric matching against a real enrolled person | **Hardware-dependent, not verified, not claimed** — `FakeAIModelOrchestrationPort` supplies a deterministic, test-author-chosen embedding; the cosine-similarity scoring and encryption round trip around it are real, but the embedding itself is not |

**What this means plainly, since fake-backed tests passing is explicitly
not sufficient on its own (per instruction):** the identity-matching
*mechanism* — consent check, embedding-to-template comparison, cosine
scoring, cross-modality fusion, session lookup, and payload construction —
now genuinely executes, using the actual production `VoiceSensor`/
`CameraSensor`/`domain/matching.py`/`domain/identity_fusion.py` classes,
not simulated stand-ins for them. What remains unexecuted in this sandbox
is the same boundary Priority 1 already named: the real AI-model RPC
backend that would supply a genuine biometric embedding, and a real second
`communication-engine` process actually consuming a real bus message. Do
not read this Gate Review as claiming NOVA can recognize a real person's
voice or face — it cannot, in this environment, because no real embedding
model runs here. What it claims, precisely, is that every piece of code
*between* a real embedding and a published, correctly-shaped signal is
real, tested, and wired.

## 7. Remaining limitations — explicitly not closed by this pass

- **Sensor `start()` itself remains ungated by consent** (§1 item 9). This
  is a pre-existing bug this review discovered, not introduced — `main.py`
  starts both sensors unconditionally at boot, and `grant_consent` never
  calls `require_active_consent` or starts anything. The practical
  consequence, now that identity matching is live: a sensor can be
  `running` and calling `detect_wake_phrase`/`estimate_attention`
  (unconditionally, unaffected by consent) even for a source that has
  never had consent granted at all — only the *matching* call is gated.
  The user was asked specifically about gating identity matching, not
  about fixing this broader gap, and approved the narrower, disclosed fix.
  This remains open, tracked here, for a future pass to decide whether to
  close.
- **World Model corroboration remains completely unwired**, by explicit
  user choice this pass. `corroborate_identity_confidence` still has zero
  production callers anywhere in this codebase — this priority populates
  `identity_id`/`identity_confidence` on the *candidate* signal
  communication-engine consumes, but does not touch the separate,
  already-existing `world_model.context.request` RPC path at all.
- **`IdentityConfidenceState`/`identity_fusion.smooth`/`perception.identity.observed`
  remain unwired** — same pre-existing, out-of-scope gap Priority 1
  disclosed (`presence_session_id` allocation is still unresolved anywhere
  in this codebase). This priority uses `fuse_window` directly against a
  correlation-window buffer, deliberately not the smoothed-state stream.
- **TypeScript codegen has never included any `perception.*` payload**,
  confirmed this pass, and is unaffected by it. `codegen/generate_typescript.py`'s
  own import list (checked directly) has never named a single
  `Perception*Payload` class, for any subject, since that module was first
  registered (Phase 2D-C's own prerequisite work) — this is a pre-existing
  gap this priority's zero-diff codegen re-run surfaced, not a regression
  this pass caused, and not something this priority's scope authorizes
  fixing unilaterally (it would touch every perception payload, not just
  the one this priority changed). Disclosed here rather than silently
  left implicit in a "zero diff" line that could otherwise be misread as
  "already covered."
- **No real second process was exercised.** Every test in this pass runs
  within a single engine's own test process — the same limitation Priority
  1 disclosed, unchanged.
- **Real Postgres verification (task #93) remains exactly as open as
  before** — this priority added no migration and touched no schema.

Phase 2D-D has not been started. Priorities 4, 5, and 6 have not been
touched. Per instruction, this review stops here and awaits the user's
review before any further Priority 4-6 work begins.
