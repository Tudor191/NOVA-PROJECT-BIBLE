# Architecture Decision Records

This directory is the official, permanent log of significant architectural
decisions made *during implementation* — as distinct from ADR-001 through ADR-010,
which are recorded inline in
[`00-overview-and-decisions.md`](../00-overview-and-decisions.md) as the
foundational decisions made *during design*, before any code existed.

**Standing requirement (established during Phase 1, permanent going forward):**
whenever a subsystem is completed, every significant architectural decision made
while building it gets filed here as its own ADR, using the structure below. The
goal is that any major architectural decision in NOVA remains traceable years from
now, independent of whoever's memory of "why did we do it this way" would otherwise
be the only record.

## Format

Every ADR in this directory follows the same seven-section structure:

1. **Context** — the situation that made a decision necessary.
2. **Problem** — the specific question being answered, stated precisely enough that
   a reader unfamiliar with the surrounding work could evaluate the alternatives.
3. **Alternatives considered** — what else was on the table, and why each one lost.
4. **Decision** — what was actually chosen, concretely.
5. **Consequences** — what follows mechanically from the decision (new invariants,
   new coupling, new capabilities).
6. **Tradeoffs** — what was explicitly given up, phrased so a future reader can tell
   whether the conditions that made the trade acceptable still hold.
7. **Future implications** — what changes (or must be revisited) if circumstances
   change; what a future engine building on top of this should know.

## Numbering

Numbering continues the existing ADR-001 through ADR-010 sequence rather than
restarting — this is one log, split across two locations for historical reasons
(design-time decisions predate this directory's existence). New ADRs are always the
next unused number, regardless of which subsystem they originate from.

## Index

| ADR | Title | Subsystem(s) |
|---|---|---|
| [011](ADR-011-unified-memory-record-schema.md) | Unified `memory_record` schema over one table per memory type | Memory Engine |
| [012](ADR-012-redis-as-primary-store-not-cache.md) | Redis as the primary store for Working Memory and Active Context, not a cache | Memory Engine, World Model Engine |
| [013](ADR-013-async-off-path-embedding-generation.md) | Asynchronous, off-write-path embedding generation | Memory Engine, Knowledge Engine |
| [014](ADR-014-postgres-then-graph-two-phase-saga.md) | Postgres-then-graph two-phase saga via transactional outbox | Knowledge Engine, World Model Engine |
| [015](ADR-015-knowledge-maturity-lifecycle.md) | Seven-stage knowledge-maturity lifecycle over a single confidence score | Knowledge Engine |
| [016](ADR-016-contradiction-recording-not-overwriting.md) | Contradictions are recorded, never silently resolved by overwrite | Knowledge Engine |
| [017](ADR-017-world-model-boundary-separation.md) | World Model boundary: no embeddings, no forgetting lifecycle, no validated-fact graph | World Model Engine |
| [018](ADR-018-world-object-state-reads-from-postgres.md) | World Object "current state" reads come from Postgres, never Neo4j | World Model Engine |
| [019](ADR-019-deferred-idle-sweep-worker.md) | The idle-sweep worker is deliberately deferred, not shipped half-correct | World Model Engine |

See also: [Phase 1 Architecture Review Report](../../roadmap/architecture-reviews/phase-1-data-memory-substrate.md)
and [Doc 20 — Engine Responsibility Boundaries](../20-engine-responsibility-boundaries.md),
both produced alongside this ADR set on Phase 1's completion.
