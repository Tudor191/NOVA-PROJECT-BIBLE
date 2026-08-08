# nova-testkit Technical Implementation Plan

**Status: Proposed — pending user review and approval. No implementation has begun.
Nothing in this document has been built.**

**Scope: STEP 2 of the Project Health Review's approved 5-step plan
([project-health-review-2026-08.md §27.1](../../roadmap/architecture-reviews/project-health-review-2026-08.md#271-build-the-nova-testkit-real-infrastructure-fixtures-16-testing-strategyd-already-claims-exist)).**
This document is a plan only, produced per direct instruction: analyze the gap
between `docs/architecture/16-testing-strategy.md` and what actually exists,
design the missing infrastructure, and stop for approval before writing any code.

---

## 0. Executive summary

`nova-testkit` today provides exactly two things: an `event_bus` fixture
(in-memory `EventBus`) and a `wait_until` polling helper. `docs/architecture/
16-testing-strategy.md` describes, in the present tense, `testcontainers`-backed
Postgres/Neo4j/Redis/NATS fixtures, a `FakeModelGateway`, and an 85%-domain-coverage
CI gate — **none of which exist**. Every engine's "integration" tests are, in fact,
FastAPI `TestClient` tests against hand-written in-memory fake repositories; no
engine's tests touch a real database, graph store, cache, or message broker. No
CI step measures or enforces coverage at all, despite `pytest-cov` already sitting
unused in the root workspace's dev-dependencies.

This plan closes that gap in nine independently-shippable pieces (§11), ordered so
the two zero-infrastructure-cost items (coverage enforcement, `FakeModelGateway`)
land first and the four `testcontainers`-backed fixtures (Postgres, Redis, Neo4j,
NATS, in that priority order) land progressively, each proven against one real
engine before the next fixture is built. It recommends one new ADR (§14), one new
import-linter contract (§9), and an incremental (not big-bang) rewrite of
`16-testing-strategy.md` (§10).

**Nothing here has been implemented, verified against Docker, or committed.** This
environment has no reachable Docker daemon (confirmed: `docker compose config` —
YAML-only, no daemon needed — succeeds; `testcontainers` is not installed anywhere
in the workspace, confirmed by grep and `uv.lock`). Every claim about container
behavior below is therefore a design decision grounded in this project's own
existing conventions (image tags copied verbatim from `infra/docker/
docker-compose.local.yml`, fixture shape copied from `nova-testkit`'s existing
`event_bus` fixture), not a verified fact — §12 and §13 are explicit about exactly
what remains unverified until a Docker-capable environment executes this plan.

---

## 1. Current state

### 1.1 `nova-testkit` package — everything that exists today

Two source files, in full:

- **`src/nova_testkit/plugin.py`** — one `pytest.fixture` named `event_bus`,
  registered globally via the `pytest11` entry point (`packages/nova-testkit/
  pyproject.toml`: `[project.entry-points.pytest11] nova_testkit =
  "nova_testkit.plugin"`) — no `conftest.py` needed by any consumer. It
  constructs `nova_eventbus_sdk.backends.in_memory.InMemoryEventBus()`, calls
  `connect()`, yields it, calls `close()`. That is the fixture's entire body.
- **`src/nova_testkit/waiting.py`** — one function, `wait_until(condition,
  timeout_s=2.0, interval_s=0.01)`, a poll-until-truthy helper used instead of
  `asyncio.sleep(n)`.

`src/nova_testkit/__init__.py` exports only `wait_until`. Dependencies
(`pyproject.toml`): `nova-eventbus-sdk`, `pytest>=8.3` (runtime); `pytest-asyncio`
(dev). **No `testcontainers`, no database drivers, no `FakeModelGateway`, no
`fixtures/` directory** — despite `16-testing-strategy.md §8` describing a
`nova-testkit/fixtures/` directory of "canonical seed data (a synthetic user, a
synthetic 'Project NOVA,' sample memories/knowledge nodes)." That directory does
not exist.

**No `conftest.py` exists anywhere in the repository** (confirmed by a repo-wide
`find`). This is a deliberate, load-bearing convention this plan must not break:
fixtures are either defined per-test-file or delivered globally via the
`pytest11` entry point, exactly as `event_bus` already is. Every new fixture this
plan adds follows the same `pytest11`-registration pattern.

### 1.2 What every engine's tests currently do

`tools/scaffold-engine.py` gives every engine (except `nova-core`, which predates
the scaffolder) an identical `tests/{unit,integration,contract,fakes}/` layout.
But **"integration" does not mean what `16-testing-strategy.md §1`'s test-pyramid
table says it means.** Across all 10 engines, zero integration tests touch
Postgres, SQLite, Neo4j, or a real cache — confirmed by a repo-wide grep for
`sqlite`/`create_async_engine`/`create_engine` under every `tests/integration/`
directory (zero hits). What they actually do:

```python
# services/memory-engine/tests/integration/test_api_memories.py
@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(),
        memory_repository=FakeMemoryRepository(),
        vector_index=InMemoryVectorStore(),
        embedding_provider=InMemoryEmbeddingProvider(),
    )
    with TestClient(app) as test_client:
        yield test_client
```

Every engine has a hand-written `FakeXRepository` in `tests/fakes/repository.py`
(plain Python dicts/lists implementing the domain repository Protocol),
substituted in at `create_app(...)` time. This is a real, valuable test tier
(it exercises the actual FastAPI routing, request validation, and domain logic
end-to-end) — it is simply **not** the "real Postgres/Neo4j/Redis via
testcontainers" tier the strategy document claims already backs it. The real
`Postgres*Repository`/`Neo4j*`/etc. classes exist only in `src/repository/` and
are never imported by any test file in the repository, in any of the 10 engines
— confirmed directly for `personality-engine`, `communication-engine`, and
`perception-engine` (the three named priority engines) and by grep across the
rest.

`tests/contract/` is populated in only 4 of 10 engines today
(`ai-model-orchestration-engine`'s connector-compliance suite per ADR-023,
`reasoning-engine`'s and `executive-cognition-engine`'s port-compliance suites,
`perception-engine`'s event-subject-wildcard test); it is an empty scaffold
(`__init__.py` only) in the other 6, including all three priority engines.

### 1.3 The existing `FakeConnector` is not the `FakeModelGateway` the doc describes

`ai-model-orchestration-engine/src/nova_ai_model_orchestration_engine/
connectors/fake_connector.py` is a full, deterministic `ModelConnector` Protocol
implementation (`generate`/`stream`/`embed`/`transcribe`/`synthesize`/biometric
methods, configurable failure modes, call tracking) — but it is a first-class
**production** connector (`connector_type = "fake"`, resolved by the real
`ConnectorFactory`), living inside `ai-model-orchestration-engine` itself, used
by that engine's own ADR-023 compliance suite. It fakes the boundary between
`ai-model-orchestration-engine` and an external provider SDK (Anthropic/Ollama/
Whisper/etc.).

That is a different boundary from the one `16-testing-strategy.md`'s
`FakeModelGateway` needs to fake. Every other engine talks to
`ai-model-orchestration-engine` exclusively over the Event Bus, request/reply,
per ADR-020 — confirmed by reading `reasoning-engine/src/.../clients/
model_orchestration_client.py`:

```python
async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload:
    envelope = await self._event_publisher.request(
        "ai_model.generate.request", request,
        source_engine=SOURCE_ENGINE, correlation_id=request.correlation_id,
        timeout_ms=self._timeout_ms,
    )
    return GenerateReplyPayload.model_validate(envelope.payload)
```

Every cross-engine client in the codebase (`memory_client.py`,
`knowledge_client.py`, `world_model_client.py`, `personality_client.py`, etc.)
follows this identical shape: a thin wrapper around
`event_publisher.request(subject, payload, ...)`. This means the
`FakeModelGateway` other engines need is **not** a provider-SDK fake at all — it
is an **event-bus responder**, buildable entirely on the `event_bus` fixture
`nova-testkit` already has, with zero new infrastructure dependency. This is the
single most important simplification this research surfaced (§2.5).

### 1.4 Coverage: measured correctly, enforced nowhere

`pytest-cov>=7.1.0` is already a root workspace dev-dependency (`pyproject.toml
[tool.uv] dev-dependencies`) — and is never invoked with `--cov` by any of the 10
engines' `package.json` `test` scripts, nor by `pr-checks.yml`. There is no
`[tool.coverage]` section anywhere in the repository. Reproduced directly this
session (`uv run pytest --cov=nova_personality_engine.domain
--cov-report=term-missing`, from inside `services/personality-engine`):
`domain/` at 99% (125 statements, 1 missed), matching the Project Health Review's
own spot-check figures for this engine. **The measurement tooling and the
practiced discipline are both real and reliable — only the enforcement is
missing.**

### 1.5 CI never starts a container

Neither `.github/workflows/pr-checks.yml` nor `build-and-scan.yml` has a
`services:` block; `docker compose ... config --quiet` is a YAML-syntax check
that never starts a daemon-backed container. `pnpm turbo run test` fans out to
`uv run --package <name> pytest` per engine — entirely against the in-memory
fakes described in §1.2. `testcontainers` appears nowhere in `uv.lock`.

### 1.6 `personality-engine`, `communication-engine`, `perception-engine` — Alembic state

All three are the simplest possible case for a first real-Postgres fixture: one
migration each (`0001_initial_schema.py`), an identical async `env.py` shape
(`async_engine_from_config`, per-engine-namespaced `version_table` — e.g.
`alembic_version_personality` — consistent with the multi-engine-single-database
convention the Project Health Review confirmed healthy), and zero existing
coupling to any fake/real database switch in their tests today.

---

## 2. Required infrastructure — target design

### 2.1 Design principle established by §1.3: two genuinely different fixture categories

- **Event-bus-level fakes** (`FakeModelGateway`): pure Python, built on the
  existing `event_bus`/`InMemoryEventBus` fixture, zero new runtime
  dependency, zero container. Cheapest, safest, highest-leverage — every engine
  that calls another engine over the bus can use this pattern, not just AI
  model calls.
- **Real backing-store fixtures** (Postgres, Neo4j, Redis, NATS): `testcontainers`-
  backed, each engine's *own* persistence layer tested against its own real
  store. This is the category `task #93` and §27.1 of the Project Health Review
  are actually about, and the category that requires Docker.

Conflating these two (as `16-testing-strategy.md §3` currently does, listing them
in the same two bullets) is itself part of the documentation gap (§10).

### 2.2 New `nova-testkit` modules (design, not yet built)

| Module | Fixture(s) | Backing | New dependency |
|---|---|---|---|
| `nova_testkit.model_gateway` | `fake_model_gateway` | `event_bus` (existing) | none |
| `nova_testkit.postgres` | `postgres_container`, `postgres_engine` | `testcontainers[postgres]` | `testcontainers`, `asyncpg` (already used by every engine's real repository) |
| `nova_testkit.redis` | `redis_container`, `redis_client` | `testcontainers[redis]` | `testcontainers`, `redis` (async client) |
| `nova_testkit.neo4j` | `neo4j_container`, `neo4j_driver` | `testcontainers.neo4j` | `testcontainers`, `neo4j` (already used by `nova-graphstore-sdk`) |
| `nova_testkit.nats` | `nats_container`, `real_event_bus` | `testcontainers.core.DockerContainer` (generic — see §3.4) | `testcontainers` |

### 2.3 Postgres fixture: the migration-running problem and its resolution

The one genuinely hard design problem: a Postgres fixture is useless for
real-repository testing unless the engine's own Alembic migrations have been
applied first, but `nova-testkit` **must never import a specific engine's
code** — that would create a reverse dependency (`nova-testkit` → engine) on top
of the existing forward one (engine → `nova-testkit`, dev-only), and would
silently break the moment two engines' models collide on import.

Resolution: `nova_testkit.postgres.postgres_engine` takes an **Alembic config
path** as a fixture parameter (via `pytest.fixture` indirection /
`request.param`, or a small factory function each engine's own test file calls
with its own `alembic.ini` path), not an engine import. `nova-testkit` knows how
to drive Alembic generically (`alembic.config.Config`,
`alembic.command.upgrade(cfg, "head")`) against whatever `env.py` it's pointed
at — it never needs to know what tables that produces. Each engine's own test
file is the only place that ever imports that engine's own code, exactly as
today.

### 2.4 Reusable service fixtures, lifecycle, readiness, cleanup, isolation

- **Scope**: session- or module-scoped containers (not function-scoped) — start
  once per test session/module, reused across many tests, to amortize Neo4j's
  slower JVM startup. Per-test isolation is achieved by test-level cleanup, not
  container-per-test:
  - **Postgres**: one transaction per test, rolled back at teardown (standard
    SQLAlchemy pattern: `async with engine.connect() as conn: async with
    conn.begin() as trans: yield session; await trans.rollback()`). Fast,
    exact, no cross-test leakage.
  - **Redis**: `FLUSHDB` between tests (cheap; Redis has no transaction/rollback
    primitive that fits this shape).
  - **Neo4j**: `MATCH (n) DETACH DELETE n` between tests (same reasoning).
  - **NATS**: fresh, uniquely-named stream/subject prefix per test
    (`test-<uuid>.>`) rather than a global flush, since JetStream streams are
    explicitly provisioned, not implicitly created.
- **Readiness**: every fixture blocks on the *same* health signal
  `docker-compose.local.yml` already uses for that service (§3), not a generic
  "wait N seconds" — `pg_isready`-equivalent driver-level connection retry for
  Postgres, a Bolt handshake for Neo4j, `PING` for Redis, the `/healthz` HTTP
  endpoint for NATS.
- **Deterministic startup/shutdown**: every fixture uses `yield`-based teardown
  (the same shape `event_bus` already uses), guaranteeing `container.stop()`
  runs in a `finally`-equivalent path even on test failure (§12).
- **Test data initialization**: `nova_testkit.fixtures` (a new module,
  §2.1/§1.1's already-documented-but-missing `fixtures/` seed data) provides the
  canonical synthetic user/"Project NOVA"/sample-memory/sample-knowledge-node
  data `16-testing-strategy.md §8` describes, as plain constructors any real- or
  fake-repository test can call — this closes a second, smaller, previously
  undocumented gap alongside the main one.
- **Parallel test safety**: `testcontainers-python` assigns each container a
  random free host port by default — fixtures must always read the assigned
  port back from the container object, never hardcode `5432`/`7687`/`6379`/
  `4222`. This is what makes the design safe if `pytest-xdist` is adopted later
  (§15, open question — not adopted today).

### 2.5 `FakeModelGateway` design

An event-bus responder registered via `bus.serve(subject, handler)` (the same
serving mechanism `nova-eventbus-sdk` already provides and every real engine
already uses) for every `ai_model.*.request` subject
(`ai_model.generate.request`, `.embed.request`, `.transcribe.request`,
`.synthesize.request`, and the Phase 2D-B biometric/wake subjects), returning
deterministic, per-test-configurable canned replies. Shape modeled directly on
`FakeConnector`'s existing, already-proven configurability
(`should_fail`, `supports_*`, call tracking) — but living in `nova-testkit`, and
operating one layer up (the event-bus contract, not the `ModelConnector`
Protocol). Any engine wanting a scripted model response uses `event_bus` +
`fake_model_gateway` together in the same test — no real orchestration engine,
no API keys, no non-determinism.

---

## 3. Testcontainers architecture

Every image tag below is copied verbatim from `infra/docker/
docker-compose.local.yml` — this project's own established version convention
for these four services — not chosen independently, per the instruction not to
select versions arbitrarily.

### 3.1 Postgres

| | |
|---|---|
| Image | `postgres:16-alpine` (matches compose exactly) |
| Startup | `testcontainers.postgres.PostgresContainer("postgres:16-alpine")` |
| Readiness | driver-level connect-retry (`asyncpg.connect` retried with backoff) — `testcontainers-python`'s Postgres module already blocks on this internally |
| Exposed | one random host port → container's `5432`; DSN reconstructed via the container's own `get_connection_url()` |
| Env config | `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` — fixed test values (no need to mirror compose's env-var-overridable defaults; nothing about a throwaway test container needs to be operator-configurable) |
| Lifecycle | session/module-scoped; started once, migrations applied once, then transaction-per-test isolation (§2.4) |
| Cleanup | `container.stop()` in fixture teardown (`yield`-based) |
| Isolation | one container per pytest session (or per engine's test module — TBD in §11's spike task); never shared across engines/CI jobs |
| Failure behavior | if the container fails to start (Docker unavailable, image pull failure), the fixture raises during setup — the requesting test errors (not silently skips), so a missing Docker daemon is loud, not a false pass. `real_infra`-marked tests are excluded from the default `pytest` invocation entirely (§8), so this only surfaces when a developer/CI job explicitly opts in. |
| CI requirement | Docker daemon reachable from the runner (§7) |

### 3.2 Neo4j

| | |
|---|---|
| Image | `neo4j:5-community` (matches compose) |
| Startup | `testcontainers.neo4j.Neo4jContainer("neo4j:5-community")` — **unverified**: this plan assumes `testcontainers-python` ships an official Neo4j module; confirming its exact API is the first item of §11's spike task, since this environment cannot install packages from PyPI to check |
| Readiness | Bolt protocol handshake retry (driver-level `driver.verify_connectivity()`) |
| Exposed | random host port → container's `7687` (Bolt); browser UI port `7474` not needed for tests |
| Env config | `NEO4J_AUTH=neo4j/<test password>`; `NEO4J_PLUGINS=["apoc"]` — APOC is enabled in compose and is used by `nova-graphstore-sdk`'s real backend, so the test container must enable it too, or tests will pass against a container that doesn't match production capability |
| Lifecycle | session/module-scoped |
| Cleanup | `container.stop()`; `MATCH (n) DETACH DELETE n` between tests (§2.4) |
| Isolation | one container per session; no shared state across engines |
| Failure behavior | same loud-failure principle as §3.1 |
| CI requirement | Docker; JVM-backed image, expect the slowest startup of the four (§7) |

### 3.3 Redis

| | |
|---|---|
| Image | `redis:7-alpine` (matches compose) |
| Startup | `testcontainers.redis.RedisContainer("redis:7-alpine")` |
| Readiness | `PING`/`PONG` retry |
| Exposed | random host port → container's `6379` |
| Env config | none required (compose's Redis has no auth configured either) |
| Lifecycle | session/module-scoped |
| Cleanup | `container.stop()`; `FLUSHDB` between tests |
| Isolation | one container per session |
| Failure behavior | same as above |
| CI requirement | Docker; fastest of the four to start |

### 3.4 NATS JetStream

| | |
|---|---|
| Image | `nats:2-alpine` (matches compose) |
| Startup | **generic** `testcontainers.core.container.DockerContainer("nats:2-alpine")` with `.with_command(["-js", "-sd", "/data", "-m", "8222"])` and exposed ports `4222`/`8222` — matching compose's exact invocation. `testcontainers-python` has no official NATS module (unlike Postgres/Redis/Neo4j); this is a deliberate, evidence-based choice, not a gap |
| Readiness | HTTP GET on the assigned host port mapped to `8222`'s `/healthz` — identical semantics to compose's own healthcheck (`wget -qO- http://localhost:8222/healthz`) |
| Exposed | random host ports → container's `4222` (client) and `8222` (monitoring/healthz) |
| Env config | none beyond the command flags above |
| Lifecycle | session/module-scoped |
| Cleanup | `container.stop()`; fresh uniquely-prefixed subject/stream per test (§2.4) — JetStream streams are explicit, so there's no "flush everything" primitive to lean on |
| Isolation | one container per session |
| Failure behavior | same as above |
| CI requirement | Docker; connects the **existing** `nova_eventbus_sdk.backends.nats.NatsEventBus` (already implements JetStream-backed durable streams, ADR-006) to the container's assigned port — no new NATS client code, only a new way to point the existing backend at a real, disposable broker instead of the compose one |

### 3.5 Why session/module scope, not a single global container

A single container shared across the *entire* CI run (all engines) would violate
isolation the moment two engines' tests ran concurrently against it (schema
collisions, cross-test data leakage) and would make one engine's fixture bug a
blast-radius risk to every other engine's tests. Per-engine-test-module
containers, each engine only starting the specific containers its own tests
request (pytest fixtures are lazy — a container fixture never executes unless a
test parameter actually asks for it), keeps the blast radius and resource cost
scoped to exactly the engine being tested.

---

## 4. Real database verification

Once §2–§3 exist, each engine's real `Postgres*Repository` (and, where
applicable, `Neo4j*`/graph and Redis-backed code) gets a **new** test file under
`tests/integration/`, marked `@pytest.mark.real_infra` (§9's new marker),
importing the real repository class for the first time in that engine's test
suite — e.g. `services/communication_engine/tests/integration/
test_repository_real_postgres.py` would import
`nova_communication_engine.repository.postgres_repository.
PostgresCommunicationRepository` directly, run it against `postgres_engine`
(migrations pre-applied), and assert real round-trips: create → real SELECT
confirms the row, matching the domain model exactly; a uniqueness/FK constraint
from the actual migration is exercised and confirmed to raise; a concurrent
update scenario confirms the transaction-isolation behavior the fake repository
cannot represent (fakes have no real ACID semantics to get wrong). This is what
closes task #93 and the "no real-Postgres verification exists anywhere" finding
(§17 of the Project Health Review) — not "the container started," but "the real
schema, the real constraints, and the real driver behave as the domain layer
assumes they do." §13 defines this precisely per fixture.

---

## 5. Coverage enforcement

- **What currently measures coverage**: `pytest-cov` (already installed,
  workspace-wide, unused). Manually invoked once per Gate Review
  (`pytest --cov=<pkg>.domain --cov-report=term-missing`), never in CI.
- **Reliability**: high — reproduced directly this session for
  `personality-engine` (99% domain, exact match to the Project Health Review's
  own figure). The tooling and the discipline are both real; only automation is
  missing.
- **Enforcement**: none, anywhere, today.
- **Where the CI gate should live**: extend each engine's own `package.json`
  `test` script — `"test": "uv run --package <name> pytest --cov=<pkg>.domain
  --cov-fail-under=85"` — the same place `mypy` already rides inside `lint`
  (Project Health Review §16's praised pattern: Turborepo needs zero new
  workflow steps, `pnpm turbo run test` already runs in CI exactly as today).
  Trade-off, stated plainly: a coverage-gate failure surfaces as a generic
  pytest non-zero exit inside the existing `test` step, not a separately-named
  CI check — consistent with how this project already treats `ruff`+`mypy`
  failures inside `lint`, not a new limitation this plan introduces.
- **Global or per-engine**: **per-engine**, scoped to `domain/` only, exactly as
  `16-testing-strategy.md` already (correctly) specifies. A single global
  aggregate threshold would be distorted by engines with more real-infra-only
  code in `clients/`/`repository/`/`workers/` (communication-engine's 65% total
  vs. 99% domain is exactly this effect) — per-engine domain-only scoping is
  the only version of "85%" that's actually meaningful, and the only version
  already being met in practice.
- **Threshold**: **do not change it.** No evidence supports raising or lowering
  85% — actual domain coverage runs 97–99% across every engine checked, with
  comfortable headroom.
- **Failure reporting**: `--cov-fail-under`'s existing non-zero exit + missing-
  line table (reproduced in §1.4) is sufficient; no additional tooling needed.
- **New root config**: a `[tool.coverage.run]`/`[tool.coverage.report]` section
  in root `pyproject.toml` (currently absent) to fix `source`/`branch`
  behavior consistently rather than relying on each engine's ad hoc CLI flags
  alone.

---

## 6. Existing engines — adoption priority

**First three, in this order** (not the order named in the prompt — reasoned
from the actual coverage data in §1.4/Project Health Review §17):

1. **`communication-engine`** — lowest total coverage today (65%), concentrated
   exactly in `repository/`/`workers/`/`clients/`/`channels/voice_adapter.py`:
   the real-infra-only code a Postgres fixture directly exercises. Highest
   marginal value of the three.
2. **`personality-engine`** — same simple one-migration Alembic shape, second
   priority.
3. **`perception-engine`** — newest engine, already highest domain coverage
   among the three (81% total / 99% domain per the Project Health Review),
   lowest marginal urgency, but explicitly named in task #93 and closes that
   backlog fully once done.

**Remaining seven, sequenced by persistence-footprint complexity and how many
other engines depend on their correctness**, after Redis/Neo4j fixtures exist
(§11):

4. **`memory-engine`** — Postgres + Redis (ADR-012: Redis as primary store, not
   cache — the most Redis-central engine, natural first Redis-fixture adopter).
5. **`knowledge-engine`** — Postgres + Neo4j (first Neo4j-fixture adopter).
6. **`world-model-engine`** — Postgres + Redis + Neo4j, the most complex
   persistence footprint; deliberately sequenced after both single-store
   adopters have proven the pattern.
7. **`ai-model-orchestration-engine`** — Postgres only, but with the most
   complex domain logic touching it (model registry, usage tracking).
8. **`reasoning-engine`** — Postgres + Redis.
9. **`executive-cognition-engine`** — Postgres + Redis.
10. **`nova-core`** — lightest persistence footprint (no engine-specific
    Postgres schema of consequence); last, and lowest priority.

---

## 7. CI

- **Docker availability**: GitHub-hosted `ubuntu-latest` runners ship Docker
  Engine pre-installed and running by default — a well-established property of
  GHA's standard runners, not something specific to this project. **This plan
  has not executed a real job against this project's actual GitHub Actions
  runner to confirm `testcontainers` works end-to-end here** — that
  confirmation is §11's task 0 (a spike, run on a real PR, before any fixture
  is trusted in the standard pipeline). Per the explicit instruction not to
  claim CI support before it's verified: **CI support is a design assumption
  in this plan, not a verified fact.**
- **Container startup time**: Postgres/Redis/NATS typically ready in
  low-single-digit seconds; Neo4j (JVM-backed) meaningfully slower, plausibly
  10–20s cold. Session/module-scoped containers (§2.4) amortize this to once
  per engine's test run, not once per test.
- **Resource consumption**: four containers simultaneously (worst case, an
  engine using all four) on a standard GHA runner (2 vCPU / 7 GB by default) is
  a real, non-trivial cost — mitigated by §3.5's per-engine-lazy-fixture
  design: no engine starts a container its own tests don't request.
- **Test isolation**: transaction-rollback for Postgres, explicit flush/delete
  for Redis/Neo4j, uniquely-prefixed subjects for NATS (§2.4) — chosen
  specifically to avoid container-per-test restart cost while still
  guaranteeing no cross-test leakage.
- **Cleanup after failure**: every fixture's teardown runs via `yield` (not a
  bare return), so `container.stop()` executes even when the test body raises
  — the same shape `event_bus` already proves works in this codebase.
- **Parallel jobs**: `pytest-xdist` is not used anywhere in this project today
  (confirmed) and this plan does not propose adopting it. If it is adopted
  later, `testcontainers`' random-port-per-container default (never hardcoded
  ports, §2.4) is what makes that safe — designed in from the start even
  though not exercised yet.
- **Caching**: lower priority; `postgres:16-alpine`/`redis:7-alpine`/
  `neo4j:5-community`/`nats:2-alpine` are common enough images that GHA
  runners likely already have them warm. Not a blocking concern for this plan.
- **Reproducibility**: every image tag is pinned (§3), matching this project's
  own existing compose-file convention — no `:latest` used for any of the four.
- **Where these tests run**: **not** inside the existing `pr-checks.yml`
  `turbo run test` step. A new, separate, explicitly-slower job/workflow is
  recommended (§11 task 10), gated the same way `16-testing-strategy.md §9`
  already plans E2E to be gated (merge-to-`main` + nightly, not every PR) —
  flagged as an open question in §15 since it's a real trade-off the user
  should confirm, not something this plan silently decides.

---

## 8. Local development workflow

Kept to the existing command shapes wherever possible — nothing new to learn for
the (already-supported) unit/fake-integration/full-suite cases:

| Goal | Command |
|---|---|
| Unit tests only, one engine | `uv run --package <name> pytest tests/unit` |
| Integration tests only (existing, fake-backed), one engine | `uv run --package <name> pytest tests/integration -m "not real_infra"` |
| Complete suite (unit + fake-integration + contract), one engine — **unchanged from today** | `uv run --package <name> pytest` (`package.json`'s existing `test` script) |
| One engine's full suite via Turborepo | `pnpm turbo run test --filter=@nova/<engine>` (existing) |
| Full real-infrastructure suite, one engine (**new**, requires local Docker) | `uv run --package <name> pytest -m real_infra` |
| Full real-infrastructure suite, whole repo (**new**, requires local Docker) | `pnpm turbo run test:real` (new turbo task, §11 task 10) |

`-m real_infra`/`-m "not real_infra"` requires registering the marker in root
`pyproject.toml`'s `[tool.pytest.ini_options]` (`markers = ["real_infra: ..."]`)
— a one-line config addition, §11 task 1.

---

## 9. Architecture boundaries

- **Zero engine-to-engine imports**: unaffected — this plan adds no new
  engine-to-engine coupling anywhere; it only adds fixtures inside
  `nova-testkit`, a package no engine's `src/` ever imports (only `tests/`
  does, and only as a dev-dependency, exactly as today).
- **Domain purity**: unaffected — `nova-testkit` is not a `domain/` package for
  any engine and was never subject to that rule; adding `testcontainers` here
  is exactly analogous to `nova-observability` or `nova-eventbus-sdk` carrying
  their own infra dependencies today.
- **Existing import-linter contracts**: unaffected by the four `root_packages`/
  `modules` contracts already in place (§6.4's `tools/scaffold-engine.py` fix
  from Step 1 already keeps these correctly populated per new engine).
- **New contract this plan recommends**: `nova-testkit must not import any
  engine's own top-level package` — mirroring the existing "no engine imports a
  message broker client directly" shape in `[tool.importlinter]`. This makes
  §2.3's "no reverse dependency" design decision a verified, CI-enforced fact
  rather than a convention someone could accidentally violate in a future PR.
- **Service independence**: preserved by construction — every new fixture is
  opt-in per test file (a test requests `postgres_engine` etc. as a parameter);
  no engine is forced to depend on infrastructure its own tests don't use
  (`communication-engine`'s tests never instantiate a Neo4j container).
- **Production dependency boundaries**: `nova-testkit` — including
  `testcontainers` and every new database-driver dependency — remains a
  `[dependency-groups] dev` dependency of every consuming engine, exactly as it
  is today (confirmed: every engine's `pyproject.toml` lists `nova-testkit`
  only under `dev`, never under `[project] dependencies`). It is never present
  in any engine's production Docker image. This plan does not change that
  convention; it depends on it continuing to hold, and the new import-linter
  contract above is one way to help guarantee it keeps holding.

---

## 10. Documentation consistency

### 10.1 What `16-testing-strategy.md` currently claims (verbatim, present tense)

- §1's pyramid table: "Integration (moderate) | Engine + real Postgres/Neo4j/
  Redis (via testcontainers)" — false today; today's "integration" tier is
  fake-repository-backed (§1.2).
- §1: "Enforced minimum coverage: 85% line coverage on `domain/`... checked in
  CI" — false today (§1.4/§5).
- §3: "`nova-testkit` provides `testcontainers`-backed fixtures: real Postgres,
  Neo4j, Redis, and an embedded NATS JetStream instance... `nova-testkit` also
  provides a `FakeModelGateway`..." — false today (§1.1/§1.3).
- §8: "`nova-testkit/fixtures/` provides canonical seed data..." — the
  directory does not exist (§1.1).
- §9: "Every PR must pass: lint → unit → integration → contract" — technically
  accurate today only because "integration" currently means the fake-backed
  tier; becomes misleading once a second, real-infra tier exists unless
  updated to distinguish them (§10.2).

### 10.2 Proposed update plan — incremental, not big-bang

Matching this project's own stated principle ("the testing-strategy
documentation must eventually match the implementation exactly," from the
user's own Step 2 framing) means updating the doc **once per implementation
milestone in §11**, not deferring every fix to one final rewrite that could
itself drift stale by the time it lands:

1. **With §11 task 1 (coverage gate)**: change §1's coverage line from
   present-tense "checked in CI" to a factual description of the new
   `--cov-fail-under=85` wiring, scoped `domain/`, per-engine.
2. **With §11 task 2 (`FakeModelGateway`)**: correct §3's `FakeModelGateway`
   paragraph to describe it accurately as an event-bus responder built on
   `event_bus`, not a `ModelConnector`-Protocol fake — and split it clearly
   from the testcontainers bullet above it, per §2.1's category distinction.
3. **With §11 task 3 (Postgres fixture foundation)**: change §3's testcontainers
   bullet from present-tense to describe exactly what exists (Postgres only,
   at that point), explicitly marking Neo4j/Redis/NATS as not-yet-built until
   their own tasks land.
4. **With each subsequent fixture task (4–9)**: extend §3 and §1's pyramid
   table incrementally — the pyramid table gains a **second** "Real-
   infrastructure integration" row, distinct from "Integration," each marked
   with which stores are covered so far.
5. **With §11 task 10 (CI wiring)**: rewrite §9 to state precisely which tier
   runs on every PR vs. merge-to-`main`/nightly, once that decision (§15 open
   question) is actually made and implemented — not before.
6. **Final pass**: once all nine fixture/engine tasks in §11 are done, a single
   proofreading pass over the whole document (not new content) to confirm no
   stray present-tense claims survived from before this plan started.

This list itself is the concrete deliverable for "eventually describes the
actual implementation" — each line above is one commit, paired with its
corresponding implementation task, independently reviewable.

---

## 11. Implementation sequence

Reordered from the prompt's example sequence: `FakeModelGateway` and coverage
enforcement need **no** infrastructure at all (§2.1, §5), so they are sequenced
first, ahead of any `testcontainers` work — cheapest, safest, and independently
valuable even if the Postgres/Neo4j/Redis/NATS work were paused indefinitely
after this plan is approved.

0. **Spike (research, not shipped code)**: in a Docker-capable environment,
   `pip install testcontainers[postgres,redis]` (and confirm whether an
   official `testcontainers.neo4j` module exists, or whether Neo4j also needs
   the generic `DockerContainer` fallback used for NATS in §3.4) and confirm
   the exact API surface this plan assumes. Output: a short findings note
   correcting any wrong assumption in §3, before any fixture is written.
1. **Coverage enforcement**: `--cov=<pkg>.domain --cov-fail-under=85` added to
   every engine's `test` script; root `[tool.coverage]` section; register the
   `real_infra` pytest marker. Independently verifiable: all 951 existing
   tests still pass; temporarily lowering one engine's domain coverage
   confirms the gate actually fails, then revert.
2. **`FakeModelGateway`**: new `nova_testkit.model_gateway` module + fixture,
   with its own unit tests inside `nova-testkit` itself, plus one proof-of-
   adoption in a real consuming engine (e.g. `reasoning-engine`, which already
   has `model_orchestration_client.py`).
3. **Postgres fixture foundation**: `nova_testkit.postgres`, the generic
   migration-runner (§2.3), verified against `nova-testkit`'s own throwaway
   synthetic table/migration — proven in isolation before any engine adopts it.
4. **`communication-engine` real-Postgres adoption** (§6, priority #1).
5. **`personality-engine` real-Postgres adoption** (§6, priority #2).
6. **Redis fixture** (`nova_testkit.redis`) + **`memory-engine` adoption**
   (§6, priority #4 — first Redis adopter).
7. **Neo4j fixture** (`nova_testkit.neo4j`) + **`knowledge-engine` adoption**
   (§6, priority #5 — first Neo4j adopter).
8. **`perception-engine` real-Postgres adoption** (§6, priority #3 — closes
   task #93 fully).
9. **NATS JetStream fixture** (`nova_testkit.nats`) + adoption by whichever
   engine's tests most benefit from real durable-stream/replay semantics
   (§15, open question — no engine's tests exercise `open_stream` today, so
   this may be lower urgency than its position in the prompt's example
   sequence suggests).
10. **CI integration**: new, separate, explicitly-slower workflow/job for
    `real_infra`-marked tests (§7, §15).
11. **Remaining engine adoption** (§6 priorities #6–#10:
    `world-model-engine`, `ai-model-orchestration-engine`, `reasoning-engine`,
    `executive-cognition-engine`, `nova-core`), each independently shippable.
12. **Final documentation consistency pass** (§10.2 step 6).

Each numbered item above is independently mergeable and independently
verifiable — none depends on a later item, and every engine-adoption item
depends only on its one prerequisite fixture, not on the full sequence
completing.

---

## 12. Risk assessment

| Risk | Mitigation |
|---|---|
| Flaky tests from container startup races | Readiness checks block on the *same* health signal each service's own compose healthcheck already uses (§3), not a fixed sleep; `wait_until` (already in `nova-testkit`) is the natural polling primitive to reuse for any check not already blocking internally. |
| Container startup failure (image pull, Docker unavailable) | Fixture setup raises loudly (§3.1); `real_infra`-marked tests are excluded from the default `pytest`/`turbo run test` invocation entirely, so a missing Docker daemon never breaks the standard, fast CI path — only the opt-in real-infra job. |
| Resource usage / CI runtime blow-up | §3.5's per-engine-lazy-fixture design: only the containers a given engine's tests actually request ever start; session/module scope amortizes startup cost; real-infra tests live in a separate, non-blocking job (§7). |
| Port collisions | `testcontainers` assigns random free host ports by default; every fixture reads the assigned port back from the container object, never hardcodes one (§2.4) — safe even under future parallel execution. |
| Test isolation / database state leakage | Transaction-rollback (Postgres), explicit flush/delete (Redis/Neo4j), uniquely-prefixed subjects (NATS) — chosen per-store based on what each store's own consistency primitives actually support (§2.4). |
| Network behavior differences (real vs. fake) | This is precisely the point of §4 — real-infra tests exist specifically to catch what fakes cannot represent (constraint violations, real transaction isolation, real query planner behavior); not a risk to mitigate away but the risk this whole plan exists to surface. |
| Provider emulation gaps in `FakeModelGateway` | Scoped explicitly to the *contract* (subject → typed reply payload), not provider-specific behavior — `FakeConnector` already proves this scoping is sufficient for `ai-model-orchestration-engine`'s own compliance suite (§1.3); the same scoping is reused, not reinvented. |
| Nondeterminism from real infra in CI | Every real-infra assertion targets structural/schema-level behavior (row exists, constraint raised, index used) per §4/§13, never timing- or ordering-sensitive assertions across containers — the same "structural verification, not exact-output matching" philosophy `16-testing-strategy.md §5` already establishes for agent-behavior testing, applied here to infrastructure testing. |
| `nova-testkit` becoming a reverse-dependency magnet (engine-specific knowledge creeping in) | §2.3's Alembic-config-path parameterization + §9's new import-linter contract make this both a design decision and an enforced one. |
| `nova-testkit`'s own CI needing Docker (bootstrapping problem, §16) | `nova-testkit`'s own tests for the new fixture modules are themselves `real_infra`-marked and excluded from its own fast default `pytest` run — `nova-testkit`'s existing fast lint/test path (currently 4 tests, ~0.1s) stays fast; only its own opt-in real-infra job needs Docker. |

---

## 13. Verification plan

"The container started" is explicitly **not** sufficient (per instruction).
Per fixture, minimum required verification once implemented:

- **Postgres**: a real engine's Alembic migrations applied end-to-end against
  the container from a blank database; a real `INSERT` through the actual
  repository class; a real `SELECT` confirming the exact row back; a real
  constraint (a FK or uniqueness constraint the migration actually declares)
  triggered and confirmed to raise the expected exception, not silently
  accepted as a fake repository would.
- **Redis**: a real `SET`/`GET` round trip through the actual repository code
  path (not the raw client directly) confirming the engine's own
  serialization/TTL logic behaves against a real server, plus one expiry-based
  test confirming a key that should expire actually does.
- **Neo4j**: a real Cypher write through the actual graph-store adapter,
  confirming a node/relationship exists via a real read query — including one
  test exercising an APOC-dependent code path, since APOC is enabled in
  production (compose) and must be confirmed enabled in the test container too
  (§3.2).
- **NATS**: a real publish through the `NatsEventBus` backend connected to the
  container, confirmed received by a real subscriber in a separate connection
  — and, distinctly, one durable-stream test (`open_stream`) confirming a
  message published *before* a subscriber connects is still delivered once it
  does, which is exactly the behavior `InMemoryEventBus` cannot represent and
  the reason a real NATS fixture has standalone value beyond request/reply.
- **`FakeModelGateway`**: a real event-bus `request()` call from a consuming
  engine's own client class (e.g. `ModelOrchestrationClient.generate(...)`,
  unmodified production code) against the fake gateway, confirming the
  client's own payload-parsing/timeout logic works against a scripted reply —
  proving the fake is a drop-in for the real event contract, not just
  "returns some payload."

Every one of these produces a pass/fail pytest assertion, runnable and
re-runnable — this is what "genuine integration testing" means in this plan,
not a smoke test that merely confirms a process is listening on a port.

---

## 14. Documentation and ADRs

**Recommend one new ADR** (next available number: **ADR-033**), covering two
permanent rules this plan establishes that are not yet written down anywhere:

1. Shared test-infrastructure packages (`nova-testkit`) may depend on real
   backing-store client libraries and `testcontainers` as **dev-only**
   dependencies, without that ever becoming a production dependency of any
   engine, and without `nova-testkit` ever importing engine-specific code
   (§2.3, §9) — the general version of the design decision this plan makes
   for four specific stores, worth encoding once so a future fifth store
   (or a future shared package with a similar shape) doesn't have to
   rediscover it.
2. "Integration test" in this project has two distinct tiers going forward —
   fake-backed (default, PR-gating) and real-infrastructure (`testcontainers`-
   backed, opt-in/separately-gated, §7) — and this split, not a single
   "integration" tier, is the permanent taxonomy, not a temporary state until
   real infra "replaces" the fakes. The fake-backed tier remains valuable
   (fast, no Docker dependency, exercises real routing/domain logic) even
   after every engine has real-infra coverage too.

Not recommending an ADR for the coverage-gate wiring, the `FakeModelGateway`'s
internal shape, or any single fixture's specific implementation — those are
implementation details within the boundary the one recommended ADR would set,
not new permanent rules of their own.

---

## 15. Open questions (for the user, not decided by this plan)

1. **Real-infra CI gating**: every PR (accepting Docker-in-Docker as a
   permanent CI cost) vs. merge-to-`main` + nightly vs. opt-in PR label? This
   plan's working assumption (§7) is merge/nightly, matching how E2E is
   already planned to be gated — but it's a real trade-off, not a foregone
   conclusion.
2. **NATS fixture priority**: no engine's tests exercise JetStream durable-
   stream/replay semantics today, so real value is speculative until a
   concrete use case is named — worth deprioritizing further than task 9's
   position, or fine as sequenced?
3. **`testcontainers-python`'s exact Neo4j module availability** (§3.2, §11
   task 0) is an assumption, not a verified fact, in this environment.
4. **The new ADR** (§14) — approve, decline, or amend before implementation
   begins?
5. **`pytest-xdist`**: not proposed here (current suite runtime is fast, ~20s
   aggregate across all 17 packages); confirm this project agrees parallel
   test execution isn't needed yet, separate from the random-port design
   choice (§2.4) that would make adopting it later safe regardless.

---

## Summary: exact files/packages expected to change (once approved)

- `packages/nova-testkit/pyproject.toml` — new dependencies: `testcontainers`
  (+ relevant extras), `asyncpg`, `redis`, `neo4j` driver.
- `packages/nova-testkit/src/nova_testkit/model_gateway.py` — new.
- `packages/nova-testkit/src/nova_testkit/postgres.py` — new.
- `packages/nova-testkit/src/nova_testkit/redis.py` — new.
- `packages/nova-testkit/src/nova_testkit/neo4j.py` — new.
- `packages/nova-testkit/src/nova_testkit/nats.py` — new.
- `packages/nova-testkit/src/nova_testkit/fixtures.py` — new (canonical seed
  data, §2.4).
- `packages/nova-testkit/src/nova_testkit/plugin.py` — extended entry-point
  registration for the new fixtures.
- `packages/nova-testkit/tests/` — new tests per module, `real_infra`-marked
  where they need Docker (§12's bootstrapping mitigation).
- `pyproject.toml` (root) — `real_infra` marker registration; `[tool.coverage]`
  section; new `nova-testkit`-boundary import-linter contract (§9).
- Every engine's `package.json` — `test` script gains `--cov` flags (10 files).
- `communication-engine`, `personality-engine`, `perception-engine`,
  `memory-engine`, `knowledge-engine`, `world-model-engine`,
  `ai-model-orchestration-engine`, `reasoning-engine`,
  `executive-cognition-engine`, `nova-core` — new `tests/integration/
  test_repository_real_*.py` files, progressively, per §11/§6.
- `.github/workflows/` — a new workflow (or a new job in an existing one) for
  the `real_infra` tier, per §7/§15 item 1.
- `docs/architecture/16-testing-strategy.md` — incremental edits per §10.2,
  one per implementation milestone.
- `docs/architecture/adr/ADR-033-<title>.md` — new, if approved (§14).

**Nothing in this list has been created or modified. This document is the plan
only, per explicit instruction.**
