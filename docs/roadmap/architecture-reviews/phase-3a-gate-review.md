# Phase 3A — reasoning-engine Multi-step Recursion Trigger: Gate Review

**Status: complete, fake/contract-backed verified. No real-infrastructure
verification applies — this slice introduces no new Postgres schema, no new
Event Bus subject, and no new nova-contracts payload (see §6).**

---

## 0. Scope executed

Exactly Phase 3A, per `docs/design/phase-3/04-tdd-3a-reasoning-recursion.md`
and the user's explicit Fork 3A-1/3A-2 decisions this pass: internal
self-recursion inside `reasoning-engine`'s own `pipeline.run()`, triggered
by existing structural signals (`mode is MULTI_STEP`, `confidence.composite
< verify_threshold`, `depth < MultiStepConfig.max_step_depth`), sub-question
derivation from the chosen alternative's weakest supporting-evidence gap,
chain-minimum confidence aggregation, `parent_process_id` lineage, and the
three named observability metrics. **No other Phase 3 component
(`planning-engine`, `capability-engine`, `action-engine`, `agent-os`,
gateways, `apps/web-client`) was touched.**

---

## 1. A discovery that changed the plan, disclosed up front

Before writing any code, re-inspection of `domain/models.py`,
`domain/trace.py`, and `nova_contracts/events/reasoning.py` (per the
"inspect the current implementation again" instruction) found that the
TDD's own proposed contract additions — a new `child_process_ids: list[UUID]`
field and a `ReasoningProcessCompletedPayload.parent_process_id` addition —
were **unnecessary**. Three mechanisms already existed, already documented
for exactly this purpose, never previously exercised:

- `ReasoningTrace.steps: list[ReasoningTrace]` (already present, comment
  `# §11`) — the Multi-step chain container.
- `domain/trace.py`'s `build_trace(..., steps: list[ReasoningTrace] | None
  = None)` parameter — already accepted, always called with the default
  (`[]`) until this pass.
- `ReasoningProcess.parent_process_id` (already a real Postgres FK,
  `repository/models.py:36-38`) and
  `ReasoningRequestPayload.parent_process_id`'s own docstring — *"Design
  doc §11 — set when this request is one step of a Multi-step reasoning
  chain"* — already wired, never previously populated by any real caller.

**This is not a fork requiring a stop** — it is strictly more compliant
with the approved instruction *"do not introduce a new persistence
mechanism unless the existing implementation strictly requires one"* than
the TDD's own proposal was, and it does not change any of the approved
Fork 3A-1/3A-2 decisions. **Result: zero `nova-contracts` changes in this
pass** — a smaller footprint than the TDD anticipated. Documented here per
the instruction to disclose any discrepancy discovered during
implementation, not silently resolve it.

**One genuinely new, disclosed domain-model field was still required**:
`ReasoningTrace.multistep_recursion_exhausted: bool = False`.
`observability.py`'s own pre-existing module docstring is explicit that
`domain/` may never import it — the structured per-process record belongs
in `ReasoningTrace`, not in an injected metrics callback. Without this one
field there is no way for `api/reason.py`/`events/handlers.py` to
distinguish "the chain resolved before hitting the depth cap" from "the
chain was exhausted," which the user's own observability requirement (item
8) explicitly asks for. Minimal, disclosed, not silently invented.

---

## 2. Exact files changed

| File | Kind | Change |
|---|---|---|
| `services/reasoning-engine/src/nova_reasoning_engine/domain/models.py` | production | `ReasoningTrace.multistep_recursion_exhausted: bool = False` (new field, §1). |
| `services/reasoning-engine/src/nova_reasoning_engine/domain/trace.py` | production | `build_trace()` gains `multistep_recursion_exhausted` param; new `chain_depth()` pure helper. |
| `services/reasoning-engine/src/nova_reasoning_engine/domain/pipeline.py` | production | `run()` gains internal-only `depth: int = 0` param; new `_derive_sub_question()` helper; the recursion trigger/aggregation block itself, inserted between the existing confidence-penalty step and the existing (unmodified) verify/override threshold branching. |
| `services/reasoning-engine/src/nova_reasoning_engine/observability.py` | production | Three new metrics on `ReasoningEngineMetrics`; new `record_multistep_recursion_metrics()` helper (the one place the trace-to-metrics derivation lives, called identically from all three entry points). |
| `services/reasoning-engine/src/nova_reasoning_engine/api/reason.py` | production | Both `/reason` and `/reason/stream` now call `record_multistep_recursion_metrics(trace, state.metrics)`. |
| `services/reasoning-engine/src/nova_reasoning_engine/events/handlers.py` | production | `reasoning.reason.request`'s handler now calls the same helper. |
| `services/reasoning-engine/tests/unit/test_pipeline.py` | test | One stale test replaced, seven tests added (§4). |

**No file outside `services/reasoning-engine` was touched.** No
`nova-contracts` change. No new Alembic migration. No `docker-compose`/CI
matrix change (nothing new to register).

---

## 3. Exact production SLOC delta

```
$ git diff --stat -- services/reasoning-engine/src
 api/reason.py        |  3 +
 domain/models.py     | 11 +
 domain/pipeline.py   | 83 ++++++++++++++++++-
 domain/trace.py      | 14 +++-
 events/handlers.py   |  2 +
 observability.py     | 51 +++++++++++
 6 files changed, 162 insertions(+), 2 deletions(-)
```

**Net production SLOC delta: +160** (162 insertions, 2 deletions), across
6 files, 0 new files.

---

## 4. Tests added

```
$ git diff --stat -- services/reasoning-engine/tests
 tests/unit/test_pipeline.py | 226 ++++++++++++++++++++--
 1 file changed, 214 insertions(+), 12 deletions(-)
```

One stale test replaced, seven new tests added (test count: 81 → 87 for
this package, net +6):

1. `test_multi_step_mode_does_not_recurse_when_confidence_meets_verify_threshold`
   — replaces the old `test_multi_step_mode_runs_a_single_pass_not_yet_a_chain`
   (whose docstring, pre-Phase-3A, asserted no trigger mechanism existed —
   now stale by construction). Confirms the non-triggering case explicitly.
2. `test_multi_step_mode_recurses_when_confidence_is_below_verify_threshold`
   — trigger boundary, confirms a real second `ReasoningProcess` is created
   and linked via `parent_process_id`.
3. `test_multistep_recursion_respects_max_step_depth_and_never_hangs` —
   depth-cap boundary; wrapped in `asyncio.wait_for(..., timeout=10.0)` as
   direct proof of non-hanging; confirms `chain_depth(trace) == 3` and
   `multistep_recursion_exhausted is True`.
4. `test_multistep_recursion_threads_parent_process_id_through_every_level`
   — walks the full persisted chain, confirms every level's
   `parent_process_id` points at its immediate parent, no level skipped or
   misattributed.
5. `test_multistep_confidence_aggregates_as_chain_minimum_not_average` —
   a purpose-built `_DegradingKnowledgePort` test fake (real knowledge on
   the first `context_assembly` call only) makes a recursive child's local
   confidence measurably lower than a knowledge-backed control run;
   confirms the returned confidence equals the child's value exactly, not
   something between it and the (higher) control value.
6. `test_low_confidence_non_multistep_mode_never_recurses` — the same
   unreachable `verify_threshold` under `ANALYTICAL` mode never builds a
   chain; direct regression proof the trigger is mode-scoped and the
   pre-existing `awaiting_human_override` path is untouched.
7. `test_recursion_lineage_is_distinct_from_correction_lineage` — a
   correction-linked process (`is_correction=True`, `parent_process_id=
   None`) and a recursion child (`parent_process_id` set, `is_correction=
   None`) are both produced in the same run and asserted never conflated.

Every verification-requirement checklist item the user named is covered by
name: trigger boundaries (tests 1, 2, 6), multiple depths (test 3, reaches
depth 3), max-depth exhaustion (test 3), chain-minimum confidence (test 5),
`parent_process_id` lineage (test 4), non-recursive path unchanged (test 6,
plus all 80 pre-existing tests passing unmodified), correction-lineage
distinctness (test 7).

---

## 5. Complete verification results

| Check | Result |
|---|---|
| `ruff check services/reasoning-engine` | Clean. |
| `mypy src` (the package's own configured gate, `package.json`'s `lint` script) | Clean, 52 source files. |
| Full `reasoning-engine` test suite (`pnpm --filter @nova/reasoning-engine test`) | **87/87 passed**, 0 failures. |
| Domain coverage (`--cov=nova_reasoning_engine.domain`) | 94% (well above the package's configured 85% gate). |
| Coverage negative control | `--cov-fail-under=100` correctly **fails** ("Total coverage: 90.75%") — the gate is genuinely wired, not a rubber stamp (§7 discloses exactly which pre-existing and new lines remain uncovered). |
| import-linter (`uv run lint-imports`) | **6/6 contracts kept**, 0 broken. |
| Full monorepo suite (`pnpm turbo run test --force`) | **19/19 packages passed, 1185/1185 tests passed** (1179 prior baseline + 6 net new, exactly matching this pass's own test-count delta). |
| Full monorepo lint (`pnpm turbo run lint --force`) | **19/19 packages passed.** |
| `docker-compose -f infra/docker/docker-compose.local.yml config --quiet` | Clean, no error (unchanged — nothing new to register). |
| TypeScript codegen | Not run — `packages/nova-contracts` untouched this pass (confirmed via `git status --porcelain packages/nova-contracts`, empty), so there is no new/changed payload to regenerate against. |
| Contract tests for the affected `nova-contracts` payload | **N/A** — no payload was changed (§1). |

---

## 6. Verification tier classification

Per the standing discipline of separating fully-verified / contract-fake
verified / real-infra verified / genuinely unverified:

**Fully verified, fake-backed (unit, through the real `pipeline.run()`,
never a real model/Postgres):** the entire recursion mechanism — trigger
boundaries, depth cap, exhaustion, chain-minimum aggregation,
`parent_process_id` lineage, correction-lineage distinctness, and the
non-recursive-path regression guard. This is the correct and complete tier
for this slice: `pipeline.run()`'s own logic was already,
by long-standing convention (`test_pipeline.py`'s entire pre-existing
suite), verified exclusively this way — no real Postgres or real model call
has ever backed any test in this file, this pass included.

**Contract-fake verified:** N/A — no wire contract changed (§1).

**Real-infrastructure verified:** N/A, and **correctly so** — this slice
introduced no new Postgres table/column beyond `ReasoningTrace`'s own
already-JSONB-serialized `trace_payload` (no migration needed, confirmed
in the TDD's own re-inspection of `repository/models.py`,
`ReasoningTraceORM.trace_payload: Mapped[dict]`), no new Event Bus subject,
and no new external dependency. There is nothing in this pass that a
real-Postgres/real-NATS run would exercise differently than the fake-backed
suite already does.

**Genuinely unverified:** none identified. The one deliberately
undertested branch (§7) is a defensive fallback, not a load-bearing path.

---

## 7. Discrepancies and limitations disclosed

- **§1's contract-addition discrepancy** — the TDD's own proposed
  `nova-contracts` changes were found unnecessary during implementation;
  documented above, not silently dropped.
- **One small, disclosed coverage gap**: `_derive_sub_question()`'s
  "no supporting evidence at all" fallback branch (`pipeline.py`, the
  `if not supporting: return f"What evidence supports or refutes..."`
  line) is not exercised by any test in this pass. Constructing a
  black-box scenario where the pipeline's top-ranked `chosen` alternative
  specifically carries zero `supporting_evidence_ids` while still reaching
  this pipeline stage (rather than failing earlier at the "no supported
  hypotheses" gate) would require deeper, fragile engineering of
  `evidence_collection.py`/`alternative_generation.py`'s own internal
  matching logic — assessed as out of proportion to the risk for a
  defensive fallback. This mirrors the existing, already-accepted,
  identical-class gap in `_resolve_reactive`'s own "no relevant
  information was found" branch, uncovered since Phase 2B. Both stay
  within the package's actual 85% coverage gate (94% actual) — not
  silently ignored, explicitly disclosed here.
- **No other limitation.** The recursion mechanism has no production
  caller beyond what already called `pipeline.run()` before this pass
  (`api/reason.py`, `events/handlers.py`) — it activates automatically,
  by construction, whenever a caller requests `ReasoningMode.MULTI_STEP`
  (or `reasoning_level_hint=4` with no explicit mode, per the existing,
  unmodified `resolve_mode_and_level` fallthrough) and first-pass
  confidence lands below `verify_threshold`. This is exactly the TDD's own
  scope — "this TDD making the mechanism real" — not a new integration;
  a real production caller defaulting to Level 3/4 requests remains a
  separate, future, out-of-scope integration question (per TDD 3A §10
  Non-goals, unchanged).

---

## 8. Recommendation

**Phase 3A is complete and fully verified within its own, correctly-scoped
tier (fake-backed unit verification through the real pipeline).** No
real-infrastructure gate applies to this slice, and none is owed. No other
Phase 3 component was touched. Ready for the user's review before any
further Phase 3 work (3B onward) is authorized.
