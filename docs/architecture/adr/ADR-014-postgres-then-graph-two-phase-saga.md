# ADR-014 — Postgres-then-graph two-phase saga via transactional outbox

**Subsystem:** Knowledge Engine (originated), World Model Engine (reused verbatim)
**Status:** Accepted, implemented

## Context

Both Knowledge Engine and World Model Engine write to two independent, non-
transactional datastores for every node/object write: Postgres (metadata, the
durable record) and Neo4j (the graph, via `GraphStore`, ADR-007). Postgres and
Neo4j cannot participate in a single ACID transaction. Without a coordination
mechanism, a crash between the two writes could either lose the graph write
entirely (data silently missing from the graph) or publish an event claiming a
node/object exists before it's actually queryable in the graph (consumers
reading the graph too early). The user's explicit review comment on this exact
mechanism, praised before World Model Engine's design even began: "I especially
approve of the explicit saga implementation across Postgres and Neo4j. The
decision to avoid silent duplication or data loss is fully aligned with the NOVA
Project Bible."

## Problem

How do two independent datastores get written consistently, without distributed
transactions, such that a crash at any point never loses a write and never
publishes an event for a write that hasn't actually landed in the graph yet?

## Alternatives considered

- **Distributed transactions (two-phase commit) across Postgres and Neo4j.**
  Rejected: Neo4j does not participate in XA/2PC with Postgres in any practically
  available way; this alternative does not actually exist as a buildable option
  for this stack.
- **Write Neo4j first, then Postgres.** Rejected: a crash after the Neo4j write
  but before the Postgres write leaves a graph node with no corresponding durable
  metadata record and no way to know it needs to be reconciled — the graph would
  have unaccounted-for state.
  Postgres, deliberately, is the side that must be the ground truth. Rejected
  because reversing the order removes Postgres's role as the single source of
  intent.
- **Best-effort: write both, log an error if the second fails, no retry
  mechanism.** Rejected outright per the user's explicit standing instruction:
  this is exactly the "silent duplication or data loss" the approved design
  avoids.

## Decision

Every node/object write is a single Postgres transaction that (a) writes the
metadata row and (b) writes an `outbox_event` row carrying a `graph_write` JSONB
column describing the intended Neo4j operation(s) (`GraphWriteIntent`, a list of
`GraphWriteOp`s). This transaction is the durable record of intent — once it
commits, the write is guaranteed to eventually reach Neo4j, exactly once. A
separate step, `apply_pending_graph_writes` (run by a dedicated outbox worker on
a short fixed interval), reads pending `outbox_event` rows, applies the
`graph_write` intent to Neo4j via `GraphStore`, and marks `graph_applied_at`. Only
after that succeeds does a second step, `dispatch_ready_events`, publish the
corresponding bus event — so a consumer receiving `knowledge.node.created` or
`world_model.object.created` is guaranteed the node is already queryable in the
graph, never a promise about a write still in flight.

## Consequences

- A crash at any point is recoverable: if the process dies before the Postgres
  commit, nothing happened (safe). If it dies after the Postgres commit but before
  the Neo4j apply, the next worker pass picks up the still-pending row and
  applies it (no data loss). If it dies after the Neo4j apply but before
  dispatch, the next pass dispatches the already-applied row without reapplying
  it (no duplicate graph write, `graph_applied_at` prevents reapplication).
- An operational visibility metric exists in both engines
  (`{knowledge,world_model}_engine_graph_write_degraded_total`) that flags outbox
  rows still pending their Neo4j write past a configured threshold
  (`graph_write_degraded_threshold_minutes`) — surfacing a stuck saga as an
  operational signal rather than a silent backlog.
- World Model Engine's version extends `GraphWriteOp.kind` with a third literal,
  `"delete_node"`, absent from Knowledge Engine's original — because world objects
  can be removed from reality (a closed window), unlike knowledge nodes, which are
  never hard-deleted (ADR-016).

## Tradeoffs

- There is a window (bounded by the outbox worker's poll interval, seconds in
  both engines' configuration) during which a node/object is durably recorded in
  Postgres but not yet queryable in the graph, and during which no event has been
  published for it. Any caller reading directly from Neo4j during this window
  will not see the new node — acceptable because no caller is expected to read
  Neo4j directly instead of going through the engine's own API, which reads from
  Postgres for exactly this reason in places where that matters (see ADR-018).
- The saga adds a second process (the outbox worker) and a second table
  (`outbox_event`) that must be run and monitored per engine — real operational
  surface area, accepted as the necessary cost of the consistency guarantee the
  user explicitly required.

## Future implications

Any future engine that writes to two independent datastores for the same logical
entity should reuse this exact pattern (transactional outbox, Postgres as
durable intent, separate apply-then-dispatch worker) rather than inventing a new
consistency mechanism — it is now a proven, tested pattern in two engines, with
an identical crash-recovery test shape in both (`tests/integration/
test_saga.py`) that a third engine can copy directly.
