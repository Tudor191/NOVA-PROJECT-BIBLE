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
| PostgreSQL | nova-core, capability-engine, autonomy-engine, planning-engine, agent-orchestrator, communication-engine | Service registry, capability registry, action ledger, policies, task graphs, agent registry, conversation sessions, permissions, audit log |
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
-- capability-engine
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

## 4. Graph storage (Neo4j)

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
physical separation.

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
