# ADR-016 — Contradictions are recorded, never silently resolved by overwrite

**Subsystem:** Knowledge Engine
**Status:** Accepted, implemented

## Context

Bible Part 10 states that nothing important should disappear permanently from
NOVA's knowledge, and that NOVA should be able to reason about *why* it believes
something, including cases where it has learned conflicting things over time. A
naive acquisition pipeline (new fact comes in, overwrite the old value) would
lose exactly this: the old belief, the fact that a conflict occurred, and any
future ability to explain "NOVA used to think X, here's why it changed."

## Problem

When newly acquired knowledge conflicts with an existing node, what happens to
the existing value?

## Alternatives considered

- **Last-write-wins: overwrite the existing node's value with the new one.**
  Rejected outright: this is silent data loss of exactly the kind Part 10
  prohibits, and the kind the user separately praised Knowledge Engine's saga
  design for avoiding in the adjacent (storage-consistency) dimension — the same
  principle applied here to the semantic dimension.
  averaging isn't meaningful for most knowledge (there is no sensible "average"
  of two conflicting facts about, say, a person's job title), and it produces a
  value neither original source actually asserted.
- **Confidence-weighted merge (keep whichever value has higher confidence,
  silently).** Rejected: this is overwrite with extra steps — it still discards
  the losing value and the fact that a conflict occurred, just with a confidence
  comparison deciding the winner instead of recency.

## Decision

`domain/contradiction.py`'s structural conflict check runs on every acquisition.
When a new fact conflicts with an existing node, `domain/acquisition.py` does
not silently pick a winner: it records a `contradiction_log` entry (both values,
both sources, detected timestamp) and publishes
`knowledge.contradiction.detected`, leaving the contradiction in an open state
for explicit resolution (`POST /v1/knowledge/contradictions/{id}/resolve`) rather
than an automatic one. The existing node's value is not overwritten as a side
effect of detection.

## Consequences

- Every contradiction NOVA has ever encountered remains queryable
  (`GET /v1/knowledge/contradictions?status=open`), giving a future Reasoning
  Engine or a human reviewer the ability to see not just what NOVA currently
  believes but what it used to believe and where the two diverged.
- `knowledge_engine_contradictions_detected_total` gives direct operational
  visibility into how often NOVA's acquired knowledge actually conflicts, which
  a silent-overwrite design would make invisible.
- Resolution is a distinct, explicit act (`resolve` endpoint) — not an automatic
  consequence of any particular confidence threshold being crossed.

## Tradeoffs

- Nodes with open contradictions carry ambiguity until explicitly resolved —
  callers reading a contradicted node get whatever value is currently stored,
  which may not reflect the most-corroborated one, until resolution happens.
  Accepted because the alternative (silent auto-resolution) trades away
  exactly the auditability Part 10 requires.
- No automatic resolution policy exists yet (e.g., "auto-resolve if one side has
  3x the corroboration of the other after N days") — contradictions can
  accumulate unresolved indefinitely in Phase 1. Acceptable because no
  auto-resolution policy is specified in the design doc, and inventing one would
  be exactly the "speculative behavior" the user's standing instruction rules
  out; a real policy needs a real specification first.

## Future implications

If a future phase adds automatic contradiction resolution, it must still write a
`contradiction_log` entry recording that resolution happened and how — the
invariant this ADR protects is "nothing about a conflict disappears," not "every
conflict requires a human," so automation is compatible with this decision as
long as the audit trail survives.
