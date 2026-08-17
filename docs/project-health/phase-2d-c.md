# Phase 2D-C — Project Health Snapshot

Source: `docs/roadmap/architecture-reviews/phase-2d-c-gate-review.md` (read in full for this snapshot).

| # | Field | Value |
|---|---|---|
| 1 | Phase identity | Phase 2D-C |
| 2 | Phase/Sub-Phase name | Conversation Intelligence |
| 3 | Report date | Not reported (no date stated in the document's own text) |
| 4 | Branch | Not reported |
| 5 | PR number | Not reported (this phase predates the PR-based workflow introduced at Phase 3B-IMPL) |
| 6 | Commit / merge commit | Not reported |
| 7 | Phase status | "Status: Implementation complete, Option B (per user approval). Not yet approved for production use — §9 states exactly what remains open before it can be." §11.3: "Gate passed, for what this wave actually claims to be ... not a claim that the full conversation-intelligence pipeline is end-to-end functional." Per direct instruction, "Phase 2D-D does not begin" as of this report. |
| 8 | Production SLOC | Before (Extraction E checkpoint): 32,043. After this wave: **33,175**. Delta: **+1,132**. (§3) |
| 9 | Total SLOC | Before: 82,282. After: **85,141**. Delta: **+2,859**. (§3) |
| 10 | SLOC methodology/tool | `scc`, explicitly stated as "consistent with every prior gate review's methodology" (§3) — this claim of consistency is later found to not hold for the very next report in the series (see `phase-2d-c-closure.md`, which uses `cloc`). |
| 11 | SLOC scope | `src/` + Alembic `versions/` (§3) |
| 12 | Test status | "18/18 tasks successful, 0 failures, 1,008 passed" (full workspace, `npx turbo run test --force`, all 18 packages) (§4) |
| 13 | Test count | 1,008 passed (+38 over the Extraction E baseline of 970) (§4) |
| 14 | Coverage | Coverage gate negative control run with `--cov-fail-under=100` (unreachable) → exit 1, "Total coverage: 99.37%" — real domain coverage 99.37%, above the real 85% threshold (§6) |
| 15 | CI status | Only local-tooling checks cited: `ruff check .` (whole workspace) and `mypy` (per-package) both clean, 0 issues (§4). No GitHub Actions run ID is cited in this document. |
| 16 | Real-infrastructure status | Written but not executable in this sandboxed environment (5 new `@pytest.mark.real_infra` functions in `test_repository_real_postgres.py`; `docker info` fails, no reachable daemon) — "the identical, already-disclosed limitation every prior phase's own gate review has carried forward, not new to this wave" (§5.4 item 6, §6) |
| 17 | Documentation health | Not reported as a dedicated section |
| 18 | Architecture status | §1.2: table of ADR-004/005/020/024/032 compliance, each explicitly verified against the actual code, not assumed. import-linter 6/6 contracts kept (§6). |
| 19 | Security status | Not reported |
| 20 | Unverified infrastructure | §5.3 names four concrete items that remain unverified end-to-end because `perception-engine`'s production signal chain is not wired: no real wake-word/gaze/identity signal has ever produced a live event; World Model corroboration is built but never called live; a high-confidence fusion outcome does not activate a session; `ResponseShapingDirectivePayload` has never influenced a delivered response. §5.4 gives a concrete, ordered closure path for all of them. |
| 21 | Open blockers | §5.4 lists, in dependency order: (1) wire perception-engine's sensor→fusion→publish orchestration into production, (2) resolve the `user_id`/session-correlation gap, (3) build the missing communication-engine↔reasoning-engine integration loop, (4) build the cross-context "start listening" signal mechanism, (5) `personality-engine`'s `channel` parameter fix (small, already scoped), (6) real-Postgres verification (execution-environment limitation only). |
| 22 | Branch hygiene | Not reported |
| 23 | Notes / important findings | §1.1: direct code inspection found no live `communication-engine` ↔ `reasoning-engine` loop exists at all — a materially bigger finding than the TDD's own framing assumed; `ResponseShapingDirectivePayload` is published with zero consumers. §1.3: two places where the user's explicit scope boundary was tested during implementation and held both times (personality-engine's `channel` fix and the reasoning-engine integration loop were both left out of scope, not silently expanded into). |
