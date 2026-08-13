# digital-twin-engine

Bible Part 16's Digital Twin Engine, minimal Phase 2D-D slice --
docs/design/phase-2d/06-personal-companion.md, ADR-030. Owns Bible Part
16's Communication Profile domain, a conversation-scoped Preference
Evolution/Habit Detection slice, the correction-frequency trust metric
(Fork C, explicitly partial), and the proactive-communication boundary
policy (Fork D). Every other Bible Part 16 domain (goals, projects,
hardware, software, skills, knowledge, productivity, general workflow) is
Phase 4.

ADR-030: "Personality stores, Digital Twin learns" -- this engine is the
sole writer of learned communication preferences; `personality-engine`
only ever applies what it publishes (`personality.memory.update`), never
queries this engine directly.

## Known gap: `CommunicationProfile`'s five learned fields ship at their static defaults

`verbosity`/`technical_depth`/`terminology_preference`/`conversation_pacing`/
`habit_timing_hint` all have a real, working wire path (this engine's own
persistence, the `digital_twin.preferences.get` RPC, and -- once a real
evidence source exists -- `personality.memory.update`), but **no evidence
source for computing any of them has been approved**. `ConversationMemory`'s
free-text categories (`corrections`/`preferences`/`decisions`/`feedback`)
cannot become a structured value without inventing a text-classification
heuristic, which this project's standing instruction explicitly forbids
(see `domain/models.py`'s module docstring, "Fork F"). `domain/
preference_evolution.py::evolve_field` -- the real, fully-tested mechanism
Bible Part 16's "never overwrite immediately, require consistent evidence"
discipline requires -- exists and is exercised directly by tests, but has
**zero production call sites** this phase. The only way these five fields
change today is a direct user edit via `PATCH /v1/digital-twin/profile`
(Bible Part 16's own "User Control," which correctly bypasses the
consistent-evidence discipline -- the user's own explicit say-so is not
inferred evidence). A future phase plugs in real evidence extraction
additively, once one is approved.

Correction-frequency is unaffected by this gap -- `ConversationMemory.
corrections` is genuine, already-flowing evidence from reasoning-engine's
own evidence-based correction judgment (Phase 2D-D Steps 1-4), consumed
directly by `domain/trust_metric.py`.

## Owned events

| Direction | Subject | Payload |
|---|---|---|
| Subscribed | `communication.session.completed` | Records `CompletedSessionEvidence` + a structural `HabitSignal`, recomputes the correction-frequency trust metric over the configured rolling window. |
| Subscribed (RPC) | `digital_twin.preferences.get.request` | Serves this engine's own pacing/habit-timing fields (Fork A's field split -- never verbosity/technical_depth/terminology, which stay on the `personality.memory.update` path). |
| Requests (outbound) | `communication.session.lookup_by_user.request`, `communication.intent.deliver.request` | Fork D, Step 9 -- `CommunicationClient` (`clients/communication_client.py`), this engine's first synchronous upstream RPC caller; called by `proactive_delivery.attempt_proactive_delivery` (no production trigger source exists yet -- see Known limitations). |
| Published | *(personality.memory.update only, still dormant)* | `personality.memory.update` remains an approved capability (Sec7.1) with no real call site -- awaits an approved evidence source (Fork F). |

## Owned APIs

All under `/v1/digital-twin`, per the project-wide `/v1/<domain>/...` REST
convention.

- `GET /v1/digital-twin/profile` -- Retrieve Profile.
- `PATCH /v1/digital-twin/profile` -- Update Profile (direct user override, bypasses the consistent-evidence discipline -- see the known gap above).
- `POST /v1/digital-twin/reset` -- Reset Domain (Communication Profile only, this phase's scope).
- `GET /v1/digital-twin/preferences` -- HTTP mirror of the served RPC.
- `GET`/`PATCH /v1/digital-twin/proactive-policy` -- not itself named in Sec7.1's bullet list, but a necessary completion of Bible Part 16's "User Control": without a way to configure `max_per_topic_per_window`, Fork D's warm-case delivery (Step 9) could never actually deliver anything (`domain/proactive_boundary.py`'s fail-closed discipline denies any unconfigured topic).
- `GET /internal/health`, `GET /internal/readiness`, `GET /internal/metrics` -- unprefixed ops/probe surface.

## Known limitations (Phase 2D-D)

- **The five `CommunicationProfile` learned fields ship at static defaults** -- see above (unchanged since Step 6).
- **(Step 9) Fork D's warm-case proactive delivery is real and fully tested, but has no production trigger.** `proactive_delivery.attempt_proactive_delivery` composes the boundary policy (`domain/proactive_boundary.py`), the new `communication.session.lookup_by_user.request` lookup, and the existing `communication.intent.deliver.request` gate -- all real, wire-tested calls. Nothing in this codebase yet proposes a `ProactiveSuggestion` (no scheduler or reminder source exists anywhere this phase) -- calling this function is the one missing piece, and it is out of this phase's approved scope (docs/design/phase-2d/06-personal-companion.md Sec10 names only the policy and the delivery mechanism, not a trigger).
- **Cold-case proactive delivery is not proposed to be closed** (Sec10.3) -- no companion-client transport exists anywhere in this repository; a user with no currently-connected session cannot receive a proactive message this phase, under any design.
- **`personality.memory.update` publishing is dormant** -- the outbox/worker infrastructure is wired from day one (Priority 1's precedent), but nothing enqueues onto it yet.
- **Real-Postgres verification of `PostgresDigitalTwinRepository` is pending** -- no Docker-capable environment has been available this session (tracked alongside the same open item for personality-engine, communication-engine, and perception-engine). `tests/integration/test_repository_real_postgres.py` includes `test_proactive_delivery_record_persists_and_lists_recent_by_window` as of Step 9, written but not locally executed.

## Testing

```bash
uv run --package digital-twin-engine pytest services/digital-twin-engine/tests
```
