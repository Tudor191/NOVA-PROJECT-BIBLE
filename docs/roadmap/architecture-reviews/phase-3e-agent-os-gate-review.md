# Phase 3E — `agent-os`: Gate Review

**Status: COMPLETE. Verdict: GO (2026-08-30).**
Branch `phase-3e-agent-os`.

> **Verdict change, 2026-08-30 — CONDITIONAL-GO → GO, on one new fact and
> nothing else.** This review was issued CONDITIONAL-GO on 2026-08-29 for
> exactly one reason: C-1, no GitHub Actions run had ever executed against
> any Phase 3E commit. PR #20 was opened on 2026-08-30 and CI ran against
> head SHA `733a31d58eb1f0f5a0f3b5670d13de9975e5dedf`. **All 27 Check Runs
> succeeded.** C-1 is discharged (§10), the verdict is now GO (§15), and the
> real-infrastructure limitation §7 recorded is now partly retired (§7.1).
>
> **Nothing else changed.** The 2026-08-29 findings stand as written — the
> six ratified deviations DEV-1…DEV-6, the two narrowed acceptance criteria
> (#2 and #3), the nine known limitations in §8, the deferred obligations,
> and the unrecoverable decisions D1–D4/D10–D12 are all unaltered. **GO is
> not a claim that those limitations were resolved; it is a claim that the
> conditions this review attached are now all discharged.** Phase 3E is
> **merged**: PR #20 was merged into `phase-3b-planning-domain` on
> 2026-08-30 as merge commit
> `59743423f32b3b8f8c470128b30cf4b798b1f46f`, and is closed.
> *(This line read "still **not merged**: PR #20 is open" until that merge.)*
**`60934ac07166acd3635e3bf33dee9462d97f8a04` is the last commit to change
production source logic.** Every commit after it changes only documentation,
one CI workflow (`pr-checks.yml`, a test gate — no production behaviour), and
one source *docstring*. **This document deliberately does not name a branch
head**, because each documentation commit would falsify it — that exact drift
was found and corrected during the pre-PR audit. Use `git rev-parse HEAD` for
the current head; use `60934ac` for "the code this review verified".

Every verification figure below was produced by a command run against the
working tree, per
[`PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md)
§0.3.1, and the **full uncached suite was re-run at the then-current head in
the pre-PR audit (2026-08-29) with identical results** — 52/52 tasks, 1,646
passed, 104 deselected. Working tree clean, nothing unpushed, **no PR open,
and no GitHub Actions run has ever executed against any Phase 3E commit.**

> **The sentence immediately above is the state as of 2026-08-29 and is
> preserved as the record of it. It is no longer true:** PR #20 opened on
> 2026-08-30, CI ran 27/27 green against
> `258ebe6547bc011fa33eea829303b45337c6a42d`, and the PR merged into
> `phase-3b-planning-domain` as `59743423f32b3b8f8c470128b30cf4b798b1f46f`.
> See §10.1, §13.1 and §15.1.

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

**Not executed and NOT previously sanctioned at the time** — the six
deviations in §2, **all now ratified as explicit Phase 3E narrowings**
(closure pass, 2026-08-29). **`agent-os` deployment** is separately
ratified as a deferred obligation (§10 C-3).

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

### 1.3.1 Closure-pass completeness check (condition C-6)

**Question asked:** do the fourteen form the *complete* recoverable
architectural decision record for Phase 3E?

**Answer: fourteen was very slightly incomplete, and the correction is
recorded here rather than absorbed silently.** A systematic re-sweep found
one further item that belongs in the record and one that does not:

- **Added — doc 15 Item B** (`15-3e-supervisor-reconciliation.md`,
  "Registry Sandbox Test Run — structural conformance vs. behavioral
  isolation"). It is a **resolved investigation, not an approved decision**:
  its own text says "resolved as a documented conclusion; no implementation
  change required", and it concluded that the shipped implementation already
  matched the intended scope. It carries a full evidence chain against TDD
  3E §5 and TDD 3C §3. It is part of the recoverable architectural record
  and was absent from the count.
- **Not added — DEV-5/DEV-6** (the mailbox transport and `DecisionMemoryPort`
  narrowings, §2). Both were *disclosed in source* but neither was a decision
  anyone took at the time; both became decisions only when ratified in this
  closure pass, and are recorded as ratifications rather than backdated.

**Revised total: fifteen recorded items** — nine approved architectural
decisions, one resolved investigation, and five recoverable implementation
decisions (D5–D9). Plus six narrowings ratified in the closure pass
(DEV-1…DEV-6), which are decisions of this pass, not recoveries.

**The absence of D1–D4 and D10–D12 is now positively verified**, not merely
unfound. A second, independent search method (word-boundary context
extraction, distinct from the pattern grep used originally) across `*.py`,
`*.md`, `*.yml`, `*.yaml` and `*.toml` over `agent-os/`, `agents/`,
`services/`, `docs/`, `tools/` and `.github/` returns, in full:

| Token | Hits | What they are |
|---|---|---|
| D1, D4, D10, D12 | 2 each | **This Gate Review's own prose and the Project Health record's**, both saying the decisions are unrecoverable. Self-referential. |
| D3 | 1 | `ENGINEERING_ROADMAP.md:637`, "D3 visualizations" — D3.js. A false positive. |
| D2, D11 | 0 | Nothing at all. |

**No content for any of the seven was invented, inferred from adjacent
slices, or reconstructed from what the code happens to do.** If the user
holds their content, it can be added; the repository does not.

---

## 2. Deviation register

Protocol §1.1 classification. Four items; **three were undisclosed until
this review**, and all four are now disclosed additively in the TDD.

> **Closure-pass update, 2026-08-29 — all four are now RATIFIED as explicit
> Phase 3E narrowings** by the user's decision, recorded in
> `08-tdd-3e-agent-os.md` §4 and §10. The existing implementation is
> preserved and none of the deferred functionality is built. **Condition
> C-4 is closed.** The table below is unchanged as the record of what was
> found; the "Approved?" column now reads Yes for all four.
>
> **The same pass found two further narrowings that this register originally
> missed** — both already disclosed in source but absent from §2's list.
> They are added as DEV-5 and DEV-6 below and ratified alongside the others.
> Recording that omission rather than quietly folding them in: the original
> register was incomplete.

| # | Deviation | Class | Disclosed at | Approved? |
|---|---|---|---|---|
| DEV-1 | **Kernel Scheduler step (2), scoring, is not implemented.** TDD 3E §4 specifies a four-step loop; `dispatch_task_node` performs registry-query, backend-select and dispatch, with the Registry's own highest-healthy-version policy as the sole selection input. No `AgentMetrics` scoring, no load or resource-availability input, and no call to `executive-cognition-engine` (grep: zero references to `executive`/`arbitrate`/`cognitive_priority` under `agent-os/kernel/src/`). | **Partially disclosed drift** — `16-3e-hot-load-design-decision.md` §5 disclosed the `AgentMetrics` half against doc 12 §6; the load / resource / Cognitive-Priority-Matrix inputs TDD 3E §4 names were undisclosed. | TDD 3E §4 (new note, this review) | **No** — condition C-4 |
| DEV-2 | **`agent.<instance_id>.<state>` lifecycle events are not published.** TDD 3E §10 lists them under "Published"; doc 12 §5 specifies them. No payload in `nova-contracts`, no entry in any `PUBLISHABLE_SUBJECTS`, no publisher. Instance state lives only in `agent_os.agent_instance.status`. | **Undisclosed drift** | TDD 3E §10 + doc 12 §15 (new notes, this review) | **No** — condition C-4 |
| DEV-3 | **`agent_os.health.snapshot` is not published and has no contract.** TDD 3E §10 lists it under "Published" and §6 states the payload "also lives in `events/agent_os.py`". It does not. Nothing aggregates health. | **Undisclosed drift** | TDD 3E §10 + doc 12 §15 (new notes, this review) | **No** — condition C-4 |
| DEV-4 | **`planning.decompose.request` is never called by any `agent-os` component.** TDD 3E §10 says "this TDD is the RPC's first real caller"; it is not. §12's already-minimal-node row therefore describes an unexecuted path. The RPC itself is served and tested by `planning-engine`. | **Undisclosed drift** | TDD 3E §10 (new note, this review) | **No** — condition C-4 |

| # | Deviation | Class | Disclosed at | Approved? |
|---|---|---|---|---|
| **DEV-5** | **`AgentMessage` mailbox transport is in-process, not over the bus.** Nothing subscribes to `agent_os.instance.*.inbox` — verified against the two real allow-lists, not their docstrings: `agent-os/kernel`'s is `{"planning.task_graph.created"}` and `agent-os/supervisors`' is `{"agent_os.supervisor.restart_plan.request", "agent_os.supervisor.peer_review.request"}`. The peer-review round delivers its `AgentMessage` through `InprocessExecutionBackend.spawn_and_review()` calling `on_message()` directly. | **Disclosed narrowing** — correct for the only enabled backend per TDD 3E §6 and `01-tdd-preparation…` §5.5 Fact 4 | `supervisors/events/published.py` and `domain/ports.py` docstrings; now TDD 3E §10 | **Yes — ratified** |
| **DEV-6** | **`DecisionMemoryPort` is a structured-log stub, not a cross-engine call.** Doc 12 §9's "Recorded to Decision Memory either way" is honoured at the Supervisor's boundary (every conflict resolution really calls the port), but the default implementation writes a log line. `memory-engine` exposes **no inbound decision-record RPC or subscription** — verified this pass: it *publishes* `memory.decision.recorded` and subscribes to nothing of the kind. | **Disclosed narrowing** | `supervisors/domain/ports.py` and `clients/decision_memory_client.py` docstrings; now TDD 3E §10 | **Yes — ratified** |

**A stale source docstring found and corrected in the closure pass**
(protocol §1.1/§1.3 — citations inside source are documentation, and one
that inspection proves false must be corrected).
`agent-os/supervisors/domain/ports.py`'s `AgentInstancePort` paragraph
justified the mailbox gap by asserting that "`agent-os/kernel`'s own
Milestone 2 shipped health-only, with an empty `SUBSCRIBABLE_SUBJECTS` (no
Scheduler, no `inprocess` execution backend)". **That reason is now false** —
`domain/scheduler.py` and `domain/execution_backend.py` both exist and the
Kernel's set is `{"planning.task_graph.created"}`. Its *conclusion* remains
true for a narrower reason (no component subscribes to the mailbox subject),
which is what the added dated correction now says. Comment-only change; no
behaviour altered.

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

> **Closure-pass update, 2026-08-29 — C-2 is closed.** Two steps were added
> to `.github/workflows/pr-checks.yml`, immediately after the existing
> `tools/tests` step (the same "not a workspace package, so CI runs it
> separately" precedent):
>
> 1. `uv run ruff check agents/` — one static pass over the whole tree.
> 2. A loop running `uv run mypy src && uv run pytest tests` **inside each
>    `agents/*/`**, collecting failures and reporting every failing package
>    rather than stopping at the first.
>
> **Why a loop and not one invocation:** all five packages expose a module
> named `handler` (`agents/<id>/src/handler.py`) and their test modules share
> names (`test_handler.py`, `test_agent_package.py`). A single pytest process
> collecting all five fails with **9 collection errors** — `handler` resolves
> to whichever agent loaded first (observed: `coding-agent`'s test importing
> `architect-agent`'s `handler`), plus `import file mismatch` on the
> duplicate test-module names. mypy collides identically. Per-package
> isolation is inherent to the Agent Package architecture, not a workaround.
>
> **Nothing about the agents changed.** No `package.json`, no
> `pyproject.toml`, no `conftest.py`, no `sys.path` change, no rename. They
> remain non-workspace-members exactly as doc 02 `:162-169` requires.
>
> Verified locally: **5/5 packages, 73 tests, ruff clean, mypy clean, exit
> 0.** Negative controls in §6.2 (NC-D/E/F).

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
| **NC-D** — the new `agents/*` CI step catches a failing test | Append `assert False` to `agents/qa-agent/tests/test_handler.py` | **exit 1**, `::error::qa-agent failed mypy or pytest`, `1 failed, 14 passed`. Restored → green. |
| **NC-E** — it catches a type error | Append a `-> int` function returning `"not an int"` to `agents/research-agent/src/handler.py` | **exit 1**, `src/handler.py:221: error: Incompatible return value type (got "str", expected "int")`, `::error::research-agent failed`. Restored → green. |
| **NC-F** — it catches a lint error | Append an unused `import os` to `agents/architect-agent/src/handler.py` | **exit 1** from `uv run ruff check agents/`, `Found 2 errors`. Restored → `All checks passed!` |

NC-D and NC-E also confirm the loop's *reporting* behaviour: it checks all
five packages and fails at the end naming the broken one, rather than
aborting at the first failure — so a reviewer sees every failing agent in
one run.

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

### 7.1 Superseded, 2026-08-30 — the testcontainers path has now run

**The paragraph immediately above is retained as the record of what was true
on 2026-08-29. It is no longer true.** PR #20 opened on 2026-08-30 and
`real-infra-checks.yml` executed against Phase 3E head SHA
`733a31d58eb1f0f5a0f3b5670d13de9975e5dedf`.

**Run [33305319396](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/33305319396)
— `completed` / `success`, all 11 matrix jobs.** Both `agent-os` entries and
the `reasoning-engine` entry this phase added are among them:

| Matrix job | Conclusion |
|---|---|
| `real-infra (kernel, agent-os/kernel)` | **success** |
| `real-infra (registry, agent-os/registry)` | **success** |
| `real-infra (reasoning-engine, services/reasoning-engine)` | **success** — the entry this phase added |
| `real-infra (planning-engine, …)` · `(action-engine, …)` · `(capability-engine, …)` · `(communication-engine, …)` · `(personality-engine, …)` · `(perception-engine, …)` · `(digital-twin-engine, …)` · `(nova-testkit, …)` | **success** (8 further jobs) |

So the specific gap this section disclosed — *"produced against a
locally-installed PostgreSQL, not against the testcontainers path CI uses"* —
**is now closed for the CI dimension**: the same suites have since run on the
real testcontainers path on GitHub-hosted runners and passed.

**What this does not retire:** Docker remains unavailable in the development
environment, so local verification still cannot use testcontainers, and the
`nova-testkit` fixture tests were still not exercised locally. Both statements
above stand.

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
8. **The six DEV items in §2** — scoring, lifecycle events, health
   snapshot, `planning.decompose.request`, in-process mailbox transport,
   and the `DecisionMemoryPort` log stub. Four were not sanctioned in
   advance; **all six are now ratified as explicit Phase 3E narrowings**
   (closure pass, 2026-08-29 — §10 C-4).
9. **`agent-os` is not deployable** — no Dockerfile, no image scan, no
   compose service. **Ratified as a deferred deployment obligation**
   (§10 C-3, `08-tdd-3e-agent-os.md` §15), with a criterion-by-criterion
   demonstration that no §14 acceptance criterion requires it.

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

## 10. Conditions attached to the original CONDITIONAL-GO

Each has an owner and a specific discharging event.

**Closure pass, 2026-08-29: five of the six were closed. C-1 alone remained
open.**

**CI pass, 2026-08-30: C-1 is now discharged. All six conditions are closed,
which is what converts the verdict to GO (§15).**

| # | Condition | Status | Evidence / discharge |
|---|---|---|---|
| **C-1** | **No GitHub Actions run has ever executed against any Phase 3E commit.** All three workflows trigger on `pull_request` or `push` to `main`; the branch had neither. Every result in §6 and §7 was local. | **CLOSED — discharged 2026-08-30** | PR #20 opened against `phase-3b-planning-domain`; all three workflows ran green, first against `733a31d58eb1f0f5a0f3b5670d13de9975e5dedf` and then against the final head `258ebe6547bc011fa33eea829303b45337c6a42d` — **the authoritative CI-verified content SHA, and the head that merged**. 27/27 Check Runs `success` on each. Full evidence in §10.1; the merge-commit distinction in §13.1. |
| **C-2** | **`agents/*` were in no CI gate.** 73 tests and 5 `handler.py` files unlinted, untyped, untested by CI. | **CLOSED** | Two steps added to `.github/workflows/pr-checks.yml`: `uv run ruff check agents/` (one static pass, no isolation needed), and a per-package loop running `uv run mypy src && uv run pytest tests` inside each `agents/*/`. **One process per package is required, not stylistic** — all five expose a module named `handler` and share test-module names, so a single pytest process fails with 9 collection errors and mypy collides identically. No `package.json`, no `pyproject.toml`, no `conftest.py`, no rename: the Agent Package architecture (doc 02 `:162-169`) is untouched and they remain non-workspace-members. Verified locally: 5/5 packages, 73 tests, exit 0. Negative-controlled three ways (§6.2). |
| **C-3** | **`agent-os/*` has no Dockerfile and appears in neither `build-and-scan.yml` nor `docker-compose.local.yml`.** | **CLOSED as a ratified deferred obligation** | By the user's decision, **no Dockerfile, matrix entry, compose service or deployment architecture is introduced by Phase 3E.** Recorded in `08-tdd-3e-agent-os.md` §15 with a criterion-by-criterion demonstration that **none of §14's five acceptance criteria requires a deployed container** — the `inprocess` backend runs agent instances inside the Kernel process by definition, so a container boundary would add nothing any criterion asks about. Neither TDD 3E nor doc 12 mentions Dockerfiles for `agent-os` anywhere. The deferring phase's inherited work list is enumerated there. |
| **C-4** | **Four TDD deviations (DEV-1…DEV-4) disclosed but not ratified.** | **CLOSED** | All four **ratified as explicit Phase 3E narrowings** by the user's decision, recorded in `08-tdd-3e-agent-os.md` §4 and §10. Implementation preserved; deferred functionality not built. The closure pass additionally found and ratified **DEV-5 and DEV-6**, which the original register missed (§2). |
| **C-5** | **The ~30,000 Production SLOC milestone is crossed** (§12). | **CLOSED — review conducted** | [`project-health-review-2026-08-29.md`](project-health-review-2026-08-29.md), addressing all twelve Engineering Review Milestone items. Verdict **HEALTHY**; four findings, none blocking Phase 3E, three of them pre-existing. **It does not discharge the 50,000 SLOC gate** — three of the twelve items are Limited for want of a runtime environment, and that review says so explicitly in its §0. |
| **C-6** | **D1–D4 and D10–D12 are unrecoverable** (§1.3). | **CLOSED as verified-absent** | Re-searched by a second, independent method in the closure pass (word-boundary context extraction across `*.py`/`*.md`/`*.yml`/`*.yaml`/`*.toml` over `agent-os/`, `agents/`, `services/`, `docs/`, `tools/`, `.github/`). **Every hit for D1, D4, D10 and D12 is this Gate Review's own prose saying they are unrecoverable; D3's single hit is "D3 visualizations" in the roadmap, i.e. D3.js; D2 and D11 have zero hits.** The absence is now confirmed, not merely unfound. **Nothing was invented or reconstructed.** §1.3 additionally now records the completeness finding for the recoverable set. |

**None of these was an unmet acceptance criterion**, which is what protocol
§3.2 forbids CONDITIONAL-GO from covering.

### 10.1 C-1 discharge evidence (2026-08-30)

**Authoritative verified SHA: `258ebe6547bc011fa33eea829303b45337c6a42d`** —
the **final** head of `phase-3e-agent-os` and the head PR #20 was merged
from. **27 of 27 Check Runs `completed`/`success`**: PR Checks
[33326242931](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/33326242931),
Build & Scan
[33326242949](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/33326242949),
Real-Infrastructure Checks
[33326242919](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/33326242919)
— all three `completed`/`success`, zero failed, cancelled, timed out,
skipped or still running.

**Two green runs exist, and this is deliberate.** CI first ran against
`733a31d58eb1f0f5a0f3b5670d13de9975e5dedf` (the table below), which was the
head when PR #20 opened. The commit recording this verdict then became a new
head, `258ebe6`, and CI re-ran against it with the same result. **`258ebe6`
is the SHA that matters** — it is what merged. The `733a31d` run is retained
below as the original C-1 discharge evidence, not superseded in substance:
the two runs differ only by that documentation commit.

**The three workflow runs against `733a31d` (the first green run):**

| Workflow | Run | Status / conclusion | Scope |
|---|---|---|---|
| **PR Checks** | [33305319352](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/33305319352) | `completed` / **`success`** | All 14 steps, including both `agents/*` steps added by C-2 — `Lint Agent Packages` and `Type-check and test every Agent Package (one process each)` |
| **Build & Scan** | [33305319349](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/33305319349) | `completed` / **`success`** | 14 build/scan jobs + `dependency-audit` |
| **Real-Infrastructure Checks** | [33305319396](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/33305319396) | `completed` / **`success`** | All 11 matrix jobs (§7.1) |

**Aggregate: 27 of 27 Check Runs `completed` / `success`. Zero `failure`,
zero `cancelled`, zero `timed_out`, zero `skipped`, zero still running.**

Protocol §3.2's GO criterion 7 — *"Real GitHub Actions CI green against the
exact head SHA"* — is therefore met on its own terms.

**One methodological point, recorded so a future reader does not
mis-verify this.** GitHub exposes two different APIs here, and they disagree
for this repository:

- The **Check Runs API** is authoritative for GitHub Actions and is what the
  table above reports: 27/27 success.
- The **legacy commit-status API** returns
  `{"state": "pending", "total_count": 0, "statuses": []}` for this SHA.
  That `"pending"` is **not** a pending check — `total_count: 0` means **no
  legacy commit statuses exist at all**, because this repository reports
  exclusively through Check Runs, and the legacy rollup defaults to
  `pending` when its list is empty. The PR's `mergeable_state` reads
  `unstable` for the same reason.

**Reading the legacy endpoint as red would be wrong; reading it as
authoritative in either direction would be wrong.** Verify Phase 3E CI via
Check Runs, enumerated in full rather than sampled.

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
| 1 | Implementation matches the approved design | **Yes** (closure pass) — nine approved decisions all verified implemented; six TDD deviations found, disclosed, and **all ratified** as Phase 3E narrowings (§2, §10 C-4) |
| 2 | All acceptance criteria verified with evidence | **Yes** — §9, 3 Met + 2 Met-with-narrowing, every row citing a test |
| 3 | Full local verification suite green | **Yes** — §6, uncached, real counts |
| 4 | Coverage gate met per package | **Yes** — §6, every affected package ≥94%, gate 85% |
| 5 | Real-infrastructure verified or gap disclosed | **Partial-yes** — 59 tests passed against real Postgres; the Docker/testcontainers path and the 11 nova-testkit fixture tests are disclosed as unrun (§7) |
| 6 | Corrections are additive | **Yes** — every historical document corrected by dated additive note; only this Gate Review was replaced, and §0's history block explains why it carried no claim to preserve |
| 7 | Documentation synchronised | **Yes** — §14 |
| 8 | Gate Review written | **Yes** — this document |
| 9 | Project Health record written | **Yes** — `docs/project-health/phase-3e.md` |
| 10 | CI green against the head SHA | **Yes** — condition **C-1** is **CLOSED**. **27 of 27 Check Runs `completed`/`success` against `258ebe6547bc011fa33eea829303b45337c6a42d`**, the final reviewed head of `phase-3e-agent-os` and of PR #20 (§10.1). *(This row read "**NO** — no CI run exists. Condition **C-1**, the sole remaining barrier to GO." through 2026-08-29, when no CI run existed; corrected 2026-08-30 when C-1 was discharged.)* **The later merge commit `59743423f32b3b8f8c470128b30cf4b798b1f46f` was not itself independently executed by CI** — see §13.1. |

### 13.1 What CI verified, and what it did not (2026-08-30)

The distinction matters and is easy to blur, so it is stated explicitly.

**CI verified the Phase 3E content.** All three workflows ran against
`258ebe6547bc011fa33eea829303b45337c6a42d` — the final head of
`phase-3e-agent-os` and the head PR #20 was merged from — and returned
**27 of 27 Check Runs `completed`/`success`** (§10.1). That is the evidence
C-1 required, and it is pinned to a real commit.

**CI did not independently verify the merge commit.** PR #20 was merged into
`phase-3b-planning-domain` on 2026-08-30 as a **true merge commit**,
`59743423f32b3b8f8c470128b30cf4b798b1f46f`, whose two parents are
`c6c6c5931091e3830e9c1a2437c6b056cf686eb8` (canonical before the merge) and
`258ebe6…` (the CI-verified Phase 3E head). **No GitHub Actions run exists
against `5974342` itself, and none can**, because all three workflows
trigger only on `pull_request` and `push: branches: [main]` — and
`phase-3b-planning-domain` is neither. This is a property of the workflow
configuration, not a failure, and this review does not change that
configuration.

**So the honest claim is:** the content that merged is CI-green; the merge
commit is not independently CI-verified. **Nothing here should be read as
claiming CI ran against `5974342`.** The merge introduced no content beyond
its two parents, so the residual risk is confined to merge resolution
itself — and this merge had no conflicts to resolve.

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

**Closure pass, 2026-08-29 — six further files:**

| File | Change |
|---|---|
| `.github/workflows/pr-checks.yml` | **C-2 closed** — two steps added: `ruff check agents/`, and a per-package `mypy src && pytest tests` loop over `agents/*/`. The only non-documentation change in the closure pass. |
| `agent-os/supervisors/src/nova_agent_os_supervisors/domain/ports.py` | Dated correction to `AgentInstancePort`'s docstring — its stated reason (Kernel is health-only) is false; its conclusion holds for a narrower reason. Comment-only. |
| `docs/design/phase-3/08-tdd-3e-agent-os.md` | **C-3 and C-4 closed** — §4 and §10 ratification notes for all six narrowings; §15 deferred-deployment record with the criterion-by-criterion justification |
| `docs/roadmap/architecture-reviews/project-health-review-2026-08-29.md` | **Created — C-5 closed.** The ~30k Project Health Review, all twelve Engineering Review Milestone items |
| `docs/project-health/phase-3e.md` | Fields 7, 15, 17, 18, 20, 21, 23 updated for the closure |
| `docs/project-health/project-health-master.md` | Phase 3E row updated; Project Health Review indexed |

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

# **GO**

**Verdict as of 2026-08-30. The CONDITIONAL-GO text below is preserved
verbatim as the 2026-08-29 record; §15.1 states what changed and why.**

Phase 3E is substantively complete. All eight scoped deliverables are built;
all five acceptance criteria are satisfied (three outright, two with
narrowings that are disclosed and, for #3, pre-approved); every local gate is
green with real numbers from an uncached run; 59 real-infrastructure tests
pass against a real PostgreSQL 16.13; and the acceptance objective — a real
multi-agent coding task ending in a real git commit and a passing test suite
in the target repository — genuinely executes end to end on the real path.

**Closure pass, 2026-08-29 — five of the six conditions are now closed;
the verdict remains CONDITIONAL-GO on the strength of one.**

It is **not GO** for exactly one reason: **no GitHub Actions run has ever
executed against any Phase 3E commit** (C-1). Protocol §3.2's GO criterion
7 — "Real GitHub Actions CI green against the exact head SHA" — is
therefore unmet, and it is unmeetable without opening the PR, which the
user has explicitly deferred.

Criterion 2 ("no undisclosed deviation") **is now met**: all six deviations
are disclosed and ratified (§2, §10 C-4). Criteria 1, 3, 4, 5, 6, 8, 9 and
10 were already met. Criterion 11 ("no open item in category 13 requires a
user decision") is met for everything except the PR decision itself.

**So the honest statement is narrow: Phase 3E is complete and verified to
the limit of what can be verified without CI, and CI is the only thing
left.** Every other condition this review raised has been closed with
evidence — the `agents/*` CI gap is wired and negative-controlled, the
`agent-os` deployment obligation is ratified as deferred with a
criterion-by-criterion justification, the six narrowings are ratified, the
Project Health Review is conducted, and the unrecoverable decisions are
positively verified absent rather than invented.

**Completing this Gate Review is not authorization to begin Phase 4**, and
is not authorization to open the Phase 3E PR. Both are separate decisions,
and both are the user's.

### 15.1 CI pass, 2026-08-30 — the verdict is now GO

**Everything above this subsection is the 2026-08-29 record and is preserved
unedited.** One thing has changed since, and it is the one thing that was
missing.

PR #20 was opened against `phase-3b-planning-domain` on 2026-08-30, and all
three workflows ran green — first against `733a31d58eb1f0f5a0f3b5670d13de9975e5dedf`,
then against the final head
`258ebe6547bc011fa33eea829303b45337c6a42d` once this verdict was recorded:
**27 of 27 Check Runs `completed` / `success` on each, zero failed,
cancelled, timed out, skipped, or still running** (§10.1). `258ebe6` is the
authoritative CI-verified content SHA, because it is what merged.

That discharges **C-1**, the sole stated barrier to GO. Protocol §3.2's GO
criterion 7 is met. All six conditions this review attached are now closed,
so **the verdict is GO.**

**What GO does and does not assert.** It asserts that every condition this
review attached is discharged and that CI is green against the reviewed
commit. It does **not** assert that the disclosed limitations were resolved,
and none of them was:

- the **six ratified narrowings DEV-1…DEV-6** (§2) stand exactly as ratified;
- acceptance criteria **#2 and #3 remain Met with disclosed narrowing** (§9)
  — CI did not change what those tests prove;
- the **nine known limitations** in §8 stand, including that `agent-os` is
  not deployable and `nova-auth` enforcement is declared-intent-only;
- **D1–D4 and D10–D12 remain unrecoverable**, verified absent, not invented;
- **PHR-1, PHR-2 and PHR-3** remain reported-not-fixed pre-existing defects.

**Phase 3E is merged.** PR #20 was merged into `phase-3b-planning-domain`
on 2026-08-30 as a **true merge commit**,
`59743423f32b3b8f8c470128b30cf4b798b1f46f`, and is closed. A merge commit
rather than a squash was chosen deliberately, so that all 27 Phase 3E
commits remain ancestors of canonical and every SHA this review and the
project-health records cite stays reachable. *(This paragraph read "Phase 3E
is not merged. PR #20 is open and unmerged" until that merge.)* The verdict
itself is about the phase's readiness; the merge is its integration, and
**CI verified the merged content, not the merge commit** (§13.1). **GO is still not
authorization to begin Phase 4** — that remains a separate decision, and
the user's.

---

**Reviewed:** 2026-08-29 · **Closure pass:** 2026-08-29 ·
**Pre-PR audit:** 2026-08-29 · **CI pass:** 2026-08-30 ·
**Branch:** `phase-3e-agent-os` ·
**Last production-source commit:** `60934ac07166acd3635e3bf33dee9462d97f8a04` ·
**CI-verified head SHA:** `733a31d58eb1f0f5a0f3b5670d13de9975e5dedf`
(named here because CI evidence is SHA-pinned; §0's rule against naming a
*current* head still holds — use `git rev-parse HEAD` for that) ·
**Working tree:** clean · **PR:** #20, **merged and closed** ·
**Merge commit:** `59743423f32b3b8f8c470128b30cf4b798b1f46f` (true merge,
two parents) · **CI-verified content SHA:**
`258ebe6547bc011fa33eea829303b45337c6a42d` ·
**CI:** 27/27 Check Runs success (merge commit not itself CI-executed, §13.1)
