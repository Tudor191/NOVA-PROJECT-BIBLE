# ADR-033 — Test infrastructure is dev-only, and integration testing is a permanent two-tier model

**Subsystem(s):** `nova-testkit`; binding on every engine's `tests/` directory and
every future shared package, from this point forward
**Status:** Accepted — permanent architectural principle

## Context

The Project Health Review (August 2026) found that `docs/architecture/
16-testing-strategy.md` described `testcontainers`-backed Postgres/Neo4j/Redis/
NATS fixtures and a `FakeModelGateway` in `nova-testkit` as already built, when
neither existed — `nova-testkit` provided only an in-memory `event_bus` fixture
and a `wait_until` helper. The user approved a Technical Implementation Plan
(`docs/design/nova-testkit/technical-implementation-plan.md`) to close that gap,
then approved implementation with five resolved open questions, one of which
was: **create ADR-033, covering exactly two permanent rules the plan's design
depends on** — not one rule per fixture, and not a rule for every implementation
detail the plan makes.

## Problem

Two questions need a standing, binding answer before any fixture is built,
because every fixture in the plan depends on both answers being fixed in
advance rather than decided ad hoc per fixture:

1. `nova-testkit` is about to gain real dependencies on database/broker client
   libraries and `testcontainers` itself — libraries no engine's own production
   code needs. What guarantees these never become a production dependency of
   any engine, now or as more fixtures are added later?
2. Once real-infrastructure fixtures exist, does "integration test" mean the
   existing fake-repository-backed tests, the new real-infrastructure tests, or
   both — and is one tier meant to eventually replace the other?

## Alternatives considered

- **Leave the dependency boundary as an informal convention** (as it already
  is today — every engine's `pyproject.toml` happens to list `nova-testkit`
  only under `[dependency-groups] dev`, never under `[project] dependencies`).
  Rejected: this has held by convention only, with nothing to catch a future
  PR that accidentally promotes it — exactly the kind of unaudited, unenforced
  claim the Project Health Review's coverage-gate finding (`16-testing-strategy.md`
  claiming 85% coverage "checked in CI" when nothing checked it) already showed
  this project cannot simply assume stays true because it's written down once.
- **Treat real-infrastructure tests as a migration that eventually replaces
  fake-backed tests**, retiring the fakes once every engine has real coverage.
  Rejected: the fake-backed tier has independent, permanent value — it is fast,
  needs no Docker, and exercises real FastAPI routing and domain logic
  end-to-end; the two tiers test different things (contract/logic correctness
  vs. real infrastructure behavior — constraints, transaction isolation,
  driver behavior) and neither subsumes the other, exactly as `tests/unit/`
  does not become unnecessary once `tests/integration/` exists.
- **Give every future engine free rein to add whatever database dependency its
  own tests need, decided independently per engine.** Rejected: this is the
  same "decided ad hoc per future consumer" failure mode ADR-032 rejected for
  identity-authorization gating — inconsistent across engines, and with no
  guarantee a future engine's test dependency stays out of its production
  image.

## Decision

1. **Test-infrastructure dependencies are development/test-only, permanently.**
   `nova-testkit` (and any future shared test-infrastructure package) may
   depend on `testcontainers`, database drivers, and any other real
   backing-store client library it needs to provide real-infrastructure
   fixtures — but every consuming engine may only ever declare `nova-testkit`
   (or such a package) under its own dev-dependency group, never under
   `[project] dependencies`. No such dependency may appear in any engine's
   production Docker image. This is enforced two ways going forward: the
   existing `[dependency-groups] dev`-only convention every engine's
   `pyproject.toml` already follows, and a new import-linter contract
   (`nova-testkit` may not import any engine's own top-level production
   package — the reverse-dependency direction is structurally impossible, not
   merely discouraged).
2. **Integration testing is a permanent two-tier model, not a migration
   path**: fake-backed tests (`tests/integration/`, default, PR-gating, no
   Docker required) and real-infrastructure tests (`@pytest.mark.real_infra`,
   `testcontainers`-backed, opt-in/separately gated per §7 of the
   implementation plan) are both permanent, both valuable, and neither retires
   the other as engines gain real-infrastructure coverage.
3. **This applies to every future shared package that provides test
   infrastructure, and to every current and future engine's `tests/`
   directory** — not scoped to `nova-testkit`'s four fixtures alone.

## Consequences

- Every engine's `pyproject.toml` continues to declare `nova-testkit` (and
  any future test-infrastructure package) exclusively under
  `[dependency-groups] dev` — a pre-existing convention this ADR now makes a
  binding rule rather than an incidental fact.
- `nova-testkit`'s own fixture design must never import a specific engine's
  `src/` code (e.g., a Postgres fixture that needs to run migrations takes an
  Alembic config *path* as a parameter, never an engine's own models module) —
  a design constraint on every fixture this ADR's implementation plan adds,
  not a one-off choice for the Postgres fixture alone.
- `tools/scaffold-engine.py`'s import-linter wiring (already fixed in the
  Project Health Review's Step 1 cleanup) must also add every new engine to
  the new `nova-testkit`-boundary contract this ADR requires, exactly as it
  already does for the four existing contracts.
- Future Gate Reviews for any engine that adds real-infrastructure tests must
  confirm both tiers exist and are each independently runnable (per the
  implementation plan's §8 local-dev workflow), not merely that "integration
  tests pass."

## Tradeoffs

- Maintaining two tiers of integration test permanently means more total test
  code than a single-tier model would need, and two tiers to keep in sync
  conceptually (both exercising the same repository contract, from different
  angles). Accepted: the alternative — retiring fakes once real infrastructure
  exists — would mean every engine's default `pytest` run (no Docker, PR-fast)
  loses its integration-level coverage entirely, regressing exactly the fast,
  deterministic feedback loop this project's existing CI design depends on.
- The new import-linter contract adds one more thing `tools/scaffold-engine.py`
  must keep correctly populated per new engine, alongside the four it already
  maintains. Accepted: this is the same mechanism already proven reliable for
  the other four contracts (once Step 1's `_update_root_pyproject` fix landed),
  not a new category of maintenance burden.

## Future implications

- If a future phase introduces a second shared test-infrastructure package
  (for example, a browser/E2E harness once `16-testing-strategy.md §6`'s
  Playwright suite is actually built), this ADR's dev-only dependency rule and
  no-reverse-import rule apply to it identically, without needing a new ADR to
  restate them.
- If a future engine's real-infrastructure tests ever reveal a need for a
  *third* tier (for example, a staging-environment smoke-test tier distinct
  from both fake-backed unit/integration and `testcontainers`-backed
  real-infrastructure tests), that is a new architectural decision requiring
  its own ADR — this one covers exactly two tiers, deliberately, not an
  open-ended "however many tiers turn out to be useful."
- Any future proposal to relax the dev-only dependency boundary (e.g., an
  engine wanting to ship a `testcontainers`-based self-test capability in
  production) must revisit this ADR explicitly rather than quietly diverging
  from it.
