# ADR-022 — The AI Model Orchestration Engine is a stateless cognitive gateway

**Subsystem:** AI Model Orchestration Engine (Phase 2A)
**Status:** Accepted — new permanent engineering principle

## Context

Bible Part 7's independence requirement (§0 of the design doc; ADR-020) already
implies this engine holds no conversation history, no memories, no knowledge, and
no world state — those belong to Memory, Knowledge, and World Model Engine. Before
the first production connector was considered complete, the user made this
explicit and permanent: "The orchestration layer must never become stateful.
Conversation state, memory, world model and knowledge must remain external. The
orchestration layer should behave as a stateless cognitive gateway."

The design doc's §9 (Caching strategy) already introduced one piece of in-process
state — an in-memory Model Registry cache, refreshed on registry-mutation events,
justified by Part 7's millisecond routing-latency target. This ADR exists to draw
the line precisely: that cache is the *only* state this engine is allowed to hold,
and it is a fundamentally different *kind* of state than conversation/cognitive
state.

## Problem

"Stateless" is easy to assert and easy to violate by accretion — a convenience
field added to "remember the last request from this caller," a per-session object
that seems harmless in isolation. What exactly distinguishes the one piece of
in-process state this engine already has (the registry cache) from the kind of
state this new rule forbids, precisely enough that a future contributor can tell
which side of the line a proposed change falls on?

## Alternatives considered

- **No in-process state at all — read the registry from Postgres on every
  request.** Rejected: this directly contradicts Part 7's own "model selection
  should complete within milliseconds" target (design doc §9, §15) and was already
  rejected once when the caching strategy was designed; re-litigating it here would
  be inconsistent, not more careful.
- **Allow a bounded per-session cache** (e.g., remember a caller's last N requests
  to reduce redundant context re-transmission). Rejected outright per the user's
  explicit "no exceptions" framing: this is exactly the kind of state that turns a
  gateway into a session-aware service, and it duplicates a concern (conversation
  continuity) that Memory Engine and, eventually, Reasoning Engine already own —
  building a second, partial version of it here would violate the same
  independence boundary ADR-020 exists to protect.

## Decision

This engine holds exactly one category of in-process state: the Model Registry /
Capability Matrix cache (design doc §9), and that cache is **derived and
disposable** — it can be dropped and rebuilt from Postgres at any moment (process
restart, cache invalidation, a fresh replica starting up) with zero data loss and
zero effect on any in-flight *conversation*, because it holds no conversation data
at all. Every other kind of state is explicitly forbidden:

- No per-caller or per-session objects.
- No conversation/message history of any kind.
- No memoization of "what a caller asked before."
- No mutable request-scoped state that outlives a single request/response cycle
  (or a single streaming connection's lifetime, for `/generate/stream`).

The test for whether a proposed addition violates this ADR: **if this engine's
entire process were killed and restarted between two calls from the same caller in
the same conversation, would anything observable break?** For the registry cache,
no (it rebuilds transparently). For anything conversation-shaped, the answer must
also be no — if it would break, the state driving that answer doesn't belong here.

## Consequences

- This engine can be horizontally scaled (multiple instances behind a load
  balancer) with zero session-affinity requirement — any instance can serve any
  request, because no instance holds anything a specific caller depends on
  persisting. This directly serves Part 7's "the orchestration layer should
  support dozens of simultaneously available models" alongside real production
  load, without a sticky-session design that would complicate it.
- Every request is fully self-contained: the caller (Reasoning Engine, and
  eventually others) supplies everything this engine needs — context components,
  tool schemas, privacy hint — and nothing this engine does depends on having seen
  a prior request from the same caller.
- Crash recovery is trivial for this engine specifically, unlike the saga pattern
  Knowledge/World Model Engine need (ADR-014): there is no dual-write consistency
  problem here because there is no durable *session* state to lose, only the
  already-covered per-request outbox pattern (design doc §17) for the usage
  record.

## Tradeoffs

- Every request must carry its full context (already true per the Context Builder
  boundary, §0 of the design doc) rather than this engine being able to
  incrementally build on a remembered conversation — slightly more payload per
  request, in exchange for zero coupling to conversation lifecycle management,
  which is a trade this project has already made consistently (Memory Engine's
  Working Memory, not this engine, owns "what's been discussed recently").

## Future implications

Any future feature request that sounds like "remember X between calls to this
engine" is a request to violate this ADR, not a routine enhancement — it should be
redirected to whichever engine actually owns that state (Memory Engine for
conversation history, World Model Engine for current context) rather than
implemented here. This is the same category of guardrail ADR-017 (World Model
boundary) provides for Memory/Knowledge/World Model, applied to this engine's own
boundary.
