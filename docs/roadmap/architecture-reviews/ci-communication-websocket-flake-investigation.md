# CI Reliability — `communication-engine` WebSocket Voice Test Flake: Investigation & Fix

**Status: complete. Test-only fix, no production code changed.**

**Scope:** dedicated to one pre-existing CI reliability defect
(`test_server_triggered_listening_activates_without_a_client_trigger_start`),
discovered during the CI investigation for PR #4
(`fix-dockerfiles-nova-service-kit`). Independent of PR #3 (trivy-action
fix) and PR #4 (Dockerfile fix) — neither is touched here.

---

## 1. Symptom

`checks` (pr-checks.yml) failed on PR #4 with:

```
FAILED tests/integration/test_websocket_voice.py::test_server_triggered_listening_activates_without_a_client_trigger_start - assert 0 == 1
```

PR #4's diff contains zero files under `services/communication-engine/`,
so this could not have been caused by that PR. The test passes reliably
in isolation; it only failed under `pnpm turbo run test`'s full,
many-package parallel execution (the CI log showed 19 concurrent turbo
tasks).

## 2. Root cause

### 2.1 What the test does

The test publishes a `perception.addressee_signal.candidate` event (via
`client.portal.call`, running on the same event loop/thread as the app),
then — before this investigation's fix — did:

```python
time.sleep(_SILENCE_POLL_INTERVAL_S * 3)  # 0.3s
websocket.send_bytes(b"\x01" * 32)
```

The 0.3s sleep was meant to give the WebSocket connection's own receive
loop (`api/websocket.py`) time to notice and consume a
`StartListeningSignal` before the audio chunk arrives.

### 2.2 The exact async/event path

1. `client.portal.call(...)` → `FakePerceptionSignalSource.publish_addressee_signal_candidate`
   → `InMemoryEventBus.publish(envelope)`.
2. **`InMemoryEventBus.publish()` awaits every subscriber handler
   in-line**: `for sub in targets: await sub.handler(envelope)`
   (`packages/nova-eventbus-sdk/src/nova_eventbus_sdk/backends/in_memory.py:93-94`)
   — no `asyncio.create_task` anywhere in this chain.
3. That handler (`make_addressee_signal_handler.handle`,
   `services/communication-engine/src/nova_communication_engine/events/handlers.py:274`)
   is itself `async def`, and `await`s `maybe_activate_listening(...)`
   synchronously, which calls `SessionRegistry.trigger_start_listening()`
   → `StartListeningSignal.trigger()`.
4. **Conclusion: by the time `client.portal.call(...)` returns, the
   signal is unconditionally already set.** There is no indeterminate
   dispatch latency here at all — confirmed by direct source inspection,
   not assumption.
5. Separately, on its **own `asyncio.Task`**, the WebSocket connection's
   receive loop (`api/websocket.py:116-143`) is structured as:
   ```python
   try:
       inbound = await asyncio.wait_for(adapter.receive(), timeout=_SILENCE_POLL_INTERVAL_S)
   except TimeoutError:
       # only here does it check/consume the StartListeningSignal
       ...
   # a successfully-received inbound message (e.g. the test's own audio
   # chunk) goes straight to its own branch below, WITHOUT ever taking
   # the except TimeoutError branch for that loop iteration
   if inbound.kind is InboundMessageKind.AUDIO_CHUNK ...:
       if turn_active:
           audio_buffer.extend(inbound.audio)   # silently does nothing if turn_active is still False
   ```
   The signal is **only** checked when `asyncio.wait_for` times out — a
   successfully-received frame (the test's own audio chunk, if it
   arrives too early) bypasses that branch for that iteration entirely,
   and is silently dropped (no error, no retry, no buffering) if
   `turn_active` is still `False`.

### 2.3 Root cause classification

**Test-synchronization defect**, not a production race and not a
NATS/broker timing issue:

- Not a production race: the receive loop's poll-based design (checking
  a signal only on its own bounded timeout) is intentional, already
  correctly documented (Priority 4 review §1.2/§1.3), and not itself
  buggy — a real device's audio arriving in the exact same instant as a
  server-triggered signal is a genuine, accepted, bounded-latency (at
  most one `_SILENCE_POLL_INTERVAL_S` ≈ 100ms) design tradeoff, not a
  defect to "fix" in application code.
- Not an `anyio` blocking-portal issue: the portal itself adds no
  meaningful latency to the publish path (confirmed via §2.2's
  synchronous chain).
- Not NATS/event-bus timing: the test forces `EVENT_BUS_BACKEND=in_memory`
  — no network or broker involved.
- **It is:** the test used a single fixed-duration sleep to stand in for
  a wait on cross-task scheduling (the receive loop's own task getting
  its next turn), which is inherently non-deterministic under CI's CPU
  contention (19 concurrent turbo tasks). A fixed guess that is
  comfortable on a lightly-loaded machine is not guaranteed sufficient
  under load — this is a textbook flaky-test pattern, and the repo
  already has a purpose-built alternative for it (§3).

### 2.4 Same behavior in related tests?

The other two tests in this file were checked and are **not** exposed to
this race:

- `test_a_mismatched_user_id_never_accumulates_a_turn` uses the same
  sleep, but asserts a *negative* outcome (`turn_count == 0`) that holds
  regardless of timing, because the signal is filtered out upstream by a
  `user_id` mismatch and never reaches `trigger_start_listening` at all.
- `test_a_barge_in_followed_by_continuing_speech_does_not_crash_the_connection`
  never publishes an addressee signal — it force-writes session state
  directly and relies entirely on the deterministic `_wait_for_turn_count`
  poll helper.

Neither was touched; only the one genuinely-affected test was changed.

## 3. Established repository pattern used

`packages/nova-testkit/src/nova_testkit/waiting.py` already provides
`wait_until(condition, timeout_s=2.0, interval_s=0.01)`, documented as
*"the alternative to sprinkling `asyncio.sleep(n)` through tests, which
is both slow... and flaky (too short on a loaded CI runner)"* — this is
this repo's own, ADR-033-blessed, already-used-elsewhere (`nova-core`'s
heartbeat test, `nova-testkit`'s own NATS test) primitive for exactly
this class of problem. No new pattern was introduced; this fix simply
uses it at the one call site in this file that hadn't adopted it yet.

## 4. The fix

`services/communication-engine/tests/integration/test_websocket_voice.py`,
`test_server_triggered_listening_activates_without_a_client_trigger_start`
only:

```python
signal = app.state.session_registry.get_start_listening_signal(UUID(session_id))
assert signal is not None
client.portal.call(lambda: wait_until(signal.is_set))
client.portal.call(lambda: wait_until(lambda: not signal.is_set()))
```

replaces:

```python
time.sleep(_SILENCE_POLL_INTERVAL_S * 3)
```

The first `wait_until` resolves immediately in practice (per §2.2, the
signal is already set by the time it's checked) — it exists as a
defensive, self-verifying step rather than an assumption. The second is
what the fix actually depends on: it does not return until the receive
loop's own task has taken its next scheduler turn and consumed
(`.clear()`-ed) the signal — the exact same instant `turn_active` is set
`True` in the same synchronous block of `api/websocket.py` (no `await`
between `.clear()` and `turn_active = True`, so there is no window for
an external observer to see an inconsistent state). This is a direct,
deterministic observation of the actual production event, not a
duration guess.

Application code was **not** modified. The two-line diff is confined to
one test function.

## 5. Verification

### 5.1 Correctness (static)

The fix's correctness rests primarily on the source-level proof in §2.2
and §4 — the wait is on the actual completion signal, not a guessed
duration, so it is correct regardless of how slow or fast the runner is,
bounded only by `wait_until`'s own generous 2.0s default timeout
(matching the file's existing `_wait_for_turn_count` convention).

### 5.2 Local test execution

- Target test, full file, isolated: 3/3 pass.
- Target test file, 20 repeated back-to-back runs (no synthetic load):
  20/20 pass, 0 failures.
- Full `communication-engine` suite (`pytest -m "not real_infra"
  --cov=nova_communication_engine.domain`): **157/157 passed**, 99.18%
  domain coverage (85% gate).
- Full monorepo suite (`pnpm -r test`): exit code 0, all packages green
  (only the known/expected harmless OTel-collector transient noise from
  `nova-observability`'s own suite, unrelated).
- `pnpm turbo run lint` (ruff + mypy, all 19 packages): all green.
- `uv run lint-imports`: 6/6 contracts kept, 0 broken.
- `docker compose -f infra/docker/docker-compose.local.yml config --quiet`: valid.

### 5.3 Attempted local reproduction of the actual CI race — inconclusive, disclosed honestly

Per instruction not to claim the flake is fixed on the strength of one
successful run, three different attempts were made to reproduce the
original race locally, under conditions approximating CI's parallel-turbo
contention, against the **unmodified (old) code** as a control:

1. **8-way CPU busy-loop contention** (`while True: pass` processes) on
   this sandbox's 4 cores, 40 repeated runs of the target test: 0
   failures on old code.
2. **16-way parallel `pytest` process contention** (80 total runs): 0
   failures on old code.
3. **12-way busy-loop contention pinned to 2 CPUs via `taskset`** (to
   more aggressively starve the process): this run did not complete
   within a bounded timeout and was aborted rather than left to hang
   indefinitely.

None of these synthetic-load approaches reproduced the original failure
on the old, known-racy code, in this sandbox. This is disclosed as a
**genuine limitation of local verification**, not swept under the rug:
this sandbox's contention profile (CPU-burn busy loops, or many bare
`pytest` process launches) evidently does not recreate whatever specific
combination of process-count, memory pressure, and scheduling behavior
GitHub Actions' own runner produced when the real failure occurred. A
fourth attempt used `unittest.mock.patch` to directly and deterministically
inject scheduling delay into the receive loop's own `asyncio.wait_for`
calls (rather than relying on OS-level noise); this approach ran into
threading/patching interaction issues with `anyio`'s blocking portal and
risked hanging, and was abandoned as not worth the additional time given
the strength of the static proof already in hand.

**Conclusion:** confidence in this fix rests on the rigorous, verified-by-
source-inspection deterministic design (§2.2–§4), not on a local
reproduction of the exact original failure. Genuine end-to-end
confirmation requires observing this fix's own `checks` job succeed on
GitHub Actions across the pattern of real, multi-package parallel
execution that originally triggered it — tracked as the explicit
follow-up in §7.

## 6. Verification classification

| Check | Result | Classification |
|---|---|---|
| Source-level synchronization proof | Deterministic wait on actual production event, not a duration | Fully verified |
| Target test, isolated + 20x repeated | 23/23 pass | Fully verified |
| `communication-engine` full suite | 157/157 pass, 99.18% coverage | Fully verified |
| Full monorepo suite | exit 0, all green | Fully verified |
| ruff + mypy + import-linter | all clean | Fully verified |
| Local reproduction of the *original* CI race | Not reproduced despite 3 methodologies | Genuinely unverified locally — see §5.3 |
| GitHub Actions `checks` job, this fix, under real parallel load | Not yet observed | Pending — required before declaring this flake closed (§7) |

## 7. Remaining uncertainty / required follow-up

This fix is **not** to be treated as conclusively proven until this PR's
own `checks` job (and, ideally, a few subsequent PRs' `checks` runs) are
observed green on GitHub Actions under real parallel-turbo load. If it
recurs, the next step is to add trace-level logging around the two
`wait_until` calls to capture actual observed latency on a real runner,
rather than attempting further synthetic local reproduction.
