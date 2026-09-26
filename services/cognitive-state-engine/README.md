# cognitive-state-engine

**Bible Part 6 — NOVA's Cognitive State Engine.** What NOVA is *currently
thinking about*: **Active Thoughts** (ongoing reasoning processes, each with
priority, confidence, dependencies, estimated completion, related memories,
related projects and current progress), the **Focus System** (*"only a limited
number of cognitive processes receive maximum computational attention"*), and
the five **Attention Layers** — Immediate, Active, Passive, Dormant, Archived —
that thoughts move between.

**Explicitly distinct from Phase 2D-C's session-scoped conversation memory**:
different lifetime, different owner. It is also a third thing alongside ADR-030's
*"Personality stores, Digital Twin learns"* — neither of those engines' data
moves here, and none of this engine's data moves there.

## The boundary — this engine proposes, and never acts

TDD 4F §6.2, ratified. It **may** produce a `DecisionRequest`, identify an action
type, supply subject, context and rationale, and carry the cognitive-state
evidence behind a request. It **must not** publish `action.execute`, call an
`action-engine` execution endpoint, invoke an actuator, or bypass
`autonomy-engine`, the Policy Engine, the Permission Matrix, the Trust Engine or
`action-engine`'s approval/execution boundary.

`autonomy-engine` remains the decision/control-plane owner; `action-engine`
remains the execution/approval boundary owner. `tests/contract/test_boundaries.py`
enforces the checkable half by property rather than by convention.

## Status — milestone slice 4F.1 only

Implemented here: the **domain** (`domain/models.py`, `attention.py`, `focus.py`,
`ports.py`) and **persistence** (`repository/`, `alembic/`). Deliberately *not*
implemented yet, each arriving with the slice that needs it:

| Slice | What it adds |
|---|---|
| 4F.6 | The initiative trigger, and the Event Bus subscriptions that feed it |
| 4F.7 | The `/v1/cognitive-state` read surface and the `cognitive-state/` panel |

The repository is therefore not wired into `main.py` yet: nothing consumes it in
4F.1, and wiring a dependency ahead of its consumer is the speculative work the
TDD's scope rule excludes.

### Status update — 4F.6 (2026-09-23)

4F.6 adds the **initiative trigger** (TDD 4F.6, `docs/design/phase-4/10-tdd-4f6-initiative-trigger.md` §19):

- an optional, all-or-nothing **`ProposedAction`** on each thought
  (`domain/models.py`), stored in one nullable JSONB column (migration `0002`);
- **`promotion_orchestration.promote_thought`** — a thought carrying a complete
  `ProposedAction` and **promoted to `IMMEDIATE`** sends exactly one
  `autonomy.decision.requested` request, with no retry;
- **`clients/decision_trigger_client.py`** — the producer-side error boundary,
  which reports `decided`, `rejected`, `degraded`, `unavailable`, `unconfirmed`
  or `failed` and never raises.

The trigger port is bound in `main.py`. The repository still is not:
**nothing in this engine's running topology calls `promote_thought` yet**. The
surface that drives promotions is 4F.7's, so CF-11 stays open. 4F.6 also added
**no** Event Bus subscription. The 4F.6 row in the table above expected "the
Event Bus subscriptions that feed it", but the ratified trigger condition is a
promotion, not an inbound event. That row is kept as it was written.

> **Correction, 2026-09-26 (4F.7 ratification, RS-1b, RS-1c and RS-11 — TDD
> 4F §24), additively.** The paragraph above is preserved as written, but its
> sentence *"The surface that drives promotions is 4F.7's"* is **superseded**.
>
> - **4F.7 is strictly read-only.** It adds the `GET`-only `/v1/cognitive-state`
>   surface and the panel. It does **not** create thoughts, author
>   `ProposedAction`s, promote thoughts, call `promote_thought`, or add a write
>   route.
> - **Production promotion is owned by this engine** (RS-1a), and is built in
>   the new slice **4F.P**, which comes before 4F.8. 4F.P also owns thought
>   ingestion and `ProposedAction` authorship.
> - **The same claim appears in two source files**:
>   `promotion_orchestration.py`'s module docstring and `main.py`'s lifespan
>   comment. They are production source, so this documentation step does not
>   edit them. Their additive clarification is an obligation of the 4F.7
>   implementation (TDD 4F.7 §17).

### Status update — 4F.7 (2026-09-26)

4F.7 adds the **read-only** Cognitive State surface (TDD 4F.7,
`docs/design/phase-4/11-tdd-4f7-cognitive-state-panel.md`):

- **three `GET` routes** under `/v1/cognitive-state` (`api/cognitive_state.py`),
  fronted by `api-gateway`, and the `cognitive-state/` panel that reads them;
- **one subscription**, to the existing subject `perception.sensor.health_changed`
  (RS-3a), handled by `events/handlers.py`;
- **one table**, `cognitive_state.sensor_state` (migration `0003`, A-4F7-1), which
  holds the last lifecycle state each sensor reported;
- the repository and a `nova-service-kit` database engine are now wired into
  `main.py` (A-4F7-4 default), for the read surface and the subscription only.

**Still true after 4F.7:** nothing in this engine's running topology calls
`promote_thought`, no route writes, and no Active Thought is created by NOVA in
production until **4F.P**. CF-9, CF-10 and CF-11 stay OPEN. The engine is now a
compose service (`infra/docker/docker-compose.local.yml`), migrated by
`run-migrations.sh`.

## Owned events

| Direction | Subject | Payload |
|---|---|---|
| Request (publish allow-list) | `autonomy.decision.requested` — **internal**, request/reply, served only by `autonomy-engine` (D-4F-9, 4F.6) | `AutonomyDecisionRequestedPayload` |
| Subscribe | `perception.sensor.health_changed` — the **existing** public subject, published by `perception-engine` on sensor lifecycle transitions (RS-3a, 4F.7) | `PerceptionSensorHealthChangedPayload`; `status` is one of `perception-engine`'s six `SensorState` lifecycle values (A-4F7-2) |

*(4F.7: the Subscribe row read **"*(none)*"** until 4F.7 added the one subject
above. It adds no subject to the registry and no entry to `PUBLIC_TOPICS`; the
handler validates the payload, accepts only the six lifecycle values
case-sensitively, and rejects anything else without storing it.)*

*(Until 4F.6 this section read **"None, in either direction."**, with the rows
"Publish — *(none — ratified decision D-4F-6)*" and "Subscribe — *(none in
4F.1; existing subjects arrive with their handlers in 4F.6)*". Preserved per
protocol §0.3.4.)*

**D-4F-6 still stands.** The trigger is a *request for a decision*, not a
cognitive-*state* subject. It is not in `PUBLIC_TOPICS`, it is not
browser-visible, and it is not exposed through either gateway. The payload
carries no `subject_id` and no `user_id`: `autonomy-engine` derives the first
and resolves the second itself.

D-4F-6: **no cognitive-state Event Bus subject is added**. `PUBLIC_TOPICS` is
`ws-gateway`'s sole browser allow-list, so a realtime panel would need a *public*
subject; the panel reads normalized state over REST instead. A subject exists to
be consumed, not to be complete (D-4D-1).

The empty publish allow-list is also the structural half of §6.2's *must not
publish `action.execute`*: `BoundEventBus.publish()` checks that set, so there is
no subject at which an execution request could be emitted.

*(4F.6: the allow-list is no longer empty. It holds exactly
`autonomy.decision.requested`, and the property above is unchanged:
`action.execute` is still not in it, and `BoundEventBus` checks the set on
`request()` as well as `publish()`.)*

See `events/published.py` / `events/subscribed.py` for the enforced allow-lists.

## Owned APIs

- `GET /internal/health`
- `GET /internal/readiness`
- `GET /internal/metrics`

`/v1/cognitive-state` arrives in 4F.7, fronted 1:1 by `api-gateway` (D-6), with
identity resolved **server-side** from `primary_user_id` (ADR-025). It will
expose only normalized state intended for the UI — never raw sensor events.

*(Updated 2026-09-26, 4F.7.)* It has arrived, **`GET`-only**, with no parameter
and no body; every other method answers 405 (TDD 4F.7 §7):

| Method | Path | Body |
|---|---|---|
| `GET` | `/v1/cognitive-state/thoughts` | `ThoughtListResponse` — every Active Thought of `primary_user_id`, with every Part 6 field and `proposed_action` as a proposal |
| `GET` | `/v1/cognitive-state/focus` | `FocusResponse` — `select_focus(..., capacity=focus_capacity, inputs=None)`; `signals_used` is always `[]` (focus-signal computation stays OPEN) |
| `GET` | `/v1/cognitive-state/sensors` | `SensorStateListResponse` — the stored `sensor_state` rows; `state` is a `SensorState` value, `reported_at` is dispatch time |

An empty store answers empty lists; a store failure is an error, never `[]`.

## Persistence

One table, `cognitive_state.active_thought`, in its own schema. **Additive only;
zero existing tables altered.**

Migration `0002` (4F.6) adds **one nullable `JSONB` column**, `proposed_action`,
and nothing else. No existing column or CHECK constraint changes. SQL `NULL`
means *"proposes no action"*: the ORM maps it with `none_as_null=True`, so the
value is never a JSON `null`.

Focus is **derived, not stored** — it is a pure function of the stored thoughts
plus the caller's signals — and an Attention Layer is a **column on a thought**,
not an entity. Neither gets a table, and no table exists here for a later slice.

*(Updated 2026-09-26, 4F.7, A-4F7-1.)* **Two tables now.** Migration `0003`
adds `cognitive_state.sensor_state` — five columns (`sensor_id` primary key,
`sensor_type`, `state`, `reported_at`, `last_event_id`) — and alters nothing.
It is **current-state storage**: one record per sensor, maintained by one
conditional upsert, so a redelivered report (same `event_id`) and an older one
change nothing. There is no history, heartbeat, audit, expiry or deletion, and
nothing resets it on startup. It is a projection of what `perception-engine`
reported, which remains the owner of the fact. *(The paragraph above says "One
table" and "no table exists here for a later slice"; both were true until 4F.7
added its own. Preserved per protocol §0.3.4.)*

`created_at` and `updated_at` are written from the domain object on every path,
never left to the column default. That is Phase 4E's ratified Option A applied
from the first line rather than retrofitted: `memory-engine`'s `create_long_term`
shipped omitting exactly those two columns, so the defaults fired and a caller's
timestamps were silently discarded.

## Testing

```bash
# Default tier (no Docker) -- ADR-033
uv run --package cognitive-state-engine pytest services/cognitive-state-engine/tests -m "not real_infra"

# Real-Postgres / real-NATS tier -- requires Docker
uv run --package cognitive-state-engine pytest services/cognitive-state-engine/tests -m real_infra
```
