# 16 — Testing Strategy

**Status note (STEP 2 of the Project Health Review's approved 5-step plan,
August 2026):** this document previously described `nova-testkit`'s
`testcontainers`-backed fixtures, `FakeModelGateway`, and the 85% CI coverage
gate as already built, when none of them were. That gap is now closed for
the pieces described below as built; anything still described as future work
in this document genuinely is future work, not an oversight. See
`docs/design/nova-testkit/technical-implementation-plan.md` for the full
design and `docs/architecture/adr/ADR-033-test-infrastructure-boundary-and-two-tier-testing.md`
for the two permanent rules this implementation established.

## 1. Test pyramid, per engine

```
        ┌────────────────────────────┐
        │   E2E (few)                  │  Full pipeline through real bus/DBs in a throwaway env
        ├────────────────────────────┤
        │  Contract tests               │  Every published event validated against nova-contracts
        ├────────────────────────────┤
        │  Real-infrastructure          │  Engine + real Postgres/Neo4j/Redis/NATS (via
        │  integration (growing)        │  testcontainers) -- opt-in, not PR-gating (§3, §9)
        ├────────────────────────────┤
        │  Integration (moderate)       │  Engine + fake in-memory repository/graph/vector
        │                                │  store + in-memory Event Bus -- PR-gating, no Docker
        ├────────────────────────────┤
        │   Unit (many)                  │  domain/ logic, pure functions, no I/O
        └────────────────────────────┘
```

Two permanent tiers, not a migration path (ADR-033): fake-backed integration
tests are fast, need no Docker, and exercise real FastAPI routing and domain
logic end-to-end; real-infrastructure tests exercise what fakes cannot --
real constraints, real transaction isolation, real driver behavior. Neither
tier retires the other as engines gain real-infrastructure coverage.

Enforced minimum coverage: 85% line coverage on `domain/` (the actual cognitive
logic) per engine, **checked in CI as of this implementation** -- every
engine's `package.json` `test` script runs `pytest -m "not real_infra"
--cov=<package>.domain`, with the 85% `--cov-fail-under` threshold centralized
in root `pyproject.toml`'s `[tool.coverage.report]`. Measured this session:
every engine already clears it with real headroom (86%-99%); the gate makes
that discipline guaranteed rather than merely observed. `api/`/`repository/`
layers are covered primarily by integration tests rather than chased for unit
coverage percentage, since their value is in correct wiring, not branching
logic.

## 2. Unit testing

- Framework: `pytest` (Python engines), `cargo test` (companion), `vitest` (frontend).
- `domain/` modules are pure and framework-free by construction ([03 §1](03-backend-architecture.md#1-architectural-style)),
  so they are testable with no mocks beyond the `ports.py` interfaces — e.g.,
  `reasoning-engine`'s Decision Matrix scoring function is tested with plain input/output
  assertions, no FastAPI or bus dependency in the test at all.

## 3. Integration testing

**Fake-backed (default, PR-gating, no Docker required).** Every engine's
`tests/integration/` boots the real FastAPI app via `TestClient`, with a
hand-written in-memory fake repository (`tests/fakes/repository.py`) and
`EVENT_BUS_BACKEND=in_memory` substituted in — real routing and domain logic,
fake persistence. This is the tier `turbo run test` always runs.

**Real-infrastructure (opt-in, `@pytest.mark.real_infra`, requires Docker).**
`nova-testkit` provides `testcontainers`-backed fixtures — `postgres.py`,
`redis.py`, `neo4j.py`, `nats.py` — each pinned to the exact image
`infra/docker/docker-compose.local.yml` already uses (`postgres:16-alpine`,
`redis:7-alpine`, `neo4j:5-community` with `apoc`, `nats:2-alpine` with
JetStream). `nova_testkit.postgres.run_alembic_upgrade` runs an engine's own
real Alembic migration against a throwaway container; `postgres_session_factory`
exposes a real, rollback-isolated `async_sessionmaker` an unmodified real
`Postgres*Repository` can be constructed against directly. All four fixture
types are self-tested inside `nova-testkit`'s own `tests/`
(`test_postgres.py`/`test_redis.py`/`test_neo4j.py`/`test_nats.py`).
**Current adoption**: `communication-engine`, `personality-engine`,
`perception-engine`, and (Phase 3C) `capability-engine` each have a
`tests/integration/test_repository_real_postgres.py` exercising their real
repository against real Postgres — closing the real-Postgres verification
gap the Project Health Review (August 2026) identified for the first
three of these. `action-engine` (Phase 3D) has the same test file
implemented and passing in real GitHub Actions CI; `phase-3d-action-engine`
(PR #13) merged into `phase-3b-planning-domain` on 2026-08-18 (squash
commit `ac285bc3533fb24d0434d7675b8fc3af2db1d079`), so this test file is
now "adopted" in the sense of being present on this lineage's own
canonical branch, alongside the other four. Redis/Neo4j/NATS fixtures exist
and are self-tested but **not yet adopted by any engine's own repository
tests** — that is tracked, sequenced future work
(`docs/design/nova-testkit/technical-implementation-plan.md §11`), not an
oversight. Excluded from the default `pytest`/`turbo run test` invocation via
`-m "not real_infra"`; run explicitly with `-m real_infra` (§9's CI job, or
locally with Docker).

`nova-testkit` also provides a `FakeModelGateway` — **not** a `ModelConnector`
protocol fake (that already exists as `ai-model-orchestration-engine`'s own
production `FakeConnector`). Every cross-engine call, including every call to
`ai-model-orchestration-engine`, is Event Bus request/reply (ADR-004,
ADR-020) — `FakeModelGateway` fakes that contract directly, serving all eight
`ai_model.*.request` subjects with deterministic, scripted replies over the
`event_bus` fixture. Needs no `testcontainers`, no database, no network: any
engine's tests reach it the same way they'd reach a real
`ai-model-orchestration-engine`, without API keys, GPU access, or
non-determinism from live model output.

## 4. Contract testing

Every engine's `tests/contract/` validates that everything it publishes matches its
declared schema in `nova-contracts`, and — critically — that everything it *claims to
subscribe to* in `events/subscribed.py` is still a schema that exists (catches drift
when a publisher renames/removes a field). CI runs this across the whole monorepo on
every PR (not just the changed engine), since a schema change's blast radius is
exactly what this test class exists to catch.

## 5. Multi-agent / orchestration testing

Because agent behavior involves LLM-driven decisions (inherently non-deterministic),
testing follows Part 8's own verification philosophy — **structural verification, not
output-string matching**:

- Assert *that* the Reasoning Engine's pipeline visited every required stage
  (hypothesis generation occurred, alternatives ≥ 3 for Level 3 reasoning per Part 8,
  confidence was recorded) — not the exact wording of the model's output.
- Assert the Task Graph produced for a scripted objective has the expected dependency
  shape and no cycles — not that Planning Engine "picked the right words."
- Golden-scenario replays: recorded real event sequences from staging (e.g., "the
  meeting-starts scenario," [10 §2 row 9](10-inter-engine-communication.md)) replayed
  against the current codebase to catch behavioral regressions in cross-engine
  coordination.

## 6. End-to-end testing

A small, deliberately limited suite (Playwright, driving the real web-client against a
full local-first stack in CI) covering the golden paths only:

1. First-run onboarding → first successful conversation with memory recall.
2. A multi-step coding task flowing through Planning → the NOVA Agent Operating System ([12](12-agent-architecture.md)) → Action →
   result surfaced to the user.
3. An autonomy approval round-trip (autonomous suggestion → user approval → execution).
4. Engine crash-and-recover (kill a container mid-task, verify resumption per Part 20's
   Recovery Engine).

E2E is intentionally small because it is slow and environment-heavy; the contract +
integration layers below it are where most confidence is bought, consistent with
standard test-pyramid economics.

## 7. Non-functional testing

| Category | Tooling | Target |
|---|---|---|
| Load/performance | `k6` against the API Gateway and Event Bus | Meets each engine's Performance Targets as stated in its own Bible Part (e.g., Part 12: "thousands of queued actions") |
| Security | `pip-audit`/`cargo audit`/`npm audit`, Trivy image scans, periodic OWASP ZAP pass against the API Gateway | Zero known-critical CVEs at release |
| Chaos/resilience | Scheduled fault injection (kill a random engine pod in staging) via a lightweight chaos job | System self-heals per Part 20 "Fault Tolerance" without manual intervention |
| Accessibility | `axe-core` in the Playwright E2E run | WCAG 2.1 AA on all panels |

## 8. Test data & fixtures

**Not yet built.** The originally-envisioned `nova-testkit/fixtures/` module
(canonical seed data — a synthetic user, a synthetic "Project NOVA," sample
memories/knowledge nodes — reused across unit, integration, and E2E layers)
does not exist. STEP 2's three real-infrastructure adopter engines
(`communication-engine`, `personality-engine`, `perception-engine`) each
construct their own minimal domain objects directly per test and did not need
it; whether a shared seed-data module earns its cost is worth revisiting once
more engines adopt real-infrastructure testing and any actual duplication
across their test data becomes concrete, rather than building it speculatively
ahead of that evidence.

## 9. CI gating

Every PR must pass: lint → unit → integration (fake-backed) → contract, via
`pr-checks.yml`'s `turbo run test`. **Not yet scoped to changed packages via
Turborepo's affected-graph filtering**, despite `[17](17-cicd-pipeline.md)`
still describing that filtering as already in place -- `pr-checks.yml`'s own
header comment is the accurate, current source: full runs on every PR are a
deliberate, temporary simplification ("with only a handful of packages...
running everything on every PR is simpler and more robust than
affected-graph edge cases"), not yet switched to filtering. Flagged here as
an existing cross-document inconsistency in `17-cicd-pipeline.md`, out of
scope for this update (STEP 2 was `nova-testkit`, not doc 17) and not
corrected in this pass. Full E2E and non-functional suites run on merge to
`main` and nightly, not on every PR, to keep PR feedback fast.

**Real-infrastructure tests are a separate, staged, non-blocking workflow**
(`.github/workflows/real-infra-checks.yml`), run on every PR, on merge to
`main`, and nightly — but **deliberately not added to this repository's
required status checks**. Per direct user instruction: the first stage is to
establish reliable CI execution and collect real runtime/flakiness data;
only once that data shows the suite is stable should the exact hard-gate
policy (every PR vs. merge-only, which packages, failure handling) be
proposed for approval and this workflow promoted to a required check. Do not
treat its current non-blocking status as permanent, and do not promote it
without that follow-up proposal.
