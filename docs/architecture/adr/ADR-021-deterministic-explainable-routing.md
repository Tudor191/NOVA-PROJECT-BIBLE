# ADR-021 — Deterministic, explainable model routing with mandatory structured telemetry

**Subsystem:** AI Model Orchestration Engine (Phase 2A)
**Status:** Accepted — new permanent engineering principle

## Context

Bible Part 7's Orchestration Principle already implies a routing decision must be
justifiable ("Select Best Model" is a step, not a black box), but says nothing
about *how* that justification is captured or whether the same inputs must always
produce the same output. Before any production connector was considered complete,
the user established two related, permanent rules: routing must be deterministic
and explainable wherever possible, with every decision exposing why a particular
model was chosen; and every inference request must produce structured telemetry
covering provider, model, routing reason, estimated complexity, latency, token
usage, estimated cost, retry count, fallback usage, and privacy classification.

## Problem

How does "explainable routing" avoid becoming a vague aspiration (a free-text log
line nobody can query) or a false promise (an explanation that doesn't actually
reflect what the algorithm did)? And how does non-determinism — the same request
routed differently on two separate calls with no registry change in between — get
prevented by construction rather than by discipline alone?

## Alternatives considered

- **A free-text explanation string, generated after the fact** (e.g., an LLM
  summarizing why a model was picked). Rejected: this would mean explaining a
  model-routing decision by calling *another* model, adding latency, cost, and a
  second point of failure to every request, and — worse — the "explanation" could
  drift from what the routing algorithm actually did, becoming a plausible-sounding
  fiction rather than a true record. Explainability must describe the real decision
  path, not narrate around it.
- **Random tie-breaking when two candidate models score equally.** Rejected:
  even a small amount of randomness in tie-breaking makes routing non-reproducible
  for the exact inputs where it matters most (near-equal candidates), and gains
  nothing — a deterministic tiebreak (§ Decision) is just as fast and costs nothing.
- **Log telemetry only on failure/fallback, to reduce write volume.** Rejected: the
  user's instruction is explicit — *every* inference request, not just the
  exceptional ones — and Part 7's "Model Learning" (routing improves over time)
  needs the full success-case record too, not just failures, to compute accurate
  historical success rates.

## Decision

`domain/router.py`'s scoring function is a pure function of `(request,
registry_snapshot)` — no hidden mutable state, no randomness, no wall-clock- or
process-order-dependent behavior. Given the same request and the same registry
snapshot, it always returns the same ranked candidate list and the same selection.
Ties in the composite score are broken by a fixed, documented rule (model `id`,
ascending) — arbitrary but *stable*, which is what determinism actually requires,
not "no ties exist."

Every routing decision produces a structured `RoutingDecision` domain object (not a
string) capturing: candidates considered, each candidate's component scores
(capability, cost, latency, historical success), the selected model, and — if this
was a fallback — which model it fell back from and why. A human-readable
`explanation` field is *derived from* these structured fields (a template, not a
generative summary), so the explanation can never claim something the structured
data doesn't support.

Every request, success or failure, produces a `RequestTelemetry` record with
exactly the fields the user specified — selected provider, selected model, routing
reason (the `RoutingDecision` above), estimated complexity, latency, token usage,
estimated cost, retry count, fallback usage, privacy classification — persisted to
`usage_record` (§4 of the design doc, expanded to carry every one of these
columns) and published on `ai_model.request.completed`/`.failed`.

## Consequences

- A routing decision is unit-testable by construction: given a fixed registry
  fixture and a fixed request, the test asserts the exact `RoutingDecision`
  returned — not just "some model was picked."
- `GET /v1/usage` and `GET /v1/models/select` (already planned, design doc §14)
  become genuinely useful debugging tools, since the data they expose *is* the
  actual decision record, not a reconstruction after the fact.
- Part 7's "Model Learning" (routing improves over time) now has a real, complete
  dataset to learn from — every request, not a sample.

## Tradeoffs

- Persisting full structured routing detail on every request (not just failures)
  is more write volume than a minimal success-path log. Accepted because Part 7's
  own learning requirement needs it, and the write is a single row in an
  already-indexed table (§8 of the design doc), not a meaningful cost at Part 7's
  stated scale (dozens of models, not millions of requests/second).
- Deterministic routing means this engine will never do exploration (e.g.,
  occasionally trying a lower-scored model to gather more data about it, a common
  bandit-algorithm technique). Accepted for Phase 2A: Part 7 describes routing
  that improves from *observed* outcomes, not active experimentation, and adding
  exploration would directly contradict "deterministic whenever possible" — if a
  future phase wants exploration, it needs its own explicit, separately-approved
  decision, not a quiet addition here.

## Future implications

Any future change to the scoring formula must preserve purity (function of request
+ registry snapshot only) and the stable tiebreak rule, or this ADR is violated.
Any future engine that makes a selection decision with real consequences (e.g., a
future Capability Engine choosing which agent handles a task) should consider the
same pattern — structured, derived-not-generated explanation plus mandatory
telemetry — as the template for "explainable" in this codebase, not a
per-subsystem reinvention.
