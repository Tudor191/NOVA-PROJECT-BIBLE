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

## Owned events

| Direction | Subject | Payload |
|---|---|---|
| Request (publish allow-list) | `autonomy.decision.requested` — **internal**, request/reply, served only by `autonomy-engine` (D-4F-9, 4F.6) | `AutonomyDecisionRequestedPayload` |
| Subscribe | *(none)* | — |

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
