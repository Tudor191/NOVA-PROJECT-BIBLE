# ADR-012 — Redis as the primary store for Working Memory and Active Context, not a cache

**Subsystem:** Memory Engine, World Model Engine
**Status:** Accepted, implemented

## Context

Both Memory Engine (Working Memory, Bible Part 3) and World Model Engine (Active
Context and Attention, Bible Part 5/18) have a category of state that is
high-write-frequency, small in size per user, and only meaningful while
recent/current — Working Memory holds what's active in the current session;
Active Context holds the user's current activity, device, and task; Attention
holds a decaying weight per entity the user has recently engaged with. Redis was
already the approved infrastructure choice for caching elsewhere in the
architecture (SAD 07).

## Problem

Is Redis, in these two engines, a cache in front of a Postgres-backed source of
truth (read-through, with Postgres as the durable record), or is it the source of
truth itself for this category of state?

## Alternatives considered

- **Redis as a read-through cache, Postgres as source of truth.** Rejected for
  this specific state category: Working Memory and Active Context/Attention are
  inherently ephemeral and session-scoped by nature — there is no durable "true"
  value to cache *from*. Treating Redis as a cache would mean inventing a Postgres
  table whose only purpose is to be read into a cache that's actually what every
  caller wants, adding a synchronization problem (keep Postgres and Redis
  consistent) for data that was never meant to be durable in the first place.
  Real durability for anything in Working Memory that *is* worth keeping already
  happens via long-term memory promotion (Memory Engine's write path); Active
  Context's durable trail already exists via `object_state_history` (World Model
  Engine) — building a second, redundant durable copy of the ephemeral layer
  itself adds a store with no distinct purpose.
- **Postgres only, no Redis, accept higher latency for this category of read.**
  Rejected: both Working Memory reads (every retrieval fan-out) and Active Context
  reads (`world_model.context.request`, called on every Thinking Pipeline
  execution, p95 < 20ms target) are on latency-critical paths where a Postgres
  round-trip is the wrong tool for data this transient.

## Decision

Redis is the primary store — not a cache — for Memory Engine's Working Memory
(`mem:*` keys) and World Model Engine's Active Context and Attention (`world:
context:*`, `world:attention:*`, `world:attention_ts:*`, `world:presence:*`
keys). There is no Postgres table backing these keys, and no synchronization
logic between Redis and Postgres for this data. When Redis is unreachable, both
engines fail the request rather than silently falling back to a stale or empty
value — `context_degraded_total` (World Model) and the equivalent Memory Engine
signal exist specifically to make this failure visible as an operational metric,
never a silent gap.

## Consequences

- Redis becomes a hard dependency for both engines' hottest read paths, not an
  optional performance optimization — if Redis is down, Working Memory and Active
  Context are unavailable, full stop, by design (§17 in both engines' design docs:
  "fails fast, never silently returns stale/empty context").
- No cache-invalidation logic exists anywhere in either engine for this data
  category, because there is nothing to invalidate against.
- World Model Engine's Attention decay formula (ADR referenced in doc 20 §3)
  depends on this being the primary store: the formula reads `raw_weight` and
  `last_boosted_at` directly from Redis at request time, with no possibility of a
  stale cached value diverging from a "real" Postgres value, because none exists.

## Tradeoffs

- Data in these keyspaces does not survive a Redis data loss event the way it
  would if Postgres were the backing store. Acceptable because the data is
  inherently ephemeral by definition (current session state, current activity) —
  losing it means "NOVA temporarily doesn't know what you're doing right now,"
  recoverable by the next observation/event, not "NOVA lost a memory."
- No historical query is possible against this data ("what was Active Context an
  hour ago") — only the current value exists. This is intentional per doc 20 §3
  (History with standalone value is Memory-shaped, not this-store-shaped); World
  Model's `object_state_history` table is the actual historical record when one is
  needed.

## Future implications

Any future engine considering "should this state live in Redis as a cache or a
primary store" should apply the same test used here: is there an independently
meaningful durable value this data is derived from (→ cache), or is the current
value the only value that has ever mattered (→ primary store)? If a future
requirement needs both fast current-state reads *and* durable history for the same
data, the answer per doc 20 §3 is two separate stores owned by the responsibility
that actually needs each facet — not turning this primary store into a cache
retroactively.
