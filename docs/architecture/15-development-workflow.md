# 15 — Development Workflow

## 1. Branching model

**Trunk-based development** with short-lived feature branches:

- `main` is always releasable (Part 1: "the codebase must remain production ready at
  all times" — taken literally: `main` never sits in a broken state).
- Feature branches: `feature/<engine-or-area>-<short-description>` (e.g.
  `feature/memory-engine-consolidation-worker`).
- No long-lived `develop` branch — feature flags ([14 §5](14-deployment-architecture.md#5-release-strategy))
  handle incomplete work that must merge before it's user-visible.
- Direct pushes to `main` are blocked; every change lands via PR with required reviews
  and required CI checks (branch protection).

## 2. Local developer environment

```bash
git clone <repo>
turbo run bootstrap        # installs uv/pnpm/cargo deps across the whole monorepo
docker compose -f infra/docker/docker-compose.local.yml up -d   # Postgres, Neo4j, Redis, MinIO, Ollama
turbo run dev               # starts nova-host in embedded mode + web-client dev server, hot-reloading
```

A single command boots the entire system locally — no engineer should need
tribal knowledge to run NOVA end-to-end, directly supporting the Bible's demand that
"thousands of developers" be able to contribute (Part 1).

## 3. Code ownership & review

- `CODEOWNERS` maps each `services/<engine>/`, `agents/<name>/`, `apps/*`, `companion/`
  directory to the team/individuals responsible — every PR touching an engine requires
  that engine's owner's approval, enforcing Part 1's "every class must have a clear
  responsibility" at the review-process level, not just in code.
- Cross-cutting changes (to `packages/nova-contracts`, `packages/nova-eventbus-sdk`,
  or `tools/`) require an additional review from a "platform" owner group, since these
  changes ripple across every engine.

## 4. Definition of Done (per PR)

A PR may merge only when:

1. It touches exactly one engine's `src/` (or `packages/`/`tools/` with platform
   review) — enforced by the import-boundary + change-scope linter.
2. Unit + integration tests pass (see [16](16-testing-strategy.md)).
3. If it adds/changes an event, `nova-contracts` was updated in the same PR and
   consumer engines' contract tests still pass.
4. If it changes an engine's public API, the OpenAPI diff is reviewed for backward
   compatibility ([11 §6](11-api-architecture.md#6-backward-compatibility--deprecation-policy)).
5. New code includes tests demonstrating the behavior described in the relevant Bible
   Part — PR descriptions are required to cite the Bible section(s) implemented, so
   architectural drift from the source specification is visible at review time.

## 5. Engine scaffolding

`tools/scaffold-engine.py <name>` generates a new `services/<name>/` from the template
in [02 §3](02-repository-and-folder-structure.md#3-anatomy-of-one-engine-the-repeatable-unit),
pre-wired with: FastAPI skeleton, Dockerfile, `nova-eventbus-sdk` connection,
OpenTelemetry instrumentation, health/readiness endpoints, and a passing empty test
suite — so adding an engine is a scaffolding command plus domain logic, never
boilerplate reinvention. This directly operationalizes Part 15's Capability Engine
principle ("NOVA should never be redesigned to learn a new skill") at the engine level
too: adding cognitive capacity to NOVA should be additive, not a core rewrite.

## 6. Commit & PR conventions

- Conventional Commits (`feat(memory-engine): ...`, `fix(event-bus): ...`) — the
  `<scope>` is always the directory under `services/`, `agents/`, `apps/`, or
  `packages/` being changed, making the git history itself queryable by engine.
- Squash-merge to `main`, so `main`'s history is one entry per completed unit of work,
  matching the Task Graph granularity used elsewhere in the system.

## 7. Documentation-as-code

Every engine's `README.md` ([02 §3](02-repository-and-folder-structure.md)) is required
to stay current as part of Definition of Done — "responsibility, owned events, owned
APIs" — and is linted in CI for staleness (a script flags READMEs whose event lists
don't match `events/published.py`/`subscribed.py`).

## 8. Design review process for new engines/major changes

For anything at the scale of a new engine or a change to an ADR in
[00](00-overview-and-decisions.md), a short design doc (problem, options considered,
decision, Bible traceability) is required before implementation starts, reviewed
async via PR against `docs/architecture/proposals/` — keeping the SAD a living document
rather than a one-time artifact, per Part 1's expectation that the architecture "evolve
continuously for many years" without requiring fundamental redesigns.

## 9. Per-Subsystem Deliverable Checklist

Per explicit user directive starting with Phase 1: **documentation, tests, and
observability are part of the implementation, not something added afterward.** No
subsystem (engine, shared package, or `agent-os` component) is considered
implemented — and no PR delivering one may be treated as done for Definition of Done
purposes ([§4](#4-definition-of-done-per-pr)) — until all ten items below exist for it,
in the same PR or PR series that introduces the subsystem:

1. **Architecture documentation** — the subsystem's design doc (e.g.
   `docs/design/phase-N/NN-<engine>.md`), covering at minimum its internal component
   breakdown, responsibilities, and how it satisfies its Bible Part(s). For subsystems
   built after Phase 1, this lives alongside that phase's design package; the doc must
   exist *before* implementation per the phase's own approval gate, and is amended if
   implementation diverges from the design.
2. **Sequence diagrams** — Mermaid `sequenceDiagram` blocks in the design doc for
   every non-trivial multi-step flow (write paths, retrieval pipelines, cross-engine
   calls, failure/recovery paths) — not just the happy path.
3. **Component diagrams** — a component tree or Mermaid `graph`/`classDiagram` showing
   the subsystem's internal module breakdown and its dependencies on shared packages,
   matching what's actually in `src/`.
4. **API documentation** — every exposed REST endpoint, event (published and
   subscribed), and request/reply contract, generated or hand-written, kept current
   per [§7](#7-documentation-as-code)'s README staleness check and
   [11 §5](11-api-architecture.md#5-openapi-as-the-source-of-truth).
5. **Unit tests** — domain logic tested with no I/O, per the base of the testing
   pyramid in [16](16-testing-strategy.md).
6. **Integration tests** — real dependencies (Postgres/Neo4j/Redis/NATS) via
   `nova-testkit` + testcontainers, per [16](16-testing-strategy.md).
7. **Performance benchmarks** — automated tests asserting the subsystem's design doc
   performance targets (its own "Performance considerations" section) are met, not
   just prose claims; these run in CI or are tracked as a scheduled job if too slow
   for per-PR execution.
8. **Failure scenarios** — each failure mode named in the subsystem's design doc
   ("Failure recovery" section) has a corresponding test that induces it (process
   crash mid-write, dependency unavailable, timeout) and asserts the documented
   recovery behavior, not just that the happy path works.
9. **Logging strategy** — structured JSON logs via `nova-observability`
   ([01 §Observability & Structured Logging](01-technology-stack.md)) at the
   subsystem's key decision points (state transitions, retries, degraded-mode
   fallbacks), with enough context (correlation id, entity id) to reconstruct a
   request's path without attaching a debugger.
10. **Observability metrics** — Prometheus metrics (via `nova-observability`, pull
    model per the Phase 0 metrics design) for the subsystem's key rates and latencies
    (write/read latency, cache hit rate, queue depth, failure rate), plus traces
    (OTLP push) for its non-trivial request paths — enough to build the dashboard a
    future on-call engineer would actually need.

This checklist is what "documentation is part of the implementation" means
concretely, and it is what the Sign-off section of every
[Architecture Review Report](../roadmap/architecture-reviews/TEMPLATE.md) checks
against for every subsystem the phase touched.

## 10. Project Metrics & the SLOC Milestone Gate

Per explicit user directive, established at the Phase 1 Gate Review: **every phase
report must include a Project Metrics section**, and **cumulative Production Source
Lines of Code (SLOC) is the official measure of NOVA's implementation size** —
excluding blank lines and comments, and excluding tests, generated code, and
documentation. See
[`docs/roadmap/architecture-reviews/METRICS_TEMPLATE.md`](../roadmap/architecture-reviews/METRICS_TEMPLATE.md)
for the required structure (Project Statistics, Implementation Statistics, Language
Breakdown, Architecture Metrics, Quality Metrics, Growth Metrics, Complexity Metrics)
and for how "Production SLOC" is precisely scoped (`src/` application code + Alembic
schema migrations; tooling scripts, tests, generated clients, and documentation are
each reported separately, never folded into this number).

**The 50,000 SLOC gate.** When cumulative Production SLOC reaches approximately
50,000, feature development pauses automatically — no phase may begin new feature
work past that threshold without first completing an **Engineering Review
Milestone**, covering:

1. Architecture audit
2. Dependency audit
3. Performance profiling
4. Security review
5. Refactoring opportunities
6. Dead code analysis
7. Duplicate code detection
8. Technical debt review
9. Database optimization review
10. Event Bus review
11. API consistency review
12. Documentation review

The milestone is filed the same way a Gate Review is
(`docs/roadmap/architecture-reviews/`) and requires the same explicit approval before
feature development resumes. This is a distinct trigger from the per-phase Gate Review
([§9 above](#9-per-subsystem-deliverable-checklist),
[architecture-reviews/TEMPLATE.md](../roadmap/architecture-reviews/TEMPLATE.md)): a
phase can pass its own Gate Review (architecture sound, tests green) while the
*system-wide* SLOC threshold still independently triggers this broader audit — the
Gate Review asks "is this phase's work sound," the Engineering Review Milestone asks
"is the codebase as a whole still healthy at this scale." Whichever phase's own
Project Metrics section first reports cumulative Production SLOC at or above ~50,000
is the phase that must produce this milestone before any later phase's feature work
begins — it is checked at every phase boundary, not just watched for informally.
