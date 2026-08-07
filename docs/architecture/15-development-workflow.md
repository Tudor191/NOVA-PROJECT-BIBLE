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

## 8. The permanent subsystem lifecycle

Per explicit user directive, established at the Phase 2D-A checkpoint immediately
following the AI Model Orchestration speech extension's approval, and stated by the
user as binding on **every future engine, subsystem, or major architectural
component of NOVA, permanently**: no implementation ever begins immediately after a
roadmap milestone. Every subsystem follows the same fixed sequence, with no step
skipped and no step reordered:

1. **Roadmap** — the phase/sub-phase entry in
   [`ENGINEERING_ROADMAP.md`](../roadmap/ENGINEERING_ROADMAP.md).
2. **Blueprint** (if required) — a master architectural blueprint one level above any
   individual engine's TDD, for work spanning multiple engines or a new phase family
   (the [Phase 2D Master Architectural Blueprint](../design/phase-2d/00-master-blueprint.md)
   is the precedent).
3. **Human/philosophical documents** (if required) — permanent, non-technical
   governing documents a subsystem must be faithful to (the precedent:
   [Doc 22](22-nova-human-interaction-principles.md),
   [Doc 23](23-nova-personality-specification.md)).
4. **Technical Design Document (TDD)** — one per engine/subsystem, structured per
   [§9's required contents](#9-per-subsystem-deliverable-checklist) below.
5. **User's explicit approval** of the TDD — implementation may not begin before this.
6. **Implementation**, built layer by layer.
7. **Continuous testing** — each layer tested before the next layer begins, not
   deferred to the end.
8. **Architecture Review** (the subsystem's Architecture Review Report).
9. **Gate Review** (Go/No-Go, per the standing requirement established at the Phase 1
   Gate Review).
10. **Engineering Metrics** (per [§10 below](#10-project-metrics--the-sloc-milestone-gate),
    reported in every completion checkpoint, not only at phase boundaries).
11. **User's final approval.**
12. **Only then** does work proceed to the next subsystem.

This is the same discipline every phase from Phase 1 onward has already been held
to in practice (Phase 1's four-document design package approved before
implementation; Phase 2B and 2C's TDDs pending explicit approval before code;
Phase 2D's blueprint-then-Doc-22-then-Doc-23-then-TDD sequence) — recorded here as
an explicit, permanent rule rather than an inferred pattern, so it applies uniformly
to every future subsystem without needing to be re-derived from precedent each time.
"Blueprint" and "human/philosophical documents" are the only optional steps, and
only when the user's own directive establishing the phase says they're not
required (e.g., a small, single-engine extension within an already-blueprinted
phase, like the AI Model Orchestration speech extension inside Phase 2D-A, does not
need its own new blueprint) — every other step is mandatory for every subsystem.

For anything at the scale of a new engine or a change to an ADR in
[00](00-overview-and-decisions.md), the TDD step above **is** the short design doc
(problem, options considered, decision, Bible traceability) — reviewed async via PR
against `docs/architecture/proposals/` if the change is smaller than a full engine —
keeping the SAD a living document rather than a one-time artifact, per Part 1's
expectation that the architecture "evolve continuously for many years" without
requiring fundamental redesigns.

## 9. Per-Subsystem Deliverable Checklist

### 9.0 Required Technical Design Document contents

Per explicit user directive, established at the same Phase 2D-A checkpoint as
[§8](#8-the-permanent-subsystem-lifecycle) above: every future TDD must define, at
minimum, each of the following. This is the canonical checklist every future TDD is
reviewed against before it may be approved — earlier phases' TDDs (Phase 1 through
Phase 2D-A) satisfy nearly all of it already by precedent (see, e.g.,
[`00-executive-cognition-engine.md`](../design/phase-2c/00-executive-cognition-engine.md)'s
numbered-section shape); this makes that shape an explicit, permanent requirement
rather than an inferred convention, and adds the items below that earlier TDDs
covered unevenly:

1. Overall architecture
2. Core responsibilities
3. Responsibilities that explicitly do **not** belong to the subsystem
4. Internal execution flow
5. Complete data flow
6. Domain model
7. State transitions
8. APIs
9. Event Bus RPCs
10. Published events
11. Consumed events
12. Database schema
13. Repository layer
14. Dependency boundaries
15. ADR compliance
16. Bible compliance
17. [Human Interaction Principles](22-nova-human-interaction-principles.md)
    compliance (where applicable)
18. [Personality Specification](23-nova-personality-specification.md) compliance
    (where applicable)
19. Failure handling
20. Recovery mechanisms
21. Observability
22. Logging strategy
23. Metrics
24. Performance goals
25. Security considerations
26. Scalability considerations
27. Testing strategy
28. Future extension points
29. Known limitations
30. Technical debt
31. Architectural risks
32. Tradeoffs
33. Explicit implementation order

Standing rules that apply throughout implementation, not only at the TDD-writing
stage:

- **Layer by layer, tested before the next layer begins** — per
  [§8](#8-the-permanent-subsystem-lifecycle), this is not a suggestion; a layer
  without passing tests is not a complete layer.
- **Stop and explain before deviating from the approved design.** If a better
  architectural solution is discovered during implementation, implementation pauses
  and the alternative is explained to the user before any change is made — the
  existing rule this project has followed since Phase 2A, restated here as
  permanent and universal.
- **Never hide technical debt, architectural limitations, or implementation
  compromises.** Every completion report names them explicitly, the same honesty
  standard this project's Architecture Review Reports have already applied since
  Phase 1.
- **Subjective experience quality is a first-class requirement.** Per
  [ADR-031](adr/ADR-031-subjective-experience-quality-is-a-first-class-requirement.md):
  whenever multiple implementations satisfy the requirements, prefer the one that
  produces the most natural, responsive, and consistent user experience, while
  remaining faithful to the approved architecture — never a license to deviate from
  it.

### 9.1 The ten-item build-time deliverable checklist

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

**The 30,000 SLOC reminder.** Per explicit user directive, established at the same
Phase 2D-A checkpoint as [§8](#8-the-permanent-subsystem-lifecycle) and
[§9.0](#90-required-technical-design-document-contents): when cumulative Production
SLOC first reaches approximately 30,000, the phase's completion report must
explicitly remind the user that it is time to consider a full **Project Health
Review** before continuing significant feature development — covering
architecture, maintainability, duplication, complexity, performance, dependency
health, and long-term scalability. Unlike the 50,000 SLOC gate below, this is a
**reminder, not an automatic pause** — the user decides whether to act on it
immediately or continue; the obligation is to surface the reminder clearly and
say so plainly in that phase's own Project Metrics section, not to block work
pending a response. If the Project Health Review is conducted at this point, it
satisfies (and need not be repeated for) the 50,000 SLOC gate's Engineering
Review Milestone below, provided its scope already covers that milestone's
twelve items; if it does not, the 50,000 SLOC gate still applies independently
when reached.

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
