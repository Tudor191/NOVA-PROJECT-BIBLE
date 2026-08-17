# Phase 3B — Project Health Snapshot

Phase 3B (`planning-engine`) shipped as **two separate, separately-reviewed PR-sized units**, each with its own Gate Review. Per the instruction not to collapse distinct reports into one set of numbers, both are preserved here separately, followed by a combined view of only the facts both documents agree on.

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

## Combined notes

Both sub-units together implement Phase 3B's `planning-engine` domain foundation and its first real orchestration path, but **neither report includes a Production SLOC or Total SLOC figure** — this snapshot does not calculate one from today's repository, per the strict no-invention rule. The decomposition-orchestration sub-unit (PR #7) is the first Phase 3 unit in this project-health record with confirmed real GitHub Actions CI results cited by run ID; the domain-foundation sub-unit (PR #2) predates that level of CI-result citation in its own gate review.
