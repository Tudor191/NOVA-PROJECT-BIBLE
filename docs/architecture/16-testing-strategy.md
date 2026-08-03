# 16 — Testing Strategy

## 1. Test pyramid, per engine

```
        ┌───────────────────────┐
        │   E2E (few)            │  Full pipeline through real bus/DBs in a throwaway env
        ├───────────────────────┤
        │  Contract tests         │  Every published event validated against nova-contracts
        ├───────────────────────┤
        │  Integration (moderate) │  Engine + real Postgres/Neo4j/Redis (via testcontainers)
        ├───────────────────────┤
        │   Unit (many)            │  domain/ logic, pure functions, no I/O
        └───────────────────────┘
```

Enforced minimum coverage: 85% line coverage on `domain/` (the actual cognitive logic)
per engine, checked in CI; `api/`/`repository/` layers are covered primarily by
integration tests rather than chased for unit coverage percentage, since their value is
in correct wiring, not branching logic.

## 2. Unit testing

- Framework: `pytest` (Python engines), `cargo test` (companion), `vitest` (frontend).
- `domain/` modules are pure and framework-free by construction ([03 §1](03-backend-architecture.md#1-architectural-style)),
  so they are testable with no mocks beyond the `ports.py` interfaces — e.g.,
  `reasoning-engine`'s Decision Matrix scoring function is tested with plain input/output
  assertions, no FastAPI or bus dependency in the test at all.

## 3. Integration testing

- `nova-testkit` provides `testcontainers`-backed fixtures: real Postgres, Neo4j,
  Redis, and an embedded NATS JetStream instance spun up per test module, torn down
  after — no mocked databases, because the Bible's requirements (contradiction
  detection across graph paths, HNSW similarity ranking, event replay) are precisely
  the behaviors that mocks hide bugs in.
- `nova-testkit` also provides a `FakeModelGateway` implementing the same
  `ModelConnector` protocol as real providers, returning deterministic, scripted
  responses — every engine's integration tests run without needing API keys or GPU
  access, and without non-determinism from live model output.

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

`nova-testkit/fixtures/` provides canonical seed data (a synthetic user, a synthetic
"Project NOVA," sample memories/knowledge nodes) reused across unit, integration, and
E2E layers so scenarios are comparable across test types and across engines — avoiding
each engine inventing its own incompatible fixture universe.

## 9. CI gating

Every PR must pass: lint → unit → integration → contract, scoped to changed
packages via Turborepo's affected-graph (`turbo run test --filter=...[origin/main]`) —
full E2E and non-functional suites run on merge to `main` and nightly, not on every PR,
to keep PR feedback fast (see [17](17-cicd-pipeline.md)).
