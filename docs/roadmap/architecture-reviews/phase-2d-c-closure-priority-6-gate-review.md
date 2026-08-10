# Phase 2D-C Closure — Priority 6 Gate Review: real-infrastructure fixes

**Status: NOT complete — 33/34 confirmed passing.** The scheduled nightly
`real-infra-checks.yml` run (`31359464265`, 2026-08-10T05:42:47Z, against
commit `cce5626`) has executed and been inspected (§4). The
`personality-engine` fix is **confirmed correct on real Postgres**:
`test_update_memory_profile_persists_and_advances_updated_at` now passes.
`nova-testkit`'s `test_real_request_reply` **still fails**, but for a
distinct, more precisely diagnosed root cause than originally documented in
the proposal — a second occurrence of the same envelope/payload conflation
defect, at the test's `.request()` call site rather than its `serve()`
handler (§4.2). This was a pre-existing defect the original fix did not
touch and did not regress; it was simply unmasked once the handler-side
defect stopped hiding it. Per explicit instruction, no further code change
was made this pass — the new failure is root-caused and reported, not
assumed away. Priority 6 remains open.

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

## 5. Current, honest status of all 34 real_infra tests

| Package | Real_infra tests | Status as of run `31359464265` (2026-08-10) |
|---|---|---|
| `communication-engine` | 11 | Confirmed passing for real (unchanged) |
| `perception-engine` | 7 | Confirmed passing for real (unchanged) |
| `personality-engine` | 5 | **All 5 confirmed passing**, including `test_update_memory_profile_persists_and_advances_updated_at` — the fix in §2.1 is verified against real Postgres |
| `nova-testkit` | 11 | 10 confirmed passing; `test_real_request_reply` **still fails**, root cause now precisely identified as a second, distinct occurrence of the envelope/payload conflation defect at the test's `.request()` call site (§4.2) — not yet fixed |
| **Total** | **34** | **33 confirmed passing for real; 1 failing with a fully root-caused, not-yet-implemented fix** |

## 6. Remaining limitations

- One real_infra test (`nova-testkit::test_real_request_reply`) still fails.
  The fix implemented this pass corrected the defect as originally scoped
  (the `serve()` handler) but did not cover a second occurrence of the same
  conflation at the `.request()` call site in the same test — that occurrence
  was not part of the approved fix scope and was only exposed, not
  introduced, once the handler-side fix stopped masking it (§4.2). A
  corrected fix (constructing and passing a plain `_Echo(question="ping")`
  payload model to `.request()`, instead of a full `EventEnvelope`) is
  implied by this diagnosis but has **not been implemented**, per instruction
  to stop and report rather than assume.
- This session still cannot run either real_infra suite locally (no reachable
  Docker daemon) and still cannot dispatch `real-infra-checks.yml` manually
  (§4's 403). Confirmation of any further fix again depends on the next
  nightly `schedule` firing, or a manual dispatch by someone with sufficient
  repository access.
- Run-to-run stability now has two data points (runs `31296349533` and
  `31359464265`): both completed cleanly through the full container
  lifecycle (start, migrate/seed, test, teardown) with no ordering or
  isolation anomalies — the only differences between the two runs are the
  ones this pass's fixes intentionally produced. No flakiness observed so far.

## 7. Compliance with this phase's constraints

No real_infra test was weakened, skipped, reclassified, or converted to a
fake-backed test. No test assertion was loosened. No production code beyond
the one documented line was touched. No CI workflow file was modified. No
GitHub permission was changed (the 403 was reported, not routed around). No
further code change was made after discovering the second `nova-testkit`
defect, per explicit instruction to stop and report. Phase 2D-D was not
started. No other Phase 2D-C priority was touched. The stale task-tracker
entries were not updated, consistent with no explicit process requirement to
do so. `git diff` was reviewed in full before committing (§3) and contains
exactly the two approved files.

**Priority 6 remains open.** 33 of 34 real_infra tests are confirmed passing
against real infrastructure; `nova-testkit::test_real_request_reply` is not,
and its precise root cause (§4.2) is reported here for review rather than
fixed unilaterally. Priority 6 will not be marked complete, and Phase 2D-D
will not begin, until the user reviews this finding and approves a next step.
