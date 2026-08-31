# Phase 3D — `action-engine`: Gate Review

**Status: Go — all 7 of TDD 3D §14's acceptance criteria are met, locally
verified, real GitHub Actions CI green (22/22 at head `046d459`). PR #13
merged into `phase-3b-planning-domain` 2026-08-18 as squash commit
`ac285bc3533fb24d0434d7675b8fc3af2db1d079`; the documentation PR (#14)
tracking this Gate Review subsequently merged the same day as merge
commit `e9ea3b8c6ae99c645e6eb41b98fbe34c55f8ec39`, both per the user's
explicit, separately-given merge approvals.** See §15 ("Acceptance
criteria") and §17 ("Final gate status") below.

This Gate Review was first written (2026-08-18) as part of a dedicated
Phase 3D documentation and project-state synchronization pass, separate
from and after the implementation pass that produced PR #13's original
commits. At that point six of seven criteria were met, and this document
recorded a "Conditional" status pending the user's decision on the
seventh (deep `Capability.input_schema` validation at stage 5). The user
directed that gap to be closed via implementation; a same-day follow-up
commit (`046d459`) did so, and this document was updated a second time,
the same day, to reflect the resulting "Go." The original "Conditional"
framing is preserved, not deleted, at §16 item 1 (struck through, with
the resolution recorded alongside it) — this project's standing
preserve-history convention.

PR #13 subsequently merged into `phase-3b-planning-domain` on 2026-08-18
as squash commit `ac285bc3533fb24d0434d7675b8fc3af2db1d079`, per the
user's explicit, separately-given merge approval (a "Go" gate status
never implies merge authorization on its own — see §17). This section and
§16/§17 below were updated the same day to record that merge; no other
content in this Gate Review was changed by that update.

It draws only on: the finalized TDD 3D (`docs/design/phase-3/07-tdd-3d-action-engine.md`),
the approved research/plan (`docs/design/phase-3/13-3d-action-engine-research.md`,
originally PR #12, synced into canonical lineage 2026-08-19 via PR #15), PR #13's actual diff and CI
history, and direct inspection of the implementation on the
`phase-3d-action-engine` branch. No historical metric is estimated; where
a value was not recorded anywhere, this document says "Not reported."

---

## 0. Scope executed

Full implementation of TDD 3D (`docs/design/phase-3/07-tdd-3d-action-engine.md`)
against the three decisions approved in PR #12's research document
(§5.1–§5.3), minus the one gap disclosed in §14:

- `nova_contracts.events.action` — `Action`, `RetryPolicy`,
  `RollbackStrategy`, `ActionExecuteRequestPayload`, `ActionResultPayload`,
  `ActionApprovalRequestedPayload`, `ActionApprovalDecidedPayload`.
- An additive `name: str | None` field on
  `CapabilityResolveRequestPayload` (backward compatible per ADR-024) plus
  `capability-engine`'s `find_by_name` repository method and resolve-handler
  branch — the mechanism `execution_target` resolution depends on (§5.1).
- `services/action-engine` (new): domain layer (`pipeline.py`, `models.py`,
  `ports.py`, `risk.py`), `CapabilityClient`/`CommunicationClient`/
  `IdentityClient` adapters, PostgreSQL persistence (`action` schema,
  hand-written Alembic migration), the `action.execute` RPC handler, `POST
  /v1/action/approvals/{id}/decide`, observability (6 named metrics), and
  the full test suite (unit/contract/integration/real-infra).
- Infra wiring: `docker-compose.local.yml` (`action-engine`, port 8012),
  `build-and-scan.yml`/`real-infra-checks.yml` matrices, root
  `pyproject.toml` import-linter (ADR-020 `source_modules` entry;
  ADR-004/006/007 auto-registered by `tools/scaffold-engine.py`; ADR-034
  already present).

---

## 1. Architectural decisions implemented, exactly as approved

**§5.1 (`execution_target` = capability name):** `CapabilityResolveRequestPayload`
gains an additive `name: str | None` field; exactly one of
`capability_id`/`name` is required (validated). `capability-engine`'s
resolve handler branches on which is set; `find_by_name` added to
`domain/ports.py`'s repository Protocol and to
`PostgresCapabilityRepository`. `action-engine`'s pipeline resolves
`Action.execution_target` through this new `name` path exclusively —
never a raw `capability_id` guess.

**§5.2 (stage-2/stage-5 validation split) — fully implemented (closed
2026-08-18, commit `046d459`; see §9a and §15 criterion 7):** stage 2
(`domain/pipeline.py`) checks only `parameters['operation']` presence —
structural, not schema-level. Stage 5 (post-resolution, pre-invocation)
validates the resolved `Action.parameters` against `Capability.input_schema`
via `domain/parameter_validation.py`, before proceeding to
`CapabilityPort.invoke()`. This was, until the same-day follow-up commit
noted here, the one approved decision not fully built — the gap was
disclosed, not silently marked done, in TDD 3D §14 criterion 7 and
`docs/project-health/phase-3d.md` field 18 before it was closed.

**§5.3 (`Action.id` natural-key idempotency):** `insert()` on
`PostgresActionRepository` translates a primary-key uniqueness violation
into `ActionAlreadyExistsError`, mirroring Fork 3C-4's `(name, version)`
precedent. A repeat request for an already-terminal `action_id` returns
the stored result unmodified (`get_result()`); a concurrent-retry race
resolves to "already in flight," never a duplicate execution or a hard
failure — verified by real-Postgres CI (§13).

**Fork 3C-3 (rollback ownership, Option B, resolved by Phase 3C):**
`action-engine` owns rollback entirely, via a read-before-write pattern
against `capability-engine`'s existing, unmodified `capability.invoke.request`
RPC (read current state, execute, and on failure re-invoke to restore it).
Only `restore_file` has a concrete, automated mechanism — the same scope
boundary Phase 3C's own Gate Review (§10) already disclosed for adapters
generally.

**Fork E2 (Phase-3-owned `action.approval.*` namespace):** the approval
loop publishes `action.approval.requested`/`action.approval.decided` —
never `autonomy.approval.*`/`autonomy.decision.made`, reserved for Phase
4. Tested directly
(`test_fork_e2_namespace_boundary_never_uses_autonomy_prefix`).

---

## 2. Action Object Model

Implemented per TDD 3D's own model (`nova_contracts.events.action.Action`):
`id`, `action_type`, `priority`, `source`, `requested_by`,
`execution_target`, `depends_on`, `parameters`, `expected_result`, `risk`,
`timeout_seconds`, `retry_policy`, `rollback_strategy`,
`required_permissions`, `status`, `verification_method`, `confidence`,
`result`, `error`, `created_at`. `RetryPolicy`/`RollbackStrategy` are
separate nested models, matching TDD 3D §5's shape exactly.

---

## 3. Contracts added

`packages/nova-contracts/src/nova_contracts/events/action.py` (new module):

| Type | Registered subject | Notes |
|---|---|---|
| `Action` | — (entity, not a payload) | The 20-field model above. |
| `RetryPolicy` / `RollbackStrategy` | — (entities) | Nested on `Action`. |
| `ActionExecuteRequestPayload` | `action.execute.request` | Carries a full `Action`; `schema_version`, `correlation_id`. |
| `ActionResultPayload` | `action.execute.reply` | `status`, `result`, `error`, `confidence`. |
| `ActionApprovalRequestedPayload` | `action.approval.requested` | Fork E2 namespace. |
| `ActionApprovalDecidedPayload` | `action.approval.decided` | Fork E2 namespace. |

Plus the additive `name: str | None` field on the existing
`CapabilityResolveRequestPayload` (§1). TypeScript codegen regenerated: 4
new `Action*.ts` files, `CapabilityResolveRequestPayload.ts`/`index.ts`
updated, idempotent on a second run.

---

## 4. Persistence

New `action` Postgres schema
(`services/action-engine/alembic/versions/0001_initial_schema.py`,
hand-written to match TDD 3D §8 exactly,
`version_table="alembic_version_action"` per this project's
cross-engine-Alembic-collision convention):

- `action.action` — the `Action` model's fields, `status` defaulting to
  `'pending'`, `id` as the natural-key primary key (§5.3's enforcement
  mechanism).
- `action.pending_approval` — `action_id` (FK to `action.action.id`),
  `risk`, `requested_at`, `decided_at`, `decision`. The approval loop's
  state.
- `action.action_execution_history` — append-only, one row per pipeline
  stage transition (`action_id`, `stage`, `outcome`, `detail`,
  `created_at`), indexed on `action_id`. Mirrors
  `capability.capability_installation_event`'s precedent.
- `action.identity_confidence_policy` — `user_id` (PK),
  `minimum_confidence_by_risk` (JSONB) — ADR-032's per-user, per-risk-tier
  policy store.

`PostgresActionRepository` implements the repository Protocol in full,
including the `IntegrityError` → `ActionAlreadyExistsError` translation
§5.3 depends on.

**One real bug caught only by real-Postgres CI, fixed before this Gate
Review:** `get_result()` originally read
`dict(row.result) if row.result is not None else None, row.error`, which
Python parses as a 2-tuple unconditionally (the ternary binds tighter than
the comma) — it never returned `None`, contradicting its own documented
"returns `None` if no result recorded yet" contract. Fixed in commit
`503a331` with an explicit `if row.result is None and row.error is None:
return None` guard.

---

## 5. Action Principle lifecycle (the 12-stage pipeline)

`domain/pipeline.py::execute_action()` implements TDD 3D §6's twelve
stages literally, each recorded to the append-only
`action_execution_history` table via an `on_stage(stage, outcome, detail)`
callback (mirrors `capability-engine`'s own `install_capability`'s
`on_stage` pattern, extended to 3 args so `main.py` can label metrics by
both stage and outcome/detail without `domain/` importing an observability
framework):

1. Receive request
2. Validate (structural only — see §1/§14)
3. Check permissions (ADR-032 identity-confidence gate, §6 below)
4. Resolve capability (§5.1's `name`-based resolution)
5. Prepare resources / approval gate (Critical-risk actions block here —
   §6 below)
6. Execute (via `CapabilityPort.invoke()`)
7. Verify result
8. Record execution history
9. Handle failure / recover if necessary (rollback, Fork 3C-3)
10. Retry if configured (`RetryPolicy`)
11. Finalize status
12. Return result

Idempotency short-circuit (§5.3): a repeat `action.execute.request` for an
already-terminal `Action.id` returns the stored result without
re-executing.

---

## 6. Approval loop and ADR-032 identity-confidence gate

**Approval loop (Fork E2):** Critical-risk actions publish
`action.approval.requested` and block on `POST
/v1/action/approvals/{id}/decide` (a stopgap endpoint — no `api-gateway`
yet, the same pattern every Phase 3 engine uses) or a configured timeout.
A timeout **denies**, never auto-approves — tested directly
(`test_critical_risk_action_timeout_denies_never_auto_approves`), matching
the roadmap's own acceptance criterion
(`ENGINEERING_ROADMAP.md:544`, "deliberately risky action ... blocked
pending approval and proceeds only after approval").

**ADR-032 gate:** stage 3 reads `world_model.context.request` for the
requester's `present_identities` and evaluates confidence against
`identity_confidence_policy`'s per-risk-tier thresholds. An absent policy
or an absent/timed-out confidence signal **fails closed** — treated as
zero confidence against a maximum-confidence-required default — tested
directly (`test_adr032_gate_fails_closed_on_absent_confidence_signal`)
plus an end-to-end RPC-level test. `action-engine` performs no identity
recognition itself; it only reads `world-model-engine`'s existing
`present_identities` field.

**Correction to PR #12 §5.4's "first-ever consumer" framing:**
`communication-engine`'s `addressee_fusion.py` already consumes
`present_identities` (for addressee detection, not ADR-032 authorization).
`action-engine` is the first **authorization** consumer of that field, not
the first consumer overall. TDD 3D's own text (§6, this canonical
document) never made the broader "first consumer" claim — only PR #12's
own, still-unmerged research document did — so no correction was required
in TDD 3D itself for this specific point. The correction is recorded here
and in `docs/project-health/phase-3d.md` field 23 for the permanent
record.

---

## 7. API surface

Exposed directly (no `api-gateway` yet): `POST /v1/action/approvals/{id}/decide`
(the approval-loop decision endpoint). `action.execute` itself is
Event-Bus RPC only (§8) — TDD 3D does not call for a REST execute
endpoint. Plus the standard `nova-service-kit`-style `/internal/health`,
`/internal/readiness`, `/internal/metrics`.

---

## 8. Event-bus request/reply implementation

`main.py`'s `_make_execute_request_handler` serves `action.execute.request`
via `bus.serve(...)`, mirroring `capability-engine`'s own
`_make_invoke_request_handler` pattern. It calls `execute_action(...)` and
increments `action_execute_total{action_type, outcome}` once per RPC call
(matching its own docstring); a separate `on_stage` closure increments the
five other named metrics, keyed on `(stage, outcome)` pairs, with `detail`
(e.g. `risk.value`, a decision string) as the label value where
applicable. Outbound: `CapabilityClient` (`capability.resolve.request`/
`capability.invoke.request`), `CommunicationClient`
(`communication.intent.deliver.request`, best-effort, wrapped in
`contextlib.suppress(TimeoutError)`), `IdentityClient`
(`world_model.context.request`).

---

## 9. Sandbox / risk classification

`domain/risk.py` classifies `Action.risk` (`negligible` through
`critical`) independently of `capability-engine`'s own sandboxing (Fork
E3) — `action-engine` never re-implements capability-level sandboxing; it
only decides whether an action needs approval and at what identity-
confidence threshold, per ADR-032 and TDD 3D §7.

---

## 9a. Deep parameter validation (§5.2's stage-5 half, closed 2026-08-18)

`domain/parameter_validation.py` (new, pure, framework-free, 100% test
coverage): `validate_parameters(parameters, *, input_schema)` validates
`Action.parameters` against the resolved `Capability.input_schema` via
the `jsonschema` library — `input_schema` already carries genuine JSON
Schema vocabulary (`type`/`properties`/`required`, unchanged from Phase
3C's `builtin_capabilities.py`), so this is literal JSON Schema
validation, not a bespoke reimplementation. Wired into `domain/pipeline.py`
stage 5, immediately after capability resolution/health-check and before
stage 6 (Execute) — matches §5.2's own "immediately before proceeding to
stage 6" requirement exactly. A validation failure returns a single
human-readable `str` error (matching every other stage-5 failure path)
and is a distinct `status="failed"` outcome, never `status="denied"`, per
§5.2's own "Consequences." A malformed `input_schema` (a
`capability-engine`-side data-quality problem) is reported with a
distinguishable message prefix from an invalid caller-supplied
`parameters` dict. `jsonschema>=4.23` added to `action-engine`'s own
dependencies; ships no `py.typed` marker, so a
`[[tool.mypy.overrides]]` entry was added to root `pyproject.toml`,
matching the existing `asyncpg`/`pgvector`/`testcontainers` precedent
exactly — no new architectural pattern introduced.

---

## 10. Testing and verification results

| Check | Result | Classification |
|---|---|---|
| `action-engine` ruff + mypy (`src`) | Clean | Fully verified |
| `action-engine` test suite (`-m "not real_infra"`) | 62/62 passed, 8 deselected (47 original + 15 new for stage-5 deep validation, commit `046d459`) | Fully verified |
| `action-engine` domain coverage | 97% (`pipeline.py` 95%, `parameter_validation.py` 100%, `models.py`/`ports.py`/`risk.py` 100%) vs. 85% gate | Fully verified |
| `capability-engine` regression (additive `name` field) | 61/61 passed, 6 deselected, domain coverage unchanged at 97% | Fully verified |
| `nova-contracts` | 86/86 passed | Fully verified |
| Full monorepo suite (`pnpm turbo run test --force`) | 22/22 packages successful | Fully verified |
| import-linter | 6/6 contracts kept; `nova_action_engine` in `root_packages`, ADR-020 `source_modules` entry added | Fully verified |
| `docker-compose config` | Valid with the new `action-engine` service block | Fully verified (syntax only — no daemon reachable locally) |
| TypeScript codegen | 4 new `Action*.ts` files, `CapabilityResolveRequestPayload.ts`/`index.ts` updated, idempotent on rerun | Fully verified |
| Alembic migration (`0001_initial_schema.py`) | Hand-written, matches `repository/models.py` field-for-field; executed for real by CI (`real-infra (action-engine, ...)`) | Real-infrastructure-verified |
| Real-Postgres persistence (`tests/integration/test_repository_real_postgres.py`) | 8 tests (insert/find/duplicate-rejection/status+result round trip/`get_result` None-before-recorded/pending-approval round trip/execution-history insert/identity-confidence-policy round trip) | **Real-infrastructure-verified** — not run locally (no Docker daemon in this environment); run for real by CI, passed after one fix-forward commit (§4, §11) |
| Docker build (`services/action-engine/Dockerfile`) | Built and Trivy-scanned by CI | Real-infrastructure-verified |
| GitHub Actions CI (all 3 workflows) | **22/22 check runs green at head `046d459`** (confirmed live, 2026-08-18, after the deep-validation commit — real-Postgres and Docker/Trivy jobs included) | Real-infrastructure-verified |
| Deep `Capability.input_schema` validation (§14 criterion 7) | **Implemented** (§9a) — 15 new tests, 100% coverage on `parameter_validation.py` | Fully verified, real GitHub Actions confirmed at head `046d459` |

---

## 11. Two real bugs found only by real-Postgres CI (disclosed, not hidden)

No Docker daemon was reachable in the implementation environment, so
`test_repository_real_postgres.py` could not run locally — exactly the
standing limitation every prior Phase 3 engine in this repo has disclosed.
The first CI run (`21b4b07`) caught two genuine bugs:

1. **`get_result()` operator-precedence bug** — see §4. Fixed in `503a331`.
2. **`test_pending_approval_insert_find_and_decide_round_trips` FK
   violation** — the test inserted a `pending_approval` row for an
   `action_id` with no parent `action` row, violating
   `pending_approval.action_id`'s foreign key. This was a **test bug, not
   a production bug** — production code always calls `insert(action)`
   before `insert_pending_approval` in the approval loop
   (`domain/pipeline.py::_run_approval_loop`). Fixed by inserting the
   parent row first in the test.

Both fixed in commit `503a331`; CI re-ran fully green. This is exactly the
class of defect real-infrastructure CI exists to catch and fake-backed
unit tests structurally cannot.

---

## 12. Known limitations (of this PR's scope, not defects)

- Only `restore_file` has a concrete, automated rollback mechanism (Fork
  3C-3's disclosed scope, inherited from Phase 3C's adapter set).
- No `api-gateway` yet — the approval-decision endpoint is a stopgap
  direct REST call, the same pattern every Phase 3 engine uses until
  Phase 3's gateway/web-client prerequisite (still design-only, no
  production code authorized per
  `docs/design/phase-3/03-gateway-web-prerequisite.md` line 3) ships.
- Deep `Capability.input_schema` validation at stage 5 reports a single
  human-readable string, not a structured multi-error list — matches
  every other stage-5 failure's existing convention in this pipeline
  (§9a), a deliberate scope choice, not a defect.

---

## 13. Phase 3C contamination check (backward)

**None found.** No modification to `capability-engine`'s installation
pipeline, sandboxing, or adapter set. The only `capability-engine` change
is the additive `find_by_name` method and the resolve handler's new
branch — both backward compatible (existing `capability_id`-based callers
unaffected) and covered by `capability-engine`'s own regression suite
(§10, 61/61 passed, coverage unchanged).

## 14. Phase 3E contamination check (forward)

**None found.** No `agent-os`, no `AgentContext`, no Kernel Scheduler, no
agent registry. `services/agent-os` does not exist in this branch. The
`action.approval.*` namespace (Fork E2) is deliberately kept separate from
`autonomy.*` (reserved for Phase 4) — verified by a dedicated boundary
test, not just documented intent.

---

## 15. Acceptance criteria (TDD 3D §14, as amended by this documentation pass)

| # | Criterion | Status |
|---|---|---|
| 1 | Deliberately risky action blocked pending approval, proceeds only after approval | **Met** — approval loop, tested |
| 2 | Approval timeout denies, never auto-approves | **Met** — tested directly |
| 3 | `action.approval.*` never confused with `autonomy.approval.*` | **Met** — tested directly (Fork E2 boundary test) |
| 4 | ADR-032 gate blocks a low-confidence-identity Critical-risk attempt, per-risk-tier configurability exercised | **Met** — tested directly |
| 5 | Forced mid-execution failure triggers configured `RollbackStrategy`, restores prior state | **Met** — `restore_file` path tested |
| 6 | Fork 3C-1/3D-1 and its rollback/snapshot consequence resolved, no outstanding TDD 3C/3D reconciliation | **Met** — resolved by Phase 3C, re-confirmed here |
| 7 | Stage-2/stage-5 validation split (research doc §5.2) implemented as specified | **Met** (2026-08-18, commit `046d459`) — stage 5 validates `Action.parameters` against the resolved `Capability.input_schema` via `jsonschema`, immediately before stage 6 (Execute); a failure is `status="failed"`, never `"denied"`. See §9a. Originally added "Not met" to TDD 3D §14 by this documentation pass (2026-08-18); closed the same day by a follow-up commit to PR #13. |

**7 of 7 criteria met.** No open acceptance-criteria gap remains.

---

## 16. Unresolved decisions requiring the user's approval

1. ~~**Deep `Capability.input_schema` validation (criterion 7 above).**~~
   **Resolved (2026-08-18):** implemented via option (a) from the original
   three offered here — a follow-up commit to PR #13 (`046d459`), before
   merge. Kept struck through rather than deleted, per this project's
   preserve-history convention: the original three-option framing (a:
   implement now / b: merge with the gap accepted / c: treat as a design
   gap needing a spec note first) is left visible below for the record.
   - *(a)* Implement it now, in a follow-up commit to PR #13, before
     merge — **this is what happened.**
   - *(b)* Merge Phase 3D as-is with this criterion explicitly accepted
     as a disclosed, deferred gap — not chosen.
   - *(c)* Treat it as a design/documentation gap requiring a small
     follow-up design note first — not chosen; the research document's
     own §5.2 already specified enough (JSON Schema vocabulary, stage
     placement, failure-status shape) to implement directly without a
     separate design note.
2. **SLOC methodology** (`scc` vs. `cloc`, `docs/project-health/project-health-master.md`
   §2) — pre-existing open decision, unaffected by Phase 3D, restated here
   only because Phase 3D's own SLOC fields are "Not reported" and any
   future measurement will need this resolved first. **Still open.**
3. ~~**`phase-3d-research`/PR #12 sync timing.**~~ **Resolved (2026-08-19):**
   deliberately not merged into canonical lineage until both implementation
   PRs merged, consistent with the precedent PR #11 established (sync after
   the implementation PR merges, not before). PR #13 (2026-08-18, squash
   commit `ac285bc3533fb24d0434d7675b8fc3af2db1d079`) and PR #14 (2026-08-18,
   merge commit `e9ea3b8c6ae99c645e6eb41b98fbe34c55f8ec39`) both merged,
   unblocking the sync; it completed via PR #15 (2026-08-19, merge commit
   `bf748d0ef4157da3a60e0eb880a24a58264d9387`). Kept struck through rather
   than deleted, per this project's preserve-history convention.

**Remaining decisions requiring the user's approval before Phase 3E
begins:** PR #13, PR #14, and PR #15 have all merged (see §17); item 2
above (SLOC methodology) remains open but does not block Phase 3E on its
own — Phase 3E itself still requires the user's separate, explicit
approval to begin.

---

## 17. Final gate status

**Go.** All seven acceptance criteria are met (§15), CI is fully green
(22/22, real GitHub Actions, real-Postgres and Docker/Trivy included) at
head `046d459` — confirmed live, 2026-08-18, after the deep-validation
commit — and no regression was introduced in `capability-engine` or
`nova-contracts` (§10, §13). This supersedes this document's own prior
"Conditional" status (recorded above at §16 item 1, now resolved): the one
gap that prevented an unqualified "Go" — deep `Capability.input_schema`
validation at stage 5 — is closed. Phase 3D is implementation-complete and
CI-green. **PR #13 merged into `phase-3b-planning-domain` on 2026-08-18 as
squash commit `ac285bc3533fb24d0434d7675b8fc3af2db1d079`. This
documentation PR (#14) subsequently reached 22/22 fresh CI green against
the new canonical base and merged the same day as merge commit
`e9ea3b8c6ae99c645e6eb41b98fbe34c55f8ec39`, per the user's explicit,
separately-given merge approvals for each PR.** Reaching "Go" never
implied merge authorization on its own for either PR — each merge
required its own separate approval, which is now recorded here. Phase 3E
has **not** begun and still requires the user's explicit approval to
start. **Update (2026-08-19):** the `phase-3d-research`/PR #12 sync (§16
item 3) also merged, as PR #15, merge commit
`bf748d0ef4157da3a60e0eb880a24a58264d9387` — with it, all Phase 3D
implementation, closure, and research documentation is now in canonical
lineage. **No branch has been deleted** as part of this Gate Review, the
closure pass that produced it, or the subsequent merges of PR #13, PR
#14, or PR #15 — `phase-3d-action-engine`, `phase-3-documentation-completion`,
and `phase-3d-research` all still exist post-merge, pending a separate
branch-cleanup decision.
