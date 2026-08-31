# planning-engine

The Planning Engine (Bible Part 9, per `docs/design/phase-3/05-tdd-3b-planning-engine.md`)
transforms a completed reasoning process into a `TaskGraph` -- objective
decomposition, Work Breakdown Structure, and Critical Path Analysis, per
doc06 §3's schema. Phase 3B of the roadmap.

**Status: domain foundation + decomposition orchestration.**
`domain/models.py` (`TaskNode`, `TaskGraph`, `Estimate`) and
`domain/task_graph.py` (graph invariants, critical-path computation) are
implemented and tested (PR #2). `domain/decomposition.py` now consumes
`reasoning.process.completed` and produces a validated, in-memory
`TaskGraph` via `ModelOrchestrationPort`/`ai_model.generate.request`
(ADR-020) -- see
`docs/roadmap/architecture-reviews/phase-3b-decomposition-orchestration-gate-review.md`.
No persistence and no API surface exist yet -- the resulting `TaskGraph`
is not stored or published; those remain later, separately scoped PRs.
`api/health.py` and `repository/__init__.py` are still the standard
scaffold-generated stubs.

## Owned events

**Subscribed:** `reasoning.process.completed` -- triggers decomposition
above `Settings.decomposition_confidence_threshold` (default `0.6`, an
unconfirmed-but-precedented value, see the Gate Review §6).

**Not yet wired:** `PlanningTaskGraphCreatedPayload` and
`PlanningDecomposeRequestPayload`/`Reply` land in the persistence-layer PR
that actually publishes/serves them (TDD 3B §6.2).

See `events/published.py` / `events/subscribed.py` for the enforced allow-lists.

## Known limitations

- No persistence-backed idempotency for `reasoning.process.completed` --
  a redelivered event triggers a second, independent, unpersisted
  decomposition attempt. Safe only because nothing is persisted yet
  (see the Gate Review §3, §11); becomes a hard requirement once
  persistence exists.
- No real-NATS-JetStream test coverage of the subscription -- this
  repo's `nats_event_bus` testkit fixture is not yet used by any engine
  for a subject-subscription proof; see the Gate Review §9.

## Owned APIs

- `GET /internal/health`
- `GET /internal/readiness`
- `GET /internal/metrics`

## Testing

```bash
uv run --package planning-engine pytest services/planning-engine/tests
```
