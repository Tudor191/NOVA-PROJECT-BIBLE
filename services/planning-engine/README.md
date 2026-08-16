# planning-engine

The Planning Engine (Bible Part 9, per `docs/design/phase-3/05-tdd-3b-planning-engine.md`)
transforms a completed reasoning process into a `TaskGraph` -- objective
decomposition, Work Breakdown Structure, and Critical Path Analysis, per
doc06 §3's schema. Phase 3B of the roadmap.

**Status: domain foundation only.** `domain/models.py` (`TaskNode`,
`TaskGraph`, `Estimate`) and `domain/task_graph.py` (graph invariants,
critical-path computation) are implemented and tested. No event
subscription, no persistence, no API surface, and no decomposition logic
exist yet -- those are later, separately scoped PRs (see
`docs/roadmap/architecture-reviews/phase-3b-domain-foundation-gate-review.md`).
`api/health.py`, `events/subscribed.py`/`published.py`, and
`repository/__init__.py` are the standard scaffold-generated stubs, inert
until those PRs fill them in.

## Owned events

Not yet wired -- `PlanningTaskGraphCreatedPayload` and
`PlanningDecomposeRequestPayload`/`Reply` land in the event-consumption PR
that actually publishes/serves them (TDD 3B §6).

See `events/published.py` / `events/subscribed.py` for the enforced allow-lists.

## Owned APIs

- `GET /internal/health`
- `GET /internal/readiness`
- `GET /internal/metrics`

## Testing

```bash
uv run --package planning-engine pytest services/planning-engine/tests
```
