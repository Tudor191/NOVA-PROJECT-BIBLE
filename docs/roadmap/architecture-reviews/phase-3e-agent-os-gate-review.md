# Phase 3E — `agent-os`: Gate Review

**Status: COMPLETE. Verdict: CONDITIONAL-GO (2026-08-29).**
Branch `phase-3e-agent-os`, head `60934ac07166acd3635e3bf33dee9462d97f8a04`,
working tree clean, nothing unpushed, **no PR open, and no GitHub Actions
run has ever executed against any Phase 3E commit.** Every figure below was
produced by a command run in the session that wrote this document, against
that exact SHA, per
[`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md)
§0.3.1.

> **Document history.** From 2026-08-20 to 2026-08-29 this file was an
> explicitly-marked placeholder ("structure only — not yet applicable",
> gate status "Not Go. Not Conditional. Not applicable in either sense").
> That placeholder was accurate when written: no implementation existed.
> It has now been replaced by a completed review rather than preserved
> alongside one, because it contained no historical claim to preserve —
> every section read "not yet", "not applicable", or "not attempted". The
> two additive 2026-08-19 update notes it carried (fork approval; the
> approval-is-not-implementation-authorization clause) are both carried
> forward verbatim in §1 below.

---

## 0. Scope executed, and what was deliberately not executed

**Executed**, per `docs/design/phase-3/08-tdd-3e-agent-os.md` §0:

| Deliverable | Location | Status |
|---|---|---|
| `agent-os/kernel` | `agent-os/kernel/` (21 mypy source files) | Built — Scheduler, `agent_instance` persistence, restart reconciliation, `InprocessExecutionBackend`, peer-review orchestration |
| `agent-os/registry` | `agent-os/registry/` (18) | Built — filesystem discovery, eight-stage install pipeline, `agent_package` persistence, version selection |
| `agent-os/supervisors` | `agent-os/supervisors/` (20) | Built — `engineering` Supervisor: restart strategies, peer-review classification, two-level conflict escalation |
| `agent-os/sdk/python` (`nova-agent-sdk`) | `agent-os/sdk/python/` (5) | Built — `AgentHandler` Protocol, `AgentManifest`, lifecycle |
| Five Agent Packages | `agents/{research,coding,qa,architect,documentation}-agent/` | All five built, all at `0.1.0` |
| `GoalsPort` real-RPC migration | `services/{reasoning,executive-cognition}-engine/clients/goals_client.py`, `services/planning-engine/events/goals_handler.py` | Built |
| Scaffolding prerequisite (Fork 3E-4) | `tools/scaffold-agent-os-component.py`, `tools/scaffold-agent-package.py` | Built; `tools/scaffold-engine.py` unchanged as approved |
| TDD 3B §6.1 `agent_os.task.completed` subscription | `services/planning-engine/domain/task_completion.py` | Built — closes 3B's last deferred item |

**Deliberately not executed**, each already sanctioned by an approved
document: Research/Operations Supervisors; `subprocess`/`container`/`remote`
backends (`agent-os/execution-backends/` intentionally not created, TDD 3E
§2); the Executive-Cognition→`communication.intent.ready` hop (TDD 3E §15);
agent categories beyond the five; Git/HTTP/marketplace discovery;
`packages/nova-auth` (TDD 3E §5 item 5, declared-intent-only).

**Not executed and NOT previously sanctioned** — the four deviations in §2.

---

## 1. Architectural decisions

### 1.1 The six pre-implementation decisions (approved 2026-08-19)

Carried forward verbatim from this document's superseded placeholder:

> **Update (2026-08-19), additive.** All four forks (3E-1 through 3E-4) are
> now **approved**, and the two remaining open items (`nova-auth` scope,
> `priority`'s critical-path-position formula) are **resolved** — full
> record in `14-3e-agent-os-research.md` §9/§8a/§8b and
> `08-tdd-3e-agent-os.md` §11. This is an approval of the **architectural
> decisions only** — it does not authorize starting Phase 3E's own
> implementation PR (a separate approval, not yet given).

Each re-verified against the shipped source this pass:

| # | Decision | Implemented at | Verified |
|---|---|---|---|
| 3E-1 | `AgentResult` → `nova_contracts.entities`; `AgentMessage` → `nova_contracts.events.agent_os` with `schema_version` + `@register_payload` | `entities.py`; `events/agent_os.py:73` | Yes |
| 3E-2 | `agent_os` Postgres schema: `agent_instance` + `agent_package` | `agent-os/kernel/repository/`, `agent-os/registry/repository/` | Yes — both verified against real PostgreSQL 16.13 |
| 3E-3 | `goal_tier = "established"` iff `len(nodes) > 1`, derived at read time, never persisted | `planning-engine/events/goals_handler.py` | Yes |
| 3E-4 | Two separate scaffold scripts; `scaffold-engine.py` untouched | `tools/scaffold-agent-os-component.py`, `tools/scaffold-agent-package.py` | Yes — `git log` shows no change to `scaffold-engine.py` in `c6c6c59..HEAD` |
| Item 5 | `nova-auth` not built; Permission Review is a local diff-and-display; no `execute()`-time re-validation | `agent-os/registry/domain/pipeline.py` | Yes — `packages/nova-auth` does not exist |
| Item 6 | `priority = 1.0 - (rank_index / max(1, len(active) - 1))` | `planning-engine/events/goals_handler.py` | Yes |

### 1.2 The three implementation-phase design decisions

Each has its own approved design document under `docs/design/phase-3/`:

| Doc | Decision | Approved | Implemented |
|---|---|---|---|
| `15-3e-supervisor-reconciliation.md` §A | Registry idempotency key is `(category, version)`, not `(id, version)`, with a UUID surrogate PK | 2026-08-23, explicit user decision | `107b0d8` |
| `16-3e-hot-load-design-decision.md` | Criterion #3 satisfied by version pinning + scheduling hot-load (Option A), **not** concurrent execution of two bytecode versions | 2026-08-28, explicit user decision | `6d1de31` |
| `17-3e-task-node-lifecycle.md` | Planning Engine owns every `TaskNode.status` transition; admission at graph creation; ready→running hand-off; `outcome="failure"` terminal (a disclosed narrowing) | 2026-08-29 | `b874de5` |

### 1.3 D1–D12 — recovery attempt, and what could not be recovered

The user's instruction was to recover and verify every approved Phase 3E
architectural decision D1–D12 from available project history and repository
evidence, and **not to invent missing decisions**. Result of an exhaustive
search (`grep -rnE "\bD1[0-2]\b|\bD[1-9]\b"` across `*.py`, `*.md`, `*.yaml`,
`*.yml`, `*.toml`; full `git log --format="%H%n%s%n%b"` over `c6c6c59..HEAD`;
`git log --all --diff-filter=D` over `docs/design/phase-3/` for deleted
decision documents):

**Five of the twelve are fully recoverable from repository evidence**, each
with implementing code, tests, and prose citing it by number:

| # | Decision, as the repository records it | Primary evidence |
|---|---|---|
| **D5** | A code change is not a change until it is committed: `coding-agent` issues three `action.execute` requests per task — filesystem `write`, `git add` of exactly that path, `git commit -m "coding-agent: <objective>"` — and checks `exit_code` itself, because TDD 3C §8 makes a non-zero git exit a *structured* failure that `action-engine` still reports as `status="completed"`. The target repository must carry a **local** `user.name`/`user.email`, which D5 assigns to the fixture. | `agents/coding-agent/src/handler.py:19,50,53,298`; `README.md:13,40`; `tests/test_handler.py:38,181,209,361`; `tests/integration/test_real_git_commit.py:1,113,239,364`; TDD 3E §9's dated implementation note; commit `a873a8c` |
| **D6** | An agent-originated `ActionExecuteRequestPayload` sets `requested_by` to `AgentContext.world_model_slice.user_id` — the real user — never the ephemeral `agent_instance_id`, which ADR-032's identity-confidence gate resolves to confidence 0.0 against an absent policy (threshold 1.0) and therefore denies. Agent provenance stays on `Action.source`. Stated generally, so it covers `documentation-agent` as well as the two agents it names. | `agents/coding-agent/tests/test_handler.py:189`; `agents/qa-agent/tests/test_handler.py:138`; `agents/documentation-agent/src/handler.py:194`, `tests/test_handler.py:180`; `agent-os/kernel/tests/integration/test_phase_3e_end_to_end_acceptance.py:844`; commit `92f33f9` |
| **D7** | Relative paths anchor at the declared capability root, not `Path.cwd()`; `Settings.sandbox_filesystem_root` designates the target repository, and no `repo_root` is ever sent, so `GitAdapter` scopes to `required_resources[0]`. No target-repository field was invented. | `agents/coding-agent/src/handler.py:166,168`; `README.md:37`; `tests/test_handler.py:224`; `tests/integration/test_real_git_commit.py:277`; commit `92f33f9` |
| **D8** | TDD 3C §3's "restricted working directory": `TerminalAdapter` takes `default_cwd` from `Settings.sandbox_filesystem_root`, runs there when no `cwd` is given, validates a supplied one against it, and **refuses** a supplied `cwd` when no root is configured (fail-closed). A constructor argument, not a second meaning for `required_resources`. | `agent-os/kernel/tests/integration/test_phase_3e_end_to_end_acceptance.py:747`; commit `92f33f9` |
| **D9** | The minimal subprocess environment is still a single `PATH` with nothing inherited, but its value comes from `Settings.sandbox_terminal_path` rather than a hardcoded `/usr/bin:/bin` that cannot resolve the executables `sandbox_terminal_allowed_executables` itself names. The default stays a conventional POSIX path — a virtualenv path baked into the module is exactly the machine-specific hardcoding D9 rules out. | commit `92f33f9` |

**Seven are not recoverable: D1, D2, D3, D4, D10, D11, D12 appear nowhere
in the repository** — not in source, tests, documentation, commit messages,
or deleted files. No decision-ledger document has ever existed under
`docs/design/phase-3/` (confirmed against git history, not just the working
tree). The numbering itself is only ever attested indirectly: commit
`92f33f9` says "decisions D6/D7/D8/D9" and `a873a8c` says "decision D5",
which establishes that a contiguous ledger existed in a planning
conversation, but no artefact of it was ever committed.

**This is recorded as an unrecovered gap, not filled in.** Their content is
not inferred from surrounding slices, and no decision is reconstructed from
what the code happens to do. **Open condition C-6 in §10.** Note that the
D-numbering is unrelated to the `D-1`/`D-2` *defect* labels in commit
`60934ac`, which are the two real-Postgres bugs, not decisions.

Note also that §1.1's six + §1.2's three = **nine** approved architectural
decisions that *are* fully documented in the repository, plus five
recoverable implementation decisions = **fourteen recorded decisions**. The
gap is specifically in the D-series numbering, not in the project's
architectural record as a whole.

---

## 2. Deviation register

Protocol §1.1 classification. Four items; **three were undisclosed until
this review**, and all four are now disclosed additively in the TDD.

| # | Deviation | Class | Disclosed at | Approved? |
|---|---|---|---|---|
| DEV-1 | **Kernel Scheduler step (2), scoring, is not implemented.** TDD 3E §4 specifies a four-step loop; `dispatch_task_node` performs registry-query, backend-select and dispatch, with the Registry's own highest-healthy-version policy as the sole selection input. No `AgentMetrics` scoring, no load or resource-availability input, and no call to `executive-cognition-engine` (grep: zero references to `executive`/`arbitrate`/`cognitive_priority` under `agent-os/kernel/src/`). | **Partially disclosed drift** — `16-3e-hot-load-design-decision.md` §5 disclosed the `AgentMetrics` half against doc 12 §6; the load / resource / Cognitive-Priority-Matrix inputs TDD 3E §4 names were undisclosed. | TDD 3E §4 (new note, this review) | **No** — condition C-4 |
| DEV-2 | **`agent.<instance_id>.<state>` lifecycle events are not published.** TDD 3E §10 lists them under "Published"; doc 12 §5 specifies them. No payload in `nova-contracts`, no entry in any `PUBLISHABLE_SUBJECTS`, no publisher. Instance state lives only in `agent_os.agent_instance.status`. | **Undisclosed drift** | TDD 3E §10 + doc 12 §15 (new notes, this review) | **No** — condition C-4 |
| DEV-3 | **`agent_os.health.snapshot` is not published and has no contract.** TDD 3E §10 lists it under "Published" and §6 states the payload "also lives in `events/agent_os.py`". It does not. Nothing aggregates health. | **Undisclosed drift** | TDD 3E §10 + doc 12 §15 (new notes, this review) | **No** — condition C-4 |
| DEV-4 | **`planning.decompose.request` is never called by any `agent-os` component.** TDD 3E §10 says "this TDD is the RPC's first real caller"; it is not. §12's already-minimal-node row therefore describes an unexecuted path. The RPC itself is served and tested by `planning-engine`. | **Undisclosed drift** | TDD 3E §10 (new note, this review) | **No** — condition C-4 |

**Already-disclosed narrowings, re-verified and unchanged** (not deviations):
`outcome="failure"` as terminal (`17-3e-task-node-lifecycle.md`);
hot-load = version pinning (`16-3e-hot-load-design-decision.md` §2);
`AgentContext.relevant_memory`/`relevant_knowledge`/`granted_permissions`/
`granted_capabilities` all empty and `world_model_slice.degraded=True`
always (`agent-os/kernel/domain/scheduler.py` module docstring);
`agent_os.instance.*.inbox` declared but with no live receiver, peer review
travelling in-process instead (`agent-os/supervisors/events/published.py`
docstring); `planning.goals.current` replies unfiltered by `user_id`
because `task_graph` has no ownership column
(`planning-engine/domain/ports.py`).

**Correction to a source docstring, already made during implementation:**
`agent-os/kernel/domain/scheduler.py` had claimed doc 12 §15's table
classifies parallel dispatch as "already-designed-for, not shipped". That
table has six rows and contains no such row; the claim was asserted only in
that docstring. Corrected in `c4bc2a4`. Re-verified against doc 12 §15 this
pass: the table still has exactly six rows and still contains no such row.

---

## 3. ADR conformance

| ADR | Verdict |
|---|---|
| ADR-004 / ADR-006 (import boundaries) | **Kept** — `uv run lint-imports`: *Contracts: 7 kept, 0 broken.* `nova_agent_os_kernel`, `nova_agent_os_registry`, `nova_agent_os_supervisors`, `nova_agent_sdk` all registered in `root_packages`; the seventh contract ("nova-agent-sdk has no engine-specific knowledge") is Phase 3E's own addition. |
| ADR-005 / doc 12 §14 | **Kept** — no agent or Supervisor publishes `communication.intent.*`; neither subject appears in any `PUBLISHABLE_SUBJECTS`. |
| ADR-008 (purpose-built NAOS) | **Implemented** — this phase is its first realisation. |
| ADR-020 (sole legal model channel) | **Kept** — every model boundary in every Phase 3E test is a fake; `ai_model.generate.request` is the only model subject in `agent-os/kernel`'s publishable set. |
| ADR-029 (`goal_tier`) | **Kept** — Fork 3E-3's derivation is tie-break-only and read-time. |
| ADR-032 (identity-confidence gate) | **Kept, and load-bearing** — D6 exists precisely because this gate is real: `requested_by` is the user, never the instance. |
| ADR-033 (two-tier testing, `real_infra`) | **Kept** — all 59 Phase-3E-relevant `real_infra` tests are correctly marked and deselected by the default tier. |
| ADR-034 | **Kept** — contract 6 unchanged. |

**No ADR was falsified by this phase, and no new ADR is required.** The
four DEV items are TDD-level, not ADR-level.

---

## 4. Contracts added

`git diff --stat c6c6c59..HEAD -- packages/nova-contracts/` → **19 files,
1,112 insertions, 1 deletion.**

New in `nova_contracts.entities`: `AgentContext`, `AgentHealth`,
`AgentMetrics`, `AgentResult`, `WorldModelSnapshot`, `TaskNodeSnapshot`
family (+162 lines).
New module `nova_contracts.events.agent_os` (+273): `AgentMessageType`,
`AgentMessage`, `AgentOsTaskCompletedPayload`, `AgentPackageSnapshot`,
`AgentOsFindHealthyPackage{Request,Reply}Payload`,
`AgentOsRestartPlan{Request,Reply}Payload`,
`AgentOsPeerReview{Request,Reply}Payload`.
Additive to `events/planning.py` (+50):
`PlanningGoalsCurrent{Request,Reply}Payload`.

Contract tests: `test_agent_os_entities.py` (+102), `test_agent_os_events.py`
(+75), `test_planning_events.py` (+29). 12 contract-test modules total; 104
tests pass.

**All additions are additive.** No field was removed, no optional field made
required, no `schema_version` bumped. Every new payload carries
`schema_version: int = 1` and `@register_payload`.

**Codegen drift: zero.** `uv run python
packages/nova-contracts/codegen/generate_typescript.py` → "Generated 97
TypeScript contract file(s)"; `git status --short packages/nova-contracts`
→ empty. (97 counted + the `index.ts` barrel = 98 files on disk, the
expected relationship.)

**Not added, and this is DEV-3:** no `agent_os.health.snapshot` payload
exists.

---

## 5. Persistence

New `agent_os` Postgres schema, two tables, two independent Alembic chains
with namespaced `version_table`s (`alembic_version_agent_os_kernel`,
`alembic_version_agent_os_registry`), each `0001` using
`CREATE SCHEMA IF NOT EXISTS` — the pre-existing property that let the
real-Postgres E2E put **six engines' schemas in one database with no
architectural change**.

- `agent_os.agent_instance` — owned by `agent-os/kernel`.
- `agent_os.agent_package` — owned by `agent-os/registry`; natural key
  `(category, version)` with a UUID surrogate PK (decision `15-…` §A).

No other engine's schema changed. The two Phase 3E remediation fixes
(`60934ac`) changed **no schema and no migration** — they are a serialization
fix and a persistence-ordering fix.

---

## 6. Testing and verification results

All figures from an **uncached** `pnpm turbo run lint test --force` at
`60934ac`: **52/52 tasks successful, 0 cached, exit 0, 1m2s.**

| Gate | Command | Result |
|---|---|---|
| Lint + types | `pnpm turbo run lint` | 26/26 pass; ruff clean; mypy clean across all 26 packages (kernel 21 source files, registry 18, supervisors 20, nova-agent-sdk 5, reasoning-engine 52, action-engine 23) |
| Tests (uncached) | `pnpm turbo run test --force` | 26/26 pass; **1,646 passed, 104 deselected, 0 failures** |
| Import boundaries | `uv run lint-imports` | **7 kept, 0 broken** |
| Scaffolding tools | `uv run pytest tools/tests -q` | **26 passed** |
| compose | `docker compose -f infra/docker/docker-compose.local.yml config --quiet` | valid, exit 0 |
| Codegen drift | generate + `git status` | 97 files; **zero drift** |

Per-package coverage against the 85% `fail_under` gate — every Phase 3E
package and every engine it touched:

| Package | Coverage | Tests |
|---|---|---|
| `agent-os/kernel` | **98%** (220 stmts, 5 miss) | 55 passed, 7 deselected |
| `agent-os/registry` | **99%** (205, 2) | 61 passed, 13 deselected |
| `agent-os/supervisors` | **96%** (135, 5) | 27 passed |
| `nova-agent-sdk` | n/a (no `domain/`) | 8 passed |
| `planning-engine` | **99%** (286, 2) | 135 passed, 15 deselected |
| `reasoning-engine` | **94%** (744, 45) | 94 passed, 6 deselected |
| `action-engine` | **97%** (254, 8) | 62 passed, 12 deselected |
| `capability-engine` | **97%** (195, 5) | 83 passed, 6 deselected |
| `executive-cognition-engine` | **98%** (332, 6) | 67 passed |
| `nova-contracts` | n/a | 104 passed |

Lowest figure repo-wide is `world-model-engine` at 86%, untouched by this
phase. **No package is below the gate.**

### 6.1 Agent Package tests — pass, but outside every gate

`agents/*` are not workspace members (no `package.json`, no
`pyproject.toml` — by design: they are Agent Packages discovered from the
filesystem by the Registry). They are therefore in **no** turbo pipeline
and **no** CI workflow, and `uv run pytest agents` from the repository root
fails collection with 9 errors. Run individually from each package
directory they all pass:

```
architect-agent:     13 passed        coding-agent:  22 passed
documentation-agent: 13 passed        qa-agent:      14 passed
research-agent:      11 passed                       (73 total)
```

Their `src/handler.py` files are also not linted and not type-checked.
**Open condition C-2.**

### 6.2 Negative controls (protocol §9.2)

Every property-asserting test added by Phase 3E was proven to fail when its
property was removed:

| Property | Control | Result |
|---|---|---|
| Parallel dispatch really overlaps | Revert `dispatch_ready_nodes` to a sequential `for` loop | All 3 concurrency tests fail; the two barrier-based unit tests deadlock on `asyncio.Barrier` |
| D5 commit step | Remove the `git commit` action | 4 integration + 7 unit tests fail |
| D7 root anchoring | Restore `Path(path).resolve()` | 5 tests fail |
| D8 restricted cwd | Remove `default_cwd` | 7 tests fail |
| D9 configurable PATH | Restore the hardcoded `/usr/bin:/bin` | 2 tests fail |
| D-1 fix (reasoning persistence order) | Revert `_resolve_reactive` | 6 unit + 5 of 6 real-Postgres tests fail; the sixth *asserts* the broken behaviour and correctly still passes |
| D-2 fix (`depends_on` JSONB) | Revert `str()`/`UUID()` pair | 3 of 4 new tests fail; the empty-`depends_on` case correctly still passes — which is exactly why it never caught this |

**One candidate control was rejected rather than reported.** Removing the
`qa` node's dependency in the E2E does not reliably fail: pytest interpreter
startup gives the other agents time to finish, so it is a race, not a
control. Discarded, not presented as evidence.

**One control was weaker than expected, and is recorded as such.** Forcing
sequential dispatch in the full E2E fails only `concurrent_peak == 1`; the
Kernel's bounded single retry recovers the other six assertions. The
rendezvous barrier therefore **proves overlap, not liveness** — stated in
that module's own docstring rather than overclaimed here.

### 6.3 Flakiness (protocol §9.2, ≥10× for timing/async/IO)

The real-Postgres acceptance E2E, 10 consecutive runs at `60934ac`:
`1 passed` every time — 11.21s, 11.08s, 10.91s, 9.96s, 9.90s, 9.88s, 9.83s,
9.78s, 9.80s, 9.83s. **10/10, no variance beyond warm-up.** The
`coding-agent` real-git integration suite was separately run 10× during
Slice 4 with no flakes.

---

## 7. Real-infrastructure results

**Reported separately per protocol §10.2. Never folded into §6.**

**Docker: NOT available.** `docker info >/dev/null 2>&1` → non-zero.
Testcontainers cannot start `postgres:16-alpine` in this environment.

**A real PostgreSQL 16.13 server is installed locally**
(`psql (PostgreSQL) 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)`), started for
this review with `pg_ctlcluster 16 main start`. Every `real_infra` suite
below was executed against it via a temporary, uncommitted `conftest.py`
shim that redirects nova-testkit's `postgres_container` fixture at the local
server. **The tests themselves were not modified**: they still call
`get_connection_url()`, still run their own real Alembic chains, and still
read back over real connections. Each package got its own database.

| Package | In `real-infra-checks.yml`? | Result here |
|---|---|---|
| `agent-os/kernel` | Yes | **7 passed**, 55 deselected — 6 repository tests + `test_the_acceptance_objective_completes_on_real_postgres` |
| `agent-os/registry` | Yes | **13 passed**, 61 deselected — incl. two-version coexistence, healthy-fallback, older-row-unmutated |
| `planning-engine` | Yes | **15 passed**, 135 deselected |
| `reasoning-engine` | **Yes — added by this phase** | **6 passed**, 94 deselected |
| `action-engine` | Yes | **12 passed**, 62 deselected (8 pre-existing + 4 new `depends_on` cases) |
| `capability-engine` | Yes | **6 passed**, 83 deselected |
| `agent-os/supervisors` | **No** | **No `real_infra` tests exist** (27 deselected → 0 collected). Correct: it has no repository layer. |
| `nova-testkit` | Yes | **11 collected, NOT RUN** — these test the Redis/Neo4j/NATS fixtures themselves and genuinely require a Docker daemon. |

**59 real_infra tests executed and passed against real PostgreSQL 16.13.**

**What remains unverified in any environment for this change:** the 11
`nova-testkit` fixture tests, which exercise Redis, Neo4j and NATS
containers. They do not touch any code Phase 3E changed — Phase 3E added no
Redis, Neo4j or NATS usage — so the exposure is nil for this phase, but the
statement is made explicitly rather than omitted.

**And the disclosure that matters most:** every result in this section was
produced against a locally-installed PostgreSQL, **not** against the
testcontainers path CI uses. The `real-infra-checks.yml` workflow — including
the `reasoning-engine` matrix entry this phase added — **has never run
against any Phase 3E commit**, because it triggers only on `pull_request`,
`push` to `main`, and a nightly schedule, and no PR exists. Its most recent
runs (#69, #70, both `success`) were scheduled runs against `main` at
`fe5a5b8`, which contains no Phase 3E code.

---

## 8. Known limitations

1. **`nova-auth` permission enforcement is declared-intent-only** — approved
   (TDD 3E §5 item 5); the same accepted gap already disclosed for
   `capability-engine` and `action-engine`. Kernel-side `execute()`-time
   permission re-validation (doc 12 §7) is correspondingly not implemented.
2. **`AgentContext` is not pre-scoped.** `relevant_memory` and
   `relevant_knowledge` are empty lists, `world_model_slice.degraded` is
   always `True`, and `granted_permissions`/`granted_capabilities` are
   empty. Doc 12 §4 describes a pre-scoped context; TDD 3E §4 names no
   mechanism for building one. Disclosed in the scheduler docstring.
3. **Peer review is a scripted consistency check, not analysis.**
   `architect-agent` approves iff the primary result's self-report is
   internally consistent — no LLM call, no static analysis. Same disclosure
   discipline as `action-engine`'s `classify_risk`.
4. **Hot-load is version pinning, not concurrent bytecode execution** —
   approved 2026-08-28, doc 16 §2.
5. **`planning.goals.current` is not filtered by user.** `task_graph` has no
   ownership column, so the RPC returns all active graphs. Flagged in
   `planning-engine/domain/ports.py` for a follow-on slice.
6. **`outcome="failure"` is terminal** — a disclosed narrowing (doc 17)
   resting on the Kernel always exhausting the Supervisor restart path and
   bounded retry first.
7. **Registry uninstall does not exist.** An old version's row is
   structurally permanent in Phase 3 (doc 16 §5).
8. **The four DEV items in §2** — scoring, lifecycle events, health
   snapshot, `planning.decompose.request` — are limitations that were not
   sanctioned in advance.

---

## 9. Acceptance criteria

Criteria enumerated from all four sources the protocol requires (TDD 3E §14;
`14-3e-agent-os-research.md`; `ENGINEERING_ROADMAP.md`'s Phase 3 entry; the
user's in-session statements).

**A note on source reconciliation.** The roadmap's Phase 3 entry lists
**four** acceptance criteria; TDD 3E §14 reproduces **three** of them plus
two of its own. The one the TDD omits — "a deliberately risky action is
blocked pending approval and proceeds only after approval" — is
**Phase 3D's**, met by Phase 3D (`phase-3d-action-engine-gate-review.md`
§9 criterion 1: "Met — approval loop, tested"), because the roadmap's list
is Phase-3-wide and spans 3D and 3E. **TDD 3E §14 is authoritative for
Phase 3E's own criteria.** No criterion is orphaned by this reading.

| # | Criterion (verbatim, TDD 3E §14) | Source | Status | Evidence |
|---|---|---|---|---|
| 1 | "A non-trivial multi-step coding objective produces a correct Task Graph, executes via at least two agent instances working in parallel where dependencies allow, includes at least one real peer-review round (`architect-agent` reviewing `coding-agent`'s output), and produces a verifiable result (a passing test suite in the target repo)." | Roadmap :542 → TDD §14 | **Met** | `test_phase_3e_end_to_end_acceptance.py` (7 tests) + `…_real_postgres.py` (1). Trigger is `POST /v1/reasoning/reason` — no hand-constructed `planning.task_graph.created`. Asserted from outside the system: a real commit read from git's own history (`rev-list`, `log`, `show --name-only`, `show HEAD:<path>`) on top of the fixture's initial commit; the target repo's own suite run by `qa-agent` through a real `pytest` subprocess exiting 0, containing assertions that hold only because the other agents really changed and committed the repository; `concurrent_peak == 2` via a two-party `asyncio.Barrier`; one real peer-review round classified by the real Supervisor; three terminal `agent_instance` rows each pinned to the `agent_package` row the real Registry installed. Real-Postgres variant: 10/10 runs. |
| 2 | "Killing `agent-os-kernel` mid-execution and restarting resumes in-flight Task Graph work rather than restarting it from scratch." | Roadmap :543 → TDD §14 | **Met with disclosed narrowing** | Kernel half: `test_restart_reconciliation.py` — a real `create_app()` entering its lifespan really calls `reconcile_running_instances` and really publishes `agent_os.task.completed` with `outcome="interrupted"` onto the bus; plus `tests/unit/test_reconciliation.py`. Planning half: `planning-engine`'s `test_events_agent_os_task_completed.py::test_kernel_restart_then_planning_resume_round_trip` resets the node to `"ready"` and republishes. **The narrowing:** no test kills a running OS process; "restart" is a fresh `create_app()`. The two halves are joined by an asserted payload shape, never by one executing process (ADR-004 forbids the cross-import). This is unit + integration + real-Postgres evidence, not full-path E2E. |
| 3 | "Installing `coding-agent@1.1.0` → `1.2.0` hot-loads without a kernel restart and without dropping in-flight instances of the old version." | Roadmap :544 → TDD §14 | **Met with disclosed narrowing** | `test_hot_load_version_pinning.py` — one `create_app()` and one `lifespan_context` stay open across both dispatches; the second pins to `1.2.0` while the first instance's row stays pinned to `1.1.0`'s package UUID. Registry side proven against the real selection policy and the real served RPC (`test_selection.py`, `test_events_find_healthy_package_request.py`) and against real Postgres (13 tests, incl. two-version coexistence and healthy-fallback). **Two narrowings:** (a) this is version pinning, not concurrent execution of two bytecode versions — approved, doc 16 §2; (b) the shipped package is `0.1.0`, so `1.1.0`/`1.2.0` are synthetic `agent_package` rows. |
| 4 | "`GoalsPort`'s real-RPC migration is provably transparent to both calling engines — no change to either engine's own `current_goals()` call sites, confirmed by an unmodified-caller regression test." | TDD §14 | **Met** | Both Protocols and both call sites are unchanged (`reasoning-engine/domain/ports.py:113`, `context_assembly.py:68`; `executive-cognition-engine/domain/ports.py:91`, `coordinate.py:117`); only the two `clients/goals_client.py` adapters changed. `reasoning-engine/tests/contract/test_port_compliance.py` is the regression test. |
| 5 | "Every one of the five agents' manifest validates against `AgentHandler` before the Registry will register it." | TDD §14 | **Met** | `agent-os/registry/domain/pipeline.py:311` — `issubclass(handler_class, AgentHandler)` gates the Register stage; failure raises before any row is written. Exercised against all five real on-disk packages by `test_real_{research,coding,qa,architect,documentation}_agent_installs.py`. |

> **3 of 5 acceptance criteria are Met outright. 2 are Met with disclosed
> narrowing: #2 and #3 are proven at unit, integration and real-Postgres
> level rather than by a full-path end-to-end test, and #3 additionally
> covers version pinning rather than concurrent execution of two bytecode
> versions (approved 2026-08-28). No criterion is Not Met. No criterion was
> reworded, softened, or dropped to fit the implementation.**

**Criterion #1 was specifically re-examined for softening, and is genuinely
satisfied.** Each binding phrase maps to an assertion made from outside the
system: "multi-step" → a four-node diamond graph; "at least two agent
instances working in parallel" → `concurrent_peak == 2` at a real barrier,
not inferred from timing; "at least one real peer-review round" → the real
Supervisor RPC classifying a real `architect-agent` verdict on a real
`coding-agent` result; "a passing test suite in the target repo" → a real
`pytest` subprocess with the target repository as cwd, exit 0; and the git
commit → read from `git log`/`git show`, never from the agent's own report.

---

## 10. Conditions attached to this CONDITIONAL-GO

Each has an owner and a specific discharging event.

| # | Condition | Discharged by |
|---|---|---|
| **C-1** | **No GitHub Actions run has ever executed against any Phase 3E commit.** All three workflows trigger on `pull_request` or `push` to `main`; the branch has neither. Every result in §6 and §7 is local. | Opening the PR and observing `pr-checks`, `build-and-scan` and `real-infra-checks` green against `60934ac` (or its successor). **The user has instructed that no PR be opened yet, so this condition is deliberately open.** |
| **C-2** | **`agents/*` are in no CI gate.** 73 passing tests and 5 `handler.py` files are unlinted, untyped and untested by CI. | A decision on how Agent Packages enter CI (§11 item 2), then the wiring. |
| **C-3** | **`agent-os/*` has no Dockerfile and appears in neither `build-and-scan.yml` (14 `services/*` entries) nor `docker-compose.local.yml`.** Four components cannot be built, scanned, or run as containers. No Trivy result exists for any of them. | A decision on `agent-os` deployment shape (§11 item 3), then the wiring. |
| **C-4** | **Four TDD deviations (§2 DEV-1…DEV-4) are now disclosed but not ratified.** | The user either accepting them as narrowings (recorded in TDD 3E) or directing that they be built. |
| **C-5** | **The `~30,000 Production SLOC` milestone is crossed** (§12). Protocol §3.1 makes this a reminder, not a pause. | The user deciding whether to schedule a Project Health Review. |
| **C-6** | **D1–D4 and D10–D12 are unrecoverable** (§1.3). | The user supplying their content, or confirming that the nine documented decisions plus the five recoverable D-items are the complete record. |

**None of these is an unmet acceptance criterion**, which is what protocol
§3.2 forbids CONDITIONAL-GO from covering. C-1 is the standard condition
this project's environment produces; C-2 through C-6 are gaps this review
found and is reporting rather than closing.

---

## 11. Gaps, ambiguities, and decisions requiring the user's approval

Per protocol §13, each with what the documents do and do not say, options,
and a recommendation — **not a decision taken.**

### 11.1 The four undisclosed TDD deviations (DEV-1…DEV-4)

*What:* TDD 3E §4's scoring step and three of §10's six event contracts
were never built and, until this review, never disclosed.
*Documents:* TDD 3E §4 and §10 specify all four. Doc 12 §5 and §13 specify
the two event families independently. `16-3e-hot-load-design-decision.md`
§5 disclosed one third of DEV-1. **No document says any of them is
deferred.** TDD 3E §15's non-goals list does not mention them.
*Options:* **(a)** Ratify all four as Phase 3 narrowings, recorded in TDD 3E
— cheapest, and consistent with how doc 12 §15 already scopes Phase 3 down.
**(b)** Build DEV-2 and DEV-3 now (two payloads plus publishers; the health
snapshot needs an aggregation source that does not yet exist). **(c)** Split:
ratify DEV-1 and DEV-4, build DEV-2/DEV-3.
*Recommendation:* **(a)**, with DEV-2 and DEV-3 explicitly re-scoped to the
phase that builds the Agent Activity panel — that panel is their only named
consumer (`03-gateway-web-prerequisite.md`), and building publishers with no
subscriber now would be exactly the build-ahead-of-phase discipline TDD 3E
§2 already refuses. DEV-4 costs nothing to ratify: the RPC is served and
tested; only the caller is absent.
*Blocked until decided:* the GO verdict. Nothing else — no acceptance
criterion depends on any of the four.

### 11.2 How Agent Packages enter CI (C-2)

*What:* `agents/*` are deliberately not workspace members, which is why
nothing runs their tests.
*Documents:* Doc 02 `:162-169` is explicit that an Agent Package is not an
instance of the engine template. `17-cicd-pipeline.md` and
`15-development-workflow.md` §4 predate Agent Packages and are silent.
*Options:* **(a)** A dedicated `agents-checks.yml` looping over
`agents/*/` and running `uv run pytest tests` in each — matches how they
actually work, no workspace change. **(b)** Give each a `package.json` so
turbo picks them up — makes them workspace members, which contradicts doc
02. **(c)** Add a step to `pr-checks.yml` doing the loop inline.
*Recommendation:* **(c)** — one step, no new workflow, no workspace-membership
change; promote to its own workflow if the loop grows.
*Blocked:* nothing. Agents pass today; only the gate is missing.

### 11.3 `agent-os` deployment shape (C-3)

*What:* Four components with `main.py`, a health surface and Postgres
persistence, none of which can be containerised.
*Documents:* `14-deployment-architecture.md` and doc 02 describe `agent-os/`
as a first-class subsystem. TDD 3E does not mention Dockerfiles at all.
`build-and-scan.yml`'s matrix comment says "One entry per
`services/<name>/Dockerfile`", assuming everything deployable lives under
`services/`.
*Options:* **(a)** Four Dockerfiles mirroring the engine template, four
matrix entries, four compose services. **(b)** Only `kernel` and `registry`
(the two with persistence and a runtime role); `supervisors` and the SDK
stay library-shaped. **(c)** Defer entirely to the phase that first deploys
NAOS.
*Recommendation:* **(a)** — `supervisors` serves two RPCs and is a real
runtime participant, so leaving it out would leave the peer-review path
undeployable; and the matrix's `services/`-only assumption needs correcting
either way.
*Blocked:* any real (non-test) execution of NAOS. Nothing in Phase 3E's own
verification.

### 11.4 The standing SLOC methodology decision (pre-existing)

`project-health-master.md` §2 records an open Option A (restore `scc`) vs
Option B (formalise `cloc`) decision, explicitly not made by that document.
It is still open. Only `cloc` is installed here, so §12 uses `cloc` and
labels the figures accordingly. *Recommendation:* **Option B** — `cloc` is
what the last two measurements actually used, and a fixed documented scope
matters more than which tool.

### 11.5 Full-path E2E for criteria #2 and #3 (the user's item 14)

*What:* Are the current unit+integration+real-Postgres proofs sufficient?
*Documents:* TDD 3E §13 files **only** criterion #1's scripted objective
under "Real-infrastructure — the roadmap's own named acceptance test", and
separately names a "real-Postgres restart-survival test for
`agent_instance`" — which exists and passes. §13 asks for **no** end-to-end
test for #2 or #3. The roadmap's testing-strategy section likewise names one
integration test, criterion #1's.
*Assessment:* **The existing coverage is sufficient for Phase 3E
completion, and demanding a full-path E2E for #2 and #3 would be adding a
requirement no approved document states.** #2's two halves are each proven
against real components and joined by a payload shape they both assert; #3
is proven against the real selection policy, the real served RPC, and real
Postgres. The honest residual is that #2's "killing" is a lifespan restart
rather than a process kill — recorded as the narrowing in §9, not hidden.
*Recommendation:* accept as-is; if the user wants a process-kill E2E, treat
it as a **new, separately-scoped slice**, not a Phase 3E blocker.

### 11.6 NATS-backed E2E (the user's item 15)

*What:* Should the acceptance E2E also run over real NATS JetStream?
*Documents:* TDD 3E §13 names the acceptance test's path — "Reasoning →
Planning → NAOS → Action Engine → a real git commit" — and says nothing
about which Event Bus backend carries it. ADR-033 and
`16-testing-strategy.md` define the `real_infra` tier around
testcontainers-backed Postgres/Redis/Neo4j/NATS fixtures but do not require
every real-infra test to exercise all four. `nova-testkit` has a NATS
fixture; `real-infra-checks.yml` runs its own fixture tests.
**No approved document requires a NATS-backed variant of this E2E.**
*Assessment:* **Not required by the approved specification.** The E2E's
subject is the Reasoning→…→git path, and `InMemoryEventBus` and the NATS
backend sit behind the same `BoundEventBus` interface with the same
allow-list enforcement — a NATS variant would re-test `nova-eventbus-sdk`,
which has its own tests, rather than test anything about Phase 3E.
*Recommendation:* **keep explicitly deferred**, recorded here as a
deliberate decision rather than an oversight. Revisit if and when NATS
delivery semantics (redelivery, ordering, at-least-once duplicates) become
load-bearing for the Kernel — which they are not while dispatch is
in-process and synchronous. **Do not implement without an approved
requirement**, per the user's own instruction.

---

## 12. Project Metrics (SAD 15 §10 / `METRICS_TEMPLATE.md`)

**Tool: `cloc` v1.98**, excluding blanks and comments. `scc` is not
installed in this environment. Per `project-health-master.md` §2, the
`cloc` and `scc` series are **not comparable**; these figures continue the
`cloc` measurement taken during the 2026-08 project-health audit (item 11,
Production 28,742 / Total 96,262) and are **not** comparable to the `scc`
series that ran from Phase 2D-B through Phase 2D-C.

### Project Statistics

| Metric | Value | Scope / flags |
|---|---|---|
| **Production SLOC (comparable scope)** | **31,319** (513 files) | `services/*/src` + `packages/*/src` + `services/*/alembic/versions` — identical to the 2026-08 audit's item-11 scope |
| **Production SLOC (full, Phase-3E-inclusive)** | **34,446** (580 files) | the above **+** `agent-os/{kernel,registry,supervisors}/src` + `agent-os/sdk/python/src` + `agents/*/src` + `agent-os/*/alembic/versions` |
| **Phase 3E's own production code** | **3,127** (67 files) | `agent-os/*` + `agents/*` alone |
| **Total SLOC** | **120,266** (2,023 files) | whole repository, excluding `node_modules`, `.venv`, `.git`, and generated TypeScript |
| **Total SLOC incl. generated TS** | **122,151** (2,121 files) | as above, plus `packages/nova-contracts/typescript/` |

### Growth

Against the 2026-08 audit's comparable-scope `cloc` figure of 28,742:
**+2,577 (+9.0%)** in the comparable scope, of which Phase 3E's own new
subsystems account for a further **3,127** outside it.

### Language Breakdown (excluding generated TypeScript)

Python dominates; also 27 TOML (1,113), 16 YAML (1,009), 14 Dockerfile
(378), 1 INI (30), 1 Mako (19).

### Architecture Metrics

14 services · **4 `agent-os` components** (`kernel`, `registry`,
`supervisors`, `sdk/python`) · **5 Agent Packages** · 8 shared packages ·
26 workspace packages · 24 ADRs · 7 import-linter contracts · 12
contract-test modules · 97 generated TypeScript contract files (98 on disk
with the barrel).

### Quality Metrics

1,646 tests passing, 0 failing · 104 `real_infra` deselected by default ·
59 `real_infra` executed against real PostgreSQL · lowest domain coverage
86% (`world-model-engine`, untouched) · all Phase 3E packages ≥96% · mypy
clean across 26 packages · ruff clean · 7/7 import contracts kept.

### SLOC milestone gates (SAD 15 §10)

- **~30,000 Production SLOC reminder — CROSSED.** 31,319 in the comparable
  scope, 34,446 in the full scope. Per protocol §3.1 this is a **reminder,
  not a pause**: a Project Health Review is **recommended to the user**, and
  feature development is not blocked. Surfaced as condition **C-5**.
- **~50,000 Production SLOC gate — not crossed.** Feature development does
  not pause.

---

## 13. `definition-of-done.md` — all ten items

| # | Item | Status |
|---|---|---|
| 1 | Implementation matches the approved design | **Partial** — nine approved decisions all verified implemented; four TDD deviations found, disclosed, unratified (§2) |
| 2 | All acceptance criteria verified with evidence | **Yes** — §9, 3 Met + 2 Met-with-narrowing, every row citing a test |
| 3 | Full local verification suite green | **Yes** — §6, uncached, real counts |
| 4 | Coverage gate met per package | **Yes** — §6, every affected package ≥94%, gate 85% |
| 5 | Real-infrastructure verified or gap disclosed | **Partial-yes** — 59 tests passed against real Postgres; the Docker/testcontainers path and the 11 nova-testkit fixture tests are disclosed as unrun (§7) |
| 6 | Corrections are additive | **Yes** — every historical document corrected by dated additive note; only this Gate Review was replaced, and §0's history block explains why it carried no claim to preserve |
| 7 | Documentation synchronised | **Yes** — §14 |
| 8 | Gate Review written | **Yes** — this document |
| 9 | Project Health record written | **Yes** — `docs/project-health/phase-3e.md` |
| 10 | CI green against the head SHA | **NO** — no CI run exists. Condition **C-1**. |

---

## 14. Documentation updated by this review

| File | Change |
|---|---|
| `docs/roadmap/ENGINEERING_ROADMAP.md` | Phase 3E entry rewritten from "Implementation not started" to the real status, verdict, criteria split and open conditions |
| `README.md` | Status section: Phase 3E state corrected; `agent-os`/`agents` described with their deployment gap |
| `docs/design/phase-3/08-tdd-3e-agent-os.md` | Four additive notes: status banner, §4 (DEV-1), §10 (DEV-2/3/4 table), §14 (criteria verification table) |
| `docs/design/phase-3/05-tdd-3b-planning-engine.md` | Additive note: the `agent_os.task.completed` deferral is closed |
| `docs/design/phase-3/03-gateway-web-prerequisite.md` | Additive correction: the two `/v1/agents` endpoints were **not** added by 3E and now have no owning TDD |
| `docs/architecture/12-agent-architecture.md` | §15: implementation-status block; the three §5/§7/§13 capabilities not covered by the table |
| `docs/project-health/phase-3e.md` | **Created** — 23-field record |
| `docs/project-health/project-health-master.md` | Phase 3E row added |
| `docs/roadmap/architecture-reviews/phase-3e-agent-os-gate-review.md` | This document |

**Inspected and found already accurate** (evidence the sweep was real, not
selective): `docs/architecture/{00,02,07,09,10,11,15,16,17,20}` — none
carries a Phase 3E status claim falsified by the implementation; ADRs
004/005/008/020/029/032/033/034 (§3); `16-3e-hot-load-design-decision.md`,
`17-3e-task-node-lifecycle.md`, `15-3e-supervisor-reconciliation.md` — all
three describe the shipped code correctly; `docs/bible/part-04` and
`part-12` — the implementation still satisfies both, and neither was
edited; every prior Phase 3 Gate Review — none makes a forward-looking claim
about 3E that this phase falsified beyond the 3B one corrected above.

---

## 15. Final gate status

# **CONDITIONAL-GO**

Phase 3E is substantively complete. All eight scoped deliverables are built;
all five acceptance criteria are satisfied (three outright, two with
narrowings that are disclosed and, for #3, pre-approved); every local gate is
green with real numbers from an uncached run; 59 real-infrastructure tests
pass against a real PostgreSQL 16.13; and the acceptance objective — a real
multi-agent coding task ending in a real git commit and a passing test suite
in the target repository — genuinely executes end to end on the real path.

It is **not GO** because six conditions in §10 are open, of which two are
structural: **no CI has ever run against this code** (C-1), and **four TDD
deviations are disclosed but unratified** (C-4). Protocol §3.2's GO
criteria 7 and 2 are therefore both unmet.

**This is not a Go-with-caveats.** Discharging C-1 requires opening the PR,
which the user has explicitly deferred; discharging C-4 requires a decision
only the user can make.

**Completing this Gate Review is not authorization to begin Phase 4**, and
is not authorization to open the Phase 3E PR. Both are separate decisions,
and both are the user's.

---

**Reviewed:** 2026-08-29 · **Branch:** `phase-3e-agent-os` ·
**Head:** `60934ac07166acd3635e3bf33dee9462d97f8a04` ·
**Working tree:** clean · **PR:** none · **CI:** none
