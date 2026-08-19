# 07 — Database Architecture

NOVA is intentionally **polyglot-persistent**: the Bible describes data with distinct
shapes (relational records, high-dimensional vectors, graph relationships, ephemeral
key-value state, blobs), and Part 10 explicitly warns that "the Knowledge Engine must
remain independent from the Memory Engine" — architecturally as well as at the
storage level. Using one database for everything would either force graph queries into
SQL recursion or force strict relational data into a schemaless store; neither serves
the Bible's requirements well.

## 1. Store-to-engine ownership map

| Store | Owning engine(s) | Data |
|---|---|---|
| PostgreSQL | nova-core, capability-engine, action-engine, autonomy-engine, planning-engine, agent-os-kernel, communication-engine | Service registry, capability registry, action ledger, policies, task graphs, agent registry, conversation sessions, permissions, audit log |
| PostgreSQL + pgvector | memory-engine, knowledge-engine | Long-term/semantic/episodic memory records + their embeddings; knowledge item text + embeddings |
| Neo4j | knowledge-engine, world-model-engine | Knowledge Graph (Part 10), Digital Environment Graph / World Object Graph (Part 5, 18) |
| Redis | memory-engine (working/short-term), cognitive-state-engine, ws-gateway (session/presence) | Working Memory, Active Thoughts, Attention layers, ephemeral caches, pub/sub side-channel |
| MinIO / S3 | memory-engine, knowledge-engine, nova-core (backups) | File attachments, documents, PDFs, memory/world snapshots, backup archives |
| TimescaleDB (Phase 2+) | world-model-engine | System health time series (CPU/GPU/RAM/temperature/network history) |

**Rule:** exactly one engine owns each table/collection/graph label. No engine queries
another engine's schema directly, even within the same physical Postgres instance —
cross-engine data access is always through the owning engine's API/events. Each engine
gets its own Postgres **schema** (`memory.*`, `knowledge.*`, `capability.*`, ...) inside
a shared cluster in local-first mode (cheap: one Postgres process) and its own database
instance in enterprise mode (isolation: see [19](19-scalability-strategy.md)) — same
migrations, different deployment topology.

## 2. Relational schema highlights (PostgreSQL)

```sql
-- capability-engine (illustrative sketch, pre-TDD -- superseded by the
-- detailed, phase-scoped schema in
-- docs/design/phase-3/06-tdd-3c-capability-engine.md §6, which is
-- authoritative for Phase 3C implementation; that TDD's `Capability`
-- model deliberately excludes `confidence` (no learning/scoring
-- mechanism exists in Phase 3) and uses `required_permissions: list[str]`
-- rather than a singular `permissions` column, among other differences.
-- The `UNIQUE (name, version)` constraint below is the one element this
-- sketch and the TDD agree on and is carried forward as real precedent.)
CREATE TABLE capability.capability (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    version TEXT NOT NULL,
    permissions JSONB NOT NULL,
    health_status TEXT NOT NULL DEFAULT 'unknown',
    confidence REAL,
    UNIQUE (name, version)
);

-- planning-engine
CREATE TABLE planning.task_graph (
    id UUID PRIMARY KEY,
    root_objective TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE planning.task_node (
    id UUID PRIMARY KEY,
    graph_id UUID REFERENCES planning.task_graph(id),
    objective TEXT NOT NULL,
    depends_on UUID[] NOT NULL DEFAULT '{}',
    assigned_agent_category TEXT,
    status TEXT NOT NULL,
    risk TEXT NOT NULL
);

-- autonomy-engine
CREATE TABLE autonomy.decision_log (
    id UUID PRIMARY KEY,
    action_id UUID NOT NULL,
    autonomy_level SMALLINT NOT NULL,
    risk TEXT NOT NULL,
    confidence REAL NOT NULL,
    policy_checks JSONB NOT NULL,
    outcome TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- agent-os/kernel (illustrative sketch -- superseded by the detailed,
-- phase-scoped schema in docs/design/phase-3/08-tdd-3e-agent-os.md §4/§5
-- and docs/design/phase-3/14-3e-agent-os-research.md §4, which are
-- authoritative for Phase 3E implementation once approved and built.
-- Approved 2026-08-19; not yet implemented.)
CREATE TABLE agent_os.agent_instance (
    id UUID PRIMARY KEY,
    agent_package_id UUID NOT NULL,
    category TEXT NOT NULL,
    execution_backend TEXT NOT NULL,
    status TEXT NOT NULL,
    assigned_task_node_id UUID,
    supervisor_id UUID,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    health_status TEXT NOT NULL DEFAULT 'unknown'
);
CREATE TABLE agent_os.agent_package (
    id UUID PRIMARY KEY,
    category TEXT NOT NULL,
    version TEXT NOT NULL,
    manifest_json JSONB NOT NULL,
    installed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    health_status TEXT NOT NULL DEFAULT 'unknown',
    UNIQUE (category, version)
);
```

Every table has a corresponding SQLAlchemy model in `services/<engine>/src/.../models/`
and an Alembic migration chain scoped to that engine's schema (`alembic/versions/<engine>/`),
so engines migrate independently — a hard requirement once engines run as
independently-versioned containers (ADR-001).

## 3. Vector storage (pgvector)

```sql
CREATE TABLE memory.long_term_memory (
    id UUID PRIMARY KEY,
    content TEXT NOT NULL,
    embedding VECTOR(1024) NOT NULL,
    importance_score REAL NOT NULL DEFAULT 0.5,
    memory_type TEXT NOT NULL,   -- semantic | procedural | episodic | preference | decision ...
    source TEXT,
    confidence REAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_accessed_at TIMESTAMPTZ
);
CREATE INDEX ON memory.long_term_memory USING hnsw (embedding vector_cosine_ops);
```

Abstracted behind `packages/nova-eventbus-sdk`'s sibling `VectorStore` interface
(`upsert`, `search(query_vec, filters, k)`, `delete`) so `knowledge-engine` and
`memory-engine` share one implementation, and so the [Scalability Strategy](19-scalability-strategy.md)
can swap the HNSW-in-Postgres implementation for Qdrant at enterprise scale by changing
one adapter, not the calling code.

## 4. Graph storage — the `GraphStore` interface (Neo4j default, per ADR-007)

Per the user's approval condition on Neo4j, `knowledge-engine` and `world-model-engine`
never call the Neo4j driver directly. Both depend only on `packages/nova-graphstore-sdk`'s
`GraphStore` Protocol:

```python
class GraphStore(Protocol):
    async def upsert_node(self, label: str, node_id: str, properties: dict) -> None: ...
    async def upsert_relationship(self, from_id: str, rel_type: str, to_id: str,
                                   properties: dict) -> None: ...
    async def query(self, query: GraphQuery) -> GraphResult: ...
    async def traverse(self, start_id: str, spec: TraversalSpec) -> GraphResult: ...
    async def delete_node(self, node_id: str) -> None: ...
```

`GraphQuery`/`TraversalSpec` are backend-agnostic builder types (label filters,
relationship-type filters, depth bounds, property predicates) — not raw Cypher —
specifically so the interface cannot be silently defeated by callers embedding
Neo4j-specific query strings. The default `Neo4jGraphStore` adapter translates these
builders to Cypher; an alternative adapter (Memgraph, ArangoDB, Amazon Neptune) would
translate the same builders to its own query language, with the shared contract-test
suite ([16 §4](16-testing-strategy.md#4-contract-testing)) verifying behavioral
equivalence. See [ADR-007](00-overview-and-decisions.md#adr-007--graph-persistence-abstracted-behind-an-explicit-graphstore-interface)
for the full reasoning.

### Default implementation: Neo4j

```cypher
// Knowledge Engine (Part 10)
(:Concept {id, name, domain, confidence})
(:Project {id, name, status})
(:Technology {id, name})
(:Person {id, name})
-[:USES]->, -[:DEPENDS_ON]->, -[:RELATED_TO]->, -[:IMPLEMENTS]->,
-[:CONFLICTS_WITH]->, -[:CREATED_BY]->, -[:EXPLAINS]->

// World Model Engine (Part 5 + 18)
(:Project), (:File), (:Window), (:Application), (:Agent), (:Task), (:Device)
-[:CONTAINS]->, -[:BELONGS_TO]->, -[:EXECUTES]->, -[:EDITS]->, -[:FOCUSES_ON]->
```

Two logically separate graphs (Knowledge Graph vs. World Object Graph) in **the same
Neo4j instance** but distinct label namespaces and distinct owning engines — chosen
over two separate graph databases to avoid unnecessary operational overhead at v1,
revisited in [19](19-scalability-strategy.md) if traversal volume ever requires
physical separation. Because both engines only ever speak to `GraphStore`, this
physical separation — or a full backend swap — is an infrastructure and adapter
change, not an engine code change.

## 5. Redis key-space conventions

| Prefix | Owner | TTL | Purpose |
|---|---|---|---|
| `wm:session:<id>` | memory-engine | task duration | Working Memory (Part 3) |
| `cog:thought:<id>` | cognitive-state-engine | hours | Active Thoughts (Part 6) |
| `cog:attention:<layer>` | cognitive-state-engine | rolling | Attention Layers |
| `route:cache:<hash>` | ai-model-orchestration-engine | minutes | Recent routing decisions |
| `session:<user>:<device>` | ws-gateway | session | Live connection presence |

## 6. Data lifecycle & the Bible's Memory Forgetting model

Part 3's forgetting stages (Active → Weak → Archived → Scheduled for Deletion →
Deleted) are implemented as a `lifecycle_state` column plus a scheduled Arq job
(`memory-engine`'s `consolidation_worker`) that runs during idle periods (Part 3
"Memory Consolidation," Part 2 "Continuous Background Thinking") — never a hard
delete on write. Nothing is destroyed synchronously; everything decays through the
documented stages, with each transition emitting `memory.lifecycle.transitioned` for
auditability.

## 7. Backup & migration strategy

- **Postgres:** continuous WAL archiving to object storage + nightly base backup
  (`pgBackRest`), satisfying Part 20 "Backup Coordination."
- **Neo4j:** nightly `neo4j-admin dump` to object storage.
- **Redis:** best-effort AOF persistence (Working Memory is explicitly ephemeral by
  design, per Part 3 — it is not a backup target).
- **MinIO/S3:** versioned buckets with lifecycle policies.
- All migrations run through Alembic (Postgres) / versioned Cypher migration scripts
  (Neo4j), gated in CI (see [17](17-cicd-pipeline.md)) — never applied manually against
  a running environment.
