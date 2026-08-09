# Phase 2D-C Closure — Priority 6: Real-Infrastructure Verification Gap

**Status:** Research/Proposal — awaiting approval. No production code, tests, CI
workflows, or GitHub permissions were modified to produce this document.

**Scope of this document:** answer the 12 research questions the closure
review's Priority 6 posed, using direct inspection of current code, workflows,
compose files, tests, and the GitHub repository's actual state (not prior Gate
Reviews) — then classify every blocker found and determine the smallest
legitimate path to a real execution result. No implementation is proposed or
performed here.

---

## 0. Executive summary

**The real-infrastructure test tier has already executed for real, on a real
GitHub Actions runner, against real Postgres/Redis/Neo4j/NATS containers —
this happened autonomously, once, via `real-infra-checks.yml`'s nightly
`schedule` trigger, which fired for the first time on 2026-08-09 (the workflow
was created 2026-08-08).** This is not a hypothetical or a dry run; it is a
completed, inspectable GitHub Actions run
([31296349533](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/31296349533))
with real logs.

Result: **32 of 34 real_infra tests passed for real.** The other 2 failed for
two distinct, fully diagnosed reasons — one is a genuine (currently dormant,
never-yet-called) production-code defect in `personality-engine`; the other is
a test-design defect in a `nova-testkit` test itself, not in any production
backend. Neither failure is a CI/workflow, infrastructure, or permissions
problem. Both are explained in full in §5.

This overturns the premise that motivated Priority 6's research question
("the exact reason the suite remains unexecuted today"): **the suite is no
longer unexecuted.** The question this document actually answers is what the
first real execution found, and what — if anything — a repository change
would need to do next. No architectural or CI-configuration fork exists to
present; see §7 for why.

The stale "29 real_infra tests" figure the closure review cited is also
addressed (§3): the true, currently-verified count is **34**, confirmed two
independent ways (static collection and the actual CI run's own reported
counts, which agree exactly).

---

## 1. Test inventory (Q1, Q9)

Verified by running `pytest <path> -m real_infra --collect-only` separately
per package (see §4's note on why "separately" is required), and cross-checked
against the real CI run's own `collected N items / M deselected / K selected`
lines:

| Package | real_infra tests | Total tests | Source file(s) |
|---|---|---|---|
| `communication-engine` | 11 | 125 | `tests/integration/test_repository_real_postgres.py` |
| `perception-engine` | 7 | 121 | `tests/integration/test_repository_real_postgres.py` |
| `personality-engine` | 5 | 59 | `tests/integration/test_repository_real_postgres.py` |
| `nova-testkit` | 11 | 25 | `tests/test_postgres.py`, `tests/test_redis.py`, `tests/test_neo4j.py`, `tests/test_nats.py` |
| **Total** | **34** | | |

All four packages' counts are independently confirmed by the CI run itself
(§4), which is strictly stronger evidence than static collection alone —
it proves these tests not only collect correctly but actually execute.

## 2. Infrastructure dependencies and isolation (Q2, Q7, Q8, Q10)

Re-confirmed by direct reading of all four `nova-testkit` fixture modules
(`postgres.py`, `redis.py`, `neo4j.py`, `nats.py`) and now also by the real
run's logs:

- **Postgres** (`postgres:16-alpine` via `testcontainers`): session-scoped
  container, per-engine Alembic migration run once via `run_alembic_upgrade`,
  per-test isolation via an outer transaction + `SAVEPOINT` rollback
  (`join_transaction_mode="create_savepoint"`). The real run confirms Alembic
  actually applies migrations against a real throwaway Postgres instance
  (`alembic/config.py` deprecation warning visible in the logs is cosmetic,
  not a failure).
- **Redis** (`redis:7-alpine`): session-scoped container, `FLUSHDB`
  before/after each test.
- **Neo4j** (`neo4j:5-community`, APOC enabled): session-scoped container,
  `DETACH DELETE` before/after each test.
- **NATS** (`nats:2-alpine`, JetStream via `-js`): session-scoped container;
  no built-in isolation primitive (subject namespacing is each test's own
  responsibility, matching `nova-eventbus-sdk`'s own subject-naming
  convention).

None of this depends on `infra/docker/docker-compose.local.yml` — confirmed
again by inspection and now also by the real run, which never invokes
`docker compose` at all; `testcontainers` starts its own independent,
throwaway containers directly against the Docker daemon. `docker-compose.local.yml`
is a separate full-stack local-dev artifact; `pr-checks.yml` only validates its
syntax (`docker compose ... config --quiet`), never runs it.

No pytest-xdist or other parallel-execution configuration exists anywhere in
the repo (re-confirmed by grep), so there is no cross-test race-condition
surface from parallelism. The one run available shows no ordering-sensitive or
flaky-looking behavior: both failures are deterministic logic defects (§5),
not timing-dependent ones.

## 3. The "29 vs 34" discrepancy (context for Q1)

The closure review's "29 real_infra tests" figure traces to
`docs/roadmap/architecture-reviews/step3-nova-service-kit-extraction-gate-review.md`
line 242 — a STEP3-era snapshot that predates `perception-engine`'s real_infra
suite (added in Phase 2D-B, STEP 2.12, after STEP3 was written). The actual
current count, confirmed both statically and by the real CI run itself
(§1, §4), is **34**. This document uses 34 throughout; nothing in this
finding requires any repository change — it is a documentation-staleness
observation only, and no doc other than this one is touched here per the "no
unrelated cleanup" instruction.

## 4. The real execution: what actually happened (Q6, Q11, Q12)

`real-infra-checks.yml`'s triggers are `pull_request`, `push` to `main`,
`schedule` (`17 4 * * *`), and `workflow_dispatch`. Direct GitHub API
inspection (`list_workflow_runs`, `list_pull_requests`, `list_branches`) shows:

- **Zero pull requests have ever been opened** on this repository (confirmed
  via `list_pull_requests(state="all")` → empty).
- **Only one branch exists** (`claude/new-session-e1cseg`, unprotected) — there
  is no `main` branch, so the `push: branches: [main]` trigger has never had
  anything to fire against.
- **`pr-checks.yml`** (triggers: `pull_request`, `push: branches: [main]`) has
  correspondingly **never run** (`list_workflow_runs` → `total_count: 0`).
  This is expected given the above, not a defect.
- **`real-infra-checks.yml`** has **run exactly once**, `run_number: 1`,
  triggered by `event: "schedule"`, `created_at: 2026-08-09T05:16:58Z`,
  `conclusion: "failure"` (2 of its 4 matrix jobs failed; see below).
  This is the workflow's first-ever nightly firing since its creation the
  previous day.

This single run is the answer to Q11 ("the exact reason the suite remains
unexecuted today"): **it doesn't remain unexecuted.** The premise was correct
at the time the closure review was written (no PR, no push-to-main, and the
nightly cron had not yet fired); it is no longer correct as of this run. This
session's own local Docker-daemon unavailability (re-confirmed fresh: no
`/var/run/docker.sock`, no init managing one) was never the actual blocker —
it only blocks running the suite **from within this specific interactive
coding session**, not from GitHub Actions, which provisions its own
Docker-capable runner independent of this session entirely.

**Per-job results** (`list_workflow_jobs` on run `31296349533`), all four on
`ubuntu-latest`:

| Job | `docker info` step | Test step | Result |
|---|---|---|---|
| `communication-engine` | success | success | **11 passed**, 114 deselected |
| `perception-engine` | success | success | **7 passed**, 114 deselected |
| `personality-engine` | success | failure | 4 passed, **1 failed**, 54 deselected |
| `nova-testkit` | success | failure | 10 passed, **1 failed**, 14 deselected |

Every job's "Confirm Docker daemon is reachable" step succeeded — this is the
concrete, empirical answer to Q6/Q12: **a stock `ubuntu-latest` GitHub-hosted
runner's pre-installed Docker Engine is sufficient.** No custom runner, no
extra setup step, no secrets, and no non-default `permissions:` block were
needed; the workflow used only the default `GITHUB_TOKEN` (implicit, for
`actions/checkout`) and required no explicit `permissions:` grant because it
neither writes to the repository nor calls any privileged API. This resolves
the single largest open uncertainty the prior (pre-this-session) fixture
docstrings flagged as "NOT YET VERIFIED against a real GitHub Actions runner."

`real-infra-checks.yml` is (correctly, by design) non-blocking: it has no
branch-protection requirement, and none could exist yet regardless, since no
branch protection rule exists on this single-branch repository. The
`conclusion: "failure"` on this run did not block anything, consistent with
its intended staged-rollout role.

## 5. Root-cause diagnosis of the 2 failures

Both failures were fetched from the actual job logs (`get_job_logs`) and
traced to their exact source lines. Neither is a flaky/ordering issue —
both are deterministic and will reproduce on every run until fixed.

### 5.1 `personality-engine`: real production-code defect

`tests/integration/test_repository_real_postgres.py::test_update_memory_profile_persists_and_advances_updated_at`
fails with:

```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call
await_only() here. Was IO attempted in an unexpected place?
```

Root cause, traced through `src/nova_personality_engine/repository/postgres_personality_repository.py`:

```python
async def update_memory_profile(self, profile: MemoryProfile) -> MemoryProfile:
    async with self._session_factory() as session, session.begin():
        row = await session.get(MemoryProfileORM, 1)
        ...
        await session.flush()
        return _profile_to_domain(row)   # <-- reads row.updated_at synchronously
```

`MemoryProfileORM.updated_at` is declared
(`repository/models.py`) as `mapped_column(DateTime(timezone=True),
server_default=func.now(), onupdate=func.now())`. Because `onupdate` is a
SQL-side expression rather than a Python value, SQLAlchemy's async ORM marks
`updated_at` **expired** after `flush()` — its real value is only known once
re-fetched from Postgres. `_profile_to_domain(row)` is a plain synchronous
function (not `await`ed), so when it touches the expired `row.updated_at`
attribute, SQLAlchemy attempts an implicit reload **outside** the
greenlet-bridged context that async SQLAlchemy requires for any such
DB-touching access — hence `MissingGreenlet`.

This is a **real, 100%-reproducible defect in production code**, invisible to
every existing fake-backed test because `tests/fakes/repository.py`'s fake
repository has no ORM attribute-expiry model to reproduce it. It has never
been observed in real production traffic only because, per
`domain/ports.py`'s own docstring, `update_memory_profile` currently has **no
caller anywhere in this codebase** — it's reserved for a future Phase 2D-D
`digital-twin-engine` integration. This is precisely the class of defect
real-infrastructure testing exists to catch before a caller exists, not after.

### 5.2 `nova-testkit`: test-design defect, not a backend defect

`tests/test_nats.py::test_real_request_reply` fails an assertion:
`reply.payload` is the full inner `EventEnvelope` dict instead of the expected
`{"question": "ping"}`.

Root cause: the test's own handler violates the shared `RequestHandler`
contract that **both** `NatsEventBus.serve()` and `InMemoryEventBus.serve()`
implement identically:

```python
async def handler(envelope: EventEnvelope) -> EventEnvelope:
    return envelope    # returns the whole received envelope, not a payload model
```

Both backends' `serve()` implementations call `reply_payload.model_dump(mode="json")`
on whatever the handler returns and use that as the reply's `payload` field
(confirmed by reading `nova_eventbus_sdk/backends/nats.py` and
`backends/in_memory.py` side by side — the two implementations are
line-for-line equivalent in this respect). Because `EventEnvelope` is itself a
`BaseModel`, returning it type-checks, but its `.model_dump()` serializes the
*entire envelope* (including its own nested `payload` field) into the reply's
`payload` field — producing exactly the double-wrapped shape the failure
shows. An `InMemoryEventBus`-backed test written the same way would fail
identically; this is not something real NATS does differently from the fake
backend, and nothing else in the `EventBus` contract is implicated.

This is a **test-design defect** in
`packages/nova-testkit/tests/test_nats.py`, not a defect in `NatsEventBus`,
`InMemoryEventBus`, or any other production code.

---

## 6. Blocker classification (required taxonomy)

| # | Blocker | Category | Requires |
|---|---|---|---|
| 1 | `personality-engine`'s `update_memory_profile` raises `MissingGreenlet` against real Postgres (§5.1) | **Repository/code blocker** | Code change |
| 2 | `nova-testkit`'s `test_real_request_reply` handler doesn't conform to the `RequestHandler` contract (§5.2) | **Test-design blocker** | Test change |
| 3 | This interactive coding session has no reachable Docker daemon | **External limitation of this session** | No repository change — GitHub Actions already provides a working alternative (§4) |
| 4 | `pr-checks.yml` and `real-infra-checks.yml`'s `pull_request`/`push:main` triggers have never fired (no PR, no `main` branch) | Not a blocker to real-infra verification — the `schedule` trigger already produced a genuine result independent of these paths | No repository change required for a first result; opening a PR or creating `main` would additionally exercise the `pull_request` trigger path, but is a repository-topology decision outside Priority 6's scope |

No **CI/workflow configuration blocker**, **infrastructure/environment
blocker**, or **permission/access blocker** was found. Specifically:
`real-infra-checks.yml`'s trigger set, matrix, steps, and Docker-availability
assumption are all confirmed correct and sufficient by the run in §4 — no
change to that file is indicated.

## 7. Fork determination: none found

The instructions require presenting alternatives with a recommendation if the
research reveals an architectural or implementation fork. It does not: every
question resolved to a single, evidence-backed answer, and both failures
decompose cleanly into "needs a code fix" (§5.1) and "needs a test fix"
(§5.2) — neither has a genuine design alternative to weigh. There is no
plausible second reading of `MissingGreenlet` under `onupdate=func.now()`, and
no plausible second reading of a handler that returns the wrong Pydantic
model. Per the hard constraint against modifying production code or tests in
this phase, this document stops at diagnosis and does not propose or perform
either fix.

## 8. Smallest legitimate path to a genuinely green result for all 34

1. Fix `PostgresPersonalityRepository.update_memory_profile` so it doesn't
   read an expired server-computed column outside an awaited context (e.g.
   `await session.refresh(row)` after `flush()`, or an equivalent that keeps
   the read inside the async-bridged path) — a `personality-engine`
   production-code change.
2. Fix `test_real_request_reply`'s handler in `nova-testkit` to return a
   payload model whose `model_dump()` matches what the test asserts, instead
   of echoing the full received `EventEnvelope` — a `nova-testkit` test-only
   change.
3. Either wait for the next nightly `schedule` firing or trigger
   `real-infra-checks.yml` manually via `workflow_dispatch` to obtain a fresh,
   fully-green run.

No CI, permissions, or infrastructure change is needed for step 3 — the
existing workflow already does everything required, as proven by the run this
document analyzes. Both fixes are implementation work requiring explicit
approval and are **not performed by this document**.

---

## 9. What is verifiable now, what remains unverified, and the exact next action

**Currently verifiable, with direct evidence obtained in this session:**
- The real-infrastructure test tier executes for real on GitHub-hosted
  `ubuntu-latest` runners, with no extra configuration.
- 32 of 34 real_infra tests pass against real Postgres, Redis, Neo4j, and NATS
  containers.
- Both current failures have a confirmed, non-speculative root cause, each
  isolated to a single file and a single defect.
- `docker-compose.local.yml` is confirmed unrelated to this test tier.
- No CI/workflow, infrastructure, or GitHub-permissions blocker exists.

**Genuinely unverified:**
- Whether the suite is flake-free across multiple runs — only one execution
  exists to date, so run-to-run stability (as opposed to within-run
  correctness, which is well evidenced) is not yet established.
- Behavior of the `pull_request`-triggered path specifically, since no PR has
  ever existed to exercise it (the `schedule` path is confirmed instead).
- Whether `update_memory_profile` and its equivalents behave correctly once
  actually fixed — that requires the fix itself, which is out of scope here.

**Exact next action required to obtain a fully green execution result:**
implement the two fixes in §8 (each requires separate explicit approval, as
they are production-code and test changes respectively, both outside this
research-only phase's permitted scope), then either await the next nightly
run or dispatch the workflow manually.

---

## 10. Compliance with this phase's constraints

No real_infra test was weakened, skipped, reclassified, deselected, or
converted to a fake-backed test. No production code was modified. No test was
modified. No CI workflow was modified. No GitHub permission was changed. Phase
2D-D was not started. No unrelated cleanup was performed. This document is the
only artifact produced by Priority 6 research.
