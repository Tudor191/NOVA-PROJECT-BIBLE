# Phase 4C — Project Health Snapshot

Phase 4C shipped as **two separately-reviewed units**, and this record keeps
them apart rather than merging their numbers, following the Phase 3B precedent
[`README.md`](README.md) sets for multi-unit phases:

- **4C.1 — `agent-os` containerization** (PR #25). **No Gate Review document
  exists for this unit** — see field 21. Its values below are cited to the
  additive implementation notes it wrote into
  [`00-master-scope.md`](../design/phase-4/00-master-scope.md) §5 and §10, and
  to the repository, because there is no Gate Review to cite.
- **4C.2 — the Agents surface** (PR #26). Source: the
  [Phase 4C.2 Gate Review](../roadmap/architecture-reviews/phase-4c2-agents-surface-gate-review.md),
  repository-driven, written against head `a405bca` and extended by a dated
  **§18 closure addendum** against head `7360763`.

Fields with no available value read **"Not reported"** or **"Not measured"**
with the reason, per [`README.md`](README.md)'s rule; nothing is inferred from
an adjacent phase or backfilled from today's tree.

---

## Phase 4C — Sub-unit 1: `agent-os` containerization (PR #25)

| # | Field | Value |
|---|---|---|
| 1 | Phase identity | Phase 4C, milestone **4C.1** |
| 2 | Phase/Sub-Phase name | `agent-os` containerization — discharges **CF-3** (Phase 3E condition C-3, ratified as a deferred obligation: `agent-os` had no Dockerfile, no compose service, no `build-and-scan` matrix entry and therefore no Trivy scan). Master scope §5 and §10 |
| 3 | Report date | 2026-09-07 (implementation); this record 2026-09-12 |
| 4 | Branch | `phase-4c`, head `e4900eb2f54e3e74d8a07cab67cc0dd337706128`, branched from the merged `phase-4` head `2854b17` (the PR #24 merge commit), per master scope §16 rule 5. Two commits: `19b33b6` the implementation, `e4900eb` a documentation correction (Phase 4 panel count, eight → eleven; G-6) |
| 5 | PR number | **#25**, `phase-4c` → `phase-4`. **Merged**, as merge commit `3433fbea25b19217542cd20155b866ca46589f01`, which became `phase-4`'s head and the base 4C.2 branched from |
| 6 | Commit / merge commit | Implementation `19b33b6`; branch head `e4900eb`; merge commit **`3433fbe`** |
| 7 | Phase status | **Complete and merged. No Gate Review verdict was ever recorded for this unit** — see field 21. Master scope §5's dated implementation note states what shipped; it is a status note, not a gate assessment |
| 8 | Production SLOC | **Not reported.** 4C.1 wrote no metrics section, and no measurement was taken at its head. Per [`README.md`](README.md) this is not backfilled from today's tree. The next measurement in the series is 4C.2's (sub-unit 2, field 8) |
| 9 | Total SLOC | **Not reported** — same reason |
| 10 | SLOC methodology/tool | **None applied this unit.** The series is unbroken rather than extended |
| 11 | SLOC scope | **N/A this unit** — nothing measured |
| 12 | Test status | **Not reported as a unit-level figure.** 4C.1 added no application code and no new test package; its verification was structural — the three images build, the three compose services start, and `tools/tests/test_e2e_stack_completeness.py::test_the_agent_os_library_has_no_container` enforces that `sdk/python` stays container-free (master scope §5's correction note) |
| 13 | Test count | `tools/tests/test_build_and_scan_matrix.py` and the `test_e2e_stack_completeness.py` guard are the unit's own tests. Exact counts **Not reported** at the time |
| 14 | Coverage | **N/A** — no Python domain package changed |
| 15 | CI status | **Green at merge.** `real-infra-checks` run 118 against `e4900eb` succeeded (2026-09-08). PR #25 merged into `phase-4` as `3433fbe`. Per-workflow Check Run counts against `e4900eb` were **not recorded** at the time |
| 16 | Real-infrastructure status | Unchanged by this unit — `real-infra-checks.yml`'s matrix is explicitly **not** modified by 4C.1 (master scope §10's implementation note). Its contribution is the *image* tier: **the first Trivy coverage any `agent-os` component has ever had** |
| 17 | Documentation health | Three documents changed: `architecture/14-deployment-architecture.md`, `design/phase-3/08-tdd-3e-agent-os.md`, `design/phase-4/00-master-scope.md`. All edits additive and dated. **No Gate Review and no health record were written** — that gap is closed by this document for the health record, and remains open for the Gate Review (field 21) |
| 18 | Architecture status | Three Dockerfiles (`kernel`, `registry`, `supervisors`), three `docker-compose.local.yml` services, three `build-and-scan.yml` matrix entries, `agent-os/kernel` and `agent-os/registry` added to `run-migrations.sh`, all three started and restart-checked by `pr-checks.yml`'s e2e job. **Three containers, not four**: `sdk/python` is a library and deliberately has no Dockerfile, consistent with `packages/*` — enforced by test, not only documented (master scope §5) |
| 19 | Security status | **First-ever Trivy scanning of `agent-os` images**, at `severity: CRITICAL,HIGH`, `exit-code: 1`. No event subject, REST path, allow-list or session change |
| 20 | Unverified infrastructure | Prometheus scrapes only `nova-core` — carried forward, reported not fixed (4C.2 Gate Review §13.3) |
| 21 | Open blockers | **None blocking. One documentation gap, recorded rather than closed: 4C.1 has no Gate Review document.** `docs/roadmap/architecture-reviews/` contains only `phase-4c2-agents-surface-gate-review.md`. Protocol §0.1 makes category 3 (Gate Review) **deferrable for a significant Slice**, so its absence was permissible at the time; §0.2 makes it a ledger row that Phase 4C's closure inherits. It is recorded here in the same shape [`phase-4b.md`](phase-4b.md) field 21 used for Phase 4A's missing records. **No 4C.1 work is reopened and no new milestone is created by recording it** |
| 22 | Branch hygiene | `phase-4c` preserved at `e4900eb`, not deleted, and a git ancestor of `phase-4`. No force push, no rebase, no squash |
| 23 | Notes / important findings | 4C.1 discharges **AC-4 clause 1** — *"`agent-os` runs as containers under `docker compose up`"* — and nothing else. Master scope §5's own note is explicit that **AC-4 remains NOT MET** after it: *"Nothing else in this milestone's list is built: no `/v1/agents`, no activity persistence, no peer-review persistence, no Agents panel, no new realtime exposure, no supervisor tree."* That work is 4C.2's |

---

## Phase 4C — Sub-unit 2: the Agents surface (PR #26)

| # | Field | Value |
|---|---|---|
| 1 | Phase identity | Phase 4C, milestone **4C.2** |
| 2 | Phase/Sub-Phase name | The Agents surface, end to end, in six implementation slices plus a documentation/verification closure pass: **4C.2a** the internal Registry `agent_os.registry.list_packages` RPC · **4C.2b** the append-only `agent_os.agent_activity` table and its transactional repository surface · **4C.2c** the Kernel's read-only `/v1/agents` REST surface fronted by `api-gateway` (closes **CF-2**) · **4C.2d** activity writes wired into the real Kernel lifecycle · **4C.2e** `agent_os.task.completed` opened to the browser through `ws-gateway` · **4C.2f** the Agents entity, panel, `/agents` route and realtime reconciliation · **4C.2g** documentation reconciliation and the Gate Review (Gate Review §1) |
| 3 | Report date | 2026-09-10 (Gate Review); §18 addendum 2026-09-11; merged and this record 2026-09-12 |
| 4 | Branch | `phase-4c.2`, head `7360763889b551291e330034443881a865cedd94`, branched from the merged `phase-4` head `3433fbe` (the PR #25 merge commit), per master scope §16 rule 5. **11 commits, linear, zero merge commits**, 11 ahead / 0 behind at merge. Working tree clean, nothing unpushed (Gate Review §18.1) |
| 5 | PR number | **#26**, `phase-4c.2` → `phase-4`. **Merged 2026-09-12T19:15:59Z** on explicit user authorization, with the Gate Review verdict standing at CONDITIONAL-GO because **C-3 is an approved deferral**. Merged by `Tudor191`; `merge_method: merge` |
| 6 | Commit / merge commit | Verified head **`7360763889b551291e330034443881a865cedd94`**; **merge commit `b1d7ca548e88ddc2fc8d5f56007a8864127cb798`**, a **normal two-parent merge** — parent 1 `3433fbea25b19217542cd20155b866ca46589f01` (previous `phase-4`), parent 2 `7360763889b551291e330034443881a865cedd94` (PR #26 head). **Not squashed**, so every SHA the Gate Review cites stays reachable. Commit chain: `8ed7436` 4C.2a · `c1dbd44` 4C.2b · `92ba4d7` 4C.2c · `e0489b9` 4C.2d · `e97602c` 4C.2e · `a405bca` 4C.2f · `69a9461` 4C.2g · `4eafa80` the transaction-ordering fix · `388c271` the E2E database isolation fix · `1182816` the js-yaml lockfile refresh · `7360763` the documentation reconciliation |
| 7 | Phase status | **Implementation complete, verified, and merged; gate verdict CONDITIONAL-GO** (Gate Review §15, unchanged; §18.9 reaffirms it at the merged head). **C-1 and C-2 are DISCHARGED** (§18.2, §18.4); **C-4 documentation reconciliation DISCHARGED** (§18.6); **C-3 remains OPEN** — **AC-4 is still NOT MET**, its clauses 2 and 3 *"renders live agent instances"* and *"at least one real peer-review round"* **Deferred by explicit user approval of 2026-09-07**, recorded under protocol §2.4 as "Deferred by approval (approval cited)". §2.1's "partially met is not met" is unaltered: a deferral changes the criterion's consequence for the gate, never its status. **The verdict was not raised to GO and is not reinterpreted as GO here.** The user explicitly authorized merging under CONDITIONAL-GO on the basis that C-3 is an approved deferral; that authorization is recorded in the merge commit body |
| 8 | Production SLOC | **32,948** on the scope comparable to Phase 4B's (`services/*/src` + `packages/*/src` + `services/*/alembic/versions`); **36,573** on Phase 3E's full scope adding `agent-os/*` and `agents/*`; **39,258** on the full scope also including `apps/*/src` (Gate Review §16). Growth on the comparable scope over Phase 4B: **+25**, because 4C.2's production code lands almost entirely in `agent-os/` and `apps/`, which that scope excludes — the +25 is `api-gateway`'s routing entry and config field. **A re-measurement at the merged head `b1d7ca5` reproduced the comparable scope exactly (32,948)** and produced **38,289 / 40,974** on the two wider scopes; those two figures used a scope string that additionally included `agent-os/*/alembic/versions`, so they are **recorded side by side as not comparable** to the Gate Review's own wider figures rather than replacing them ([`README.md`](README.md)'s incomparable-measurement rule). Measured on identical scope strings at both revisions, production SLOC moved **+1 line** between `a405bca` and the merged head — the transaction-ordering fix |
| 9 | Total SLOC | **Not reported.** The Gate Review §16 reports production scopes and the architecture/quality metric set, not a whole-repository total. Not backfilled |
| 10 | SLOC methodology/tool | **`cloc` v2.06** — the same tool *and* the same version Phase 4B's closure pass used, so this figure continues that series comparably rather than only directionally. The **`scc` series (Phases 2D-B → 2D-C) remains separate and non-comparable**, and the Option A / Option B methodology decision in [`project-health-master.md`](project-health-master.md) §2 **remains open and is not decided here** |
| 11 | SLOC scope | Three scopes reported side by side, continuing Phase 4B's four-scope precedent minus its `--skip-uniqueness` variant: comparable, Phase 3E full, and full including `apps/*/src`. **§2 needs no new methodology entry** — neither the tool nor the scope definitions changed |
| 12 | Test status | `pnpm turbo run lint` **30/30**; `pnpm turbo run typecheck` **5/5**; `pnpm turbo run test --force` **30/30 successful, `Cached: 0`**; **2,242 passing via turbo + 218 `tools/tests` = 2,460 passing, 0 failing**, 322 deselected; `uv run lint-imports` **7 kept, 0 broken**; `docker compose … config` valid; codegen **116 files, zero drift** (Gate Review §6, re-run at the merged head) |
| 13 | Test count | 4C.2 added tests across all six slices; the Gate Review §6 per-package table records `agent-os/kernel` 190 passed / 50 deselected, `agent-os/registry` 68 / 18, `services/api-gateway` 88, `services/ws-gateway` 103, `apps/web-client` 173. **`real_infra` selection moved 48 → 50 for the kernel** when `4eafa80` added two regression tests for the transaction-ordering defect; the Gate Review §8's **48** is correct for its own head `a405bca` and is left as written (§18.2) |
| 14 | Coverage | `agent-os/kernel` **99%** (295 stmts / 4 miss) and `agent-os/registry` **99%** (206 / 2) against the 85% `fail_under` gate. `services/api-gateway`, `services/ws-gateway` and `apps/web-client` are **not coverage-gated** — the gate is `[tool.coverage.report]` in `pyproject.toml` and applies to Python domain packages only (Gate Review §6) |
| 15 | CI status | **GREEN — 34 of 34 Check Runs `success` against head `7360763889b551291e330034443881a865cedd94`** (2026-09-12): `checks` (pr-checks), **12/12** `real-infra` matrix jobs, **19/19** `build-and-scan` image jobs, `dependency-audit`, and the staged non-blocking Playwright golden path. Verified through the **Check Runs API**, not the legacy commit-status endpoint, which returns `total_count: 0` for this repository. **`build-and-scan` required one re-run**: on attempt 1 `docker/setup-buildx-action@v3` failed pulling `moby/buildkit:buildx-stable-1` from Docker Hub (`connection reset by peer` from `auth.docker.io`), which fail-fast propagated as 18 cancellations; the job's own step record shows Build and Scan both **skipped**, so no repository file was read and no scan ran. Attempt 2 (`run_attempt: 2`, run `34684203439`) is **Build success + Trivy Scan success on all 19 images**. The failure was infrastructural and is recorded as such rather than as a repository result |
| 16 | Real-infrastructure status | **PASSED, not merely disclosed — this is the field Phase 4B could not fill.** `real-infra-checks` run `34684203435`, **all 12 matrix jobs success** against `7360763`. `real-infra (kernel)` **50 passed, 190 deselected in a single pytest process** — the only configuration that can prove absence of cross-test contamination — including the Phase 3E real-PostgreSQL acceptance E2E at position 8 of 50; `real-infra (registry)` **18**. Total **68** (50 kernel + 18 registry). **Docker was unavailable locally throughout**, so every real-infrastructure result is CI's and is labelled as such; nothing was simulated |
| 17 | Documentation health | 4C.2g changed eight documents plus the new Gate Review (§14); the 2026-09-11 reconciliation pass added the Gate Review's **§18 closure addendum** (append-only, +189/−0, §§0–17 and the original Sign-off byte-identical), corrected `ENGINEERING_ROADMAP.md`'s 4C row — which still read **"Not started"**, a direct contradiction of the repository — and added a dated note to master scope §9.2. A repository-wide sweep found **zero** documents claiming 4C is "Not started", **zero** claiming 4C.2 is merged while it was not, and **zero** claiming 4C or 4C.2 is GO. **Historical sections were never rewritten**: every superseded figure is affirmed as correct for its own head and superseded additively, per protocol §0.3.4 |
| 18 | Architecture status | Every 4C.2 rule verified at the merged head. **D-1**: a degraded Registry answers **503**, never `200` with `packages: []`. **D-3**: `insert` has one `async with`, **one `commit()`** and one `flush()` whose `try` body is exactly `await session.flush()`; `update_status` and `append_activity` one commit each; **no `update_activity`, no `delete_activity`, no `DELETE FROM`** — the append-only guarantee. **D-4**: three `@router.get`, **zero** mutating routes. Gateway forwards one prefix `/v1/agents` → `agent-os-kernel`, 1:1. Six activity kinds, five write sites. `correlation_id` propagated, never minted; `NULL` when no event is published (decision B2). `uv run lint-imports` **7 kept, 0 broken** |
| 19 | Security status | `PUBLIC_TOPICS` **18 exact strings, zero wildcards, exactly one `agent_os.` entry** (`agent_os.task.completed`); `SUBSCRIBABLE_SUBJECTS` **11 patterns**, `agent_os.task.*` present and `agent_os.*` absent — `BoundEventBus` matches with `fnmatchcase`, where `*` spans dots, so the wide form would have covered every Registry and Supervisor RPC subject. Authorization is exact `frozenset` membership, never a prefix: **14/14 live probes** behaved correctly, including `agent_os.task.completedX` and `agent_os.task.started` rejected from the browser while matching the bus pattern. Browser source contains no NATS client, no `nats://`, no `:4222`, no kernel host and no `/internal/` path. **Trivy green on all 19 images** at `CRITICAL,HIGH`, `exit-code: 1` |
| 20 | Unverified infrastructure | **None outstanding for 4C.2.** Both defects the first real database exposed are fixed and verified: **(a)** a transaction-ordering fault — `AgentActivityORM` declares a foreign key but no ORM `relationship()`, so SQLAlchemy sorted the mappers by name and emitted the child INSERT first, compounded by a blanket `IntegrityError` handler that reported the foreign-key failure as `AgentInstanceAlreadyExistsError`; fixed in `4eafa80` with **decision D-3 preserved**. **(b)** a Phase 3E E2E database-isolation fault, latent since 4C.2c and masked by (a); fixed in `388c271` with **`list_instances()` production behaviour unchanged** and no assertion weakened. Carried forward unchanged: the over-broad `communication.*` / `personality.*` bus patterns (§13.1, still six pinned subjects, none browser-reachable), the hand-maintained codegen `MODELS` list, Prometheus scraping only `nova-core`, `supervisor_id` as dead schema, CF-8, CF-9 |
| 21 | Open blockers | **None blocking the merge, which the user explicitly authorized. One condition remains open by approval: C-3.** AC-4 clauses 2 and 3 are **Deferred by the user's explicit approval of 2026-09-07**, traced through code in master scope §1.1 — an `agent_instance` row has exactly one creation path, `scheduler.py::_spawn_tracked`, reachable only from `planning.task_graph.created`, whose sole input is `decompose()`, which calls `ai_model.generate.request` and raises `DecompositionError` with **no deterministic fallback**. **The remaining trigger is provider configuration and nothing else**; both clauses become demonstrable the moment a provider exists, with no further Agents work. **This does not create a 4C.3 milestone, and no 4C.3/4C.4/4C.5/4C.6 implementation milestone exists** — a search across all branches and all history finds `4C.4`/`4C.5`/`4C.6` in **zero commits ever**, and `4C.3` in exactly one: the 4C.2 Gate Review's own sign-off sentence *"4C.3 — or whatever follows — is a separate decision"*, which is placeholder phrasing, not a plan. **4C implementation is complete.** Carried to Phase 4 closure: 4C.1's missing Gate Review (sub-unit 1 field 21) and Phase 4A's missing Gate Review and health record ([`phase-4b.md`](phase-4b.md) field 21) |
| 22 | Branch hygiene | `phase-4c.2` preserved at `7360763`, **not deleted**, and a git ancestor of `phase-4`. `phase-4`, `phase-4a`, `phase-4b`, `phase-4c` and `phase-4c.2` all intact. `main` verified **unchanged at `7e273e62e942ecd5528ca807e65933d6bb675669`** — Phase 4 is not merged to `main` and `main` was not modified. No force push, no rebase, no squash, no history rewrite. **`phase-4d` deliberately not created** — master scope §16 rule 4 creates milestone branches strictly one at a time, and completing this record is not authorization to begin 4D |
| 23 | Notes / important findings | **The finding that matters most: local gates cannot see a foreign key.** The 4C.2 Gate Review recorded acceptance item 4, "Transaction semantics — Met", on the strength of source inspection plus a fake repository. Against a real database at that head the claim was **false** — every coupled insert raised. It is genuinely true now, proven by three named tests against real PostgreSQL. Condition C-1 existed precisely to catch this, and it did; the Gate Review's §18.3 records the correction additively rather than editing §9. **The second finding: fixing one defect exposed another.** The E2E isolation fault had been latent since 4C.2c and was invisible while the first defect suppressed all instance creation — the four `test_list_instances_*` tests passed in the one CI run before the fix for the wrong reason. **Third: an infrastructural CI failure is not a repository failure, and the distinction was verified rather than assumed** — the step record showed Build and Scan both `skipped`, proving the job never read a repository file. **Fourth, and recorded because the number would have entered a permanent record:** a hand-rolled line count during 4C.2g returned 49,112 and appeared to put the project within 900 lines of the ~50,000 gate that pauses feature development; it was wrong, because a `grep`-based filter cannot strip multi-line Python docstrings. `cloc` gives 39,258 on the same scope. The **~50,000 gate is not crossed** |

---

## Phase 4C closure

**Phase 4C consists of exactly two milestones — 4C.1 and 4C.2. Both are
complete and both are merged into `phase-4`.** There is no 4C.3, 4C.4, 4C.5 or
4C.6, and none is created by this record.

`phase-4` head at closure: **`b1d7ca548e88ddc2fc8d5f56007a8864127cb798`**, the
two-parent merge commit of PR #26. It contains the complete 4C.1 + 4C.2
history: `19b33b6`, `e4900eb` (4C.1) and `8ed7436`, `c1dbd44`, `92ba4d7`,
`e0489b9`, `e97602c`, `a405bca`, `69a9461`, `4eafa80`, `388c271`, `1182816`,
`7360763` (4C.2), all verified as ancestors. `main` remains **unchanged at
`7e273e6`**.

**AC-4 status, stated once and precisely.** Clause 1 — *"`agent-os` runs as
containers under `docker compose up`"* — is **Met** by 4C.1. Clauses 2 and 3 —
*"renders live agent instances"* and *"at least one real peer-review round"* —
remain **Deferred by the user's explicit approval of 2026-09-07** and are **not
modified by this closure**. AC-4 as a whole is therefore **NOT MET**, and this
record does not say otherwise. The remaining trigger is **provider
configuration**; the discharge milestone is, per master scope §1.1, still
undesignated.

**Gate Review status.** The
[Phase 4C.2 Gate Review](../roadmap/architecture-reviews/phase-4c2-agents-surface-gate-review.md)
remains part of the permanent history with its verdict unchanged at
**CONDITIONAL-GO**. Its §§0–17 and original Sign-off are untouched; §18 and §19
are dated, append-only addenda. **No historical section was rewritten to look
current.**

**The §18.8 deferred-obligations ledger is settled by this pass** for its two
project-health rows: this file, and the Phase 4C row in
[`project-health-master.md`](project-health-master.md) §1 and §3. Its third
row — the top-level `README.md` Phase 4 status line — is owned by **Phase 4
closure**, not 4C, and remains open. Master scope §17's
`03-tdd-4c-agent-os-api-and-containerization.md` row is settled in that
document as a recorded waiver.

**Carried to Phase 4 closure, not to a new 4C milestone:**

| Obligation | Owner |
|---|---|
| 4C.1 has no Gate Review document (sub-unit 1, field 21) | Phase 4 closure |
| Phase 4A has no Gate Review and no Project Health record ([`phase-4b.md`](phase-4b.md) field 21) | Phase 4 closure |
| `README.md` carries no Phase 4 status line | Phase 4 closure |
| AC-4 clauses 2 and 3, Deferred by approval | An undesignated provider milestone |
| CF-9 (ADR-032 identity-confidence policy has no creation path) | Phase 4D's policy surface |
| SLOC methodology Option A / Option B decision (§2) | Open, undecided |

**Completing this record is not authorization to begin Phase 4D**, and
`phase-4d` has not been created.
