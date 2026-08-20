# Phase 3B — Project Health Snapshot

Phase 3B (`planning-engine`) shipped as **three separate, separately-reviewed PR-sized units**, each with its own Gate Review. Per the instruction not to collapse distinct reports into one set of numbers, all three are preserved here separately, followed by a combined view of only the facts the documents agree on.

---

## Phase 3B — Sub-unit 1: Domain Foundation (PR #2)

Source: `docs/roadmap/architecture-reviews/phase-3b-domain-foundation-gate-review.md` (read in full for this snapshot).

| # | Field | Value |
|---|---|---|
| 1 | Phase identity | Phase 3B, sub-unit 1 |
| 2 | Phase/Sub-Phase name | `planning-engine` Domain Foundation |
| 3 | Report date | Not reported (no date stated in the document's own text) |
| 4 | Branch | `phase-3b-planning-domain`, branched from `phase-3` |
| 5 | PR number | PR #2 (per §6a: "not introduced by this PR or by PR #1"; the document's own review references "this PR" throughout, consistent with PR #2 per the session's own commit-message record) |
| 6 | Commit / merge commit | Post-initial-review fix commit `41122e2` (§3a/§3b's correction); no separate merge-commit SHA stated in this document |
| 7 | Phase status | "Status: complete, fully verified (domain-only). Covers exactly one PR-sized unit ... not the whole of Phase 3B." Post-initial-review update: an independent review found and fixed a real defect (duplicate `TaskNode.id` handling) and corrected an inaccurate coverage claim — both resolved as of commit `41122e2`. |
| 8 | Production SLOC | Not reported |
| 9 | Total SLOC | Not reported |
| 10 | SLOC methodology/tool | Not reported |
| 11 | SLOC scope | Not reported |
| 12 | Test status | "35/35 passed (30 original + 5 from independent review, §3a/§3b)" (§6) |
| 13 | Test count | 35 (original PR: 30; +5 added during independent review) |
| 14 | Coverage | Corrected figure: 100% statement **and** branch coverage (`domain/models.py`: 24 stmts/0 branches; `domain/task_graph.py`: 86 stmts/40 branches, 0 missed), vs. an 85% branch-coverage gate — corrected from an originally-reported, inaccurate "100%" that was actually 98.50% branch coverage under statement-only reporting (§3b explains the root cause: `--cov-report=term-missing` was omitted the first time) |
| 15 | CI status | `checks` (pr-checks.yml) — "Passed on PR #2" (§6). `build-and-scan.yml` — **fails on this PR, but confirmed pre-existing and unrelated** (§6a): a `trivy-action@0.24.0` version-resolution failure present since the very first run of this workflow, before any Phase 3B PR existed. |
| 16 | Real-infrastructure status | "Not applicable. This PR introduces no persistence, no new Event Bus subject, no cross-process integration — nothing for a real-infra test to exercise." (§6) — explicitly not applicable, not deferred. |
| 17 | Documentation health | Not reported as a dedicated section; §1 documents an explicit, evidenced deviation from TDD 3B's own original proposal (splitting `RiskLevel` into `nova_contracts` while keeping `TaskNode`/`TaskGraph`/`Estimate` domain-local), disclosed with reasoning, not silent |
| 18 | Architecture status | §1 confirms the split-model decision matches every other existing engine's established convention (domain model separate from wire payload); import-linter 6/6 contracts kept, `nova_planning_engine` correctly wired and independent (§6) |
| 19 | Security status | Not reported |
| 20 | Unverified infrastructure | "No contract/fake-verified, local-integration-verified, or genuinely unverified items in this PR's own scope" (§6) — everything in this PR is either a pure domain function or an unexercised scaffold stub |
| 21 | Open blockers | `build-and-scan.yml`'s pre-existing trivy-action failure (§6a) — explicitly not fixed in this PR, tracked as a separate, dedicated CI-maintenance item |
| 22 | Branch hygiene | Not reported |
| 23 | Notes / important findings | Independent review (post-initial) found a real defect: duplicate `TaskNode.id` values would silently corrupt cycle detection, dangling-dependency detection, and critical-path computation with no error signal — fixed by `find_duplicate_ids()`, wired as the first check in `compute_critical_path` (§3a). A separate independent-review finding corrected an inaccurate "100%" coverage claim to the true, re-verified 98.50%→100%-after-fix figure (§3b). |

---

## Phase 3B — Sub-unit 2: Decomposition Orchestration (PR #7)

Source: `docs/roadmap/architecture-reviews/phase-3b-decomposition-orchestration-gate-review.md` (read in full for this snapshot).

| # | Field | Value |
|---|---|---|
| 1 | Phase identity | Phase 3B, sub-unit 2 |
| 2 | Phase/Sub-Phase name | `planning-engine` Decomposition Orchestration |
| 3 | Report date | Not reported (no date stated in the document's own text) |
| 4 | Branch | `phase-3b-decomposition-orchestration`, branched from `phase-3b-planning-domain` |
| 5 | PR number | PR #7 (explicitly named throughout §9/§10) |
| 6 | Commit / merge commit | PR #7's head commit `1bf948d` (§10, "confirmed after push, PR #7, head `1bf948d`") |
| 7 | Phase status | "Status: complete, fully verified locally and via real GitHub Actions (see §6). Covers exactly one PR-sized unit ... not the whole of Phase 3B." |
| 8 | Production SLOC | Not reported |
| 9 | Total SLOC | Not reported |
| 10 | SLOC methodology/tool | Not reported |
| 11 | SLOC scope | Not reported |
| 12 | Test status | "57/57 passed" (§9) |
| 13 | Test count | 57 total (35 pre-existing from PR #2 + 22 new) (§8) |
| 14 | Coverage | 99% branch coverage (`decomposition.py`: 96%, 2 structurally-unreachable lines disclosed in §8; `models.py`/`ports.py`/`task_graph.py`: 100%), vs. 85% gate (§9) |
| 15 | CI status | All three workflows green on real GitHub Actions, confirmed via `pull_request_read(method="get_check_runs")`, not assumed: `PR Checks` run [31918753085] `success`; `Build & Scan` run [31918751521] `success`; `Real-Infrastructure Checks` run [31918752447] `success`. 18 individual check runs total, all `conclusion: success`. PR #7's `mergeable_state` is `clean` (§9, §10). |
| 16 | Real-infrastructure status | Partially verified: real GitHub Actions `Real-Infrastructure Checks` workflow passed (§9), but `planning-engine` itself has "no `real-infra` matrix entry of its own (no Postgres/Redis/Neo4j-backed repository exists in this PR)" (§10) — the green result covers other packages' real-infra suites, not a planning-engine-specific real-infra test. The `reasoning.process.completed` → `planning-engine` path over real NATS JetStream (consumer groups, redelivery, durable-stream semantics) is explicitly listed as "Genuinely unverified (explicitly, not silently assumed)" (§9). |
| 17 | Documentation health | §7 lists an update to `docs/design/phase-3/05-tdd-3b-planning-engine.md` (§3 adds `ModelOrchestrationPort`; §8 adds a model-call-failure row; a stale top status line, stale since before PR #2, is corrected) |
| 18 | Architecture status | §5 discloses and closes a new enforcement gap found during implementation: `nova_planning_engine` was absent from the ADR-020 import-linter contract's `source_modules` list — closed as this PR's own responsibility (the PR that first gives planning-engine model-adjacent code), not a separate CI-maintenance PR. import-linter 6/6 contracts kept after the fix (§9). |
| 19 | Security status | Not reported |
| 20 | Unverified infrastructure | §9 explicitly separates 5 verification tiers and marks the real NATS JetStream round trip as genuinely unverified (see field 16); the real provider round trip through a live `ai-model-orchestration-engine` process is marked "Contract/fake verified only," not exercised. |
| 21 | Open blockers | None stated as blocking; §11 lists known, disclosed, non-blocking scope limitations (no persistence yet, no `planning.task_graph.created` publication, no persistent idempotency — flagged as a hard requirement once persistence exists, not yet). |
| 22 | Branch hygiene | Not reported |
| 23 | Notes / important findings | §1: the decomposition algorithm decision (LLM-backed via `ModelOrchestrationPort`) is grounded directly in a dedicated prior research pass — `docs/design/phase-3/11-3b-decomposition-architecture-research.md` §6/§13, branch `phase-3b-decomposition-research`, commit `654570d` — the same research branch and commit this Project Health system's own audit later found still unmerged into the canonical lineage. §3: no dedup/idempotency mechanism was added, deliberately, since nothing in this PR is persisted yet; flagged as a required follow-up once persistence exists. |

---

## Phase 3B — Sub-unit 3: Planning Persistence (precursor PR, `phase-3b-planning-persistence`)

Source: `docs/roadmap/architecture-reviews/phase-3b-planning-persistence-gate-review.md` (read in full for this snapshot).

| # | Field | Value |
|---|---|---|
| 1 | Phase identity | Phase 3B, sub-unit 3 |
| 2 | Phase/Sub-Phase name | `planning-engine` Persistence (TDD 3B §4/§5/§6.2) |
| 3 | Report date | 2026-08-20 |
| 4 | Branch | `phase-3b-planning-persistence`, branched from `phase-3b-planning-domain` |
| 5 | PR number | PR #18, open, not yet merged |
| 6 | Commit / merge commit | Head `41afd01684707eb11126d4e70f78c9e1af514db4` (not yet merged) — the last *application-code* commit is `ac364b998e130c944c355e52608b57849407c785`; `41afd01` is a docs-only follow-up whose own CI run was independently reconfirmed 24/24 green during the 2026-08-20 consistency audit |
| 7 | Phase status | "Status: complete, fully verified locally and via real GitHub Actions (see §10) — 24/24 checks green at head `ac364b9`. Covers exactly one PR-sized unit ... the fourth and, per TDD 3B's own scope, final PR closing this phase's approved surface" except §6.1's `agent_os.task.completed`, correctly deferred to Phase 3E |
| 8 | Production SLOC | Not reported |
| 9 | Total SLOC | Not reported |
| 10 | SLOC methodology/tool | Not reported |
| 11 | SLOC scope | Not reported |
| 12 | Test status | "67 tests passing locally (10 real-infra tests correctly deselected by the package's own `test` script)" (§6/§9) |
| 13 | Test count | 67 non-real-infra + 10 real-infra = 77 total collected; 21 new tests added in this PR (4 unit `decompose_node`, 3 new contract, 3 new `planning.decompose.request` integration, 4 new `/v1/plans` API integration, 4 modified `reasoning.process.completed` integration, 10 new real-infra) |
| 14 | Coverage | Domain-layer coverage 98.68%, vs. 85% gate (§6/§9) |
| 15 | CI status | **24/24 checks green on real GitHub Actions at head `ac364b9`** (Gate Review §10), confirmed via `pull_request_read(method="get_check_runs")` — `checks`, `dependency-audit`, all 13 `build-and-scan` matrix entries (incl. `planning-engine`, first time ever), all 10 `real-infra` matrix entries (incl. `planning-engine`, first time ever). `mergeable_state` is `clean`. One real defect was caught by the first push's own real-infra run and fixed same-day; see §16 and Gate Review §3a. |
| 16 | Real-infrastructure status | **Fully verified via real CI**: 10 new real-Postgres tests, "10 passed" against a real `postgres:16-alpine` container (`real-infra-checks.yml`, `planning-engine` matrix entry, first time ever for this engine). The first push (commit `3c71e77`) failed 1 of these 10 with a genuine bug — `TaskNode.depends_on` (`list[UUID]`) was not stringified before writing to the JSONB column, only surfacing for a node with a non-empty `depends_on` — fixed same-day (commit `ac364b9`) by mirroring the existing `critical_path` stringify-on-write/parse-on-read pattern; the corrected run passed all 10. |
| 17 | Documentation health | TDD 3B's top status banner corrected (§4/§5/§6.2 now shipped); both prior Phase 3B Gate Reviews additively updated with forward pointers to this closure; a dated reconciliation note added to the Phase 3E research document disclosing this prerequisite's discovery and closure under Phase 3B without reopening any of Phase 3E's six approved decisions |
| 18 | Architecture status | No new architectural decisions — every structural choice (domain-vs-wire-payload split, per-engine schema/migration convention, RPC serve pattern, transactional outbox + separate Arq worker, `relationship()` usage) follows an already-established codebase convention, verified against `action-engine`/`memory-engine`/`communication-engine` precedent before implementing (Gate Review §1). import-linter 6/6 contracts kept. |
| 19 | Security status | Not reported |
| 20 | Unverified infrastructure | Outbox worker's real dispatch to a live NATS/Postgres pair not exercised (same disclosed gap as every other engine's own outbox worker); `reasoning.process.completed`/`planning.decompose.request` over real NATS JetStream redelivery/consumer-group semantics not exercised (same disclosed gap as the decomposition-orchestration PR's own §9) — both explicitly listed as "Genuinely unverified," not silently assumed (Gate Review §8) |
| 21 | Open blockers | None stated as blocking; this engine had no `build-and-scan.yml`/`docker-compose.local.yml` entry at all before this PR (a gap inherited from the decomposition-orchestration PR's own disclosed "no persistence/API to serve yet" scoping) — closed here, not carried forward |
| 22 | Branch hygiene | Not reported |
| 23 | Notes / important findings | A self-caught design correction during implementation, before any test was written against it: the first draft of `decompose_handler.py` built the `planning.task_graph.created` outbox payload before the graph mutation (stale `critical_path`) and left an unimplemented stub; redesigned via an `outbox_event_builder` callback called after mutation, inside the same transaction, with the fully-updated graph (Gate Review §3). "Mutation, not regeneration" was scoped exactly to the node-scoped `planning.decompose.request` path, not invented for the `reasoning.process.completed` path, since no `reasoning_process_id`-to-`task_graph_id` linkage is specified anywhere in TDD 3B or the Phase 3E research documents (Gate Review §2). A separate, genuinely CI-caught defect (not self-caught — no Docker daemon was available locally to catch it): `TaskNode.depends_on` UUIDs were not stringified before the JSONB write, failing only for a node with a non-empty `depends_on`; fixed same-day by mirroring the existing `critical_path` stringify/parse pattern (Gate Review §3a). |

---

## Combined notes

All three sub-units together implement Phase 3B's `planning-engine`: domain foundation, decomposition orchestration, and now persistence/API/event-contracts — the phase's approved surface is closed except §6.1's `agent_os.task.completed` subscription, correctly deferred to Phase 3E. **No report includes a Production SLOC or Total SLOC figure** — this snapshot does not calculate one from today's repository, per the strict no-invention rule. The decomposition-orchestration sub-unit (PR #7) is the first Phase 3 unit in this project-health record with confirmed real GitHub Actions CI results cited by run ID; the domain-foundation sub-unit (PR #2) predates that level of CI-result citation in its own gate review; the persistence sub-unit's own CI results are confirmed (see field #15 above): 24/24 checks green, including 10/10 real-Postgres tests.
