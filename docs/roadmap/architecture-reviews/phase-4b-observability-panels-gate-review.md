# Architecture Review Report — Phase 4B: Observability Panels

**Phase:** 4B — Observability panels (Planning, Reasoning Trace, Capabilities,
Approvals, Events, Health)
**Completed:** implementation and engineering verification complete 2026-09-06;
**gate verdict NO-GO** pending one user decision (§15)
**Design document(s):** [`docs/design/phase-4/00-master-scope.md`](../../design/phase-4/00-master-scope.md)
§5 (4B), §6 (panel scope table), decision **D-8**. **No 4B TDD exists** — see §4.1.
**Author:** AI-assisted (Claude Opus 5), executing
[`docs/PROJECT_PHASE_COMPLETION_PROTOCOL.md`](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md)
as read from `origin/main` at `733a31d`.
**Verified code SHA:** `0f3412c73b6dbd28b48c6f1ff9de14db3c238e53` — every figure in
§6–§8 was produced against it. Commits after it change documentation only.

---

## 0. Read this section first

Phase 4B's **engineering** verification is unambiguous and green: 30 of 30 GitHub
Actions Check Runs succeeded against the exact head SHA, including a full
Docker-backed end-to-end run of the real stack. That result is recorded in §6–§8
and is not in doubt.

This Gate Review nonetheless returns **NO-GO**, for one reason: **acceptance
criterion AC-3, the criterion the master scope assigns to this milestone, is not
met** (§9). Three approved panel capabilities named in master scope §5 were also
not built (§2). Neither fact was visible from CI, because no test asserts them —
which is precisely why this protocol requires the acceptance criteria to be
enumerated from the design documents rather than inferred from a green pipeline.

The verdict is a NO-GO under [protocol §3.2](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md),
which states that an unmet acceptance criterion is a NO-GO *unless the user has
explicitly approved deferring it*, and that CONDITIONAL-GO "is not a way to pass a
phase with an unmet acceptance criterion." The user has not been asked. §15 states
exactly what an approval would need to say and what the verdict becomes if given.

**Nothing in this review asks for Phase 4A to be reopened, and nothing in it
changes any Phase 4B production code.**

---

## 1. What was implemented

Five commits on `phase-4b`, branched from the merged `phase-4` head `481ceac`.

| Commit | Scope |
|---|---|
| `9af0708` | `api-gateway` route table 2 → 5 prefixes; `ws-gateway` `PUBLIC_TOPICS` 8 → 17; topic-guard correction |
| `b10e30d` | `GET /v1/plans` (planning-engine), `GET /v1/action/approvals` (action-engine) |
| `a7cf674` | Six panels, six `entities/` modules, reducers, lazy routing, 30 new frontend tests, E2E spec |
| `b22ec83` | E2E correction — Capabilities asserts rows, not emptiness |
| `0f3412c` | E2E correction — panels asserted to *settle*, not what they settle on |

43 files, +2,619 / −71. `packages/nova-contracts/` untouched.

### 1.1 Gateway surface

`build_route_table` returns five `UpstreamRoute`s: `/v1/communication`,
`/v1/plans`, `/v1/reasoning`, `/v1/capabilities`, `/v1/action`. Paths are
forwarded verbatim against an allow-list, not a pattern — decision **D-6**.
`executive-cognition-engine` and `nova-core` are deliberately not fronted;
`services/api-gateway/src/nova_api_gateway/domain/routing.py`'s docstring records
why.

`ws-gateway` `PUBLIC_TOPICS` grew to 17, with matching narrow patterns in
`events/subscribed.py`: `planning.task_graph.*`, `reasoning.process.*`,
`reasoning.human_override.*`, `action.approval.*`, `ai_model.model.*`,
`nova.module.status_changed`. `capability-engine` gets no entry — it publishes no
domain events, and inventing one is how `PUBLIC_TOPICS` acquired three dead topics
that 4A had to remove.

**A 4A guard defect was found and corrected.** `test_every_public_topic_is_reachable_on_the_bus`
compared `topic in SUBSCRIBABLE_SUBJECTS or f"{first}.*" in SUBSCRIBABLE_SUBJECTS`,
which silently passes any subject containing `*`. `BoundEventBus` authorises
subscriptions with `fnmatchcase`, where `*` spans dots. The guard now uses
`fnmatchcase`, and a parametrised test pins that it matches the way the SDK does.

### 1.2 Backend endpoints

Two, both additive; no existing route changed.

- `planning-engine` `GET /v1/plans` — declared **before** `/{task_graph_id}`
  because FastAPI matches in declaration order. Ordering lives in the repository
  (`ORDER BY created_at DESC`) because the `TaskGraph` domain model carries no
  `created_at` field.
- `action-engine` `GET /v1/action/approvals` — undecided only, oldest first,
  matching the order the panel's reducer maintains.

### 1.3 Panels

Six panels, six `entities/` modules, seven lazily-loaded routes beneath a layout
shell. `RealtimeProvider` sits above the router outlet so navigation does not
remount the socket and lose frames — most visible in the Events panel, exactly
where a gap in the stream is the subject.

One envelope throughout (`{data, meta, error}`). No polling for realtime state.
No optimistic mutation of shared cognitive state.

---

## 2. Why each architectural decision was made

| Decision | Alternative | Why this one |
|---|---|---|
| Health panel is **push-fed**, with no REST source | Build `GET /v1/system/health` on `nova-core` | `nova-core` exposes only `/internal/*`, which [doc 11 §3](../../architecture/11-api-architecture.md) makes permanently unroutable. Building the endpoint means giving `nova-core` a public HTTP surface — an architectural decision outside 4B's remit (§13, item G-1) |
| Approvals reconcile from the bus, never from the click | Optimistic removal | Shared cognitive state. A 409 (someone else decided first) would already have rendered as done. Negative-controlled (§7) |
| Confidence rendered as a tier word | Raw score or percentage | A number implies a precision the engine does not claim |
| A failed reasoning process reports **no** confidence | `0` | Zero asserts the engine was certain it was wrong; absence is the fact |
| A silent module goes `unknown` after 45s | Keep last good status | Silence is not health. Negative-controlled (§7) |
| Events keeps **arrival** order | Sort by `generated_at` | Re-sorting hides the out-of-order delivery the panel exists to show |
| Panels lazily loaded | One bundle | The Conversation panel — the one AC-1 measures — must not wait for six panels the operator may never open |

### 2.1 Deviation register

| # | Deviation | Class | Approval |
|---|---|---|---|
| **DEV-1** | Capabilities panel is **list-only**. Master scope §5 specifies "(list / install / uninstall)" | **Undisclosed narrowing** | **None.** `capability-engine` already exposes `POST /v1/capabilities/install` and `DELETE /v1/capabilities/{id}`, and `api-gateway` forwards `/v1/capabilities` — both were reachable and simply not built |
| **DEV-2** | Events panel has **no filter**. Master scope §5 specifies "filterable raw bus inspector" | **Undisclosed narrowing** | **None** |
| **DEV-3** | Reasoning Trace renders `reasoning_level` (the 1–4 reasoning tier), not **3A's recursion depth**. Master scope §5 specifies "including 3A's recursion depth" — which is `MultiStepConfig.max_step_depth` / `multistep_recursion_exhausted` (`services/reasoning-engine/src/nova_reasoning_engine/domain/models.py:298,351,378`), a different field | **Undisclosed narrowing** | **None** |
| **DEV-4** | `GET /v1/system/health` not built; Health is push-fed | **Disclosed narrowing** | Disclosed in PR #24 and in §2 above; grounded in doc 11 §3. Still requires ratification (§15) |
| **DEV-5** | `useLiveProcesses` uses `queryFn: undefined, enabled: false` rather than `skipToken`, unlike the other two push-fed keys | **Defect (cosmetic)** | None needed. Behaviour identical; emits a TanStack "no queryFn was passed" warning on mount |

DEV-1 through DEV-3 are the substance of the NO-GO alongside AC-3. Protocol
principle 0.3.6: *"Never narrow scope unilaterally. If part of a phase's approved
scope was not built, the phase is not complete."*

---

## 3. Tradeoffs considered

- **Six panels at once (D-8) over a subset.** Approved. Marginal cost of the sixth
  is far below a second pass. Held: the shared `AsyncPanelBody` and `entities/`
  layer made panels 2–6 cheap.
- **Reading existing surfaces over inventing new ones.** Only two endpoints were
  added; all 115 generated TypeScript contract types already existed. The cost is
  that panels show what the engines happen to expose, not an ideal shape.
- **Empty-state honesty over a populated-looking demo.** Seeding data would have
  made the panels look busy and stopped them testing the transport. The cost is
  that a green E2E proves reachability, not richness — which is exactly the gap
  AC-3 measures and §9 reports as unmet.

---

## 4. Known limitations

Every item here is disclosed, none is hidden, and none is presented as resolved.

1. **AC-3 is not met** — §9. The governing limitation of this milestone.
2. **DEV-1/2/3** — install/uninstall, event filtering, and recursion depth are
   not built (§2.1).
3. **`reasoning.process.*` and `ai_model.model.*` carried no observed frame.**
   Both subjects are authorised (negative-controlled topic guard, §7) and both
   owning workers start in the real stack (§8). But no test observed a frame on
   either subject, because with `ANTHROPIC_API_KEY` unset
   (`infra/docker/docker-compose.local.yml:340,408`) nothing produces one.
   Subject-level delivery for these two is **verified as reachable, not as
   delivered**.
4. **`GET /v1/system/health` does not exist** (DEV-4).
5. **No 4B TDD was ever written.** `docs/design/phase-4/02-tdd-4b-observability-panels.md`
   is listed as *"not yet written / Planned"* at `00-master-scope.md:520`. Master
   scope §5/§6 and D-8 are therefore the authoritative acceptance source, and
   there is no module-by-module conformance table to check against.
6. **`list_all` and `list_pending_approvals` have no real-Postgres test.** Both
   new endpoints' SQL is covered by fakes plus the live E2E stack only — see §8
   for the enumerated `real_infra` sets, in which neither method appears.
7. **`useLiveProcesses`** (DEV-5).
8. **Phase 4A has no Gate Review and no Project Health record.** Pre-existing,
   outside this milestone, analysed in §13 (G-4). Not repaired here, and — per
   the protocol as read — not a blocker on 4B.

---

## 5. Technical debt introduced

- **DEV-5**, one line.
- **Two untested repository methods** (limitation 6). The correct fix is one
  `real_infra` test per method in each engine's existing
  `test_repository_real_postgres.py`. Low cost, and the absence is exactly the
  defect class that produced Phase 3E's D-1/D-2 findings.
- Nothing else. The panels add no schema, no migration, no contract, and no new
  event subject.

---

## 6. Verification results

All figures uncached, produced against `0f3412c`.

| Gate | Command | Result |
|---|---|---|
| Lint + types | `pnpm turbo run lint --force` | **30/30 successful, 0 cached** |
| Tests (uncached) | `pnpm turbo run test --force` | **30/30 successful, 0 cached** — 1,813 pytest + 146 vitest |
| Scaffolding tools | `uv run pytest tools/tests -q` | **146 passed** |
| Import boundaries | `uv run lint-imports` | **7 kept, 0 broken** |
| compose | `docker compose -f infra/docker/docker-compose.local.yml config --quiet` | **valid** (exit 0) |
| Codegen drift | generate + `git status --short packages/nova-contracts` | **114 files, zero drift** (empty output) |

**Total: 2,105 passing**, 104 `real_infra` deselected locally (§8).

Coverage against the 85% `fail_under` gate, per affected package:
`api-gateway` **98%** (109 stmts / 2 miss) · `ws-gateway` **98%** (66/1) ·
`planning-engine` **99%** (286/2) · `action-engine` **97%** (255/8).
No affected package is below the gate.

`ruff format` and `prettier` are **not gates** in this repository — neither
appears in `package.json`, `turbo.json`, or any workflow, per protocol §9.2. They
were not run as gates and nothing was reformatted.

---

## 7. Negative controls and flakiness

Protocol §9.2 requires every property-asserting test to be proven to fail when the
property is removed. Three were controlled; all three fired; all three restored
green.

| Property | Injected break | Result |
|---|---|---|
| Every public topic is reachable on the bus | Removed `reasoning.process.*` from `events/subscribed.py` | **FAILED** — `'reasoning.process.completed' is public but not declared in events/subscribed.py`. Restored: 39/39 pass |
| No optimistic removal of an approval | Added an `onMutate` `setQueryData` filter | **FAILED** — *"does not remove a row optimistically when a decision is clicked"*. Restored: green |
| A silent module goes `unknown` | Made `withStaleness` return the entry unchanged | **FAILED** — *"falls back to unknown when a module stops reporting"*, `expected 'healthy' to be 'unknown'`. Restored: green |

**Flakiness:** the two 4B suites (`observability-panels.test.tsx`,
`observability-reducers.test.ts`) run **10×, 10/10 green, 0 failures**.

---

## 8. Real-infrastructure status

Reported as its own section, per protocol §10.2, and never folded into §6.

1. **Docker locally: NOT available.** `docker info >/dev/null 2>&1 && echo
   available || echo NOT available` → `NOT available`. Testcontainers cannot run
   in this environment.
2. **Deselected `real_infra` tests in the packages 4B changed — enumerated by
   name:**
   - `api-gateway`: **none.** `pytest -m real_infra --collect-only` → *"no tests
     collected (72 deselected)"*.
   - `ws-gateway`: **none.** → *"no tests collected (64 deselected)"*.
   - `planning-engine` (15), all in `tests/integration/test_repository_real_postgres.py`:
     `test_insert_then_find_by_id_round_trips`,
     `test_insert_persists_multiple_nodes_in_order`,
     `test_find_node_locates_the_graph_containing_it`,
     `test_find_node_returns_none_for_an_unknown_id`,
     `test_append_nodes_mutates_in_place_and_recomputes_critical_path`,
     `test_append_nodes_raises_for_an_unknown_task_graph_id`,
     `test_set_approved_at_persists_the_decision`,
     `test_set_approved_at_raises_for_an_unknown_task_graph_id`,
     `test_apply_transitions_mutates_status_and_republishes`,
     `test_apply_transitions_advances_a_completion_and_its_dependent_atomically`,
     `test_apply_transitions_raises_for_an_unknown_task_node_id`,
     `test_apply_transitions_raises_for_an_unknown_task_graph_id`,
     `test_insert_hands_off_admitted_nodes_while_publishing_them_as_ready`,
     `test_outbox_list_dispatch_ready_and_mark_dispatched_round_trip`,
     `test_a_fresh_repository_instance_reads_back_a_graph_written_earlier`.
   - `action-engine` (12), same file name:
     `test_insert_then_find_by_id_round_trips`,
     `test_insert_round_trips_a_rollback_strategy`,
     `test_inserting_a_duplicate_action_id_raises_action_already_exists`,
     `test_update_status_and_record_result_persist`,
     `test_get_result_returns_none_before_any_result_is_recorded`,
     `test_pending_approval_insert_find_and_decide_round_trips`,
     `test_record_execution_history_persists`,
     `test_identity_confidence_policy_round_trips`,
     `test_insert_round_trips_an_empty_depends_on`,
     `test_insert_round_trips_a_single_dependency`,
     `test_insert_round_trips_multiple_dependencies_in_order`,
     `test_a_dependent_action_survives_a_full_write_read_lifecycle`.
3. **Do they cover code 4B changed?** **No — and that is itself the finding.**
   4B added exactly two repository methods, `PostgresPlanningRepository.list_all`
   and `PostgresActionRepository.list_pending_approvals`. **Neither name appears
   in either list above.** The 27 enumerated tests exercise pre-existing methods.
   4B's own new SQL — including the `ORDER BY created_at DESC` clause — has no
   dedicated real-Postgres test in any environment.
4. **Matrix coverage:** `planning-engine` and `action-engine` are both in
   `.github/workflows/real-infra-checks.yml`'s 11-entry matrix. `api-gateway` and
   `ws-gateway` are not, correctly — they have no `real_infra` tests and no
   repository layer.
5. **Has the workflow run against this head?** **Yes.** Real-Infrastructure Checks
   run [34023254679](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/34023254679)
   (#100), **all 11 matrix jobs success**, against `0f3412c`.
6. **What remains unverified:** the two repository methods 4B added are exercised
   only by in-memory fakes and by the live Docker E2E stack, which reads them
   through the browser but asserts only that the panel settled without a
   degradation notice. **No test anywhere asserts their SQL returns the right rows
   in the right order against a real PostgreSQL.** The 11 `nova-testkit` fixture
   tests (Redis/Neo4j/NATS) remain unrun locally and touch no code 4B changed.

---

## 9. Acceptance criteria

Enumerated from all four sources protocol §2.1 requires: master scope §1.1,
master scope §5, `ENGINEERING_ROADMAP.md`'s Phase 4 entry, and this session's
instructions. **4B owns exactly one criterion.**

| # | Criterion (verbatim) | Source | Status | Evidence |
|---|---|---|---|---|
| **AC-3** | "Every Phase 3 sub-phase 3A–3D is exercised end-to-end **from the browser**: a plan is generated and rendered, a reasoning trace is inspected, a capability is installed, and a risky action is blocked pending approval and then approved." | `00-master-scope.md:55`, assigned to 4B at `:157` | **Not met** | Four sub-clauses, none satisfied — see below |

**Sub-clause accounting:**

| Sub-clause | Status | Why |
|---|---|---|
| "a plan is generated and rendered" | Not met | The Planning panel renders; **no plan was generated**. Generation needs an LLM provider; `ANTHROPIC_API_KEY` is unset in the E2E stack |
| "a reasoning trace is inspected" | Not met | Panel renders; **no trace exists**, same cause |
| "a capability is installed" | Not met | Four built-ins are installed **by `capability-engine`'s own boot bootstrap** (`main.py:191`) and are rendered in the browser — but not installed *from the browser*. **DEV-1**: no install control was built |
| "a risky action is blocked pending approval and then approved" | Not met | Approve/Deny controls exist and the reducer is correct, but **no risky action was created, blocked, or approved end-to-end** |

**0 of 1 acceptance criteria are met. The unmet criterion is AC-3.**

Protocol §2.1: *"Partially met criteria. These are not met."* Two sub-clauses fail
for an environment reason (no provider); two fail because the capability was not
built. The criterion's own wording — "end-to-end **from the browser**" — is
binding and is not softened here.

**AC-1 and AC-2 (Phase 4A) were re-verified as still passing** by the same CI run
and are not reopened: the four golden-path specs, including `/internal`
indistinguishability and the refused direct NATS socket, passed against `0f3412c`.

---

## 10. Forward and backward contamination

- **Backward:** 4B changed no Phase 4A production file's behaviour. It corrected
  one 4A **test** (the `fnmatch` topic guard, §1.1), which strengthens a 4A
  assertion rather than relaxing it. Phase 4A's golden path is untouched and still
  green.
- **Forward:** no 4C/4D/4E/4F work leaked in. No Agents, Autonomy, Digital Twin, or
  Cognitive State panel exists. `agent-os` remains uncontainerized (Phase 3E's
  ratified deferred obligation, untouched).
- **Owed-but-pushed-forward:** DEV-1/2/3 are work 4B owed and did not do. They are
  **not** silently reassigned to a later milestone — they are reported here as
  unbuilt scope requiring a user decision (§15).

---

## 11. CI and branch evidence

- **Branch** `phase-4b`, head `0f3412c73b6dbd28b48c6f1ff9de14db3c238e53`, working
  tree clean, nothing unpushed at the time of verification.
- **Ancestry:** branched from `phase-4` `481ceac` (the PR #23 merge commit).
  `main` `7e273e6`, `phase-4` `481ceac`, `phase-4a` `fbd75d7` — all untouched.
- **PR #24**, `phase-4b` → `phase-4`, open, **not merged**, opened at the user's
  explicit request so CI could run the Docker-backed verification (protocol §11.1
  satisfied).

| Workflow | Run | Conclusion | Against |
|---|---|---|---|
| PR Checks | [34023254683](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/34023254683) (#71) | **success** (both jobs) | `0f3412c` |
| Build & Scan | [34023254685](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/34023254685) (#71) | **success** | `0f3412c` |
| Real-Infrastructure Checks | [34023254679](https://github.com/Tudor191/NOVA-PROJECT-BIBLE/actions/runs/34023254679) (#100) | **success**, 11/11 | `0f3412c` |

**30 of 30 Check Runs `completed`/`success`.** Verify via the Check Runs API — the
legacy commit-status endpoint returns `total_count: 0` for this repository, as
Phase 3E's record also notes.

**Trivy:** no Dockerfile was touched by 4B. `build-and-scan` ran its full 14-service
matrix green regardless.

**Live-stack evidence** (PR Checks, Playwright job): stack start **success** (86s,
34 compose services); schema migration **success**; engines-not-crash-looping
**success**; both gateways answer **success**; golden path **success — 8 specs, 0
failures**. Both new workers, `reasoning-engine-worker` and
`ai-model-orchestration-engine-worker`, start and tear down cleanly by name.

**Commit-message accuracy** (protocol §11.1): every factual claim in the five
commit messages was re-checked. One is now known **overstated**: `a7cf674`'s body
says the E2E "asserts what a live stack can honestly show — every panel renders,
no panel reports an unreachable engine". Two of its assertions were in fact wrong
and were corrected in `b22ec83` and `0f3412c`, whose own messages record exactly
what was wrong and why. Per protocol principle 0.3.4 the original message is left
as written; this paragraph is the additive correction.

---

## 12. Compatibility with the NOVA Project Bible

**Part 01 §Personality** — *"Transparent … Never fabricate information. Never hide
uncertainty."* This is the requirement the panels are built against, and it is
implemented literally:

- Every panel distinguishes "has no data" from "could not reach its engine"
  (`AsyncPanelBody`'s four states).
- A module that stops reporting goes `unknown`, never keeps its last good status.
- A failed reasoning process reports no confidence rather than `0`.
- The Events panel shows the event's own time *and* arrival time, labelled.
- Confidence is a tier word, never a raw number.

**Faithfulness assessment: high for what was built, incomplete in coverage.** The
engine state each panel exposes is specified in Part 08 (reasoning), Part 09 (task
graphs, critical path), Part 12 (approval gating), Part 15 (installed
capabilities), Part 20 (heartbeat, module status). Part 15's capability *lifecycle*
(install/uninstall) is named in the Bible and in master scope §5 but is
**not surfaced** — DEV-1 is a Bible-coverage gap as well as a scope gap.

---

## 13. Gaps, ambiguities, and decisions requiring the user's approval

| # | Item | Options | Recommendation |
|---|---|---|---|
| **G-1** | **AC-3 is unmet** (§9). Two sub-clauses need an LLM provider the phase does not add; two need UI that was not built | (a) Ratify AC-3 as **deferred to a later milestone**, recording that the panels are the surface and the end-to-end demonstration follows when a provider exists; (b) build DEV-1 and drive an approval end-to-end, leaving only the two provider-dependent sub-clauses; (c) treat 4B as incomplete and extend it | **(b)**, then defer only the provider-dependent half. It closes the two sub-clauses that are genuinely 4B's to close, and leaves a narrow, honest deferral |
| **G-2** | **DEV-1/2/3** — three approved capabilities not built | (a) Build them in 4B; (b) ratify as explicit 4B narrowings and reassign to a named later milestone | **(a) for DEV-1** (it is also half of AC-3), **(b) for DEV-2 and DEV-3**, which are presentation refinements with no acceptance criterion depending on them |
| **G-3** | **`GET /v1/system/health` does not exist**; doc 11 §2 names it, master scope §5 lists it as a 4B backend addition | (a) Ratify the push-fed Health panel as the permanent design and correct doc 11 §2; (b) give `nova-core` a public surface and build it | **(a).** `nova-core` publishing its own heartbeat is already the architecture; a REST aggregate would duplicate it |
| **G-4** | **Phase 4A has no Gate Review and no Project Health record** | (a) Leave the gap recorded and repair it when `phase-4` closes; (b) write both retroactively now | **(a).** See §13.1 — the protocol as read does not require it before 4B |
| **G-5** | **SLOC not measured** — neither `cloc` nor `scc` is installed | (a) Install one and re-measure; (b) record "Not measured" | **(b) for this pass, (a) before `phase-4` merges to `main`.** The open Option A/B methodology decision in `project-health-master.md` §2 also remains open |
| **G-6** | Master scope prose says *"Phase 4 builds eight"* panels while its own §6 table lists **eleven** Phase-4 rows (conversation, six 4B, agents, autonomy, digital-twin, cognitive-state) | Correct the prose, or the table | Pre-existing, not caused by 4B. Recorded; an additive note has been added. Needs the user's call on which number is right |

### 13.1 Does the protocol require repairing the Phase 4A gap before 4B can receive GO?

**No.** Determined by direct inspection, not assumption:

- **Protocol §3.2 GO condition 9** requires *"Gate Review, Project Health record,
  roadmap entry, and README status all exist and are current"* — for the phase
  being gated. It is not a statement about sibling milestones.
- **`project-health/README.md`** establishes that *"a phase is not fully closed
  until both its Gate Review and its Project Health record exist."* That makes
  **Phase 4A not closed**. It does not make Phase 4B blocked.
- **Protocol §0.2**'s bar — *"A Sub-Phase may not be declared complete while any
  ledger row from any of its Slices is unsettled"* — is about a Sub-Phase's own
  Slices. Phase 4A is a sibling milestone of 4B, not a Slice of it.
- **Protocol §3.2 GO condition 10 / §12** would be triggered if any document
  claimed Phase 4A was complete, closed, or GO while no such record existed. A
  repository-wide sweep found **zero** such claims:
  `grep -rniE 'phase 4[ab][^|]{0,60}(complete|closed|merged|go\b|gate review)' docs/ README.md` →
  **0 hits.** There is therefore no contradiction to resolve.

Phase 4A is consequently left **entirely untouched** — no production code, no
history, no retroactive Gate Review — and the gap is recorded here (G-4) and in
[`phase-4b.md`](../../project-health/phase-4b.md) field 21 so `phase-4`'s eventual
closure inherits it rather than rediscovering it.

---

## 14. Documentation updated by this review

| Document | Change |
|---|---|
| This Gate Review | Created |
| [`docs/project-health/phase-4b.md`](../../project-health/phase-4b.md) | Created — 23-field record |
| [`docs/project-health/project-health-master.md`](../../project-health/project-health-master.md) | §1 row added; §3 index entries added for `phase-3e.md` (missing) and `phase-4b.md`; a stray blank line that had split §1 into two tables removed |
| [`docs/roadmap/ENGINEERING_ROADMAP.md`](../ENGINEERING_ROADMAP.md) | Additive status block on the Phase 4 entry: the 4A–4F restructure, 4A merged, 4B verified-but-NO-GO, and which document is authoritative for the criteria |
| [`docs/architecture/11-api-architecture.md`](../../architecture/11-api-architecture.md) | §2 catalogue: `GET /v1/plans` and `GET /v1/action/approvals` added; `GET /v1/system/health` annotated as not implemented |
| [`services/api-gateway/README.md`](../../../services/api-gateway/README.md) | Scaffold TODOs replaced with the real responsibility and the five forwarded prefixes |
| [`services/ws-gateway/README.md`](../../../services/ws-gateway/README.md) | Scaffold TODOs replaced with the real responsibility and the 17 public topics |
| [`services/planning-engine/README.md`](../../../services/planning-engine/README.md) | "Owned APIs" listed only `/internal/*`; the public `/v1/plans` surface added |
| [`services/action-engine/README.md`](../../../services/action-engine/README.md) | `GET /v1/action/approvals` added |
| [`docs/design/phase-4/00-master-scope.md`](../../design/phase-4/00-master-scope.md) | Additive 4B status note: what was built, DEV-1/2/3, the `system/health` decision, and the eight-vs-eleven count (G-6) |

> **Correction, 2026-09-06 (same day).** The row above for the four READMEs
> originally also recorded removing a `GET /internal/metrics` claim from each,
> asserting the route did not exist. **That was wrong.** All four services do
> expose it — `main.py` mounts `prometheus_asgi_app()` at `/internal/metrics`
> as a sub-application, which is why it is absent from `api/health.py` where
> the check had looked. The four READMEs have been corrected back, and the
> claim that it was a "scaffold artifact" is withdrawn. Recorded here rather
> than silently reverted, per principle 0.3.4.

**Inspected and found already accurate** — evidence the sweep was not selective:
`docs/architecture/09-event-bus-architecture.md` §6 (names `ws-gateway` as the sole
bridge; enumerates no subject list, so nothing went stale) ·
`docs/architecture/10-inter-engine-communication.md` (4B added no subject or RPC) ·
`docs/architecture/adr/` (no ADR falsified; 4B added none) ·
`docs/architecture/07-database-architecture.md` (no table, no migration) ·
`docs/architecture/17-cicd-pipeline.md` (no gate changed) ·
`docs/architecture/16-testing-strategy.md` (no tier, marker, or coverage rule
changed) · `docs/bible/part-01`, `08`, `09`, `12`, `15`, `20` (checked for
compatibility, not edited — §12) · top-level `README.md` (its Status section
describes `main`, where Phase 4 is not yet merged; correctly silent on Phase 4 —
see [`phase-4b.md`](../../project-health/phase-4b.md) field 17).

### 14.1 SAD 15 §9.1 — ten-item build-time deliverable checklist

4B introduced **no new subsystem** — no engine, package, or `agent-os` component.
It extended four existing services and one existing app. The checklist is therefore
assessed against the extended surface rather than a new one.

| # | Item | Status |
|---|---|---|
| 1 | Architecture documentation | **Present** — doc 11 §2 updated; both gateway READMEs written |
| 2 | Sequence diagrams | **Absent.** No new diagram for the panel read/realtime paths |
| 3 | Component diagrams | **Absent** |
| 4 | API documentation | **Present** — doc 11 §2 + engine READMEs |
| 5 | Unit tests | **Present** — 30 new frontend tests; 146 tools; gateway/engine suites green |
| 6 | Integration tests | **Present** — `test_plans_api.py`, `test_approvals_api.py`, plus the Docker E2E |
| 7 | Performance benchmarks | **Absent.** No benchmark for panel load or socket throughput |
| 8 | Failure scenarios | **Present** — `AsyncPanelBody`'s degradation path, asserted in the E2E; health staleness; `/internal` and NATS boundary specs |
| 9 | Logging strategy | **N/A** — no new backend service; the two endpoints inherit their engines' existing logging |
| 10 | Observability metrics | **N/A** — same reason; no new metric introduced |

**Three items absent (2, 3, 7).** Recorded, not waived; they are inputs to the §15
decision.

---

## 15. Gate verdict

### **NO-GO**

Under protocol §3.2, which is explicit: *"An unmet acceptance criterion is a NO-GO
unless the user has explicitly approved deferring it,"* and *"CONDITIONAL-GO is not
a way to pass a phase with an unmet acceptance criterion."*

**What is blocking:**

| # | Blocker | What would clear it |
|---|---|---|
| **B-1** | **AC-3 unmet** (§9) — 0 of 1 acceptance criteria met | Either the user's explicit approval to defer AC-3 (recorded, with the milestone that inherits it), or the work in G-1(b) |
| **B-2** | **DEV-1/2/3 are undisclosed narrowings** of master scope §5 (§2.1) — protocol principle 0.3.6 forbids narrowing scope unilaterally | Either building them, or the user's explicit ratification of each as a disclosed 4B narrowing |

**What is *not* blocking**, stated so it is not mistaken for a blocker:

- Every engineering gate is green (§6, §7, §11). 30/30 Check Runs, real Docker E2E.
- Real-infrastructure ran and passed in CI against this exact SHA (§8).
- The Phase 4A documentation gap (§13.1) — analysed against the protocol and found
  not to be a precondition for 4B.
- The unobserved `reasoning.process.*` / `ai_model.model.*` frames (§4 item 3) —
  a disclosed limitation, and no acceptance criterion turns on delivery of those
  two subjects specifically.
- SLOC not measured (G-5) — a disclosure, and both SLOC milestones are addressed
  in §16.

### If the user approves the deferral

If the user explicitly approves deferring AC-3 and ratifies DEV-1/2/3 as disclosed
4B narrowings, **both blockers convert to disclosed narrowings and this verdict
becomes CONDITIONAL-GO**, with these conditions:

- **C-1** AC-3 is reassigned, by name, to the milestone that will demonstrate it.
  Discharged when that milestone's Gate Review records it met.
- **C-2** DEV-1 (capability install/uninstall), DEV-2 (event filtering), DEV-3
  (recursion depth) each get an owning milestone. Discharged the same way.
- **C-3** A `real_infra` test for `list_all` and `list_pending_approvals`
  (§8 item 6). Discharged by a green `real-infra-checks` run covering them.
- **C-4** SLOC measured with `cloc` or `scc` before `phase-4` merges to `main`
  (G-5).
- **C-5** SAD 15 §9.1 items 2, 3, 7 (§14.1) supplied or explicitly waived.
- **C-6** Phase 4A's Gate Review and Project Health record written before
  `phase-4` closes (G-4).

That decision is the user's and is not taken here.

---

## 16. Project Metrics

Per SAD 15 §10 and `METRICS_TEMPLATE.md`.

**Production SLOC: Not measured.** Neither tool is installed in this environment:

```
$ command -v cloc || echo "cloc NOT installed"     → cloc NOT installed
$ command -v scc  || echo "scc NOT installed"      → scc  NOT installed
```

Per `project-health/README.md`, a value that cannot be measured reads **"Not
measured"** and is never estimated, inferred, or backfilled. No substitute line
count is offered here, because a hand-rolled count would not be comparable to
either historical series.

**SLOC milestone status:**

- **~30,000 reminder** — already crossed at Phase 3E (31,319, `cloc` v1.98,
  comparable scope) and already discharged by the
  [Project Health Review 2026-08-29](project-health-review-2026-08-29.md)
  (verdict HEALTHY). Not re-triggered by 4B.
- **~50,000 gate** — **not crossed.** Stated as a bound rather than a
  measurement: the last measured figure is 31,319 in the comparable scope, and
  4B's *entire* diff against `phase-4` is +2,619 lines across all file types —
  tests, TypeScript, YAML and Markdown included, none of which count as Production
  SLOC. Even attributing every added line to production code leaves the figure
  below 34,000, far short of 50,000. **This is a bound derived from the diff, not
  a measurement**, and it is not entered into the series.

**Implementation statistics:** 43 files changed, +2,619 / −71. 5 commits.
**Architecture metrics:** 16 `services/`, 4 `agent-os/`, 5 `agents/`, 9
`packages/`, 24 ADRs, 7 import-linter contracts (0 broken), 115 generated
TypeScript files, 34 compose services, 30 CI Check Runs.
**Quality metrics:** 2,105 tests passing, 0 failing; coverage 97–99% on the four
affected packages against an 85% gate; 3/3 negative controls fired; 10/10 flake
runs clean.

---

## 17. Definition of Done — all ten items

Per [`definition-of-done.md`](../../project-health/definition-of-done.md), checked
item by item.

| # | Item | Status |
|---|---|---|
| 1 | Gate Review | **Done** — this document |
| 2 | Project Health record + master row | **Done** — [`phase-4b.md`](../../project-health/phase-4b.md), master §1 row and §3 index |
| 3 | TDD / design currency | **Partial** — no 4B TDD exists (§4 item 5); master scope carries an additive 4B status note |
| 4 | Roadmap status | **Done** — additive Phase 4 status block |
| 5 | README / project status | **Done** — four subsystem READMEs; top-level README correctly unchanged (it describes `main`, where Phase 4 is not merged) |
| 6 | Additive corrections | **Done** — every historical edit is an additive dated note; nothing rewritten |
| 7 | Tests and verification evidence | **Done** — §6, §7, real counts and percentages |
| 8 | CI / Trivy / real-infra | **Done** — §8, §11; Trivy N/A (no Dockerfile touched) |
| 9 | Final acceptance-criteria status | **Done** — §9, and the gap is flagged, not glossed |
| 10 | Final merge-readiness review | **Done, and it does not pass** — head SHA, CI, clean tree and diff scope all confirmed; the gate verdict is NO-GO on B-1/B-2 |

---

## Sign-off

- [x] All items in the phase's design-doc review checklist are either satisfied or
      explicitly noted as changed, with reasoning above — **with three
      exceptions, DEV-1/2/3, reported as unbuilt scope rather than as changes.**
- [ ] The phase's Definition of Done ([SAD 15 §4](../../architecture/15-development-workflow.md#4-definition-of-done-per-pr))
      was met for every PR. **Item 1 ("touches exactly one engine's `src/`") is not
      met**: PR #24 spans both gateways, two engines, `apps/web-client` and
      `packages/nova-ui`. It is a milestone PR, and no change-scope linter enforces
      item 1 in CI. Items 2–5 are met; item 3 is N/A (no contract changed); item 4
      is satisfied — both new endpoints are purely additive and no existing route
      changed.
- [x] The per-subsystem deliverable checklist ([SAD 15 §9](../../architecture/15-development-workflow.md#9-per-subsystem-deliverable-checklist))
      was assessed for every subsystem this phase touched — §14.1, **three items
      absent (sequence diagrams, component diagrams, performance benchmarks).**

**Completing this Gate Review is not authorization to begin Phase 4C, and not
authorization to merge PR #24.**
