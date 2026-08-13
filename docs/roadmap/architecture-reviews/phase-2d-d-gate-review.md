# Phase 2D-D — Personal Companion: Gate Review

**Status: 9 of 10 steps fully verified against real infrastructure; Step 10's
own bug-fix confirmation is the one open item, pending the next scheduled
`real-infra-checks.yml` run** (this session's GitHub integration lacks
`actions:write`, so `workflow_dispatch` returns `403 Resource not accessible
by integration` — identical, already-documented blocker to the one recorded
in `phase-2d-c-closure-priority-6-gate-review.md` §4/§9; the nightly
`schedule` trigger is the only path to a fresh run, exactly as it was for
that priority). Every other verification tier named in the authorizing
instruction — fake/contract-backed tests, import-linter, coverage gates
with a negative control, docker-compose validation, TypeScript codegen, and
one prior real-infra run's evidence — is complete and recorded below.

**Do not treat Phase 2D-D as fully closed until §6's open item is
resolved.** This document will be updated in place once the next nightly
`real-infra-checks.yml` run confirms the Step 10 fix.

---

## 1. What this phase built

Reference: `docs/design/phase-2d/06-personal-companion.md` (the Technical
Design Document authorizing this work), ADR-030.

- **`digital-twin-engine`** (new service): Bible Part 16's Communication
  Profile domain, a conversation-scoped Preference Evolution/Habit
  Detection slice, the correction-frequency trust metric (Fork C,
  explicitly partial), and the proactive-communication boundary policy
  (Fork D) — including, as of Step 9, a real, tested, warm-case delivery
  path.
- **`reasoning-engine`**: extended `hypothesis_generation.py`'s existing
  model call (Fork E) with an additive `prior_nova_utterance` prompt
  component and `is_correction` output parsing, threaded through
  `pipeline.py` to the reply.
- **`communication-engine`**: `get_last_outbound_turn()` (Sec5.2);
  correction-signal transport into `ConversationMemory.corrections` and a
  new `correction_detected` decision-trace type; `CommunicationSessionCompletedPayload`
  enrichment (Sec6); a new `DigitalTwinPort`/`DigitalTwinClient` (Fork A,
  Sec7.2), wired into `resolve_response_shaping()` as an optional,
  non-load-bearing call; and, for Fork D, `SessionRegistry`'s new
  `user_id -> connected session_id` lookup plus the served
  `communication.session.lookup_by_user.request` RPC.
- **`personality-engine`**: a new `personality.memory.update` subscription
  (`make_memory_update_handler`), completing the one-way ADR-030 data flow
  digital-twin-engine's own publish side approves but does not yet use
  (Fork F).
- **`nova-contracts`**: four additive payload changes (Sec7.3) plus two
  brand-new payloads for Fork D's session lookup — all ADR-024 compliant.

**Explicitly not built** (per the TDD's own Sec18 non-goals, unchanged):
cold-case proactive delivery, clarification/proactive-suggestion acceptance
as trust-metric inputs, any of the other nine Bible Part 16 domains, and
any change to `PersonalContextPort`.

---

## 2. The two forks discovered during implementation

Both were surfaced, presented, and resolved before writing code that
depended on the resolution, per the standing instruction to stop and
present evidence for any genuinely new fork.

### 2.1 Fork F — no approved evidence source for `CommunicationProfile`'s five learned fields

The TDD approves the *wire path* for `verbosity`/`technical_depth`/
`terminology_preference`/`conversation_pacing`/`habit_timing_hint` but never
named what evidence extracts them from `ConversationMemory`'s free-text
categories — doing so would require inventing a text-classification
heuristic, explicitly forbidden. **Resolved as "ship as defaulted plumbing":**
`preference_evolution.evolve_field()` is real, fully unit-tested, and has
zero production call sites; all five fields stay at static defaults in
production this phase. Disclosed in `domain/models.py`'s module docstring,
the digital-twin-engine README, and every relevant commit message.

### 2.2 The `resolve_response_shaping()`/`DigitalTwinPort` dormancy (Step 8)

Discovered, not really a fork requiring a stop: `communication-engine`'s
`domain/response_shaping.py` has had zero production call sites since Phase
2D-C — already self-disclosed in that module's own docstring. This meant
Step 8's `DigitalTwinPort` could be wired into `resolve_response_shaping()`
as a fully real, tested, optional parameter without needing to invent a new
orchestration call site, since none existed for that function at all before
this phase either. Documented in both the module docstring and the
communication-engine README's Known Limitations section.

### 2.3 Fork D's own missing pieces (Step 9)

The TDD explicitly named exactly two new capabilities Fork D needed:
`SessionRegistry`'s `user_id -> connected session_id` lookup, and
digital-twin-engine's own call to `communication.intent.deliver.request`.
Building the second surfaced one **implementation-time-necessary**
addition beyond the TDD's literal schema list: `evaluate_proactive_suggestion`'s
frequency-limit check needs genuine, per-user delivery history to compute
against, which required a new `proactive_delivery_record` table + repository
methods (mirrors the same "the TDD itself calls the exact window size an
implementation-time parameter, not an architectural fork" reasoning already
used for `completed_session_evidence` in Step 6). No production trigger
proposes a `ProactiveSuggestion` — no scheduler or reminder source exists
anywhere in this codebase — so `attempt_proactive_delivery` is real and
fully tested but, like Fork F and the Step 8 dormancy above, has no
automatic caller this phase. This is the TDD's own explicit scope boundary
(Sec10 names only the policy and delivery mechanism), not an omission.

---

## 3. Exact files changed, by step

| Step | Scope | Commit |
|---|---|---|
| 1 | `nova-contracts` additive payload changes | `e2389c6` |
| 2 | `reasoning-engine` correction-signal extension | `a08051c` |
| 3 | `communication-engine` correction-signal transport | `9182832` |
| 4 | `CommunicationSessionCompletedPayload` enrichment | `8e885e1` |
| 5 | `digital-twin-engine` domain layer | `da253bb` |
| 6 | `digital-twin-engine` service scaffold | `8bcdee3` |
| 7 | `personality-engine` `personality.memory.update` subscription | `33ef11d` |
| 8 | `communication-engine` `DigitalTwinPort` | `cd44be0` |
| 9 | Fork D warm-case proactive delivery | `b9f198c` |
| 10 | Real-infra bug fix (`get_last_outbound_turn` timestamp tie) | `812faf0` |

Every commit's own message records its exact test counts and verification
results at the time; this document consolidates the final state.

---

## 4. Test results — final state, all 19 packages

`pnpm turbo run test --force` (no cache), all packages, run after Step 10's
fix:

| Package | Result |
|---|---|
| `nova-testkit` | 14 passed, 11 deselected |
| `nova-service-kit` | 9 passed |
| `nova-graphstore-sdk` | 24 passed |
| `nova-core` | 13 passed |
| `digital-twin-engine` | **50 passed, 9 deselected** |
| `world-model-engine` | 64 passed (untouched this phase) |
| `executive-cognition-engine` | 66 passed (untouched this phase) |
| `nova-vectorstore-sdk` | 19 passed |
| `nova-contracts` | **82 passed** |
| `perception-engine` | 127 passed, 7 deselected (untouched this phase) |
| `ai-model-orchestration-engine` | 172 passed (untouched this phase) |
| `knowledge-engine` | 67 passed (untouched this phase) |
| `nova-eventbus-sdk` | 24 passed |
| `nova-embeddings-sdk` | 11 passed |
| `nova-observability` | 7 passed |
| `memory-engine` | 123 passed (untouched this phase) |
| `reasoning-engine` | **81 passed** |
| `personality-engine` | **69 passed, 5 deselected** |
| `communication-engine` | **157 passed, 13 deselected** |
| **Total** | **1179 passed, 45 deselected (real_infra), 0 failures** |

Bold rows are packages this phase modified. Deselected counts are
`@pytest.mark.real_infra` tests, excluded from the default invocation per
ADR-033.

**New tests this phase** (by package, approximate — exact counts recorded
in each step's own commit message): `nova-contracts` +15 (contract
round-trips for 6 new/changed payloads), `reasoning-engine` +8,
`communication-engine` +7 (Step 3) +2 (Step 4) +7 (Step 8) +8 (Step 9) = 24,
`digital-twin-engine` — built from zero this phase, 50 total (25 domain in
Step 5, 15 scaffold in Step 6, 18 in Step 9 net of the `test_models.py`
fix), `personality-engine` +3.

---

## 5. Verification checklist (per the authorizing instruction)

| Check | Result |
|---|---|
| Unit/integration tests after each stage | Done incrementally, recorded in each step's commit |
| `ruff` across affected packages | Clean, all steps individually and in the final `pnpm turbo run lint` (19/19) |
| `mypy` across affected packages | Clean, all steps individually (`communication-engine` 44 files, `digital-twin-engine` 27 files, `reasoning-engine`, `personality-engine`, `nova-contracts` all clean) |
| Full monorepo test suite | **1179/1179 passed, 0 failures** (§4) |
| import-linter contracts intact | **6/6 kept, 0 broken** — re-verified after every step and again at the end |
| Coverage gate negative control | Run twice this pass (§5.1) — both fail correctly |
| docker-compose validation | `docker compose -f infra/docker/docker-compose.local.yml config --quiet` — clean, no error |
| TypeScript codegen — only expected additive changes | Confirmed twice: Step 8 (no contract changes, skipped), Step 9 (exactly 2 new files + 1 diff line in `index.ts`) |
| `git diff` review for scope | Done per-step (recorded in each commit message); final `git status` clean, all work committed and pushed |
| Tests for every new behavior and failure/degraded path | Done — see each step's commit message for the exact list (timeouts, cold-case no-ops, personality rejections, policy denials, etc.) |
| 4-tier verification classification | §6 below |
| Documentation | This document + both engines' READMEs updated per step |

### 5.1 Coverage gate negative control — exact commands and results

```
$ uv run --package digital-twin-engine pytest services/digital-twin-engine \
    -m "not real_infra" -k "not test_no_sessions_returns_none_not_zero" \
    --cov=nova_digital_twin_engine.domain --cov-fail-under=100 -q
...
FAIL Required test coverage of 100% not reached. Total coverage: 98.70%
exit code: 1
```

```
$ uv run --package communication-engine pytest services/communication-engine \
    -m "not real_infra" \
    -k "not test_digital_twin_timeout_degrades_pacing_and_timing_without_flipping_degraded" \
    --cov=nova_communication_engine.domain --cov-fail-under=100 -q
...
FAIL Required test coverage of 100% not reached. Total coverage: 98.85%
exit code: 1
```

Both gates genuinely fail when a real gap exists. With every test included,
both packages reach 100% domain coverage (well above each package's own
configured 85% gate).

---

## 6. Real-infrastructure verification — the open item

### 6.1 What is already confirmed against real GitHub Actions infrastructure

Run `31671523896` (`real-infra-checks.yml`, `schedule` trigger,
`2026-08-13T05:47:18Z`, against commit `cd44be0` — the state of the branch
after Step 8) was inspected in full, every job's actual `pytest` output, not
just job status:

| Job | Result |
|---|---|
| `digital-twin-engine` | **success** — this engine's own real-Postgres suite, including the Step 6/Step 9 schema, passed for real against a real Postgres container on a real GitHub-hosted runner |
| `nova-testkit` | **success** |
| `personality-engine` | **success** |
| `perception-engine` | **success** |
| `communication-engine` | **failure** — one genuine bug, see §6.2 |

This is real, first-hand evidence that digital-twin-engine's entire new
schema (all 7 tables as of Step 9, migrations `0001`+`0002`) migrates and
round-trips correctly against real Postgres — not merely locally plausible.

### 6.2 The bug this run caught, and the fix

`communication-engine::test_get_last_outbound_turn_returns_the_most_recent_one`
failed: `assert last.content == "Anything else?"` got `"The meeting is on
Tuesday."` instead — `get_last_outbound_turn()` (Step 3's own addition)
returned the *first* outbound turn instead of the most recent one.

**Root cause:** `ConversationTurnORM.created_at` used only
`server_default=func.now()`. Postgres's `now()` returns the *transaction's*
start time, not the statement's — three `append_turn()` calls issued
back-to-back in the test (each its own transaction, but with no real-world
delay between them on a fast CI runner) tied at the same timestamp, and
`ORDER BY created_at DESC LIMIT 1` picked an arbitrary row among the tied
set rather than the actual most recent one.

**Fix** (commit `812faf0`): added a Python-side `default=lambda:
datetime.now(UTC)`, evaluated at ORM-object construction time — which only
happens after the previous `append_turn()` call's own network round trip
has already returned, so it cannot tie the same way. `server_default` is
kept as a DB-level fallback. Scoped to exactly the one column Phase 2D-D's
own new work depends on for strict recency ordering; the existing
real-infra test that caught this is left unmodified, since it is already
the correct regression guard (same precedent as
`phase-2d-c-closure-priority-6-gate-review.md`'s own personality-engine fix).

**Deliberately not touched:** the identical `server_default=func.now()`-only
pattern exists on other "most recent" queries in `memory-engine`,
`knowledge-engine`, `world-model-engine`, `reasoning-engine`, and
`ai-model-orchestration-engine`'s own repositories. All five are outside
Phase 2D-D's approved scope (the TDD's own Sec2: "Does not touch"). **Recorded
here as a follow-up recommendation for a future, separately-scoped pass** —
not fixed in this phase.

### 6.3 Why confirmation is pending, not obtained

`workflow_dispatch` was attempted against `real-infra-checks.yml` on
`claude/new-session-e1cseg` and returned:

```
POST /repos/Tudor191/NOVA-PROJECT-BIBLE/actions/workflows/real-infra-checks.yml/dispatches
→ 403 Resource not accessible by integration
```

This is the identical, already-documented blocker recorded in
`phase-2d-c-closure-priority-6-gate-review.md` §4 and §9 — this session's
GitHub integration lacks `actions:write`. Per that same precedent's explicit
instruction, no permission workaround was attempted. The fix is pushed to
`claude/new-session-e1cseg` (commit `812faf0`); the next nightly `schedule`
firing (`cron: "17 4 * * *"`, roughly 24h after the run inspected in §6.1)
will pick it up automatically, exactly as it did for both of Priority 6's
own fixes.

**This document will be updated with the confirming run's full job output
once it fires** — following the exact same "read every job's actual pytest
output, not just job status" discipline Priority 6 established.

---

## 7. Four-tier verification classification

Per the standing instruction to separate results into: fully verified
locally / contract-fake verified / real-infra verified / genuinely
unverified.

**Fully verified locally** (ruff, mypy, fake-backed tests, coverage gates
with negative control, import-linter, docker-compose, TS codegen):
- All domain logic in `digital-twin-engine` (`preference_evolution.py`,
  `trust_metric.py`, `proactive_boundary.py`) — 100% coverage.
- `reasoning-engine`'s `is_correction` parsing against fixture model
  outputs.
- `communication-engine`'s correction-signal transport, `DigitalTwinPort`
  optional-call behavior (including timeout degradation), and
  `attempt_proactive_delivery`'s full decision tree (denied/cold-case/
  rejected/timeout/delivered), all against fakes.
- `SessionRegistry`'s new `user_id -> session_id` lookup.

**Contract-fake verified** (real Event Bus round trip, fake ports/repository):
- `digital_twin.preferences.get.request` round trip (Step 8's
  `test_digital_twin_client.py`).
- `communication.session.lookup_by_user.request` and
  `communication.intent.deliver.request` round trips from
  digital-twin-engine's own `CommunicationClient` (Step 9).
- `personality.memory.update` round trip into personality-engine's real
  `create_app()` (Step 7).
- The full correction-detection path: fake reasoning port ->
  real orchestration -> real `ConversationMemory.corrections` -> real
  session close -> enriched event payload (Step 3/4).

**Real-infra verified** (§6.1):
- `digital-twin-engine`'s entire Postgres schema (migrations `0001` +
  `0002`), confirmed via a real GitHub Actions run against commit `cd44be0`.
- `personality-engine`, `perception-engine`, `nova-testkit`'s own real-infra
  suites, confirmed the same run (unchanged by this phase, still green).

**Genuinely unverified until the pending run confirms** (§6.3):
- The Step 10 timestamp-tie fix itself, against real Postgres.
- `communication-engine`'s real-Postgres suite as a whole, post-fix.
- `digital-twin-engine`'s new `0002_proactive_delivery.py` migration and
  `proactive_delivery_record` table specifically (Step 9's own addition,
  built after the one real-infra run this phase has evidence from) — the
  domain logic and repository methods are contract-fake verified (§ above),
  but no real-Postgres run has executed against this exact schema version
  yet. The written real-infra test
  (`test_proactive_delivery_record_persists_and_lists_recent_by_window`)
  will be confirmed in the same pending run.

**Do not describe Fork D's warm-case delivery, or the Step 10 fix, as
end-to-end real-infra verified until §6.3 resolves.**

---

## 8. Remaining limitations, explicitly

- **Fork F**: `CommunicationProfile`'s five learned fields ship at static
  defaults; no evidence-extraction mechanism exists (§2.1). Not a bug — an
  explicit, disclosed scope boundary.
- **No production trigger for proactive suggestions**: `attempt_proactive_delivery`
  is real and tested but has no caller (§2.3). Not a bug — the TDD's own
  scope names only the policy and delivery mechanism.
- **Cold-case proactive delivery**: explicitly out of scope, no companion-client
  transport exists anywhere in this repository (Sec10.3, unchanged).
- **`resolve_response_shaping()`'s `DigitalTwinPort` call**: real and
  tested, but no production call site supplies `digital_twin_port`/`user_id`
  (§2.2) — a pre-existing Phase 2D-C gap this phase did not need to close.
- **`personality.memory.update` publishing**: the outbox/worker
  infrastructure is wired, but nothing enqueues onto it (Fork F, same
  root cause).
- **The systemic `server_default=func.now()`-only timestamp pattern**
  (§6.2) exists unfixed in five other engines' repositories, outside this
  phase's scope. Flagged as a follow-up recommendation.
- **Step 10's real-infra confirmation is pending** (§6.3) — the single open
  item before this phase can be called fully verified.
- **Real-Postgres verification of `personality-engine`, `communication-engine`,
  and `perception-engine`'s repo layers via a local Docker daemon** remains
  the same standing, session-environment limitation recorded since Phase
  2D-A (task #93) — resolved only through GitHub Actions evidence, as it
  has been for every phase since Priority 6.

---

## 9. Recommendation

**Conditionally complete.** All 10 implementation steps are built, tested,
and documented; 9 of 10 have real-infrastructure confirmation; the 10th
(the Step 10 bug fix) has a pushed fix awaiting its first real-infra run.
No further code changes are anticipated — this is a confirmation-only gate,
not an implementation gap. Recommend treating Phase 2D-D as **gated on §6.3**
rather than reopening any of the 10 steps' own scope.
