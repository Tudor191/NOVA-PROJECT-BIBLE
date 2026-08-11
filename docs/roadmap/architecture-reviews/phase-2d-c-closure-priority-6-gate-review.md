# Phase 2D-C Closure — Priority 6 Gate Review: real-infrastructure fixes

**Status: COMPLETE — 34/34 real_infra tests confirmed passing on real
GitHub Actions infrastructure.** The scheduled nightly `real-infra-checks.yml`
run (`31461343807`, 2026-08-11T05:20:55Z, against commit `9a81238`) executed
and was inspected in full (§10) — every job's actual test output, not just
job status. All four matrix jobs passed for real: `communication-engine`
(11/11), `perception-engine` (7/7), `personality-engine` (5/5, including the
previously-failing `update_memory_profile` test), and `nova-testkit` (11/11,
including `test_real_request_reply`, with the Pydantic `ValidationError`
confirmed absent from the log). Both root-caused defects from this priority
(§2.1, §8) are now proven fixed against real Postgres, real NATS, and every
other real backing store this suite exercises — not merely locally plausible.

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

## 4. GitHub Actions re-run — dispatch blocker, then the scheduled result

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
explicit instruction no CI permission was altered to work around it. No
fallback substitute was used; no result was claimed at that time.

**The nightly `schedule` trigger then fired on its own** (no action needed,
as predicted): run `31359464265`, `run_number: 2`, `event: "schedule"`,
`created_at: 2026-08-10T05:42:47Z`, against `head_sha: cce5626` (the Gate
Review commit, which includes both fixes from `4007e44`). All four jobs'
"Confirm Docker daemon is reachable" steps succeeded again, consistent with
the first run.

### 4.1 `personality-engine` — confirmed fixed

Job `93365293712`: **success**. Full log:

```
tests/integration/test_repository_real_postgres.py::test_get_core_identity_returns_the_real_migration_seeded_row PASSED
tests/integration/test_repository_real_postgres.py::test_get_memory_profile_returns_the_real_migration_seeded_default PASSED
tests/integration/test_repository_real_postgres.py::test_update_memory_profile_persists_and_advances_updated_at PASSED
tests/integration/test_repository_real_postgres.py::test_record_validation_audit_persists_a_real_row PASSED
tests/integration/test_repository_real_postgres.py::test_core_identity_singleton_check_constraint_is_enforced PASSED
5 passed, 66 deselected, 2 warnings in 10.21s
```

The specific test that raised `MissingGreenlet` in run `31296349533` now
passes against real Postgres. §2.1's fix is confirmed, not merely locally
plausible.

### 4.2 `nova-testkit` — still fails, distinct root cause found

Job `93365293691`: **failure**, but not the original failure. Full traceback:

```
FAILED tests/test_nats.py::test_real_request_reply - TimeoutError: No reply on 'testkit.rpc.echo' within 2000ms
```

Following the traceback: `nc.request()` timed out because the `serve()`
callback itself raised before it could publish a reply:

```
File "packages/nova-eventbus-sdk/src/nova_eventbus_sdk/backends/nats.py", line 146, in _callback
    reply_payload = await handler(envelope)
File "packages/nova-testkit/tests/test_nats.py", line 61, in handler
    return _Echo(**envelope.payload)
pydantic_core._pydantic_core.ValidationError: 1 validation error for _Echo
question
  Field required [type=missing, input_value={'event_id': '319e4bdc-c8...': {'question': 'ping'}}, input_type=dict]
```

`envelope.payload` inside the handler is not `{"question": "ping"}` — it is
a full envelope-shaped dict (`event_id`, `subject`, `occurred_at`,
`source_engine`, `correlation_id`, `causation_id`, `confidence`, and a
*nested* `payload: {"question": "ping"}`). Tracing where that shape comes
from, in `packages/nova-testkit/tests/test_nats.py:66-73` (unchanged by this
pass's fix, since the approved scope was the handler only):

```python
reply = await nats_event_bus.request(
    "testkit.rpc.echo",
    EventEnvelope(                      # <-- a full EventEnvelope,
        subject="testkit.rpc.echo",     #     passed as the `payload`
        source_engine="test-client",    #     argument
        correlation_id=uuid4(),
        payload={"question": "ping"},
    ),
    source_engine="test-client",
    timeout_ms=2000,
)
```

`NatsEventBus.request(self, subject, payload: BaseModel, ...)` expects
`payload` to be a plain payload model. The test passes a full `EventEnvelope`
instead. Because `EventEnvelope` is itself a `BaseModel`, this type-checks,
and inside `request()`, `payload.model_dump(mode="json")` serializes the
*entire* inner envelope into the *outer* envelope's `payload` field —
exactly the double-wrapping this pass's proposal (§5.2) diagnosed, but at
`.request()`'s call site rather than `.serve()`'s handler. This is a second,
independent occurrence of the same envelope/payload conflation, not a new
class of defect and not a regression: it was already present in run
`31296349533`'s original failure (the old handler's `return envelope` masked
it under a second layer of wrapping, which is why the original assertion
diff showed extra nesting beyond what a single-layer bug would produce).
Fixing only the handler, as approved, unmasked it rather than introducing
it. Per instruction, no further code change is made in this pass — this
finding is reported, not assumed away or silently fixed.

**Not run locally** for the same reason as before: no reachable Docker
daemon in this session. This finding is entirely sourced from the real CI
run's own logs, not local reproduction.

### 4.3 `communication-engine` / `perception-engine` — unchanged, still passing

Job `93365293694` (`communication-engine`): `11 passed, 135 deselected` —
identical count to run `31296349533`, confirming no regression.
Job `93365293714` (`perception-engine`): `7 passed, 127 deselected` — same.
Neither package was touched by this pass's fixes, as expected.

## 5. Status as of run `31359464265` (before the second fix)

| Package | Real_infra tests | Status |
|---|---|---|
| `communication-engine` | 11 | Confirmed passing for real |
| `perception-engine` | 7 | Confirmed passing for real |
| `personality-engine` | 5 | **All 5 confirmed passing**, including `test_update_memory_profile_persists_and_advances_updated_at` — §2.1's fix verified against real Postgres |
| `nova-testkit` | 11 | 10 confirmed passing; `test_real_request_reply` failing, root cause identified as a second, distinct occurrence of the envelope/payload conflation defect at the test's `.request()` call site (§4.2) |
| **Total** | **34** | **33 confirmed passing for real; 1 failing, root-caused** |

This was reported to the user, who approved fixing the second occurrence
(§8).

## 8. The second fix

**Approved scope:** change only `test_nats.py`'s `.request()` call so
`NatsEventBus.request()` receives a plain payload model instead of a full
`EventEnvelope`; preserve request/reply semantics and the existing
assertion; no production code, no `InMemoryEventBus`, no `RequestHandler`
contract change; no unrelated cleanup.

**Fix** (`packages/nova-testkit/tests/test_nats.py`, commit `42ca8f2`):

```python
reply = await nats_event_bus.request(
    "testkit.rpc.echo",
    _Echo(question="ping"),      # was: EventEnvelope(subject=..., payload={"question": "ping"})
    source_engine="test-client",
    timeout_ms=2000,
)
```

`_Echo` is the same payload model already introduced for the `serve()`
handler side in the first fix — reused here, not duplicated, since both
call sites need exactly the same shape. The `assert reply.payload ==
{"question": "ping"}` assertion is unchanged.

**Regression coverage:** no new test was added. This one test
(`test_real_request_reply`) already exercises the full round trip — the
`.request()` call site *and* the `serve()` handler — and is the same test
that caught both the original failure and this second occurrence, so it
remains the correct and sufficient regression guard for both without
duplication.

**Local verification performed** (full sequence, matching the first pass):

| Check | Result |
|---|---|
| Import-linter | 6/6 contracts kept |
| Lint (ruff + mypy), all 18 packages | 18/18 passed |
| Fast-tier tests, all 18 packages | 18/18 passed, including `personality-engine` (66/66) — confirms the first fix's coverage is still intact and untouched by this change |
| `nova-testkit` fast-tier | 14 passed, 11 deselected |
| Coverage gate negative control (`personality-engine`) | Exit 1, 99.22% — same pre-existing gap, unchanged (this package was not touched) |
| docker-compose config | Valid |
| TypeScript codegen | Zero diff |
| `git diff` review | Exactly 1 file, `test_nats.py`, 6 insertions / 10 deletions |

**Not run locally:** the real_infra suite itself, for the same
already-documented reason (no reachable Docker daemon in this session).

## 9. Second `workflow_dispatch` attempt — same blocker, no workaround

After pushing the second fix, `workflow_dispatch` was attempted again:

```
POST /repos/Tudor191/NOVA-PROJECT-BIBLE/actions/workflows/real-infra-checks.yml/dispatches
→ 403 "Resource not accessible by integration"
```

Identical to §4's original blocker — this session's GitHub integration still
lacks `actions:write`. Per explicit instruction, no permission workaround was
attempted. The fix is pushed to `claude/new-session-e1cseg`
(commit `42ca8f2`), which remains the repository's default branch, so the
next nightly `schedule` firing will pick it up automatically, exactly as
happened for the first fix (§4).

## 10. The confirming run — full evidence, not just job status

The nightly `schedule` trigger fired again on its own the following night, no
dispatch needed: run `31461343807`, `run_number: 3`, `event: "schedule"`,
`created_at: 2026-08-11T05:20:55Z`, against `head_sha: 9a81238` (the second
fix's Gate Review commit, itself built on `42ca8f2`). All four jobs'
top-level `conclusion` read `"success"` — but per instruction, that summary
alone was not treated as sufficient; every job's full `pytest` output was
pulled and read.

**`nova-testkit`** (job `93685276497`):

```
tests/test_nats.py::test_real_publish_and_subscribe PASSED
tests/test_nats.py::test_real_request_reply PASSED
tests/test_nats.py::test_durable_stream_retains_messages_until_pulled PASSED
tests/test_neo4j.py::test_real_node_and_relationship_creation_and_traversal PASSED
tests/test_neo4j.py::test_detach_delete_isolates_each_test PASSED
tests/test_postgres.py::test_real_insert_and_select_round_trip PASSED
tests/test_postgres.py::test_real_unique_constraint_is_enforced PASSED
tests/test_postgres.py::test_transaction_rollback_isolates_each_test PASSED
tests/test_redis.py::test_real_set_and_get_round_trip PASSED
tests/test_redis.py::test_real_ttl_expiry PASSED
tests/test_redis.py::test_flushdb_isolates_each_test PASSED
11 passed, 14 deselected, 2 warnings in 35.53s
```

`test_real_request_reply` passes explicitly, and the log contains no
`ValidationError`, no `TimeoutError`, and no `pydantic_core` traceback
anywhere — the exact failure mode from both prior runs (§1, §4.2) is
genuinely gone, not merely absent from a truncated summary.

**`personality-engine`** (job `93685276546`):

```
tests/integration/test_repository_real_postgres.py::test_get_core_identity_returns_the_real_migration_seeded_row PASSED
tests/integration/test_repository_real_postgres.py::test_get_memory_profile_returns_the_real_migration_seeded_default PASSED
tests/integration/test_repository_real_postgres.py::test_update_memory_profile_persists_and_advances_updated_at PASSED
tests/integration/test_repository_real_postgres.py::test_record_validation_audit_persists_a_real_row PASSED
tests/integration/test_repository_real_postgres.py::test_core_identity_singleton_check_constraint_is_enforced PASSED
5 passed, 66 deselected, 2 warnings in 12.71s
```

`test_update_memory_profile_persists_and_advances_updated_at` passes again,
with no `MissingGreenlet` anywhere in the log — the §2.1 fix's second
consecutive real-Postgres confirmation.

**`communication-engine`** (job `93685276534`): `11 passed, 135 deselected,
2 warnings in 18.38s` — unchanged, untouched by any fix in this priority.

**`perception-engine`** (job `93685276532`): `7 passed, 127 deselected,
2 warnings in 10.59s` — unchanged, untouched by any fix in this priority.

| Package | Expected | Actual | Confirmed via |
|---|---|---|---|
| `communication-engine` | 11/11 | **11/11** | Full log, unchanged from runs 1–2 |
| `perception-engine` | 7/7 | **7/7** | Full log, unchanged from runs 1–2 |
| `personality-engine` | 5/5 | **5/5** | Full log; the specific fixed test named and PASSED |
| `nova-testkit` | 11/11 | **11/11** | Full log; the specific fixed test named and PASSED, no ValidationError present |
| **Total** | **34/34** | **34/34** | |

## 11. Remaining limitations

- This session's own inability to reach a Docker daemon, or to dispatch
  `real-infra-checks.yml` directly (§4, §9), remain true as general facts
  about this environment — but neither blocked obtaining this result, since
  the nightly `schedule` trigger provided it without either capability.
- Run-to-run stability now has three data points (runs `31296349533`,
  `31359464265`, `31461343807`), all clean through the full container
  lifecycle (start, migrate/seed, test, teardown) with no ordering or
  isolation anomalies observed in any of them.
- No other limitation is open. Both defects this priority set out to fix are
  confirmed fixed against real infrastructure.

## 12. Compliance with this phase's constraints

No real_infra test was weakened, skipped, reclassified, or converted to a
fake-backed test, at any point across this priority. No test assertion was
loosened. No production code, no `InMemoryEventBus`, and no shared
`RequestHandler` contract was touched by either fix. No CI workflow file was
modified. No GitHub permission was changed (every `workflow_dispatch` 403 was
reported, never routed around). Phase 2D-D was not started. No other Phase
2D-C priority was touched. The stale task-tracker entries were not updated,
consistent with no explicit process requirement to do so. `git diff` was
reviewed in full before every commit and contained exactly the intended
files each time. No additional cleanup was performed alongside this closure.

**Priority 6 is complete.** All 34 real_infra tests across
`communication-engine`, `perception-engine`, `personality-engine`, and
`nova-testkit` have a confirmed passing execution on real GitHub Actions
infrastructure (run `31461343807`), verified from actual test output, not
job-status summaries alone. The two defects this priority found and fixed:

1. `personality-engine`'s `PostgresPersonalityRepository.update_memory_profile`
   read an expired `onupdate=func.now()` column outside SQLAlchemy's async
   greenlet-bridged context, raising `MissingGreenlet` on real Postgres —
   fixed with `await session.refresh(row)`, the same pattern already used by
   every other engine's repository layer.
2. `nova-testkit`'s `test_real_request_reply` conflated a full `EventEnvelope`
   with a plain payload `BaseModel` at two independent call sites (the
   `serve()` handler, then the `.request()` call) — both fixed by passing and
   returning the test's own `_Echo` payload model instead of the envelope.

Phase 2D-D has not been started and will not begin until the user reviews
this closure and gives explicit approval.
