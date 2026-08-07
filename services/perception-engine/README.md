# perception-engine

Identity & Presence (Bible Part 11, minimal Phase 2D-B slice) --
docs/design/phase-2d/03-perception-engine.md, ADR-032. Owns the Sensor
Abstraction Layer, the Identity Registry (encrypted voiceprint/faceprint
templates), consent management, multi-factor identity confidence (evidence
fusion, continuously reassessed), presence/attention/gaze signals, wake-phrase
detection, and addressee-candidate signal publishing. Two sensor modalities
this phase -- voice (`sensors/voice_sensor.py`) and camera
(`sensors/camera_sensor.py`) -- behind a full lifecycle contract from day
one, so Phase 4's `nova-companion` desktop sensors can register behind the
same interface without redesign.

This engine never decides whether NOVA should respond to anything (that is
`communication-engine`'s 2D-C job), never renders output, and never calls a
biometric/AI model directly (every model call routes through
`ai-model-orchestration-engine`, ADR-020). It publishes confidence-scored,
tiered identity signals; a future privileged-capability engine (ADR-032) is
responsible for turning those signals into an authorization decision -- this
engine performs no gating itself.

## Owned events

| Direction | Subject | Payload |
|---|---|---|
| Published | `perception.presence.observed` | `PresenceObservation` -- matches World Model's `perception.*.observed` wildcard. |
| Published | `perception.identity.observed` | Smoothed `IdentityConfidenceState` (full confidence float + tier, ADR-032) -- matches the wildcard. |
| Published | `perception.attention.observed` | `AttentionObservation` -- matches the wildcard. |
| Published | `perception.wake.detected` | Wake-phrase trigger -- deliberately does **not** match the wildcard. |
| Published | `perception.addressee_signal.candidate` | Raw addressee-candidate signals, no verdict field -- deliberately does **not** match the wildcard. |
| Published | `perception.consent.changed` | Consent grant/revocation audit event. |
| Published | `perception.sensor.health_changed` | Sensor health-status change. |
| Published (RPC) | `ai_model.detect_wake_phrase.request`, `ai_model.embed_voice.request`, `ai_model.embed_face.request`, `ai_model.estimate_gaze.request` | This engine's own outbound calls to `ai-model-orchestration-engine` (ADR-020). |
| Subscribed | `communication.session.created`, `communication.session.completed` | Feeds `SessionActivityTracker` -- one of the addressee-candidate signals (§10). `communication.session.state_changed` is deliberately not subscribed (no `user_id` in that payload). |

See `events/published.py` / `events/subscribed.py` for the enforced
allow-lists, and `tests/contract/test_event_subject_wildcard.py` for the
mechanical wildcard-match/non-match verification.

## Owned APIs

All under `/v1/perception`, per the project-wide `/v1/<domain>/...` REST
convention -- a narrow admin/config surface only, no content API (this
engine produces no user-facing content; current presence/identity is
queried through World Model's `GET /v1/world/context`, not duplicated here).

- `POST /v1/perception/identities` -- enroll (requires active consent).
- `GET /v1/perception/identities` -- list enrolled identities (metadata only, never a template).
- `DELETE /v1/perception/identities/{id}` -- revoke (hard delete of the encrypted template).
- `GET /v1/perception/consent` -- consent status.
- `POST /v1/perception/consent` -- grant consent for a source.
- `DELETE /v1/perception/consent/{source}` -- revoke consent (stops the matching sensor synchronously).
- `GET /v1/perception/sensors` -- sensor health status.
- `POST /v1/perception/sensors/{id}/calibrate` -- calibration.
- `GET /v1/perception/diagnostics` -- current sensor state/health/capabilities dump.
- `GET /internal/health`, `GET /internal/readiness`, `GET /internal/metrics` -- unprefixed ops/probe surface.

## Known limitations (Phase 2D-B scope)

- **No live capture/ingestion path this phase.** Sensors operate on
  already-captured audio windows / already-detected face crops supplied by
  a caller -- there is no raw microphone/camera capture, and no HTTP/event
  entry point yet feeds sensors live data end-to-end. That integration is a
  future desktop/companion client's responsibility (§0.1); this phase builds
  the mechanism (sensors, evidence fusion, AIMO client, admin API), not a
  live orchestration loop with nothing yet to drive it.
- **Automatic sensor restart-on-failure is not yet an autonomous poller.**
  The state machine permits `failed -> initialize` (§5, §12) and
  `report_error()` drives that transition, but nothing currently calls
  `health_check()` on a timer and restarts a sensor without an external
  caller -- there is no live sensor process yet that could fail
  asynchronously without a real client feeding data.
- **Confidence-tier calibration (`ALPHA`, tier boundaries) is a starting
  point**, not scientifically validated against real data (§8, §24).
- **Real-Postgres verification of `PostgresPerceptionRepository` is
  pending** -- no Docker-capable environment has been available this session
  (tracked alongside the same open item for personality-engine and
  communication-engine).

## Testing

```bash
uv run --package perception-engine pytest services/perception-engine/tests
```
