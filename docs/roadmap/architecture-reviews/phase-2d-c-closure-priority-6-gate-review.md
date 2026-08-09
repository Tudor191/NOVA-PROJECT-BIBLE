# Phase 2D-C Closure — Priority 6 Gate Review: real-infrastructure fixes

**Status: NOT complete.** Both root-caused fixes from the approved proposal
are implemented, committed, and pushed, and pass full local verification.
**The post-fix real-infrastructure GitHub Actions result is not yet
available** — `workflow_dispatch` is blocked in this environment (§4), and
this review does not claim the fixes are confirmed against real
infrastructure until that run has actually happened and been inspected, per
explicit instruction. This document will be updated once that result exists;
until then, Priority 6 is not to be treated as closed.

---

## 1. The two original failures (recap of the approved proposal)

From `phase-2d-c-closure-priority-6-proposal.md` §5, both observed in the one
real `real-infra-checks.yml` run that existed before this pass
(run `31296349533`, nightly `schedule` trigger, 2026-08-09):

1. `personality-engine::test_update_memory_profile_persists_and_advances_updated_at`
   failed with `sqlalchemy.exc.MissingGreenlet`.
2. `nova-testkit::test_real_request_reply` failed an assertion: the reply
   payload was the full inner envelope instead of `{"question": "ping"}`.

## 2. Confirmed root causes and exact fixes

### 2.1 `personality-engine` — repository/code blocker

**Root cause:** `MemoryProfileORM.updated_at` is `mapped_column(DateTime(timezone=True),
server_default=func.now(), onupdate=func.now())`. Because `onupdate` is a
SQL-side expression, SQLAlchemy's async ORM marks it expired after
`flush()`. `PostgresPersonalityRepository.update_memory_profile` called the
plain synchronous `_profile_to_domain(row)` — which reads `row.updated_at` —
immediately after `flush()` without `await`ing a refresh first. Touching the
expired attribute triggered an implicit reload outside the greenlet-bridged
context async SQLAlchemy requires, raising `MissingGreenlet`.

**Fix** (`services/personality-engine/src/nova_personality_engine/repository/postgres_personality_repository.py`):

```python
row.source = profile.source
await session.flush()
await session.refresh(row)          # added
return _profile_to_domain(row)
```

This is not a new pattern: `await session.flush(); await session.refresh(orm)`
immediately before converting to a domain object is the existing convention
already used by `memory-engine`, `world-model-engine`, `knowledge-engine`,
`communication-engine`, and `perception-engine`'s own repository layers
(confirmed by grep across all five before writing this fix — 12 call sites).
`personality-engine`'s `update_memory_profile` was the one write path that
had drifted from that convention; nothing about the repository was
redesigned, and no other method was touched.

**Regression coverage:** the existing real-infra test
`test_update_memory_profile_persists_and_advances_updated_at`
(`services/personality-engine/tests/integration/test_repository_real_postgres.py:85`)
already asserts `updated.updated_at >= before.updated_at` on the exact return
value that previously crashed — it is the test that caught this failure in
the first place, and it is left unmodified because it already is the correct
regression guard: if `session.refresh(row)` is ever removed, this test will
raise `MissingGreenlet` again on the next real-Postgres run. No fake-backed
equivalent is meaningful here — `tests/fakes/repository.py`'s fake has no
ORM attribute-expiry model to reproduce, which is exactly why this defect
was invisible until real-infrastructure testing existed (see the proposal's
§5.1 for why this is a currently-dormant, never-yet-called code path,
reserved for a Phase 2D-D caller).

### 2.2 `nova-testkit` — test-design blocker

**Root cause:** `test_real_request_reply`'s handler returned the full
received `EventEnvelope` instead of a payload `BaseModel`, violating the
`RequestHandler` contract (`nova_eventbus_sdk.interface`: "Returns the reply
payload... the handler never constructs a reply envelope... itself").
Because `EventEnvelope` is itself a `BaseModel`, this type-checked but caused
`serve()` to re-wrap the entire envelope as the reply's payload. Confirmed
before fixing that `NatsEventBus.serve()` and `InMemoryEventBus.serve()`
implement this exactly the same way — an `InMemoryEventBus`-backed test
written the same way would fail identically, so this was never a NATS-only
defect.

**Fix** (`packages/nova-testkit/tests/test_nats.py`): added a small
`_Echo(BaseModel)` with one field (`question: str`), matching the same
ad-hoc-payload-model idiom `nova-eventbus-sdk`'s own fast-tier request/reply
tests already use (`tests/test_in_memory_backend.py`'s `_Ping(BaseModel)`),
and changed the handler to construct and return it from `envelope.payload`
instead of returning `envelope`:

```python
class _Echo(BaseModel):
    question: str

async def handler(envelope: EventEnvelope) -> _Echo:
    return _Echo(**envelope.payload)
```

The test's own assertion, `assert reply.payload == {"question": "ping"}`, is
**unchanged** — the fix makes the handler honor the contract the assertion
was always written against, rather than loosening what the test checks. No
NATS-specific workaround was introduced; the fix is backend-agnostic (it
would pass identically against `InMemoryEventBus`).

## 3. Local verification performed

Both fixes are covered by the same verification sequence used for every
prior priority in this closure effort:

| Check | Command / scope | Result |
|---|---|---|
| Workspace sync | `uv sync --all-packages --frozen` | Clean, 117 packages audited |
| Import-linter | `uv run lint-imports` | **6/6 contracts kept**, 0 broken |
| Lint (ruff + mypy) | `pnpm turbo run lint` (all 18 packages) | **18/18 passed** |
| Fast-tier tests | `pnpm turbo run test --force` (all 18 packages) | **18/18 passed**, 0 failures |
| Coverage gate negative control (personality-engine) | `pytest -m "not real_infra" --cov=nova_personality_engine.domain --cov-fail-under=100` | **Exit 1**, `FAIL Required test coverage of 100% not reached. Total coverage: 99.22%` — same pre-existing single uncovered `validator.py` line noted in the Priority 5 Gate Review, nothing new introduced by this pass; the gate genuinely enforces |
| nova-testkit fast-tier | `pytest -m "not real_infra"` | 14 passed, 11 deselected |
| docker-compose config | `docker compose -f infra/docker/docker-compose.local.yml config --quiet` | Valid, no error |
| TypeScript contract generation | `generate_typescript.py` re-run | **Zero diff** — `nova-contracts` was not touched by either fix |
| `git diff` review | Full diff read before commit | Exactly 2 files changed, 13 insertions / 2 deletions, no unrelated changes |

**Not run locally:** neither real_infra suite (`personality-engine`'s or
`nova-testkit`'s) could be executed in this session — re-confirmed no
reachable Docker daemon here (`docker info` fails to connect;
`/var/run/docker.sock` does not exist), identical to every prior priority in
this closure effort. This is the same, already-documented external
limitation of this interactive session, not a new blocker. It is exactly why
the GitHub Actions run is the only source of a genuine result for these two
fixes.

## 4. Attempted GitHub Actions re-run — exact blocker

Both fixes were committed and pushed to `claude/new-session-e1cseg`
(commit `4007e44`), which is confirmed via the GitHub API to be **this
repository's default branch** (`default_branch: "claude/new-session-e1cseg"`)
— the same branch `real-infra-checks.yml`'s `schedule` trigger already runs
against.

An explicit attempt was made to dispatch `real-infra-checks.yml` via its
`workflow_dispatch` trigger, to get a result without waiting for the next
nightly firing:

```
POST /repos/Tudor191/NOVA-PROJECT-BIBLE/actions/workflows/real-infra-checks.yml/dispatches
→ 403 "Resource not accessible by integration"
```

**Classification:** permission/access blocker — this session's GitHub
integration token does not carry the `actions:write` scope required to
trigger a manual dispatch. This is a human-action item (a broader permission
grant, or a manual dispatch performed by someone with sufficient repository
access through the GitHub UI directly), **not** a repository change, and per
explicit instruction no CI permission was altered to work around it.

**No fallback substitute was used.** No real_infra test was run against a
fake backend, no test was skipped or reclassified, and no result is claimed
here that has not actually happened. Per instruction, this workflow result is
left unclaimed.

**What happens next without further action:** because `claude/new-session-e1cseg`
is the default branch, `real-infra-checks.yml`'s nightly `schedule` trigger
(`17 4 * * *` UTC) will run against these exact fixes automatically at its
next firing — no dispatch, PR, or additional push is required for that to
happen.

## 5. Current, honest status of all 34 real_infra tests

| Package | Real_infra tests | Status as of this pass |
|---|---|---|
| `communication-engine` | 11 | Confirmed passing for real (unchanged by this pass; run `31296349533`) |
| `perception-engine` | 7 | Confirmed passing for real (unchanged by this pass; run `31296349533`) |
| `personality-engine` | 5 | 4 confirmed passing (run `31296349533`); the 5th (`test_update_memory_profile_persists_and_advances_updated_at`) has a fix implemented and locally lint/type/import-verified, but **not yet re-run against real Postgres** |
| `nova-testkit` | 11 | 10 confirmed passing (run `31296349533`); the 11th (`test_real_request_reply`) has a fix implemented and locally lint/type/import-verified, but **not yet re-run against real NATS** |
| **Total** | **34** | **32 confirmed passing for real; 2 fixed but unconfirmed pending the next CI run** |

This table will not read "34/34 confirmed" until a fresh
`real-infra-checks.yml` run against commit `4007e44` (or later) has been
inspected.

## 6. Remaining limitations

- The two fixes have full local static verification (lint, types, import
  boundaries, fast-tier tests, coverage gate) but no real-infrastructure
  execution evidence yet — this is the single open item blocking Priority 6
  closure.
- This session cannot manually dispatch the workflow (§4); obtaining a result
  sooner than the next nightly firing requires either a permission grant to
  this session's GitHub integration or a manual dispatch by someone with
  sufficient repository access.
- As previously documented, run-to-run flakiness of the real_infra suite
  remains unestablished beyond the one execution that exists — a second data
  point (this pass's eventual run) will be the first opportunity to observe
  run-to-run stability at all.

## 7. Compliance with this phase's constraints

No real_infra test was weakened, skipped, reclassified, or converted to a
fake-backed test. No test assertion was loosened. No production code beyond
the one documented line was touched. No CI workflow file was modified. No
GitHub permission was changed (the 403 was reported, not routed around).
Phase 2D-D was not started. No other Phase 2D-C priority was touched. The
stale task-tracker entries were not updated, consistent with no explicit
process requirement to do so. `git diff` was reviewed in full before
committing (§3) and contains exactly the two approved files.

**Priority 6 remains open pending the next `real-infra-checks.yml` result.**
This Gate Review will be updated with that result once available; Phase 2D-D
will not begin until the user reviews that update and gives explicit
approval.
