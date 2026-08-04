# world-model-engine

NOVA's world-state subsystem (the merged Bible Part 5 + Part 18, per ADR-002 /
`docs/design/phase-1/03-world-model-engine.md`). Owns the current state of reality -- object
lifecycle, Active Context, Attention, relationship consistency between world
objects, and short-horizon prediction. It is the only engine that ever writes
to `world_model.*` Postgres tables, `:WorldProject|File|Window|Application|
Agent|Task|Device|SystemResource` Neo4j nodes, or the `world:context:*` /
`world:attention:*` / `world:presence:*` Redis keys.

## Responsibility -- and the boundary that shapes every other decision below

The user's standing architectural constraint for this engine: **the World
Model must not become another Knowledge Engine, and must not become another
Memory Engine.** World Model represents the current state of reality; Memory
represents historical experience; Knowledge represents validated facts and
relationships. Every module in `domain/` was built to preserve that
separation even where it costs extra complexity -- see the ADR directory
(`docs/architecture/adr/`) and the Memory/Knowledge/World Model comparison
document for the full reasoning. Concretely, in this engine:

- **No embeddings, no vector index.** `pyproject.toml` depends on
  `nova-graphstore-sdk` but deliberately not `nova-vectorstore-sdk` /
  `nova-embeddings-sdk` (§10). There is no `vector_store_dsn()` in
  `config.py`, no `embedding` column anywhere in the schema, and no async
  embedding worker -- world objects are looked up by id/label/scope, never by
  semantic similarity.
- **No forgetting lifecycle.** Memory Engine's importance-decay-then-archive
  pipeline has no analogue here. A World Object's row simply reflects the
  latest observed state; there is no "long-term" tier and nothing is ever
  consolidated into a narrative.
- **No validated-fact graph.** Knowledge Engine's contradiction detection,
  confidence-scored corroboration, and seven-stage maturity model
  (raw -> ... -> strategic) do not exist here. `:WorldProject` is a distinct
  Neo4j label from Knowledge's `:Project`, linked only by a shared UUID
  convention -- never by a graph traversal that crosses the label boundary,
  preserving ADR-007's requirement that each engine's graph data stay
  independently replaceable.

Within that boundary, the engine's actual responsibilities:

- **Object lifecycle** (`domain/state_management.py`, `domain/object_graph.py`):
  a table-driven state machine (`UNKNOWN -> ACTIVE -> {IDLE, EXECUTING,
  LEARNING}`, `EXECUTING -> {COMPLETED, FAILED, WAITING}`) mirroring Memory
  Engine's own `lifecycle.py` pattern, but for object *state* rather than
  memory *tier*. Only the transitions the design doc's §6 diagram actually
  draws are implemented; `WAITING`/`LEARNING` having no outgoing edges is a
  documented gap, not an oversight.
- **The two-phase saga** (`repository/outbox_dispatcher.py`, `workers/
  outbox_worker.py`): identical mechanism to Knowledge Engine's -- the
  Postgres commit (with an `outbox_event` row carrying the pending
  `graph_write` intent) is the durable record of intent; a separate
  dispatcher applies it to Neo4j and only then publishes the event (§17).
  `GraphWriteOp.kind` adds a third literal, `"delete_node"`, absent from
  Knowledge Engine's version -- world objects can be removed from reality
  (e.g. a closed window), unlike knowledge nodes, which are never hard-deleted.
- **Active Context & Attention** (`domain/context.py`, `domain/attention.py`,
  `repository/redis_context_repository.py`): Redis is the *primary* store for
  these, not a cache -- `world:context:<user_id>` (HASH),
  `world:attention:<user_id>` (ZSET) plus a companion
  `world:attention_ts:<user_id>` (HASH) for `last_boosted_at` (a ZSET score
  can only carry one number; the lazy-decay formula needs two), and
  `world:presence:<user_id>:<device>` (STRING, TTL). Attention decay is
  implemented literally per §6's stated formula: `raw_weight *
  exp(-(now - last_boosted_at) / half_life)`.
- **Multi-modal perception fusion** (`domain/fusion.py`): correlates signals
  within a window and publishes at most one `world_model.context.changed`
  event per window, never one per raw signal.
- **Conflict resolution** (`domain/conflict_resolution.py`): confidence ->
  policy-priority -> recency-window -> unresolved fallback chain. The
  unresolved branch still produces a value (falls back to most recent) but
  labels `resolution_strategy="unresolved"` as a visible flag for later
  Reasoning Engine review -- it never blocks the write and never silently
  claims a confident result it doesn't have.
- **Temporal reasoning & prediction** (`domain/temporal.py`,
  `domain/prediction.py`): `predict_from_history` is a structural heuristic
  (recurring `(object_label, previous_state, new_state)` transition-pattern
  counting via `collections.Counter`), explicitly not a learned model --
  same honesty precedent as Knowledge Engine's `summarization.py`.
- **World Simulation** (`domain/simulation.py`): Phase 1 ships only the
  interface, `simulate(action) -> PredictedOutcome`, as an honest stub
  returning `confidence=0.0, reason="simulation not yet implemented"` (§20).
- **Agent-scoped context** (`domain/context.scoped_view`): server-side
  per-category field whitelist (Part 11 "Agent Awareness", §7 step 4) so a
  `coding-agent` caller sees `project_id`/`task`/`device` while a
  `communication-engine` caller sees `activity`/`device`/`platform`;
  `user_id`/`confidence`/`updated_at` are always included.

## Architecture

```mermaid
flowchart TB
    subgraph API["api/ (FastAPI)"]
        context["context.py"]
        objects["objects.py"]
        graph["graph.py"]
        snapshots["snapshots.py"]
        health["health.py"]
    end

    subgraph Events["events/"]
        handlers["handlers.py\n(perception/action subscribers)"]
        serveRPC["serve(world_model.context.request)"]
    end

    subgraph Domain["domain/ (framework-free)"]
        stateMgmt["state_management.py"]
        objectGraph["object_graph.py"]
        fusion["fusion.py"]
        conflict["conflict_resolution.py"]
        attention["attention.py"]
        ctxDomain["context.py"]
        temporal["temporal.py"]
        prediction["prediction.py"]
        simulation["simulation.py"]
        ranking["ranking.py"]
        ports["ports.py (Protocols)"]
    end

    subgraph Workers["workers/ (Arq, separate process)"]
        outboxWorker["outbox_worker.py\n(saga dispatcher, every 10s)"]
        snapshotWorker["snapshot_worker.py\n(scheduled, no-op: no user directory yet)"]
        predictionWorker["prediction_worker.py\n(scheduled, no-op: no user directory yet)"]
    end

    subgraph Repository["repository/"]
        pgRepo["postgres_history_repository.py"]
        redisRepo["redis_context_repository.py"]
        outboxDispatcher["outbox_dispatcher.py"]
    end

    API --> Domain
    Events --> Domain
    Domain -. depends on .-> ports
    Repository -. implements .-> ports
    Domain --> Repository
    Workers --> Domain
    Workers --> Repository
    pgRepo --> Postgres[(Postgres\nworld_model schema)]
    redisRepo --> Redis[(Redis\nprimary store, not cache)]
    outboxDispatcher -. apply_graph_write .-> objectGraph
    objectGraph --> Neo4j[(Neo4j)]
    outboxDispatcher --> EventBus{{nova-eventbus-sdk}}
    serveRPC --> EventBus
    handlers --> EventBus
```

`domain/` never imports FastAPI, SQLAlchemy, Redis, or Neo4j clients --
everything it needs is expressed as a `Protocol` in `domain/ports.py`
(`WorldHistoryRepository`, `ContextRepository`, `GraphStore`,
`EventPublisher`), matching `docs/architecture/03-backend-architecture.md`
§1's framework-free rule. Deliberately absent from `ports.py`:
`VectorIndex`/`EmbeddingProvider` -- see the boundary section above.

There is no `repository/neo4j_world_repository.py` distinct from
`nova-graphstore-sdk`'s own `GraphStore` implementation, same pattern as
Knowledge Engine.

## Owned events

| Direction | Subject | Payload |
|---|---|---|
| Publishes | `world_model.object.created` / `.updated` / `.deleted` | `WorldObjectChangedPayload` |
| Publishes | `world_model.context.changed` | `ContextChangedPayload` |
| Publishes | `world_model.attention.shifted` | `AttentionShiftedPayload` |
| Publishes | `world_model.prediction.generated` | `PredictionPayload` |
| Serves | `world_model.context.request` / reply | `ContextRequestPayload` / `ContextReplyPayload` (`degraded: bool` on failure -- the Thinking Pipeline's tightest Phase 1 latency budget, p95 < 20ms per §15) |
| Subscribes | `perception.*.observed` | real effect -- creates/transitions World Objects via `object_graph.observe_object` |
| Subscribes | `action.result` | real effect -- completes/fails/blocks `EXECUTING` objects |
| Subscribes | `nova.mode.changed` | honest no-op -- §13 gives one worked example of an Attention-weighting shift, not a general formula, so nothing is guessed at |
| Subscribes | `agent_os.task.*` | honest no-op, registered ahead of its Phase 3+ producer per §13's explicit instruction |

Unlike Memory Engine, this engine initiates no outbound RPC calls in Phase 1
-- it only serves `world_model.context.request`. See `events/published.py` /
`events/subscribed.py` for the enforced allow-lists (checked by
`nova_eventbus_sdk.boundary.BoundEventBus`).

Note: there is no dedicated relationship-created event (unlike Knowledge
Engine's `knowledge.edge.created`) -- §13's event table has none for World
Model. Relationships are expressed as additional `GraphWriteOp`s riding on
the same outbox row as whichever object upsert implies them
(`object_graph.observe_object`'s optional `relationships` parameter), never
as a standalone fabricated event.

## Owned APIs

- `GET /v1/world/context?user_id=&scope=` -- current Active Context, agent-scoped
  via `scope`.
- `GET /v1/world/objects/{object_id}` -- latest known state of one object
  (reads Postgres's `object_state_history`, never Neo4j -- see Known
  limitations for why).
- `GET /v1/world/objects/{object_id}/history` -- full state-transition trail.
- `GET /v1/world/graph?scope=project:<id>` -- subgraph traversal outward from
  a seed `:WorldProject` node.
- `POST /v1/world/snapshot` -- trigger a manual World State Snapshot.
- `GET /v1/world/snapshots?user_id=` -- list snapshots for a user.
- `GET /v1/world/predictions?user_id=` -- list generated predictions for a user.
- `GET /internal/health`, `GET /internal/readiness`, `GET /internal/metrics`.

## Observability

`observability.py` defines `WorldModelEngineMetrics`, created once per
process (API or worker) right after `configure_observability()` runs, then
threaded explicitly through request handlers, API routes, and worker
functions:

| Metric | Kind | Labels |
|---|---|---|
| `world_model_engine_context_request_duration_seconds` | Histogram | -- |
| `world_model_engine_object_write_duration_seconds` | Histogram | -- |
| `world_model_engine_fusion_window_duration_seconds` | Histogram | -- |
| `world_model_engine_context_requests_total` | Counter | -- |
| `world_model_engine_context_degraded_total` | Counter | -- (Redis unreachable -- fails fast, never returns silently stale/empty context) |
| `world_model_engine_objects_observed_total` | Counter | `outcome` (`created`/`updated`) |
| `world_model_engine_objects_removed_total` | Counter | -- |
| `world_model_engine_conflicts_resolved_total` | Counter | `strategy` (`confidence`/`recency`/`policy`/`unresolved`) |
| `world_model_engine_attention_boosts_total` | Counter | -- |
| `world_model_engine_predictions_generated_total` | Counter | -- |
| `world_model_engine_snapshots_taken_total` | Counter | `trigger` (`scheduled`/`manual`/`pre_risky_action`) |
| `world_model_engine_graph_writes_applied_total` | Counter | -- |
| `world_model_engine_outbox_dispatched_total` | Counter | `subject` |
| `world_model_engine_graph_write_degraded_total` | Counter | -- (§17 step 4's operational signal) |

Structured logs go through `nova_observability.get_logger`; both the FastAPI
process (`main.py`) and the Arq worker process (`workers/__init__.py`) call
`configure_observability()` independently, since they are separate OS
processes.

## Running locally

```bash
# from the repo root
docker compose -f infra/docker/docker-compose.local.yml up -d postgres neo4j redis nats
uv run --package world-model-engine alembic -c services/world-model-engine/alembic.ini upgrade head
uv run --package world-model-engine python cypher/apply_constraints.py  # from services/world-model-engine/
uv run --package world-model-engine uvicorn nova_world_model_engine.main:app --reload --port 8003

# separate process, same infra
uv run --package world-model-engine arq nova_world_model_engine.workers.WorkerSettings
```

Real Postgres, Neo4j, and Redis are required to boot `main.py`/`workers/`
without dependency injection -- this container has no Docker, so that path is
not exercised here; see Testing below for what *is* verified without it.

## Testing

```bash
uv run --package world-model-engine pytest services/world-model-engine/tests
```

- `tests/unit/` -- pure domain logic (`state_management`, `attention`,
  `conflict_resolution`, `fusion`, `prediction`), no I/O.
- `tests/integration/` -- boots the real FastAPI app (lifespan-driven, real
  routes, real event subscriptions) with `WorldHistoryRepository`,
  `ContextRepository`, and `GraphStore` all substituted for in-memory
  fakes/backends via `create_app()`'s dependency-injection parameters
  (`tests/fakes/`, `nova-graphstore-sdk`'s `InMemoryGraphStore`).
  `test_saga.py` exercises the two-phase saga's crash-recovery property
  (§19's explicit requirement: kill between step 1 and step 2, restart,
  assert the pending graph write completes and the event publishes exactly
  once -- never zero, never twice). `test_handlers.py` drives the real
  perception/action-result handlers with synthetic events (no live Perception
  Engine exists yet). Postgres/Redis/Neo4j-specific code
  (`repository/postgres_history_repository.py`,
  `repository/redis_context_repository.py`) is the one layer this suite
  cannot reach; validating it needs the real backends via Docker Compose,
  same limitation already accepted for Memory Engine and Knowledge Engine.

Current count: 54 tests (34 unit, 20 integration), all passing; `ruff check`
and `mypy` both clean across `src/` and `tests/`.

## Known limitations (Phase 1)

- **No idle-sweep worker.** `domain/state_management.next_state_on_idle_timeout`
  (the `ACTIVE -> IDLE` transition) exists and is unit-tested, but has no
  scheduled caller. A correct implementation needs either a nontrivial
  Postgres "latest row per object_id, filtered by staleness" query or a
  Neo4j property-based staleness check -- deliberately deferred per the
  standing "do not optimize prematurely, build the correct architecture
  first, optimization should always be evidence-driven" instruction, rather
  than shipped half-correct.
- **No general Attention-weighting-on-mode-change formula.**
  `events/handlers.make_mode_changed_handler` is an honest no-op. §13 gives
  one worked example of a mode-change shifting Attention weights, not a
  general formula applicable to arbitrary mode transitions -- nothing is
  guessed at here.
- **No user-directory / active-user-discovery mechanism.**
  `snapshot_worker.py` and `prediction_worker.py` both take an explicit
  `user_ids` list rather than discovering active users themselves;
  `workers/__init__.py` sets `ctx["known_user_ids"] = []` unconditionally, so
  both scheduled cron jobs currently run and log normally but have nothing to
  iterate. This is honest inertness, not a silent failure -- the moment a
  real user feed exists (e.g. from Agent OS or a session registry), wiring it
  into `known_user_ids` is a one-line change.
- **`GET /v1/world/objects/{id}` never queries Neo4j.** `GraphStore.query()`
  requires an upfront `label` the caller doesn't have, and
  `GraphStore.traverse()` excludes the start node itself from its results.
  Postgres's `object_state_history` already has everything needed for
  "current state" and is always consistent even if the Neo4j apply for that
  observation is still pending in the saga -- so this endpoint reads Postgres
  only, by design, not as a workaround.
- **No read-through cache**, mirroring Memory Engine and Knowledge Engine's
  same accepted gap -- every read hits Postgres/Redis/Neo4j directly.
- **World Simulation is an interface-only stub** (`domain/simulation.py`,
  §20) -- `simulate()` always returns `confidence=0.0,
  reason="simulation not yet implemented"`. Building a real simulator is out
  of scope until Reasoning Engine exists to consume its output meaningfully.
- **Environment Prediction is a structural heuristic, not a learned model**
  (`domain/prediction.py`, §7/§20) -- transition-pattern frequency counting
  over recent history, same honesty precedent as Knowledge Engine's
  `summarization.py`.
