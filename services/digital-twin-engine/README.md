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
| Published | *(none yet)* | `personality.memory.update` and `communication.intent.deliver.request` are both approved capabilities (Sec7.1) with no real call site this phase -- see `events/published.py`'s module docstring. |

## Owned APIs

All under `/v1/digital-twin`, per the project-wide `/v1/<domain>/...` REST
convention.

- `GET /v1/digital-twin/profile` -- Retrieve Profile.
- `PATCH /v1/digital-twin/profile` -- Update Profile (direct user override, bypasses the consistent-evidence discipline -- see the known gap above).
- `POST /v1/digital-twin/reset` -- Reset Domain (Communication Profile only, this phase's scope).
- `GET /v1/digital-twin/preferences` -- HTTP mirror of the served RPC.
- `GET`/`PATCH /v1/digital-twin/proactive-policy` -- not itself named in Sec7.1's bullet list, but a necessary completion of Bible Part 16's "User Control": without a way to configure `max_per_topic_per_window`, Fork D's warm-case delivery (Step 9) could never actually deliver anything (`domain/proactive_boundary.py`'s fail-closed discipline denies any unconfigured topic).
- `GET /internal/health`, `GET /internal/readiness`, `GET /internal/metrics` -- unprefixed ops/probe surface.

## Known limitations (Phase 2D-D Step 6 scope)

- **The five `CommunicationProfile` learned fields ship at static defaults** -- see above.
- **Fork D's warm-case proactive delivery is not yet wired** -- this engine's own publish side (`communication.intent.deliver.request`) and the `user_id -> connected session_id` lookup are Step 9's scope.
- **`personality.memory.update` publishing is dormant** -- the outbox/worker infrastructure is wired from day one (Priority 1's precedent), but nothing enqueues onto it yet.
- **Real-Postgres verification of `PostgresDigitalTwinRepository` is pending** -- no Docker-capable environment has been available this session (tracked alongside the same open item for personality-engine, communication-engine, and perception-engine).

## Testing

```bash
uv run --package digital-twin-engine pytest services/digital-twin-engine/tests
```
