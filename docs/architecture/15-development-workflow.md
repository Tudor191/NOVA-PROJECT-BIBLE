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
