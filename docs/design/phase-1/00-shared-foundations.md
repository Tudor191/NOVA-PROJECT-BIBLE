# Phase 1 Technical Design — 00: Shared Foundations

Status: **Draft — pending approval. No implementation code will be written until this
design package (00–04) is approved**, per explicit instruction.

This document set is the detailed technical design for Phase 1 of the
[Engineering Roadmap](../../roadmap/ENGINEERING_ROADMAP.md): the **Memory Engine**,
**Knowledge Engine**, and **World Model Engine**. It sits one level below the
[Software Architecture Document](../../architecture/00-overview-and-decisions.md) —
the SAD establishes system-wide structure and ADRs; this package works out the
concrete internal design of three specific engines against that structure, at the
depth needed to implement them correctly the first time.

## Why these three engines get this level of design

The user's framing is architecturally correct and worth stating explicitly: Memory,
Knowledge, and World Model are the only Phase 1 engines, but they are not "just
storage." Per the Bible, nearly every other engine reads from or writes into them:

- Reasoning Engine cannot run its pipeline without Memory/Knowledge/World Model
  retrieval as non-skippable stages ([SAD 06 §2](../../architecture/06-ai-layer-architecture.md#2-reasoning-engine)).
- Planning, Autonomy, Digital Twin, Communication, and every Agent all consume World
  Model context and Memory/Knowledge retrieval (Bible Parts 3, 5/18, 10 — "every
  engine retrieves information from it").
- Getting the schema, the retrieval contract, or the event shape wrong here means
  redesigning it under every consumer built on top later. A mistake in Phase 3's
  `coding-agent` is local; a mistake in Phase 1's memory schema is systemic.

This justifies the depth requested, and justifies treating this as a proper design
review before code, rather than the lighter "storage and retrieval" pass the original
Roadmap Phase 1 entry sketched.

## New Architecture Decisions this design introduces

Two gaps in the existing SAD need to be closed before these three engines can be
designed concretely. Both are captured as ADRs in
[docs/architecture/00-overview-and-decisions.md](../../architecture/00-overview-and-decisions.md)
(added alongside this design):

### ADR-009 — Embedding generation abstracted behind an explicit `EmbeddingProvider` interface

**Context.** Both Memory and Knowledge Engines need vector embeddings for semantic
search *now*, in Phase 1. The AI Model Orchestration Engine that will eventually route
all model calls (including embeddings) is a Phase 2 deliverable
([Roadmap](../../roadmap/ENGINEERING_ROADMAP.md#phase-2--ai-core-model-orchestration--reasoning)).
Phase 1 cannot depend on a Phase 2 engine.

**Decision.** A new shared package, `packages/nova-embeddings-sdk`, defines an
`EmbeddingProvider` Protocol (`embed(text: str) -> Embedding`, `embed_batch(texts: list[str]) -> list[Embedding]`)
with a default `OllamaEmbeddingProvider` implementation — the same
interface-first-then-default-implementation pattern as ADR-006/007. Memory and
Knowledge Engines depend only on the Protocol. When the AI Model Orchestration Engine
exists (Phase 2), it becomes a second `EmbeddingProvider` implementation (routing
through the Model Gateway for provider selection, cost tracking, and privacy
classification per [SAD 06 §1](../../architecture/06-ai-layer-architecture.md#1-model-gateway-ai-model-orchestration-engine)),
swapped in via configuration — not a redesign of either engine.

### ADR-010 — One embedding model, standardized system-wide, for Phase 1

**Context.** Memory Engine, Knowledge Engine, and (transitively) World Model Engine
each need embeddings. Running different models per engine would mean operating
multiple local models, and would forfeit the option of ever comparing embeddings
across engines (e.g., "does this memory relate to this knowledge node" via direct
vector comparison, not just a graph edge).

**Decision.** Phase 1 standardizes on a single embedding model,
**`nomic-embed-text` (768 dimensions)** served locally via Ollama — chosen for strong
open benchmark performance at its size, Ollama-native support (zero-budget default,
Bible Part 7), and a practical dimension count (768 keeps HNSW index memory/build
time reasonable at the row counts Phase 1 targets, vs. 1536+ dimension models). Every
`VECTOR(...)` column in this design is `VECTOR(768)`. The `embedding_model` column
present on every embedded table exists specifically so this choice is changeable
later without a migration disaster: a model change is a background re-embedding job
(designed in [01 §10](01-memory-engine.md#10-embedding-strategy)), not a schema change.

## New shared packages this design requires

Per ADR-001 (modular monolith, replaceable modules) and the existing pattern for
`nova-eventbus-sdk`, two more interface-first shared packages are needed before the
three engines can be built, plus the one from ADR-009:

| Package | Interface | Default implementation | Consumers |
|---|---|---|---|
| `nova-vectorstore-sdk` | `VectorStore` (`upsert`, `search`, `delete`) | pgvector (HNSW) | memory-engine, knowledge-engine |
| `nova-graphstore-sdk` | `GraphStore` (ADR-007, already specified) | Neo4j | knowledge-engine, world-model-engine |
| `nova-embeddings-sdk` | `EmbeddingProvider` (ADR-009) | Ollama (`nomic-embed-text`) | memory-engine, knowledge-engine |

These are built first, in that order, before any of the three engines — mirroring
Phase 0's own implementation order (contracts → SDKs → the service that uses them).

## Conventions shared by all three engines

Stated once here; each engine's design document (01/02/03) references this section
instead of repeating it.

### Identity, tenancy, and time

- Every persisted entity has a `UUID` (or, for graph nodes, a `TEXT` id matching the
  same UUID string — Neo4j has no native UUID type) primary key.
- Every row/node carries `user_id`, and (from Phase 7 forward) `tenant_id`; Phase 1
  implements the column and the query-scoping discipline now, even though full
  multi-tenant enforcement (Postgres RLS policies, tenant isolation tests) is a
  Phase 7 deliverable per [SAD 19 §3](../../architecture/19-scalability-strategy.md#3-multi-tenancy-model-enterprise) —
  this avoids a schema migration later to retrofit tenancy.
- All timestamps are `TIMESTAMPTZ`, UTC, matching `EventEnvelope.occurred_at`.

### Confidence and privacy, everywhere

Every entity in all three engines carries two fields, because the Bible requires both
pervasively (Parts 3, 7, 8, 10, 18) and retrofitting them is exactly the kind of
mistake this design pass exists to prevent:

```python
confidence: float          # 0.0-1.0, per Part 8's Confidence System
privacy_level: PrivacyLevel  # public | internal | confidential | highly_sensitive (Part 7)
```

`privacy_level` is enforced at retrieval: a query whose result will be handed to a
cloud-routed reasoning call (Phase 2+) must filter out anything above the caller's
declared privacy ceiling. Phase 1 stores and propagates the field; the enforcement
point (Model Orchestration Engine's privacy classifier) is built in Phase 2 — this is
the same "mechanism now, policy enforcement point later" split used for Autonomy
Engine's permission model in the SAD.

### Versioning (detailed per-engine, principle stated once)

Three independent versioning concerns, present in every engine:

1. **Row/node version** — an integer `version` column, incremented on every mutating
   write, used for optimistic concurrency (`WHERE version = :expected`) so a
   consolidation-worker write and a user edit can never silently clobber each other.
2. **Schema version** — Alembic migration chains (Postgres) and versioned Cypher
   migration scripts (Neo4j), one chain per engine schema, exactly as
   [SAD 07 §7](../../architecture/07-database-architecture.md#7-backup--migration-strategy)
   already specifies.
3. **Content version history** — an explicit history table/log (not just
   "the old value is gone"), because the Bible explicitly requires this for knowledge
   (Part 10 "Knowledge Versioning": "nothing important should disappear permanently")
   and decisions (Part 3 "Decision Memory"). Each engine's design specifies its own
   history table below.

### The transactional outbox pattern (write-then-publish correctness)

Every engine in this design writes to a database **and** publishes an Event Bus
message as a consequence of most writes. Without care, a process crash between the
two leaves the database committed but the event never published — silent, permanent
inconsistency between what an engine knows and what it told the rest of NOVA.

**Decision, applied uniformly across all three engines:** every mutating write that
must also publish an event does so via a **transactional outbox**: the event row is
inserted in the *same database transaction* as the entity write, and a background
dispatcher polls undispatched outbox rows, publishes them via `nova-eventbus-sdk`,
and marks them dispatched. This is a standard, well-understood pattern for exactly
this dual-write problem, applied here rather than the informal "retried" language the
SAD used for this concern at the whole-system level — Phase 1 is where it needs to be
concrete.

```sql
-- Present, with this exact shape, in memory / knowledge / world_model schemas.
CREATE TABLE <schema>.outbox_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject TEXT NOT NULL,
    payload JSONB NOT NULL,
    correlation_id UUID NOT NULL,
    causation_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    dispatched_at TIMESTAMPTZ
);
CREATE INDEX outbox_undispatched_idx ON <schema>.outbox_event (created_at)
    WHERE dispatched_at IS NULL;
```

For Knowledge Engine and World Model Engine specifically, whose writes span
**two** datastores (Postgres metadata + Neo4j graph, which cannot share a
transaction), the outbox additionally becomes the mechanism that makes the
cross-database write a saga rather than a hope: the Postgres write (with its outbox
row) is the durable record of *intent*; the Neo4j write is applied by the same
dispatcher that publishes the event, and a failed Neo4j write is retried from the
outbox row rather than lost. This is detailed per-engine in
[02 §17](02-knowledge-engine.md#17-failure-recovery) and
[03 §17](03-world-model-engine.md#17-failure-recovery).

### Caching (principle stated once, keys specified per engine)

All three engines use Redis for the same two purposes, never conflating them:

1. **Primary storage for genuinely ephemeral state** (Working Memory, World Model's
   Active Context) — not a cache of something else, the actual store, matching Part 3
   ("Working Memory... old information should leave automatically").
2. **A cache in front of Postgres/Neo4j** for hot reads — always invalidated
   event-driven (the writing engine instance publishes, every instance — including
   itself — invalidates the affected cache key on receipt), never time-only TTL for
   correctness-sensitive data. A short TTL is used only as a safety net against a
   missed invalidation, not as the primary invalidation mechanism.

### Testing conventions (detailed per-engine in §19 of each document)

Every engine's test suite follows the pyramid from
[SAD 16](../../architecture/16-testing-strategy.md): unit (domain logic, no I/O) →
integration (real Postgres/Neo4j/Redis via `nova-testkit` + testcontainers) →
contract (published events validated against `nova-contracts`) → performance
(benchmarked against the explicit targets stated in each engine's §15) → failure
scenario (each engine's §17 failure modes get a corresponding test, not just a
paragraph of intent).

## How to read documents 01–04

| Doc | Covers |
|---|---|
| [01 — Memory Engine](01-memory-engine.md) | Full design, all 20 requested sections |
| [02 — Knowledge Engine](02-knowledge-engine.md) | Full design, all 20 requested sections |
| [03 — World Model Engine](03-world-model-engine.md) | Full design, all 20 requested sections |
| [04 — Cross-Engine Integration](04-cross-engine-integration.md) | Sequence diagrams for how the three interact with each other and with the rest of NOVA during Phase 1 |

Each of 01–03 is organized under exactly the 20 headings requested, in order, so
review can proceed section-by-section against the request.
