# ADR-017 — World Model boundary: no embeddings, no forgetting lifecycle, no validated-fact graph

**Subsystem:** World Model Engine
**Status:** Accepted, implemented — the foundational constraint the entire engine was built under

## Context

Before World Model Engine's design began, the user stated an explicit, absolute
architectural constraint, quoted here in full because it is the single most
consequential decision this ADR set records:

> "The World Model must not become another Knowledge Engine. The World Model must
> not become another Memory Engine. The World Model represents the current state
> of reality. Memory represents historical experience. Knowledge represents
> validated facts and relationships. These three responsibilities must remain
> completely separated. Whenever you are uncertain where information belongs,
> choose the architecture that preserves this separation, even if it requires
> additional complexity."

The risk this addresses is concrete: World Model Engine, like Memory and
Knowledge Engine, deals in entities with state, relationships, and a Postgres +
Neo4j persistence pattern (ADR-014). Without an explicit boundary, the natural
path of least resistance — reusing patterns that already exist in the two
sibling engines — would have pulled World Model toward re-implementing pieces of
both: semantic search over world objects (Knowledge's shape), or a
decay-and-archive lifecycle for stale objects (Memory's shape).

## Problem

Where exactly is the line between "current state of reality" (World Model),
"historical experience" (Memory), and "validated facts and relationships"
(Knowledge), stated precisely enough to decide concrete implementation questions
— does World Model get embeddings? Does it get a forgetting lifecycle? Does it
get a Knowledge-Graph-style corroboration/contradiction model for its own data?

## Alternatives considered

- **Give World Model its own vector index and embeddings**, so world objects
  could be found by semantic similarity the way memories and knowledge nodes
  can. Rejected: World Model's central question is "what is true right now,"
  answered by id/label/scope lookup — there is no described Phase 1 use case
  where "which world objects are semantically similar to this query" is a
  meaningful operation distinct from "which world objects match this label/scope
  filter." Adding embeddings here would be capability without a corresponding
  requirement — the definition of speculative implementation the user's standing
  instruction prohibits.
- **Give World Model a decay-and-archive lifecycle for objects**, mirroring
  Memory Engine's `active → dormant → archived → ...`. Rejected: an object's
  *record* in World Model does not decay in importance the way a memory does —
  it either still reflects current reality (kept) or it doesn't (replaced by a
  new observation, or removed via `delete_node` if the object left reality
  entirely). There is no intermediate "this used-to-matter-more" state for a
  *current* fact the way there is for a *past experience*.
- **Give World Model a confidence-scored, corroboration-driven fact graph**,
  mirroring Knowledge Engine's node/edge model with contradiction detection.
  Rejected: World Model's conflict resolution (confidence → policy → recency →
  unresolved) resolves *which single current value* to hold when multiple
  simultaneous observations disagree — a fundamentally different problem from
  Knowledge's "should this newly acquired fact update, corroborate, or contradict
  an existing validated belief over time." World Model conflicts resolve in
  real time and the losing observation is simply not the current value; Knowledge
  contradictions are recorded and preserved indefinitely (ADR-016). Merging these
  models would either weaken Knowledge's audit guarantee or bloat World Model
  with a persistence model it doesn't need.

## Decision

World Model Engine is built with these boundaries as hard constraints, verified
throughout implementation (see `domain/models.py`'s own module docstring, which
states this explicitly as the file's enforcement purpose):

- **No embeddings, no vector index.** `pyproject.toml` excludes
  `nova-vectorstore-sdk`/`nova-embeddings-sdk`; no `embedding` column exists
  anywhere in the `world_model` Postgres schema; no async embedding worker
  exists.
- **No forgetting lifecycle.** The object state machine (`UNKNOWN → ACTIVE →
  {IDLE, EXECUTING, LEARNING}`, etc.) transitions based on new observations, not
  time-based decay toward deletion. `object_state_history` grows as an append-only
  audit trail of state changes, but nothing in World Model treats that history as
  a retrievable narrative for its own sake — that remains Memory's role if a
  future capability needs it.
- **No validated-fact graph.** `:WorldProject` is a distinct Neo4j label from
  Knowledge's `:Project`, sharing only a UUID convention, never a graph
  traversal — enforced by never writing code in either engine that crosses the
  label boundary. World Model's conflict resolution never produces a
  "contradiction record" the way Knowledge does; it always produces a current
  value (falling back to most-recent, labeled `unresolved`, if nothing else
  resolves it), because World Model's job is to always represent *something* as
  current reality, never to hold an open unresolved question the way Knowledge
  can.

## Consequences

- Every domain module in `services/world-model-engine/src/nova_world_model_engine/
  domain/` can be reasoned about without cross-referencing Memory or Knowledge
  Engine's implementations — the boundary is enforced by omission (the ports and
  dependencies that don't exist), not by a runtime check.
- The import-linter's engine-independence contract (ADR-004) provides a
  mechanical backstop, but the actual boundary decisions above are architectural,
  not just import-hygiene — a future contributor could technically add
  `nova-vectorstore-sdk` as a dependency without breaking any lint rule, and this
  ADR is the record of why that would be wrong regardless.
- Doc 20 (Engine Responsibility Boundaries) formalizes the general version of
  this reasoning as a decision procedure for every future engine, not just World
  Model.

## Tradeoffs

- World Model cannot answer "which objects are conceptually similar to this
  one" — only exact id/label/scope queries. Accepted because no Phase 1
  requirement needs semantic object search, and adding it later (if a real
  requirement emerges) is an additive change to `domain/ports.py`, not a
  redesign.
- World Model's historical audit trail (`object_state_history`) is intentionally
  not exposed as a rich, queryable narrative the way Memory's timeline is —
  `GET /v1/world/objects/{id}/history` returns the raw transition log, with no
  summarization or importance-weighting. If a future capability needs "tell me
  the story of what this object has been doing," that capability should query
  Memory Engine (once World Model's observations are promoted into memories via
  the existing event-driven pattern), not expect World Model itself to grow a
  narrative layer.

## Future implications

Any future change proposal that would add embeddings, a decay lifecycle, or a
corroboration/contradiction model to World Model Engine should be treated as a
proposal to violate this ADR, not a routine feature addition — it requires either
demonstrating the underlying problem doesn't actually belong to Memory or
Knowledge Engine instead (per doc 20 §6's decision procedure), or an explicit,
recorded decision to revise this boundary, not a quiet accretion of one sibling
engine's shape into World Model over time.
