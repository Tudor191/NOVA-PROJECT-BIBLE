# ADR-018 — World Object "current state" reads come from Postgres, never Neo4j

**Subsystem:** World Model Engine
**Status:** Accepted, implemented

## Context

`GET /v1/world/objects/{object_id}` needs to answer "what is this object's
current state." World Model Engine persists object state in two places per
ADR-014's saga: Postgres's `object_state_history` (the durable, always-current
record, per that ADR) and Neo4j (the graph representation, applied
asynchronously by the saga's second phase). `GraphStore` (ADR-007) exposes
`query()` and `traverse()` as its read primitives.

## Problem

Which datastore should back a single-object "give me its current state" read?

## Alternatives considered

- **`GraphStore.query()`, filtering by the object's id.** Rejected on inspection:
  `GraphQuery` (the backend-agnostic query type ADR-007 defines) requires an
  upfront `label` — but the caller of `GET /v1/world/objects/{id}` has only an
  id, not the Neo4j label that id was stored under. Requiring the caller to know
  the label defeats the purpose of a single object-id lookup endpoint.
- **`GraphStore.traverse()`, starting from the object's own id.** Rejected on
  inspection: `traverse()`'s contract explicitly excludes the start node itself
  from its results (it returns what the start node connects *to*, not the start
  node's own properties) — structurally the wrong primitive for "give me this
  node's own current state."
- **Add a new `GraphStore` primitive** (e.g., `get_node(id) -> Node`) just for
  this lookup. Rejected: this would be a `GraphStore` interface change made for
  one caller's convenience, when a correct, already-available answer exists
  without touching the shared interface at all (see Decision) — exactly the kind
  of unnecessary complexity the user's standing anti-speculative-implementation
  instruction argues against.

## Decision

`GET /v1/world/objects/{object_id}` reads the latest row from Postgres's
`object_state_history` for that object_id — never Neo4j. Per ADR-014, this table
is the durable record of every state transition, always consistent and always
current, independent of whether that transition's corresponding Neo4j write has
been applied yet by the saga's second phase. `domain/temporal.py`'s
`object_history()` function is the read-side composition point.

## Consequences

- This endpoint has zero read dependency on the saga's completion state — a
  caller gets the correct current state even if the corresponding Neo4j apply is
  still pending (which, per ADR-014, is always eventually consistent but not
  always immediately so).
- `GET /v1/world/graph?scope=...` (the subgraph/visualization endpoint) remains
  the only World Model read path that touches Neo4j directly — a deliberate,
  narrow exception, because subgraph traversal genuinely needs graph-native
  relationship-following that Postgres cannot provide, unlike a single-object
  state lookup.

## Tradeoffs

- Object relationship data (what this object connects to) is not available from
  this endpoint — only its own state. A caller needing relationships must use
  `/v1/world/graph`. Accepted because conflating "what is this object's state"
  with "what does this object connect to" into one endpoint would blur two
  genuinely different queries with different backing stores and different
  consistency guarantees.

## Future implications

If a future `GraphStore` interface revision adds a label-agnostic single-node
lookup primitive (useful beyond just this case), this endpoint could switch to
using Neo4j as an additional cross-check or for relationship-inclusive reads —
but the Postgres-first behavior for pure state lookups should remain the
default, since it correctly reflects state before the saga's graph write lands,
which a Neo4j-first read never could.
