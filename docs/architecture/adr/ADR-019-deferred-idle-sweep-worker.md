# ADR-019 — The idle-sweep worker is deliberately deferred, not shipped half-correct

**Subsystem:** World Model Engine
**Status:** Accepted — deferred by design, not an oversight

## Context

World Model Engine's object state machine (§6 of the design doc) defines an
`ACTIVE → IDLE` transition, meant to fire when an object has gone without a
related perception event for longer than `idle_timeout_minutes`. Unlike every
other transition in the state machine, this one is not triggered by an incoming
observation — it requires something to actively notice that *time has passed
without* an observation, which means a scheduled sweep over currently-`ACTIVE`
objects checking each one's staleness. The user's standing instruction for this
engine was explicit: "Do not optimize prematurely. Build the correct architecture
first. Optimization should always be evidence-driven."

## Problem

Should a scheduled worker implementing the `ACTIVE → IDLE` staleness sweep be
built now, in Phase 1, alongside the rest of the object lifecycle machinery?

## Alternatives considered

- **Build a Postgres query that finds the single latest `object_state_history`
  row per `object_id`, filtered to `ACTIVE` and older than the timeout.**
  Considered and set aside: this is a "latest row per group" query
  (`DISTINCT ON` or a window function), which is a real query but one whose
  correct, efficient form depends on actual data volume and access patterns that
  do not exist yet in Phase 1 — there is no real Perception Engine producing
  events, so there is no real traffic shape to design an efficient version
  against. Building it now means guessing at the shape of a problem that has no
  evidence behind it yet.
- **Build a Neo4j property-based staleness check** (store `last_observed_at` as
  a node property, query for `:WorldObject` nodes past the threshold).
  Considered and set aside for the same reason, plus an additional one: this
  would require querying Neo4j for a purpose ADR-018 specifically avoids for
  object-state reads (Neo4j is not guaranteed current relative to the saga, per
  ADR-014) — building this now would mean either accepting that inconsistency or
  solving a second, harder problem (a staleness check that's saga-aware) with no
  evidence yet that it's needed.
- **Build a naive, unoptimized version now anyway** (e.g., load all `ACTIVE`
  objects into memory, filter in Python), accepting it's not production-grade,
  just to have *something*. Rejected per the user's explicit instruction: this is
  exactly "build now, optimize later" in the wrong direction — it ships a known-
  wrong-shaped implementation instead of waiting for evidence to inform the
  correct one.

## Decision

`domain/state_management.next_state_on_idle_timeout` — the pure transition
function itself — is implemented and unit-tested (it correctly computes
`ACTIVE → IDLE` given a current state and elapsed time). No scheduled worker
calls it. `idle_timeout_minutes` remains a configured `Settings` field,
documented as consumed only by this untriggered function today. This is recorded
explicitly as a Known Limitation in the engine's README, not left as a silent
gap: "A correct implementation needs either a nontrivial Postgres... query or a
Neo4j property-based staleness check — deliberately deferred... rather than
shipped half-correct."

## Consequences

- Objects that go idle in reality will continue reporting as `ACTIVE` in World
  Model Engine's state until their next observation naturally supersedes it (at
  which point `next_state_on_new_observation` correctly transitions `IDLE →
  ACTIVE`, so the state machine self-corrects on the next real signal even
  without the sweep).
- The pure transition function existing and being tested means building the
  worker later is purely an infrastructure task (write the query, write the
  cron registration) — no domain logic needs to be invented at that point.
- This is the one instance in Phase 1 where a described capability (§6's full
  state diagram) is not fully wired end-to-end, and it is the direct, deliberate
  result of following the user's evidence-driven-optimization instruction rather
  than a resource or time constraint.

## Tradeoffs

- World Model's Active Context can report an object as active longer than it
  actually is, until the next real observation. Accepted because no consumer of
  World Model data in Phase 1 currently depends on precise idle detection (no
  Perception Engine, no Reasoning Engine yet exists to notice or act on the
  difference) — the cost of this gap is currently zero in practice, which is
  exactly the condition under which deferring is the correct call rather than a
  shortcut.

## Future implications

Build this worker once real Perception Engine traffic (Phase 4) provides an
actual data volume and access pattern to design the staleness query against —
at that point, choose between the Postgres window-function approach and the
Neo4j property approach based on measured query cost, not a guess made in Phase
1 with no data. Until then, this ADR is the record that the gap is known,
intentional, and bounded — not something a future engineer should assume was
simply missed.
