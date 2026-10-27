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
| Published | `perception.workspace.observed` | **Phase 4F.2.** `PerceptionWorkspaceObservedPayload` -- the first **object-shaped** perception event, matching the wildcard and falling through World Model's dispatcher to its object-graph handler with **zero changes there**. Carries a **file-path hash**, never the raw path. **Internal only:** absent from `PUBLIC_TOPICS`, and `ws-gateway`'s bus allow-list was narrowed from `perception.*` to the three browser-relevant subjects so the gateway process cannot receive it. |
| Published | `perception.consent.changed` | Consent grant/revocation audit event. |
| Published | `perception.sensor.health_changed` | Sensor health-status change. **Phase 4F.7 (RS-3a, A-4F7-2):** now actually published -- one report per real lifecycle transition, see below. |
| Published (RPC) | `ai_model.detect_wake_phrase.request`, `ai_model.embed_voice.request`, `ai_model.embed_face.request`, `ai_model.estimate_gaze.request` | This engine's own outbound calls to `ai-model-orchestration-engine` (ADR-020). |
| Subscribed | `communication.session.created`, `communication.session.completed` | Feeds `SessionActivityTracker` -- one of the addressee-candidate signals (§10). `communication.session.state_changed` is deliberately not subscribed (no `user_id` in that payload). |
| Subscribed | `memory.long_term.created` | **Phase 4F.8** (A-4F8-2 (a)). Only `project_id` and `user_id` are read: a memory of this deployment's user that names a project makes that project **known** (`perception.known_project`). See *Known projects* below. |

See `events/published.py` / `events/subscribed.py` for the enforced
allow-lists, and `tests/contract/test_event_subject_wildcard.py` for the
mechanical wildcard-match/non-match verification.

*(Phase 4F.P, 2026-10-05.)*

- **A second consumer.** `perception.workspace.observed` is now also consumed
  by `cognitive-state-engine`, which turns each observation into at most one
  Active Thought (TDD 4F.P A-4FP-1).
- **This engine is unchanged**, and the subject stays internal.
- **The e2e stack** sets `PERCEPTION_ENGINE_PRIMARY_USER_ID` to the stack's
  one user (A-4FP-12). Unset, this engine publishes no workspace observation
  (`workspace_orchestration.py`'s explicit degrade).

### `perception.sensor.health_changed` -- published since Phase 4F.7 (2026-09-26)

The subject was registered and allow-listed from Phase 2D-B, with a builder
(`events/publishers.py::sensor_health_changed`) that nothing called. Since
4F.7 (TDD 4F §24.4 **RS-3a**; TDD 4F.7 §8.1) it is published through the
transactional outbox whenever an **existing** lifecycle call actually changes a
sensor's state (`sensor_lifecycle.py`):

| Call site | Reports | Correlation id |
|---|---|---|
| Startup (`main.py`) | each sensor's `initialized`, then `running` | one fresh id for the whole startup |
| Consent revocation (`api/consent.py`) | the revoked source's sensor `stopped` | the revoked grant's `consent_id` |
| Observation-window failure (`observation_orchestration.py`) | a camera or voice sensor's `failed` | the observation's `correlation_id` |
| Shutdown (`main.py`) | each still-running sensor's `stopped` | one fresh id for the whole shutdown |

- **`status` is a `SensorState` lifecycle value** -- `sensor.state()` read after
  the call, one of `uninitialized`, `initialized`, `running`, `paused`,
  `stopped`, `failed` (**A-4F7-2**). `health_check()`'s `"healthy"` /
  `"unhealthy"` string is never published. The payload contract in
  `nova-contracts` is unchanged (`status: str`).
- **No report for a no-op.** A call that leaves the state where it was reports
  nothing.
- **No transition is added.** `pause` / `resume` still have no production
  caller, and the filesystem sensor still has no path to `failed` (RS-3b, OPEN).
- **A failed enqueue is logged, not raised**: the transition has already
  happened, and nothing retries the report.
- The subject is already in `ws-gateway`'s `PUBLIC_TOPICS`, so browsers receive
  these frames (the accepted RS-3a consequence); `cognitive-state-engine`
  subscribes to it and keeps the last reported state per sensor. Core NATS does
  not deliver to a subscriber that is not connected at dispatch time
  (TDD 4F.7 §15 K-1).

## Known projects -- Phase 4F.8

*(A-4F8-2 (a), (a1) and (a2), ratified 2026-10-11; TDD 4F.8 §29.1, §33. It
settles ledger row L-13.)*

A workspace observation carries a `project_id` only when **both** of these
hold:

1. **An operator declared the folder.** `PERCEPTION_ENGINE_PROJECT_FOLDER_BINDINGS`
   is JSON mapping an absolute folder, as the companion reports paths, to a
   project UUID. In compose it is passed through from `NOVA_PROJECT_FOLDER_BINDINGS`.
   - **Empty by default**, so nothing is known unless declared.
   - The nearest declared ancestor folder wins, matched by whole path segments.
2. **NOVA holds that project.** Its `project_id` has been seen on
   `memory.long_term.created` and recorded in `perception.known_project`
   (migration `0002`).
   - Current state only.
   - It survives a restart.
   - A declared folder for a project never seen is **inert**.

Otherwise the observation is published with `project_id = None`, never a guess
(§9, N-13).

**Unchanged:**
- the correlation happens here, where the path is transiently available, and
  the path is never published (D-4F3-2);
- `world-model-engine` is unchanged (A-4F8-2 (a2)). *"Known"* shows on the
  published observation, and the World Model object stays per file (F-4F8-6).

## Outbox dispatch -- every second, from one worker

*(Phase 4F.8, 2026-10-11; TDD 4F.8 §30, §31.)*

`perception-engine-worker` runs `arq nova_perception_engine.workers.WorkerSettings`.
Its only job drains `perception.outbox_event` to the bus.

- **Every second.** D-4F-1 was reopened for this engine's dispatch interval
  only, so that a workspace observation reaches the bus well inside AC-7's
  5-second budget. Every other engine keeps its 10-second poll.
- **One run at a time (`max_jobs = 1`).** arq enqueues each tick whether or not
  the previous run has finished, and `list_dispatch_ready` claims no row. So a
  slow run delays the next tick instead of overlapping it.
- **Exactly one worker replica.** `max_jobs` bounds one process. Two replicas
  can publish one row twice. Making that safe would need row claiming in
  `nova_service_kit`'s shared outbox, which is not built.
  - Compose defines one `perception-engine-worker`.
  - `tools/tests/test_perception_dispatch_cadence.py` fails if anything adds a
    second one or scales it.
- **Delivery is still at-least-once.** A crash between a publish and its mark
  republishes that row under the same `event_id`, as before.

`tests/integration/test_outbox_dispatch_cadence_real_infra.py` proves the
no-overlap, no-duplicate claim. It uses a real worker with real Redis,
PostgreSQL and NATS, and its last test is the control without `max_jobs = 1`.

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
- `POST /v1/perception/workspace-observations` -- **Phase 4F.2.** Structured intake for workspace observations: JSON `{path, observed_at}`, with `source` and an optional `correlation_id` as query parameters. A **sibling** of the capture-window route above, not a replacement -- that one takes a raw `application/octet-stream` window and runs biometric detection over it, which structured metadata cannot enter. **`user_id` is resolved server-side** from `Settings.primary_user_id` (ADR-025); the request model has no `user_id` and no `object_id` field, so a caller can forge neither. Internal only: `/v1/perception` is **not** among `api-gateway`'s proxied prefixes, so no browser can reach it.
- `POST /v1/perception/permission-revocations` -- **Phase 4F.8** (A-4F8-1 (a1)). The one route through which `nova-companion` reports that it lost its OS permission on the watched directory: JSON `{detected_at}` only, with `source` and an optional `correlation_id` as query parameters. Only the `filesystem` source is accepted. The filesystem sensor moves `running -> failed`, and `failed` is published on `perception.sensor.health_changed`. A repeat changes nothing (`transitioned: false`). Internal only, like the workspace route.
- `GET /v1/perception/sensors` -- sensor health status.
- `POST /v1/perception/sensors/{id}/calibrate` -- calibration.
- `GET /v1/perception/diagnostics` -- current sensor state/health/capabilities dump.
- `GET /internal/health`, `GET /internal/readiness`, `GET /internal/metrics` -- unprefixed ops/probe surface.

## Sensors

| Source | Sensor | Observes |
|---|---|---|
| `microphone` | `VoiceSensor` | Wake phrase, voiceprint -- via `ai-model-orchestration-engine` (ADR-020) |
| `camera` | `CameraSensor` | Gaze/attention, faceprint -- same boundary |
| `filesystem` | `FilesystemSensor` | **Phase 4F.3.** Nothing directly -- see below |

**`FilesystemSensor` performs no detection** (**D-4F3-1**). Real OS observation
belongs to `nova-companion`, the Rust daemon in `companion/`, which submits
through the workspace route above. This class is the *registry and lifecycle*
half of that split: the route resolves `sensors_by_source["filesystem"]` and
gates on `state() != "running"`, so pausing it makes the engine drop the
companion's observations whatever the companion is still doing -- which is what
makes AC-7 clause 2's revocation real at the pipeline level.

`VoiceSensor` and `CameraSensor` are the precedent: perception-engine classes
representing a capability executed elsewhere.

**Its `permission_status()` is not a consent claim.** **D-4F3-3** is explicit
that 4F.3 adds no consent mechanism, and Doc 22 Principle 8's per-source consent
requirement for the filesystem source remains an open policy question carried as
ledger row **L-14**. What bounds it meanwhile is that the companion watches only
an explicitly configured directory.

**Phase 4F.8: the `failed` path** (A-4F8-1 (a), RS-3b; TDD 4F.8 §29.1).

- **The trigger.** The companion detects losing its OS permission, and reports
  it on the revocation route above. That report, and only that report, moves
  this sensor `running -> failed`, through `sensor_lifecycle.report_sensor_error`
  as camera and voice already do.
  - Any other error is still recorded and changes nothing. A failure is never
    inferred (N-8), and `tests/unit/test_revocation_is_the_only_failed_path.py`
    checks that structurally.
- **What follows:**
  - `permission_status().granted` reads `False`;
  - `failed` is published;
  - the workspace route's `running` gate drops every later observation.
- **No automatic recovery** (a2). Both processes must restart.

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
