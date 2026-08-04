# knowledge-engine

NOVA's knowledge subsystem (Bible Part 10 / `docs/design/phase-1/
02-knowledge-engine.md`). Owns the knowledge graph -- acquisition, normalization,
validation, contradiction detection, graph operations, relationship discovery,
summarization/compression, retrieval, ranking, and the knowledge-maturity
("evolution") state machine. It is the only engine that ever writes to
`knowledge.*` Postgres tables, the Neo4j graph (via `nova-graphstore-sdk`), or the
`knowledge_nodes` vector collection.

## Responsibility

- **Acquisition** (`domain/acquisition.py`): the full pipeline traced in the
  design doc's §3 sequence diagram -- normalize (`normalization.py`) -> validate
  and score confidence (`validation.py`) -> check for structural conflicts
  (`contradiction.py`) -> create-or-corroborate a node (`graph_operations.py`), or
  record a contradiction instead of silently overwriting existing knowledge.
- **The two-phase saga** (`repository/outbox_dispatcher.py`, `workers/
  outbox_worker.py`): every node/edge write spans two non-transactional
  datastores (Postgres metadata + Neo4j graph). The Postgres commit (with an
  `outbox_event` row carrying the pending `graph_write` intent) is the durable
  record of intent; a separate dispatcher step applies it to Neo4j and only then
  publishes the corresponding event -- consumers never see a node "created"
  before it's actually queryable in the graph (§17).
- **Retrieval** (`domain/retrieval.py`): fans out semantic (vector), graph
  traversal, and name-based search concurrently, merges by `node_id`, and ranks
  (`domain/ranking.py`) with relationship context attached to each result --
  richer than Memory Engine's retrieval by design, since "the surrounding
  context, the relationships, the history" is the point (§7).
- **Evolution** (`domain/evolution.py`, `workers/maintenance_worker.py`): the
  seven-stage knowledge-maturity state machine (raw -> processed -> verified ->
  connected -> applied -> expert -> strategic, §6) -- knowledge never gets
  deleted the way memory does, only matures.
- **Discovery & compression** (`domain/discovery.py`, `domain/compression.py`,
  `workers/maintenance_worker.py`): infers `RELATED_TO` edges between
  semantically similar nodes, and flags (never deletes or silently merges) likely
  duplicates -- Part 10's "nothing important should disappear permanently" is
  taken literally.
- **Async embedding** (`workers/embedding_worker.py`): identical mechanism to
  Memory Engine's -- a node's `embedding` column starts `NULL`, filled in later
  off the write path.

## Architecture

```mermaid
flowchart TB
    subgraph API["api/ (FastAPI)"]
        nodes["nodes.py"]
        graph["graph.py"]
        contradictions["contradictions.py"]
        health["health.py"]
    end

    subgraph Events["events/"]
        handlers["handlers.py\n(upstream subscribers)"]
        serveRPC["serve(knowledge.retrieve/traverse/link.request)"]
    end

    subgraph Domain["domain/ (framework-free)"]
        acquisition["acquisition.py"]
        normalization["normalization.py"]
        validation["validation.py"]
        contradiction["contradiction.py"]
        graphops["graph_operations.py"]
        discovery["discovery.py"]
        compression["compression.py"]
        retrieval["retrieval.py"]
        ranking["ranking.py"]
        evolution["evolution.py"]
        ports["ports.py (Protocols)"]
    end

    subgraph Workers["workers/ (Arq, separate process)"]
        maintenanceWorker["maintenance_worker.py"]
        embeddingWorker["embedding_worker.py"]
        outboxWorker["outbox_worker.py\n(saga dispatcher)"]
    end

    subgraph Repository["repository/"]
        pgRepo["postgres_metadata_repository.py"]
        outboxDispatcher["outbox_dispatcher.py"]
    end

    API --> Domain
    Events --> Domain
    Domain -. depends on .-> ports
    Repository -. implements .-> ports
    Domain --> Repository
    Workers --> Domain
    Workers --> Repository
    Repository --> Postgres[(Postgres + pgvector\nknowledge schema)]
    outboxDispatcher -. apply_graph_write .-> graphops
    graphops --> Neo4j[(Neo4j)]
    outboxDispatcher --> EventBus{{nova-eventbus-sdk}}
    serveRPC --> EventBus
    handlers --> EventBus
```

`domain/` never imports FastAPI, SQLAlchemy, Neo4j/pgvector clients, or an
event-bus client -- everything it needs is expressed as a `Protocol` in
`domain/ports.py` (`KnowledgeMetadataRepository`, `GraphStore`, `VectorIndex`,
`EmbeddingProvider`, `EventPublisher`), matching `docs/architecture/
03-backend-architecture.md` §1's framework-free rule. `graph_operations.py` is
the only module that ever produces a `GraphWriteIntent` or calls a live
`GraphStore` (via `apply_graph_write`, invoked exclusively by the saga
dispatcher) -- no other module touches the graph directly.

There is no `repository/neo4j_knowledge_repository.py` module distinct from
`nova-graphstore-sdk`'s own `Neo4jGraphStore` -- the shared SDK's `GraphStore`
implementation already is that adapter (mirroring how Memory Engine uses
`PgVectorStore`/`OllamaEmbeddingProvider` directly, with no per-engine wrapper).

## Owned events

| Direction | Subject | Payload |
|---|---|---|
| Publishes | `knowledge.node.created` / `.updated` | `KnowledgeNodeChangedPayload` |
| Publishes | `knowledge.edge.created` | `KnowledgeEdgeCreatedPayload` |
| Publishes | `knowledge.contradiction.detected` / `.resolved` | `ContradictionPayload` |
| Publishes | `knowledge.layer.advanced` | `LayerAdvancedPayload` |
| Serves | `knowledge.retrieve.request` / reply | `KnowledgeRetrieveRequestPayload` / `KnowledgeRetrieveReplyPayload` |
| Serves | `knowledge.traverse.request` / reply | `KnowledgeTraverseRequestPayload` / `KnowledgeTraverseReplyPayload` |
| Serves | `knowledge.link.request` / reply | `KnowledgeLinkRequestPayload` / `KnowledgeLinkReplyPayload` (called by Memory Engine, §01 §5) |
| Subscribes | `memory.long_term.created` | candidate for graph node creation/linking (placeholder -- see Known limitations) |
| Subscribes | `perception.filesystem.observed` | triggers documentation reindexing (placeholder) |
| Subscribes | `reasoning.result` | usage signal feeding `evolution.py`'s Applied/Expert/Strategic transitions (real effect, synthetic producer) |

See `events/published.py` / `events/subscribed.py` for the enforced allow-lists
(checked by `nova_eventbus_sdk.boundary.BoundEventBus` at publish/subscribe/serve
time). Unlike Memory Engine, this engine initiates no outbound RPC calls in
Phase 1 -- it only serves requests.

## Owned APIs

- `POST /v1/knowledge/nodes` -- acquire (create-or-corroborate) a node.
- `GET /v1/knowledge/search` -- semantic + graph + name-based retrieval.
- `GET /v1/knowledge/nodes/{id}`, `PATCH /v1/knowledge/nodes/{id}` (manual
  correction -- `label`/`scope`/`layer` are never editable here).
- `GET /v1/knowledge/graph?scope=project:<id>` -- subgraph query for
  visualization.
- `GET /v1/knowledge/contradictions?status=open`, `POST
  /v1/knowledge/contradictions/{id}/resolve`.
- `GET /internal/health`, `GET /internal/readiness`, `GET /internal/metrics`.

## Observability

`observability.py` defines `KnowledgeEngineMetrics`, created once per process
(API or worker) right after `configure_observability()` runs, then threaded
explicitly through request handlers, API routes, and worker functions:

| Metric | Kind | Labels |
|---|---|---|
| `knowledge_engine_acquisition_duration_seconds` | Histogram | -- |
| `knowledge_engine_retrieval_duration_seconds` | Histogram | -- |
| `knowledge_engine_nodes_acquired_total` | Counter | `outcome` (`created`/`corroborated`/`conflict`) |
| `knowledge_engine_retrieval_degraded_total` | Counter | -- |
| `knowledge_engine_contradictions_detected_total` | Counter | -- |
| `knowledge_engine_layer_advances_total` | Counter | `to_layer` |
| `knowledge_engine_embeddings_total` | Counter | -- |
| `knowledge_engine_graph_writes_applied_total` | Counter | -- |
| `knowledge_engine_outbox_dispatched_total` | Counter | `subject` |
| `knowledge_engine_graph_write_degraded_total` | Counter | -- (§17 step 4's operational signal) |

Structured logs go through `nova_observability.get_logger`; both the FastAPI
process (`main.py`) and the Arq worker process (`workers/__init__.py`) call
`configure_observability()` independently, since they are separate OS processes.

## Running locally

```bash
# from the repo root
docker compose -f infra/docker/docker-compose.local.yml up -d postgres neo4j redis nats
uv run --package knowledge-engine alembic -c services/knowledge-engine/alembic.ini upgrade head
uv run --package knowledge-engine python cypher/apply_constraints.py  # from services/knowledge-engine/
uv run --package knowledge-engine uvicorn nova_knowledge_engine.main:app --reload --port 8002

# separate process, same infra
uv run --package knowledge-engine arq nova_knowledge_engine.workers.WorkerSettings
```

Real Postgres (pgvector), Neo4j, and an embedding provider (Ollama, per ADR-010)
are required to boot `main.py`/`workers/` without dependency injection -- this
container has no Docker, so that path is not exercised here; see Testing below
for what *is* verified without it.

## Testing

```bash
uv run --package knowledge-engine pytest services/knowledge-engine/tests
```

- `tests/unit/` -- pure domain logic (`normalization`, `validation`,
  `contradiction`, `evolution`, `ranking`, `compression`, `discovery`), no I/O.
- `tests/integration/` -- boots the real FastAPI app (lifespan-driven, real
  routes, real event subscriptions) with `KnowledgeMetadataRepository`,
  `VectorIndex`, `EmbeddingProvider`, and `GraphStore` all substituted for
  in-memory fakes/backends via `create_app()`'s dependency-injection parameters
  (`tests/fakes/`, `nova-vectorstore-sdk`'s `InMemoryVectorStore`,
  `nova-embeddings-sdk`'s `InMemoryEmbeddingProvider`,
  `nova-graphstore-sdk`'s `InMemoryGraphStore`). `test_saga.py` specifically
  exercises the two-phase saga's crash-recovery property (§19's explicit
  requirement: kill between step 1 and step 2, restart, assert the pending
  graph write completes and the event publishes exactly once). Postgres/Neo4j
  -specific code (`repository/postgres_metadata_repository.py`) is the one layer
  this suite cannot reach; validating it needs the real backends via Docker
  Compose, same limitation already accepted for Memory Engine and Phase 0.

## Known limitations (Phase 1)

- **No read-through cache.** The design doc's §9 caching strategy
  (`know:cache:node:<id>`, etc.) is not implemented, mirroring Memory Engine's
  same accepted gap -- every read hits Postgres/Neo4j directly.
- **`memory.long_term.created` and `perception.filesystem.observed` handlers are
  placeholders.** `LongTermMemoryCreatedPayload` (docs/design/phase-1/
  01-memory-engine.md §13) deliberately carries only ids/scores/enums, no
  free-text content a concept name could be extracted from -- real graph-linking
  from that event needs either a richer payload or an NLP-based extraction
  pipeline (Phase 2+). Filesystem reindexing is a larger feature than one event
  handler. Both are documented contracts this engine is ready to serve, not
  silent gaps.
- **No periodic confidence decay.** §6's "confidence updates" only happen at
  acquisition time (corroboration) -- the design doc specifies no decay formula
  for knowledge confidence the way Memory Engine's §9 importance formula does
  for memory, so nothing is guessed at here.
- **Duplicate detection flags, never merges.** `domain/compression.py` +
  `workers/maintenance_worker.py` identify near-duplicate node clusters and
  record an auditable `node_version_history` entry, but never delete or fold
  data together -- Part 10's "nothing important should disappear permanently" is
  taken as a hard constraint, not a preference.
- **The `/v1/knowledge/graph` subgraph endpoint issues one `GraphStore.traverse`
  call per node** (capped at 50 nodes) rather than a single batched Cypher
  query, since `GraphQuery`'s backend-agnostic interface (ADR-007) has no
  label-agnostic "give me everything" primitive. Acceptable at visualization-call
  sizes; would need revisiting if used for something larger.
